"""Real OS write-denial probe; no Blender GUI interaction."""
import json
import subprocess
import sys
import pytest
from app.drivers import blender_tutorial as module


def test_sandbox_denies_writes_outside_own_scratch(tmp_path):
    if sys.platform != 'darwin':
        pytest.skip('macOS Seatbelt integration test')
    folder=tmp_path/'run'
    folder.mkdir()
    outside=tmp_path/'outside.txt'
    code="""import json,sys
from pathlib import Path
inside=Path(sys.argv[1]);outside=Path(sys.argv[2])
inside.write_text('real sandbox probe')
try:
    outside.write_text('must be denied')
    denied=False
except PermissionError:
    denied=True
print(json.dumps({'inside':inside.exists(),'outside_denied':denied}))
"""
    result=subprocess.run([*module.sandbox_command(folder),sys.executable,'-c',code,str(folder/'inside.txt'),str(outside)],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'inside':True,'outside_denied':True}
    assert not outside.exists()


def test_kernel_scope_query_matches_real_sandbox(tmp_path):
    folder=tmp_path/'run';folder.mkdir()
    child=subprocess.Popen([*module.sandbox_command(folder),sys.executable,'-c','import os,time;print(os.getpid(),flush=True);time.sleep(30)'],stdout=subprocess.PIPE,text=True)
    try:
        assert child.stdout is not None
        pid=int(child.stdout.readline())
        module.require_kernel_scope(pid,folder)
        with pytest.raises(RuntimeError,match='sandbox'):
            module.require_kernel_scope(__import__('os').getpid(),folder)
    finally:
        child.terminate();child.wait(timeout=5)


def test_bare_driver_refuses_input_before_guard(monkeypatch):
    from types import SimpleNamespace
    def forbidden(*args):raise AssertionError('Input must not be dispatched')
    monkeypatch.setattr(module,'guard',forbidden)
    driver=module.BlenderTutorialDriver(SimpleNamespace(pid=123))
    with pytest.raises(RuntimeError,match='sandbox'):
        driver.perform({'action':'key','text':'f3'})


def test_sandbox_blocks_symlink_overwrite_and_rename(tmp_path):
    folder=tmp_path/'run';folder.mkdir();outside=tmp_path/'protected.blend';outside.write_bytes(b'protected test fixture')
    (folder/'escape').symlink_to(outside)
    script='''import os,sys
from pathlib import Path
folder,outside=map(Path,sys.argv[1:])
for operation in (lambda:outside.write_bytes(b'bad'),lambda:(folder/'escape').write_bytes(b'bad'),lambda:os.rename(outside,folder/'stolen.blend')):
 try:operation()
 except PermissionError:pass
 else:raise AssertionError('write escaped sandbox')
'''
    result=subprocess.run([*module.sandbox_command(folder),sys.executable,'-c',script,str(folder),str(outside)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert outside.read_bytes()==b'protected test fixture'
    assert not (folder/'stolen.blend').exists()


def test_forged_receipt_cannot_replace_kernel_scope(tmp_path,monkeypatch):
    import hashlib,json,os
    folder=tmp_path/'run';folder.mkdir();module.sandbox_command(folder)
    identity='synthetic identity; identity validation is tested separately'
    stamp={'pid':os.getpid(),'folder':str(folder.resolve()),'process_identity':identity,
        'profile_sha256':hashlib.sha256((folder/'write-sandbox.sb').read_bytes()).hexdigest()}
    (folder/'sandbox-attestation.json').write_text(json.dumps(stamp))
    monkeypatch.setattr(module,'process_identity',lambda pid:identity)
    monkeypatch.setattr(module,'guard',lambda *a:pytest.fail('No input before live scope validation'))
    with pytest.raises(RuntimeError,match='sandbox'):module.BlenderTutorialDriver.resume(os.getpid(),folder)


def test_launch_uses_sandbox_private_environment_and_attestation(tmp_path,monkeypatch):
    from types import SimpleNamespace
    folder=tmp_path/'run';calls=[];checks=[]
    monkeypatch.setenv('APPDNA_PRIVATE_TEST_VALUE','synthetic-sentinel')
    def start(command,**kwargs):
        calls.append((command,kwargs));return SimpleNamespace(pid=123456789,poll=lambda:None)
    monkeypatch.setattr(module.subprocess,'Popen',start)
    monkeypatch.setattr(module,'process_identity',lambda pid:'synthetic process identity')
    monkeypatch.setattr(module,'require_kernel_scope',lambda pid,f:checks.append((pid,f)))
    monkeypatch.setattr(module,'guard',lambda *args:{'locked':False})
    driver=module.BlenderTutorialDriver.launch(folder)
    assert driver.sandbox_folder==folder.resolve() and (folder/'sandbox-attestation.json').is_file()
    assert len(calls)==1 and calls[0][0][0]=='/usr/bin/sandbox-exec'
    env=calls[0][1]['env']
    assert 'APPDNA_PRIVATE_TEST_VALUE' not in env
    assert not any(k.startswith(('HCOMPANY','GLADIA','DATABRICKS')) for k in env)
    assert all(v.startswith(str(folder.resolve())) for k,v in env.items() if k.startswith('BLENDER_'))
    assert env['TMPDIR'].startswith(str(folder.resolve())) and checks
    with pytest.raises(RuntimeError,match='reuse'):module.BlenderTutorialDriver.launch(folder)


def test_resume_refuses_unattested_process(tmp_path,monkeypatch):
    def forbidden(*args):
        raise AssertionError('No input/probe before sandbox attestation')
    monkeypatch.setattr(module,'guard',forbidden)
    with pytest.raises(RuntimeError,match='sandbox'):
        module.BlenderTutorialDriver.resume(123,tmp_path)
