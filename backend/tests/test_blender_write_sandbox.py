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


def test_resume_refuses_unattested_process(tmp_path,monkeypatch):
    def forbidden(*args):
        raise AssertionError('No input/probe before sandbox attestation')
    monkeypatch.setattr(module,'guard',forbidden)
    with pytest.raises(RuntimeError,match='sandbox'):
        module.BlenderTutorialDriver.resume(123,tmp_path)
