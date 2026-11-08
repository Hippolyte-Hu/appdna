"""Dedicated PID-scoped scratch Blender process; never reuse the user's scene."""
import json
import os
import subprocess
import time
from pathlib import Path
from app.engines.tutorial import validate_action

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'tasks/video-agent/blender_guard.swift'
GUARD=ROOT/'tasks/video-agent/evidence/blender-guard'
BLENDER=Path('/Applications/Blender.app/Contents/MacOS/Blender')


def guard(command: str, pid: int=0, *arguments: str) -> dict:
    if not GUARD.exists() or GUARD.stat().st_mtime<SOURCE.stat().st_mtime:
        subprocess.run(['swiftc',str(SOURCE),'-o',str(GUARD)],check=True,capture_output=True,timeout=60)
    result=subprocess.run([str(GUARD),command,str(pid),*arguments],capture_output=True,text=True,timeout=8)
    try:value=json.loads(result.stdout)
    except ValueError as exc:raise RuntimeError('Blender guard did not return usable evidence') from exc
    if result.returncode or value.get('error'):raise RuntimeError(value.get('error','Blender guard failed'))
    return value


class BlenderTutorialDriver:
    def __init__(self, process):self.process=process;self.pid=process.pid

    @classmethod
    def launch(cls, folder: Path):
        if guard('lock')['locked']:raise RuntimeError('Mac is locked. Unlock it before running Blender actions.')
        folder.mkdir(parents=True,exist_ok=True)
        # Factory startup is a NEW process; this never resets an existing scene.
        with (folder/'blender.log').open('w') as log:
            process=subprocess.Popen([str(BLENDER),'--factory-startup','-noaudio','--offline-mode','--disable-autoexec'],stdout=log,stderr=log,env={**os.environ,'BLENDER_USER_RESOURCES':str((folder/'blender-user').resolve())})
        driver=cls(process)
        for _ in range(20):
            if process.poll() is not None:raise RuntimeError('Scratch Blender exited during launch')
            try:guard('activate',driver.pid);return driver
            except RuntimeError:time.sleep(.5)
        raise RuntimeError('Scratch Blender did not become foreground; no input sent')

    def capture(self,path: Path) -> Path:
        bounds=guard('probe',self.pid)['bounds']
        region=','.join(str(int(bounds[k])) for k in ('X','Y','Width','Height'))
        subprocess.run(['screencapture','-x','-R',region,str(path)],check=True,capture_output=True,timeout=8)
        guard('probe',self.pid)
        return path

    def perform(self,action: dict, *, save_target: Path | None=None):
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
