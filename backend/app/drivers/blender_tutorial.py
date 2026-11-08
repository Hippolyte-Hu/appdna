"""Dedicated PID-scoped scratch Blender process; never reuse the user's scene."""
import ctypes
import hashlib
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


def sandbox_command(folder: Path) -> list[str]:
    """Seatbelt enforces writes under this run, not a prompt or coordinate check."""
    folder=folder.resolve(strict=True)
    if folder.name!='run' or folder.parent==Path(folder.anchor):
        raise RuntimeError('Write sandbox requires a dedicated run directory')
    binary=Path('/usr/bin/sandbox-exec')
    if not binary.is_file():raise RuntimeError('Required macOS write sandbox is unavailable')
    profile='(version 1)\n(allow default)\n(deny file-write*)\n'
    profile+='(allow file-write* (subpath '+json.dumps(str(folder),ensure_ascii=False)+'))\n'
    # No broader temporary/home-directory exception, and no unsandboxed fallback.
    path=folder/'write-sandbox.sb'
    if path.exists() and path.read_text()!=profile:
        raise RuntimeError('Existing sandbox profile does not match this run')
    path.write_text(profile)
    return [str(binary),'-f',str(path)]


def process_identity(pid: int) -> str:
    value=subprocess.run(['/bin/ps','-p',str(pid),'-o','lstart=,comm='],capture_output=True,text=True,timeout=5)
    identity=value.stdout.strip()
    if value.returncode or not identity.endswith(str(BLENDER)):
        raise RuntimeError('Sandbox process identity is not the dedicated Blender binary')
    return identity


def require_kernel_scope(pid: int,folder: Path):
    """Query the actual PID's kernel sandbox; a marker alone is not proof."""
    library=ctypes.CDLL('/usr/lib/libsandbox.dylib',use_errno=True)
    check=library.sandbox_check
    check.restype=ctypes.c_int
    check.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int]
    # sandbox_check reports denial for nonexistent paths even without a sandbox.
    # Query existing directories, then combine with the launch/profile attestation.
    inside=os.fsencode(folder)
    outside=os.fsencode(folder.parent)
    for operation in (b'file-write-data',b'file-write-create'):
        if check(pid,operation,1,inside)!=0 or check(pid,operation,1,outside)!=1:
            raise RuntimeError('Kernel sandbox write-scope check failed; no input sent')


class BlenderTutorialDriver:
    def __init__(self, process, *, sandbox_folder: Path | None=None):
        self.process=process;self.pid=process.pid;self.sandbox_folder=sandbox_folder

    def _check_sandbox(self):
        folder=self.sandbox_folder
        if folder is None:raise RuntimeError('Missing sandbox attestation; no input sent')
        try:
            stamp=json.loads((folder/'sandbox-attestation.json').read_text())
            profile=(folder/'write-sandbox.sb').read_bytes()
        except (OSError,ValueError) as exc:
            raise RuntimeError('Missing or invalid sandbox attestation; no input sent') from exc
        if (stamp.get('pid')!=self.pid or stamp.get('folder')!=str(folder.resolve()) or
            stamp.get('profile_sha256')!=hashlib.sha256(profile).hexdigest() or
            stamp.get('process_identity')!=process_identity(self.pid)):
            raise RuntimeError('Sandbox attestation mismatch; no input sent')
        require_kernel_scope(self.pid,folder)

    @classmethod
    def resume(cls,pid: int,folder: Path):
        from types import SimpleNamespace
        driver=cls(SimpleNamespace(pid=pid),sandbox_folder=folder.resolve())
        driver._check_sandbox()
        guard('probe',pid)
        return driver

    @classmethod
    def launch(cls, folder: Path):
        if guard('lock')['locked']:raise RuntimeError('Mac is locked. Unlock it before running Blender actions.')
        folder=folder.resolve()
        if folder.exists():raise RuntimeError('Refusing to reuse an existing scratch run directory')
        folder.mkdir(parents=True)
        command=sandbox_command(folder)
        (folder/'tmp').mkdir()
        environment={k:v for k,v in os.environ.items() if k in {'PATH','HOME','USER','LOGNAME','LANG','LC_ALL','LC_CTYPE','__CF_USER_TEXT_ENCODING'}}
        environment.update(TMPDIR=str(folder/'tmp')+'/',BLENDER_USER_RESOURCES=str(folder/'blender-user'),
            BLENDER_USER_CONFIG=str(folder/'blender-user/config'),BLENDER_USER_SCRIPTS=str(folder/'blender-user/scripts'),
            BLENDER_USER_EXTENSIONS=str(folder/'blender-user/extensions'),BLENDER_USER_DATAFILES=str(folder/'blender-user/datafiles'))
        # Factory startup in a NEW process; OS-enforced writes stay under this run.
        with (folder/'blender.log').open('w') as log:
            process=subprocess.Popen([*command,str(BLENDER),'--factory-startup','-noaudio','--offline-mode','--disable-autoexec'],stdout=log,stderr=log,env=environment,cwd=folder)
        driver=cls(process,sandbox_folder=folder)
        last_error='Scratch Blender did not become foreground; no input sent'
        for _ in range(20):
            if process.poll() is not None:raise RuntimeError('Sandboxed scratch Blender exited during launch; inspect blender.log')
            try:
                identity=process_identity(driver.pid)
                require_kernel_scope(driver.pid,folder)
                stamp={'pid':driver.pid,'folder':str(folder),'process_identity':identity,
                    'profile_sha256':hashlib.sha256((folder/'write-sandbox.sb').read_bytes()).hexdigest()}
                (folder/'sandbox-attestation.json').write_text(json.dumps(stamp,indent=2))
                driver._check_sandbox()
                guard('activate',driver.pid)
                return driver
            except RuntimeError as exc:last_error=str(exc);time.sleep(.5)
        process.terminate();process.wait(timeout=5)
        raise RuntimeError(last_error)

    def capture(self,path: Path) -> Path:
        self._check_sandbox()
        bounds=guard('probe',self.pid)['bounds']
        region=','.join(str(int(bounds[k])) for k in ('X','Y','Width','Height'))
        subprocess.run(['screencapture','-x','-R',region,str(path)],check=True,capture_output=True,timeout=8)
        guard('probe',self.pid)
        return path

    def perform(self,action: dict, *, save_target: Path | None=None):
        self._check_sandbox()
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
