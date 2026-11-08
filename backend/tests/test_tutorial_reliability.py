"""Synthetic regression tests for save sequencing and bounded vision recovery."""
import asyncio
import pytest
from app.engines import tutorial_runner as module
from app.providers.base import ProviderError


@pytest.mark.parametrize('persistent',[False,True])
@pytest.mark.parametrize('error_type',[RuntimeError,ProviderError])
def test_provider_timeout_recaptures_once_without_any_input(tmp_path,persistent,error_type):
    calls=[];captures=[]
    class Driver:
        def capture(self,path):
            frame=('Synthetic frame '+str(len(captures)+1)).encode();captures.append(frame);path.write_bytes(frame)
        def perform(self,*args,**kwargs):pytest.fail('A failed model request must never issue input')
    class Vision:
        async def tutorial_action(self,**kwargs):
            calls.append(kwargs['image_bytes'])
            if persistent or len(calls)==1:raise error_type('H Company took too long to answer')
            return {'action':'done','text':'Synthetic completion'}
    result=asyncio.run(module.execute_plan({'steps':[{'id':'test'}]},tmp_path,Driver(),Vision(),lambda:False,max_actions=3))
    assert result['status']==('blocked' if persistent else 'observed_complete')
    assert len(calls)==2 and calls==captures and calls[0]!=calls[1]
    errors=result['provider_errors']
    assert len(errors)==(2 if persistent else 1)
    assert all(e['input_sent'] is False for e in errors)
    assert (tmp_path/errors[0]['before']).read_bytes()==b'Synthetic frame 1'
    assert result['events']==[] if persistent else result['events'][0]['action']['action']=='done'


def test_save_model_receives_required_next_field(tmp_path,monkeypatch):
    target=tmp_path/'replica.blend';contexts=[]
    actions=iter([{'action':'set_text','x':100,'y':100,'text':str(tmp_path)+'/'},
        {'action':'set_text','x':100,'y':900,'text':'replica.blend'},{'action':'click','x':900,'y':900},{'action':'done'}])
    class Vision:
        async def tutorial_action(self,**kwargs):contexts.append(kwargs['step']['save_policy']);return next(actions)
    class Driver:
        def capture(self,path):path.write_bytes(b'Synthetic unit screenshot')
        def perform(self,action,**kwargs):
            if action['action']=='click':target.write_bytes(b'Synthetic unit artifact')
    async def no_delay(*args):pass
    monkeypatch.setattr(module.asyncio,'sleep',no_delay)
    result=asyncio.run(module.execute_plan({'steps':[{'id':'save'}]},tmp_path/'receipt',Driver(),Vision(),lambda:False,save_target=target))
    assert result['status']=='observed_complete'
    assert [c['required_next'] for c in contexts]==['directory','filename','confirm_save','done']
    assert contexts[0]['directory']==str(tmp_path)+'/'
