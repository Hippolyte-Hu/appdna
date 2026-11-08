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


def test_save_target_must_be_absolute_blend_path():
    for target in [Path('relative.blend'),Path('/tmp/startup.py')]:
        with pytest.raises(ValueError):validate_action({'action':'wait'},save_target=target)
