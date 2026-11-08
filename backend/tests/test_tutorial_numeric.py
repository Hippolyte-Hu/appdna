import pytest
from app.engines.tutorial import validate_action
from app.drivers.blender_tutorial import BlenderTutorialDriver


def test_numeric_edit_validates_point_and_bounded_number():
    assert validate_action({'action':'set_number','x':940,'y':458,'text':'4'})
    for value in ['NaN','inf','-1','10001','4;exec','Save Startup File','']:
        with pytest.raises(ValueError):validate_action({'action':'set_number','x':940,'y':458,'text':value})
    with pytest.raises(ValueError):validate_action({'action':'set_number','x':1001,'y':458,'text':'4'})


def test_numeric_edit_replaces_and_commits_with_real_keys(monkeypatch):
    from app.drivers import blender_tutorial
    calls=[]
    monkeypatch.setattr(blender_tutorial,'guard',lambda *args:calls.append(args) or {})
    monkeypatch.setattr(blender_tutorial.time,'sleep',lambda _:None)
    driver=BlenderTutorialDriver(type('Process',(),{'pid':123})())
    driver.perform({'action':'set_number','x':940,'y':458,'text':'4'})
    assert calls==[('double_click',123,'940','458'),('key',123,'ctrl+a'),('type',123,'4'),('key',123,'return')]
