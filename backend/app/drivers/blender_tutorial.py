"""Dedicated PID-scoped scratch Blender process; never reuse the user's scene."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from app.blender_runtime import resolve_blender
from app.config import get_settings
from app.engines.tutorial import validate_action

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'tasks/video-agent/blender_guard.swift'
GUARD=ROOT/'tasks/video-agent/evidence/blender-guard'
BLENDER=Path(resolve_blender(get_settings().blender_bin))
_OWNED={}


def sandbox_command(folder: Path) -> list[str]:
    """Kernel-enforced write confinement, inherited by every Blender child.

    The path is a sandbox parameter, never interpolated into profile code.
    There is deliberately no unsandboxed fallback on unsupported systems.
    """
    if sys.platform!='darwin' or not Path('/usr/bin/sandbox-exec').is_file():
        raise RuntimeError('Blender GUI execution requires the macOS write sandbox')
    folder=Path(folder).resolve(strict=True)
    if folder==Path('/') or not folder.is_dir():
        raise RuntimeError('A dedicated scratch directory is required for the sandbox')
    profile='''(version 1)
(allow default)
(deny file-write*
    (require-all
        (require-not (subpath (param "APPDNA_SCRATCH")))
        (require-not (literal "/dev/null"))))'''
    return ['/usr/bin/sandbox-exec','-D',f'APPDNA_SCRATCH={folder}','-p',profile]


def guard(command: str, pid: int=0, *arguments: str) -> dict:
    if not GUARD.exists() or GUARD.stat().st_mtime<SOURCE.stat().st_mtime:
        GUARD.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['swiftc',str(SOURCE),'-o',str(GUARD)],check=True,capture_output=True,timeout=60)
    result=subprocess.run([str(GUARD),command,str(pid),*arguments],capture_output=True,text=True,timeout=8)
    try:value=json.loads(result.stdout)
    except ValueError as exc:raise RuntimeError('Blender guard did not return usable evidence') from exc
    if result.returncode or value.get('error'):raise RuntimeError(value.get('error','Blender guard failed'))
    return value


class BlenderTutorialDriver:
    def __init__(self, process, folder=None):
        self.process=process;self.pid=process.pid
        self.folder=Path(folder).resolve() if folder else None

    def _assert_attested(self):
        if _OWNED.get(self.pid) is not self or self.folder is None or self.process.poll() is not None:
            raise RuntimeError('No live sandbox attestation for this Blender process')

    @classmethod
    def resume(cls, pid: int, folder: Path, *, activate=False):
        # A PID file is not proof. Only this controller's still-live Popen may
        # resume. Restarted controllers must create a new scratch process.
        driver=_OWNED.get(pid)
        if driver is None or driver.folder!=Path(folder).resolve():
            raise RuntimeError('Cannot resume Blender without a matching live sandbox attestation')
        driver._assert_attested()
        guard('activate' if activate else 'probe',pid)
        return driver

    @classmethod
    def launch(cls, folder: Path):
        if guard('lock')['locked']:raise RuntimeError('Mac is locked. Unlock it before running Blender actions.')
        folder=Path(folder).resolve()
        folder.mkdir(parents=True,exist_ok=False)
        runtime=folder/'.runtime'
        for name in ('tmp','cache','config','data'):(runtime/name).mkdir(parents=True)
        command=[*sandbox_command(folder),str(BLENDER),'--factory-startup','-noaudio','--offline-mode','--disable-autoexec']
        env={key:value for key,value in os.environ.items()
             if not any(secret in key.upper() for secret in ('KEY','TOKEN','SECRET','PASSWORD','CREDENTIAL'))}
        env.update(BLENDER_USER_RESOURCES=str(runtime/'data'),TMPDIR=str(runtime/'tmp')+'/',
                   XDG_CACHE_HOME=str(runtime/'cache'),XDG_CONFIG_HOME=str(runtime/'config'),
                   PYTHONDONTWRITEBYTECODE='1')
        # Factory startup is a NEW process; this never resets an existing scene.
        with (folder/'blender.log').open('w') as log:
            process=subprocess.Popen(command,stdout=log,stderr=log,env=env,cwd=folder)
        driver=cls(process,folder)
        _OWNED[driver.pid]=driver
        launch={'pid':driver.pid,'write_sandbox':True,'status':'starting','attempts':[]}
        def receipt():
            (folder/'launch.json').write_text(json.dumps(launch,indent=2))
        receipt()
        try:
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError('Sandboxed scratch Blender exited during launch; see blender.log')
                try:
                    guard('activate',driver.pid)
                    launch['status']='ready';receipt();return driver
                except RuntimeError as exc:
                    launch['attempts'].append(str(exc));receipt()
                    if any(message in str(exc) for message in ('locked','permission is missing')):raise
                    time.sleep(.5)
            reason=launch['attempts'][-1] if launch['attempts'] else 'No visible window'
            raise RuntimeError('Scratch Blender did not become foreground: '+reason+'; no input sent')
        except BaseException as exc:
            launch.update(status='blocked',error=str(exc));receipt()
            driver.close()
            raise

    def prepare_save(self, target: Path, *, allow_existing=False):
        self._assert_attested()
        target=Path(target)
        if target.is_symlink() or target.resolve()!=self.folder/'replica.blend' or (target.exists() and not allow_existing):
            raise RuntimeError('Save requires a new replica.blend inside this process sandbox')
        return target

    def close(self):
        if _OWNED.get(self.pid) is not self:return
        _OWNED.pop(self.pid,None)
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill();self.process.wait(timeout=5)

    def capture(self,path: Path) -> Path:
        self._assert_attested()
        bounds=guard('probe',self.pid)['bounds']
        region=','.join(str(int(bounds[k])) for k in ('X','Y','Width','Height'))
        subprocess.run(['screencapture','-x','-R',region,str(path)],check=True,capture_output=True,timeout=8)
        guard('probe',self.pid)
        return path

    def perform(self,action: dict, *, save_target: Path | None=None):
        self._assert_attested()
        if save_target is not None:self.prepare_save(save_target)
        action=validate_action(action,save_target=save_target)
        kind=action['action']
        if kind in {'click','double_click','right_click'}:guard(kind,self.pid,str(action['x']),str(action['y']))
        elif kind in {'set_number','set_text'}:
            guard('double_click',self.pid,str(action['x']),str(action['y']));time.sleep(.15)
            guard('key',self.pid,'ctrl+a');time.sleep(.1)
            guard('type',self.pid,action['text']);time.sleep(.1)
            guard('key',self.pid,'return')
        elif kind in {'key','type'}:guard(kind,self.pid,action['text'])
        elif kind=='wait':guard('probe',self.pid);time.sleep(.5)
        else:raise ValueError('Not an input action')
