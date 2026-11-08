import json
import pytest
from fastapi.testclient import TestClient
from app import tutorial_app as module


def client(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'DATA',tmp_path)
    return TestClient(module.app)


def seed(tmp_path):
    job_id='a'*32;p=tmp_path/job_id;p.mkdir()
    (p/'job.json').write_text(json.dumps({'id':job_id,'status':'ready_for_review'}))
    (p/'plan.json').write_text(json.dumps({'steps':[]}))
    return job_id


def test_cross_origin_control_rejected(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    assert c.post('/api/tutorials',headers={'origin':'https://evil.example'}).status_code==403


def test_run_requires_review_and_scratch_approval(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch);job_id=seed(tmp_path)
    assert c.post(f'/api/tutorials/{job_id}/run',json={}).status_code==400


def test_locked_mac_never_launches_blender(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch);job_id=seed(tmp_path)
    monkeypatch.setattr(module,'guard',lambda *a:{'locked':True})
    response=c.post(f'/api/tutorials/{job_id}/run',json={'reviewed':True,'confirm_scratch':True})
    assert response.status_code==409
    assert 'locked' in response.json()['detail']
    assert not (tmp_path/job_id/'run').exists()


def test_media_endpoint_cannot_read_settings(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch);job_id=seed(tmp_path)
    assert c.get(f'/assets/{job_id}/job.json').status_code==404
    assert c.get('/api/tutorials/not-valid').status_code==404


def test_source_targets_are_exposed_for_review(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch);job_id=seed(tmp_path)
    target={'scope':'blender_bevel_v1','values':{'width':.24},'source_check':{'supported':True,'issues':[]}}
    (tmp_path/job_id/'artifact-expectations.json').write_text(json.dumps(target))
    assert c.get(f'/api/tutorials/{job_id}').json()['artifact_targets']==target


def test_form_rejects_non_youtube_url(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    assert c.post('/api/tutorials',data={'url':'http://127.0.0.1/'}).status_code==400


def test_video_source_is_retrievable_and_searchable_without_executing(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch);job_id=seed(tmp_path);p=tmp_path/job_id
    knowledge={'source_type':'video','status':'source_checked','verification':'not_executed',
        'title':'Bevel fixture','objective':'Round an object','steps':[{'id':'s1'}]}
    (p/'knowledge.json').write_text(json.dumps(knowledge))
    (p/'agent.json').write_text(json.dumps({'status':'completed','events':[]}))
    d=c.get(f'/api/tutorials/{job_id}').json()
    assert d['knowledge']['verification']=='not_executed' and d['agent']['status']=='completed'
    result=c.get('/api/video-sources',params={'q':'Bevel','limit':1})
    assert result.status_code==200 and result.json()['items'][0]['id']==job_id
    assert c.get('/api/video-sources',params={'q':'absent'}).json()['items']==[]
    assert c.get(f'/api/video-sources/{job_id}').json()==knowledge
    assert not (p/'run').exists()


def test_unresolved_source_cannot_execute_even_with_approval(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch);job_id=seed(tmp_path)
    (tmp_path/job_id/'knowledge.json').write_text(json.dumps({'status':'needs_input'}))
    monkeypatch.setattr(module,'guard',lambda *a:{'locked':False})
    monkeypatch.setattr(module,'spawn',lambda coro:coro.close())
    monkeypatch.setattr(module,'active',None)
    r=c.post(f'/api/tutorials/{job_id}/run',json={'reviewed':True,'confirm_scratch':True})
    assert r.status_code==409 and 'source' in r.json()['detail'].lower()
    assert not (tmp_path/job_id/'run').exists()


def test_parent_invokes_learning_agent_and_preserves_needs_input(tmp_path,monkeypatch):
    import asyncio
    c=client(tmp_path,monkeypatch);job_id=seed(tmp_path);p=tmp_path/job_id
    module.save(p,{'id':job_id,'source_file':'source.mp4','objective':'Follow this source','status':'queued'})
    (p/'source.mp4').write_bytes(b'unit video fixture')
    monkeypatch.setattr(module,'prepare_media',lambda *a:{'duration':10})
    monkeypatch.setattr(module,'providers',lambda:(object(),object()))
    async def fake_agent(media,folder,asr,vision,**kwargs):
        assert kwargs['source']==p/'source.mp4' and kwargs['objective']=='Follow this source'
        return {'status':'needs_input','reason':'Unit fixture ambiguous branch'}
    monkeypatch.setattr(module,'learn_video_source',fake_agent)
    asyncio.run(module.learn(job_id))
    assert c.get(f'/api/tutorials/{job_id}').json()['status']=='needs_input'


def test_new_video_source_never_inherits_legacy_reference_verification(tmp_path,monkeypatch):
    """Synthetic execution receipt: no real Blender or model requests."""
    import asyncio
    from app.engines import tutorial_artifact
    c=client(tmp_path,monkeypatch);job_id=seed(tmp_path);p=tmp_path/job_id
    (p/'knowledge.json').write_text(json.dumps({'status':'source_checked','verification':'not_executed'}))
    class Driver:
        pid=123
        @classmethod
        def launch(cls,folder):folder.mkdir();return cls()
    async def execute(*a,**kw):return {'status':'observed_complete'}
    async def save(*a,**kw):return {'verification':'verified','artifact':'replica.blend','checks':{'legacy_reference':True}}
    monkeypatch.setattr(module,'BlenderTutorialDriver',Driver)
    monkeypatch.setattr(module,'execute_plan',execute)
    monkeypatch.setattr(module,'providers',lambda:(object(),type('Vision',(),{'model':'unit'})()))
    async def no_target(*args):return None
    monkeypatch.setattr(module,'build_expectations',no_target)
    monkeypatch.setattr(tutorial_artifact,'save_and_verify',save)
    monkeypatch.setitem(module.stops,job_id,False)
    asyncio.run(module.execute(job_id))
    result=c.get(f'/api/tutorials/{job_id}').json()
    assert result['status']=='saved_unverified'
    assert result['verification']['verification']=='not_assessed'
    assert result['verification']['reference_check']['verification']=='verified'
    assert result['verification']['artifact']=='replica.blend'


def test_learning_model_override_does_not_change_desktop_action_model(monkeypatch):
    from types import SimpleNamespace
    settings=SimpleNamespace(gladia_api_key='unit',gladia_base_url='https://unit.invalid',  # pragma: allowlist secret -- synthetic fixture
        hcompany_api_key='unit',hcompany_base_url='https://unit.invalid',hcompany_model='holo4-27b')  # pragma: allowlist secret -- synthetic fixture
    monkeypatch.setattr(module,'get_settings',lambda:settings)
    monkeypatch.setenv('APPDNA_LEARNING_MODEL','holo4-35b-a3b')
    monkeypatch.setenv('APPDNA_ACTION_MODEL','holo4-27b')
    _,vision=module.providers()
    assert vision.model=='holo4-35b-a3b'
    assert module.os.environ['APPDNA_ACTION_MODEL']=='holo4-27b'


@pytest.mark.parametrize('binding_matches',[False,True])
def test_new_source_verification_requires_pre_execution_target_binding(tmp_path,monkeypatch,binding_matches):
    import asyncio
    from app.engines import tutorial_artifact
    c=client(tmp_path,monkeypatch);job_id=seed(tmp_path);p=tmp_path/job_id
    (p/'knowledge.json').write_text(json.dumps({'status':'source_checked'}))
    target={'binding_sha256':'unit-target','source_sha256':'unit-source'}
    class Driver:
        pid=123
        @classmethod
        def launch(cls,folder):folder.mkdir();return cls()
    async def build(*args):return target
    async def execute(*a,**kw):return {'status':'observed_complete'}
    async def save(*a,**kw):
        assert kw['expectations']==target and kw['source_folder']==p
        return {'verification':'verified','artifact':'replica.blend','scope':'blender_bevel_v1',
                'sha256':'a'*64,'read_only_hash_unchanged':True,
                'source_sha256':'unit-source','target_binding_sha256':'unit-target' if binding_matches else 'wrong-target'}
    monkeypatch.setattr(module,'build_expectations',build)
    monkeypatch.setattr(module,'BlenderTutorialDriver',Driver)
    monkeypatch.setattr(module,'execute_plan',execute)
    monkeypatch.setattr(module,'providers',lambda:(object(),type('Vision',(),{'model':'holo4-unit'})()))
    monkeypatch.setattr(tutorial_artifact,'save_and_verify',save)
    monkeypatch.setitem(module.stops,job_id,False)
    asyncio.run(module.execute(job_id))
    result=c.get(f'/api/tutorials/{job_id}').json()
    assert result['status']==('verified' if binding_matches else 'saved_unverified')
