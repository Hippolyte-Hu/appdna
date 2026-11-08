from pathlib import Path
import pytest
from app.engines.tutorial import validate_action


def test_save_target_allows_only_fixed_destination(tmp_path):
    target=tmp_path/'replica.blend'
    for text in [str(tmp_path)+'/',target.name]:
        assert validate_action({'action':'type','text':text},save_target=target)['text']==text
    for text in ['/tmp/unrelated.blend','exec(open','Save Startup File','Save Preferences']:
        with pytest.raises(ValueError):validate_action({'action':'type','text':text},save_target=target)


def test_save_shortcuts_not_allowed_during_tutorial(tmp_path):
    for key in ['ctrl+shift+s','ctrl+a']:
        with pytest.raises(ValueError):validate_action({'action':'key','text':key})
        assert validate_action({'action':'key','text':key},save_target=tmp_path/'replica.blend')


def test_save_text_edit_is_restricted_to_exact_target(tmp_path):
    target=tmp_path/'replica.blend'
    action={'action':'set_text','x':500,'y':80,'text':str(tmp_path)+'/'}
    assert validate_action(action,save_target=target)
    with pytest.raises(ValueError):validate_action(action)
    with pytest.raises(ValueError):validate_action({**action,'text':'/tmp/elsewhere/'},save_target=target)


def test_save_stage_sets_directory_before_filename_or_commit(tmp_path,monkeypatch):
    import asyncio
    from app.engines import tutorial_runner as module
    target=tmp_path/'replica.blend';posted=[]
    actions=iter([
        {'action':'set_text','x':500,'y':950,'text':target.name},
        {'action':'set_text','x':500,'y':50,'text':str(target.parent)+'/'},
        {'action':'set_text','x':500,'y':950,'text':target.name},
        {'action':'click','x':900,'y':950,'text':'Save As'},
        {'action':'done'}])
    class Vision:
        async def tutorial_action(self,**kwargs):return next(actions)
    class Driver:
        def capture(self,path):path.write_bytes(b'synthetic unit image')
        def perform(self,action,**kwargs):
            posted.append(action)
            if action['action']=='click':target.write_bytes(b'synthetic unit artifact')
    async def no_sleep(*args):pass
    monkeypatch.setattr(module.asyncio,'sleep',no_sleep)
    result=asyncio.run(module.execute_plan({'steps':[{'id':'save'}]},tmp_path/'save',Driver(),Vision(),lambda:False,save_target=target))
    assert result['status']=='observed_complete'
    assert posted[0]['text']==str(target.parent)+'/'
    assert len(posted)==3
    assert 'rejected' in result['events'][0]


def test_save_policy_never_rewrites_an_existing_target(tmp_path):
    from app.engines.tutorial_runner import SavePolicy
    target=tmp_path/'replica.blend';target.write_bytes(b'protected unit artifact')
    policy=SavePolicy(target)
    assert policy.check({'action':'click'})
    assert policy.check({'action':'done'}) is None
    assert target.read_bytes()==b'protected unit artifact'


def test_save_policy_rejects_done_without_file(tmp_path):
    from app.engines.tutorial_runner import SavePolicy
    assert SavePolicy(tmp_path/'replica.blend').check({'action':'done'})


def test_save_target_must_be_absolute_blend_path():
    for target in [Path('relative.blend'),Path('/tmp/startup.py')]:
        with pytest.raises(ValueError):validate_action({'action':'wait'},save_target=target)
