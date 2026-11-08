"""Synthetic checkpoint tests. No model, desktop or real execution success is mocked into live evidence."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import tutorial_app
from app.engines import tutorial_artifact
from app.engines.tutorial_runner import execute_plan
from app.providers.base import ProviderError


class Driver:
    def __init__(self):self.inputs=[]
    def capture(self,path):path.write_bytes(path.name.encode());return path
    def perform(self,action):self.inputs.append(action)


def test_resume_preserves_finished_steps_inputs_and_failed_request_capture(tmp_path):
    driver=Driver();calls=[]
    class Vision:
        async def tutorial_action(self,**kwargs):
            calls.append(kwargs['step']['id'])
            if len(calls)==2:return {'action':'click','x':500,'y':500}
            if len(calls)==3:raise ProviderError('Unit provider timeout')
            return {'action':'done'}
    plan={'steps':[{'id':'s1'},{'id':'s2'}]};vision=Vision()
    paused=asyncio.run(execute_plan(plan,tmp_path,driver,vision,lambda:False))
    assert paused['status']=='paused' and paused['completed_steps']==['s1']
    failed_capture=(tmp_path/'before-002.png').read_bytes()
    resumed=asyncio.run(execute_plan(plan,tmp_path,driver,vision,lambda:False,resume=True))
    assert resumed['status']=='observed_complete'
    assert calls==['s1','s2','s2','s2'] and len(driver.inputs)==1
    assert resumed['completed_steps']==['s1','s2'] and len(resumed['events'])==3
    assert (tmp_path/'before-002.png').read_bytes()==failed_capture
    assert (tmp_path/'before-003.png').is_file()


def test_changed_plan_cannot_resume_before_a_new_capture(tmp_path):
    class Timeout:
        async def tutorial_action(self,**kwargs):raise ProviderError('Unit timeout')
    asyncio.run(execute_plan({'steps':[{'id':'s1'}]},tmp_path,Driver(),Timeout(),lambda:False))
    class Forbidden:
        def capture(self,path):raise AssertionError('Capture before plan validation')
    with pytest.raises(ValueError,match='changed'):
        asyncio.run(execute_plan({'steps':[{'id':'changed'}]},tmp_path,Forbidden(),None,lambda:False,resume=True))


def test_resume_does_not_reset_the_action_budget(tmp_path):
    class Timeout:
        async def tutorial_action(self,**kwargs):raise ProviderError('Unit timeout')
    driver=Driver();plan={'steps':[{'id':'s1'}]}
    first=asyncio.run(execute_plan(plan,tmp_path,driver,Timeout(),lambda:False,max_actions=1))
    assert first['status']=='paused'
    final=asyncio.run(execute_plan(plan,tmp_path,driver,None,lambda:False,max_actions=1,resume=True))
    assert final['status']=='blocked' and 'budget' in final['reason']
    assert not driver.inputs


def test_auth_failure_is_terminal_without_a_resumable_checkpoint(tmp_path):
    class Unauthorized:
        async def tutorial_action(self,**kwargs):raise ProviderError('Unit auth error',status=401)
    result=asyncio.run(execute_plan({'steps':[{'id':'s1'}]},tmp_path,Driver(),Unauthorized(),lambda:False))
    assert result['status']=='blocked' and not result['events']


def seed(tmp_path,status='queued'):
    path=tmp_path/('a'*32);path.mkdir()
    tutorial_app.save(path,{'id':path.name,'status':status,'objective':'Unit workflow'})
    (path/'plan.json').write_text(json.dumps({'steps':[{'id':'s1'}]}))
    return path


def test_controller_resume_uses_same_scene_then_closes_it_after_completion(tmp_path,monkeypatch):
    path=seed(tmp_path);instances=[];resume_calls=[];turns=[]
    class Owned:
        pid=123
        closed=False
        @classmethod
        def launch(cls,folder):folder.mkdir();value=cls();instances.append(value);return value
        @classmethod
        def resume(cls,pid,folder,**kwargs):
            resume_calls.append((pid,folder,kwargs));return instances[0]
        def close(self):self.closed=True
    async def run(*args,**kwargs):
        turns.append(kwargs.get('resume',False))
        return {'status':'paused','reason':'Unit timeout'} if len(turns)==1 else {'status':'observed_complete'}
    async def save(*args,**kwargs):return {'verification':'verified','artifact':'explicit-unit-fixture.blend'}
    monkeypatch.setattr(tutorial_app,'DATA',tmp_path)
    monkeypatch.setattr(tutorial_app,'executions',{})
    monkeypatch.setattr(tutorial_app,'stops',{path.name:False})
    monkeypatch.setattr(tutorial_app,'active',path.name)
    monkeypatch.setattr(tutorial_app,'BlenderTutorialDriver',Owned)
    monkeypatch.setattr(tutorial_app,'providers',lambda:(None,None))
    monkeypatch.setattr(tutorial_app,'action_provider',lambda:SimpleNamespace(model='unit'))
    monkeypatch.setattr(tutorial_app,'execute_plan',run)
    monkeypatch.setattr(tutorial_artifact,'save_and_verify',save)
    async def exercise():
        await tutorial_app.execute(path.name)
        assert tutorial_app.read(path.name)['status']=='paused'
        assert not instances[0].closed and tutorial_app.active==path.name
        await tutorial_app.execute(path.name,resume=True)
    asyncio.run(exercise())
    assert len(instances)==1 and turns==[False,True]
    assert resume_calls==[(123,path/'run',{'activate':True})]
    assert instances[0].closed and tutorial_app.active is None
    assert path.name not in tutorial_app.executions


def test_resume_without_live_context_never_probes_a_pid(tmp_path,monkeypatch):
    path=seed(tmp_path,'paused')
    monkeypatch.setattr(tutorial_app,'DATA',tmp_path)
    monkeypatch.setattr(tutorial_app,'executions',{})
    monkeypatch.setattr(tutorial_app,'guard',lambda *args:pytest.fail('No probe before attestation'))
    client=TestClient(tutorial_app.app)
    assert client.post(f'/api/tutorials/{path.name}/resume',json={}).status_code==400
    response=client.post(f'/api/tutorials/{path.name}/resume',json={'reviewed':True,'confirm_scratch':True})
    assert response.status_code==409 and 'sandbox' in response.json()['detail']


def test_stop_releases_the_paused_owned_scene(tmp_path,monkeypatch):
    path=seed(tmp_path,'paused');closed=[]
    monkeypatch.setattr(tutorial_app,'DATA',tmp_path)
    monkeypatch.setattr(tutorial_app,'active',path.name)
    monkeypatch.setattr(tutorial_app,'stops',{})
    monkeypatch.setattr(tutorial_app,'executions',{path.name:{'driver':SimpleNamespace(close=lambda:closed.append(True))}})
    asyncio.run(tutorial_app.stop(path.name))
    assert closed==[True] and tutorial_app.read(path.name)['status']=='stopped'
    assert tutorial_app.active is None and not tutorial_app.executions


def test_saved_file_resume_is_inspected_without_more_model_or_input_calls(tmp_path,monkeypatch):
    target=tmp_path/'replica.blend';target.write_bytes(b'explicit unit artifact')
    prepared=[];inspected=[]
    class Saved:
        def prepare_save(self,path,**kwargs):prepared.append((path,kwargs))
        def capture(self,path):path.write_bytes(b'unit capture')
        def perform(self,*args):raise AssertionError('Input after an existing save')
    def inspect(path,**kwargs):
        inspected.append(path);return {'verification':'failed','reason':'Unit inspection fixture'}
    monkeypatch.setattr(tutorial_artifact,'inspect_replica',inspect)
    result=asyncio.run(tutorial_artifact.save_and_verify(tmp_path,Saved(),None,lambda:False,resume=True))
    assert inspected==[target] and prepared==[(target,{'allow_existing':True})]
    assert target.read_bytes()==b'explicit unit artifact'
    assert result['verification']=='failed'


def test_resume_never_inspects_an_artifact_symlink(tmp_path):
    outside=tmp_path/'outside.blend';outside.write_bytes(b'unit outside')
    run=tmp_path/'run';run.mkdir();(run/'replica.blend').symlink_to(outside)
    with pytest.raises(ValueError,match='symlink'):
        asyncio.run(tutorial_artifact.save_and_verify(run,None,None,lambda:False,resume=True))
