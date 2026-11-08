"""Regression fixtures, explicitly separate from real model/desktop receipts."""
import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import tutorial_app
from app.drivers import blender_tutorial
from app.engines.captions import read_captions,validate_transcript
from app.engines import video_projects
from app.models import Base,Capability,KnowledgeClaim,Project


def test_real_sandbox_blocks_overwrite_and_symlink_escape_in_child(tmp_path):
    if sys.platform!='darwin':pytest.skip('macOS Seatbelt')
    scratch=tmp_path/'run';scratch.mkdir()
    outside=tmp_path/'previous.blend';outside.write_bytes(b'previous artifact')
    (scratch/'escape').symlink_to(outside)
    script="""import pathlib,subprocess,sys
target=pathlib.Path(sys.argv[1])
for path in (target,pathlib.Path(sys.argv[2])):
    try:path.write_bytes(b'overwrite')
    except PermissionError:pass
    else:raise AssertionError('escaped sandbox')
result=subprocess.run([sys.executable,'-c',"from pathlib import Path; import sys; Path(sys.argv[1]).write_text('escape')",str(target)],capture_output=True)
assert result.returncode!=0
"""
    result=subprocess.run([*blender_tutorial.sandbox_command(scratch),sys.executable,'-c',script,
                           str(outside),str(scratch/'escape')],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert outside.read_bytes()==b'previous artifact'


def test_unattested_constructor_cannot_capture_perform_or_save(tmp_path,monkeypatch):
    def forbidden(*args):raise AssertionError('Input before attestation')
    monkeypatch.setattr(blender_tutorial,'guard',forbidden)
    driver=blender_tutorial.BlenderTutorialDriver(SimpleNamespace(pid=123))
    for operation in (lambda:driver.capture(tmp_path/'capture.png'),
                      lambda:driver.perform({'action':'wait'}),
                      lambda:driver.prepare_save(tmp_path/'replica.blend')):
        with pytest.raises(RuntimeError,match='sandbox'):operation()


def test_real_blender_can_save_inside_but_cannot_overwrite_outside(tmp_path):
    if sys.platform!='darwin':pytest.skip('macOS Seatbelt')
    if not blender_tutorial.BLENDER.is_file():pytest.skip('Blender not installed')
    scratch=tmp_path/'run';scratch.mkdir()
    previous=tmp_path/'previous.blend';previous.write_bytes(b'prior artifact probe')
    target=scratch/'replica.blend'
    script=scratch/'write_probe.py'
    script.write_text(f"""import bpy
bpy.ops.wm.save_as_mainfile(filepath={str(target)!r})
try:
    bpy.ops.wm.save_as_mainfile(filepath={str(previous)!r})
except RuntimeError:
    pass
else:
    raise AssertionError('Blender escaped write confinement')
""")
    result=subprocess.run([*blender_tutorial.sandbox_command(scratch),str(blender_tutorial.BLENDER),
        '--background','--factory-startup','--offline-mode','--disable-autoexec','--python-exit-code','1',
        '--python',str(script)],capture_output=True,text=True,timeout=45)
    assert result.returncode==0,result.stderr
    assert target.is_file() and target.stat().st_size>1000
    assert previous.read_bytes()==b'prior artifact probe'


def test_live_resume_is_bound_to_process_object_and_scratch(tmp_path,monkeypatch):
    process=SimpleNamespace(pid=123,poll=lambda:None)
    driver=blender_tutorial.BlenderTutorialDriver(process,tmp_path)
    monkeypatch.setitem(blender_tutorial._OWNED,123,driver)
    calls=[];monkeypatch.setattr(blender_tutorial,'guard',lambda *args:calls.append(args) or {})
    assert driver.resume(123,tmp_path) is driver
    with pytest.raises(RuntimeError,match='sandbox'):driver.resume(123,tmp_path/'other')
    process.poll=lambda:0
    with pytest.raises(RuntimeError,match='sandbox'):driver.resume(123,tmp_path)
    assert calls==[('probe',123)]


def test_save_gate_refuses_existing_files_and_other_destinations(tmp_path,monkeypatch):
    driver=blender_tutorial.BlenderTutorialDriver(SimpleNamespace(pid=123,poll=lambda:None),tmp_path)
    monkeypatch.setitem(blender_tutorial._OWNED,123,driver)
    assert driver.prepare_save(tmp_path/'replica.blend')==tmp_path/'replica.blend'
    with pytest.raises(RuntimeError):driver.prepare_save(tmp_path/'other.blend')
    (tmp_path/'replica.blend').write_bytes(b'previous')
    with pytest.raises(RuntimeError):driver.prepare_save(tmp_path/'replica.blend')


def test_caption_json3_preserves_actual_times_and_text(tmp_path):
    path=tmp_path/'source.en.json3'
    path.write_text(json.dumps({'events':[{'tStartMs':1000,'dDurationMs':3000,'segs':[{'utf8':'Add '},{'utf8':'Bevel'}]}]}))
    assert read_captions(path,10)==[{'start':1,'end':4,'text':'Add Bevel'}]


@pytest.mark.parametrize('segment',[
    {'start':float('nan'),'end':2,'text':'invalid'},
    {'start':1,'end':float('inf'),'text':'invalid'},
    {'start':3,'end':2,'text':'invalid'},
    {'start':0,'end':20,'text':'outside video'},
    {'start':True,'end':2,'text':'invalid'},
    {'start':1,'end':2,'text':''},
])
def test_invalid_captions_are_not_model_input(segment):
    with pytest.raises(ValueError):validate_transcript([segment],10)


def seed_job(root,status='queued'):
    path=root/('a'*32);path.mkdir()
    tutorial_app.save(path,{'id':path.name,'status':status,'source_file':'source.mp4','objective':'Unit objective'})
    (path/'source.mp4').write_bytes(b'unit video')
    return path


def test_stop_during_media_preparation_never_calls_provider(tmp_path,monkeypatch):
    path=seed_job(tmp_path)
    monkeypatch.setattr(tutorial_app,'DATA',tmp_path)
    monkeypatch.setitem(tutorial_app.stops,path.name,False)
    def prepare(*args):
        tutorial_app.stops[path.name]=True
        return {'duration':10}
    monkeypatch.setattr(tutorial_app,'prepare_media',prepare)
    monkeypatch.setattr(tutorial_app,'providers',lambda:pytest.fail('Provider after Stop'))
    asyncio.run(tutorial_app.learn(path.name))
    assert tutorial_app.read(path.name)['status']=='stopped'


def test_restart_retains_evidence_and_marks_interrupted_job(tmp_path,monkeypatch):
    path=seed_job(tmp_path,'running')
    (path/'plan.json').write_text('{"unit":"evidence"}')
    monkeypatch.setattr(tutorial_app,'DATA',tmp_path)
    tutorial_app.recover_jobs()
    assert tutorial_app.read(path.name)['status']=='blocked'
    assert 'restarted' in tutorial_app.read(path.name)['error']
    assert (path/'plan.json').read_text()=='{"unit":"evidence"}'


def test_desktop_failure_does_not_hide_learning_ui(tmp_path,monkeypatch):
    monkeypatch.setattr(tutorial_app,'DATA',tmp_path)
    def unavailable(*args):raise RuntimeError('Screen session unavailable')
    monkeypatch.setattr(tutorial_app,'guard',unavailable)
    client=TestClient(tutorial_app.app)
    assert client.get('/').status_code==200
    desktop=client.get('/api/desktop')
    assert desktop.status_code==200 and desktop.json()['available'] is False
    assert client.get('/api/tutorials').json()==[]


def test_missing_accessibility_blocks_before_launch_directory(tmp_path,monkeypatch):
    path=seed_job(tmp_path,'ready_for_review')
    (path/'plan.json').write_text('{"steps":[]}')
    monkeypatch.setattr(tutorial_app,'DATA',tmp_path)
    monkeypatch.setattr(tutorial_app,'active',None)
    monkeypatch.setattr(tutorial_app,'guard',lambda command,*args:
        {'locked':False} if command=='lock' else {'accessibility':False,'screen_recording':True})
    response=TestClient(tutorial_app.app).post(f'/api/tutorials/{path.name}/run',json={'reviewed':True,'confirm_scratch':True})
    assert response.status_code==409 and 'Accessibility' in response.json()['detail']
    assert not (path/'run').exists()


def test_launch_permission_failure_closes_process_and_preserves_reason(tmp_path,monkeypatch):
    class Process:
        pid=81234
        returncode=None
        def poll(self):return self.returncode
        def terminate(self):self.returncode=0
        def wait(self,**kwargs):return self.returncode
    process=Process();captured={}
    def start(command,**kwargs):
        captured.update(command=command,env=kwargs['env']);return process
    def guard(command,*args):
        if command=='lock':return {'locked':False}
        raise RuntimeError('Accessibility permission is missing')
    monkeypatch.setattr(blender_tutorial.subprocess,'Popen',start)
    monkeypatch.setattr(blender_tutorial,'guard',guard)
    monkeypatch.setenv('GLADIA_API_KEY','unit-secret-fixture')
    with pytest.raises(RuntimeError,match='Accessibility'):blender_tutorial.BlenderTutorialDriver.launch(tmp_path/'run')
    assert process.returncode==0 and process.pid not in blender_tutorial._OWNED
    assert 'GLADIA_API_KEY' not in captured['env']
    assert captured['command'][0]=='/usr/bin/sandbox-exec'
    assert json.loads((tmp_path/'run/launch.json').read_text())['error']=='Accessibility permission is missing'


def test_main_app_serves_workbench_without_backend_redirect():
    from app.main import app
    client=TestClient(app)
    for path in ('/video','/video/'):
        response=client.get(path,follow_redirects=False)
        assert response.status_code==200
        assert 'src="/video/workbench.js" data-base="/video"' in response.text
    assert client.get('/video/workbench.js').status_code==200
    assert client.get('/video/api/runtime').status_code==200


def test_empty_upload_or_whitespace_objective_does_not_create_job(tmp_path,monkeypatch):
    monkeypatch.setattr(tutorial_app,'DATA',tmp_path)
    client=TestClient(tutorial_app.app)
    assert client.post('/api/tutorials',files={'video':('source.mp4',b'')}).status_code==400
    assert client.post('/api/tutorials',data={'url':'https://youtu.be/l12k19-imCY','objective':'   '}).status_code==400
    assert not list(tmp_path.iterdir())


def test_project_import_is_idempotent_keeps_steps_observed_and_checks_source(tmp_path,monkeypatch):
    path=seed_job(tmp_path)
    source_hash=hashlib.sha256((path/'source.mp4').read_bytes()).hexdigest()
    steps=[{'id':'s1','instruction':'Unit source step','expected':'Unit expected state','evidence_ids':['frame-1']}]
    knowledge={'status':'source_checked','source_file':'source.mp4','title':'Unit workflow',
               'objective':'Unit objective','steps':steps,'source_sha256':source_hash}
    (path/'knowledge.json').write_text(json.dumps(knowledge))
    (path/'plan.json').write_text(json.dumps({'steps':steps,'source_sha256':source_hash}))
    engine=create_engine('sqlite:///'+str(tmp_path/'unit.db'))
    Base.metadata.create_all(engine)
    monkeypatch.setattr(video_projects,'session_scope',lambda:Session(engine))
    monkeypatch.setattr(video_projects,'get_settings',lambda:SimpleNamespace(artifacts_dir=tmp_path/'artifacts'))
    project_id=video_projects.import_video_project(path)
    assert video_projects.import_video_project(path)==project_id
    with Session(engine) as db:
        assert db.query(Project).count()==1
        assert db.query(Capability).count()==1
        assert db.query(Capability).one().verification_status=='observed'
        assert db.query(KnowledgeClaim).one().verification_status=='observed'
        assert Path(db.query(Project).one().package_path).is_file()
    import zipfile
    with zipfile.ZipFile(tmp_path/'artifacts'/project_id/'appdna-package.zip') as archive:
        assert any(name.endswith('/evidence/video-source/knowledge.json') for name in archive.namelist())
        assert any('/skills/' in name and name.endswith('.md') for name in archive.namelist())
    (path/'source.mp4').write_bytes(b'changed source')
    with pytest.raises(ValueError,match='source bytes'):video_projects.import_video_project(path)


def test_reuse_keeps_checked_knowledge_but_never_old_run_proof(tmp_path,monkeypatch):
    path=seed_job(tmp_path,'verified')
    source_hash=hashlib.sha256((path/'source.mp4').read_bytes()).hexdigest()
    steps=[{'id':'s1','instruction':'Unit step','evidence_ids':['frame-1']}]
    knowledge={'status':'source_checked','source_file':'source.mp4','source_sha256':source_hash,
               'title':'Unit workflow','objective':'Unit objective','steps':steps,'verification':'not_executed'}
    (path/'knowledge.json').write_text(json.dumps(knowledge))
    (path/'plan.json').write_text(json.dumps({'steps':steps,'source_sha256':source_hash}))
    (path/'run').mkdir();(path/'run/replica.blend').write_bytes(b'explicit old unit artifact')
    (path/'audio.wav').write_bytes(b'unit audio fixture')
    (path/'frame_000.jpg').write_bytes(b'unit frame fixture')
    (path/'manifest.json').write_text(json.dumps({'audio_path':str(path/'audio.wav')}))
    monkeypatch.setattr(tutorial_app,'DATA',tmp_path)
    response=TestClient(tutorial_app.app).post(f'/api/video-sources/{path.name}/reuse')
    assert response.status_code==200
    job=response.json();copy=tmp_path/job['id']
    assert job['status']=='ready_for_review' and job['reused_from']==path.name
    assert (copy/'plan.json').read_bytes()==(path/'plan.json').read_bytes()
    assert (copy/'source.mp4').read_bytes()==(path/'source.mp4').read_bytes()
    assert not (copy/'run').exists()
    assert (copy/'frame_000.jpg').read_bytes()==b'unit frame fixture'
    assert json.loads((copy/'manifest.json').read_text())['audio_path']==str(copy/'audio.wav')
    assert json.loads((copy/'knowledge.json').read_text())['verification']=='not_executed'
