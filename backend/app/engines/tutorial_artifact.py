"""Save via live GUI, then inspect the SAVED artifact in a separate read-only Blender."""
import asyncio
import hashlib
import json
import math
import subprocess
from pathlib import Path
from app.drivers.blender_tutorial import BLENDER
from app.engines.tutorial_runner import execute_plan

INSPECT=Path(__file__).resolve().parents[1]/'adapters/inspect_tutorial_artifact.py'


def assess_replica(audit: dict) -> dict:
    meshes=[o for o in audit.get('objects',[]) if o.get('type')=='MESH']
    mesh=meshes[0] if len(meshes)==1 else {}
    bevels=[m for m in mesh.get('modifiers',[]) if m.get('type')=='BEVEL']
    bevel=bevels[0] if len(bevels)==1 else {}
    checks={
        'single_cube_mesh':len(meshes)==1 and mesh.get('base_vertices')==8 and mesh.get('base_faces')==6,
        'one_visible_bevel':len(bevels)==1 and bevel.get('visible') is True,
        'four_segments':bevel.get('segments')==4,
        'width_0_22_m':math.isclose(bevel.get('width',0),.22,abs_tol=1e-5),
        'edge_affect':bevel.get('affect')=='EDGES',
        'evaluated_geometry_rounded':mesh.get('evaluated_vertices',0)>8,
        'smooth_shading':mesh.get('evaluated_smooth_faces',0)>0,
    }
    return {'verification':'verified' if all(checks.values()) else 'failed','checks':checks,'scope':'First edge-Bevel workflow at 0–50.326 seconds; not the later vertices/edit-mode alternatives'}


def inspect_replica(target: Path, *, expectations=None, source_folder=None) -> dict:
    if not target.is_file():return {'verification':'failed','reason':'GUI did not save the requested .blend file'}
    if expectations is not None:
        from app.engines.tutorial_expectations import validate_binding
        validate_binding(expectations,Path(source_folder))
    original_hash=hashlib.sha256(target.read_bytes()).hexdigest()
    audit_path=target.with_suffix('.audit.json')
    process=subprocess.run([str(BLENDER),'--background','--offline-mode','--disable-autoexec',str(target),'--python',str(INSPECT),'--',str(audit_path)],capture_output=True,text=True,timeout=90)
    if process.returncode or not audit_path.exists():return {'verification':'failed','reason':'Read-only artifact inspection failed'}
    audit=json.loads(audit_path.read_text())
    if expectations is not None:
        from app.engines.tutorial_expectations import assess_source_replica
        assessment=assess_source_replica(audit,expectations)
    else:assessment=assess_replica(audit)
    final_hash=hashlib.sha256(target.read_bytes()).hexdigest()
    result={**assessment,'artifact':target.name,'sha256':final_hash,'audit':audit,'read_only_hash_unchanged':original_hash==final_hash}
    if original_hash!=final_hash:result.update(verification='failed',reason='Artifact changed during read-only inspection')
    target.with_suffix('.verification.json').write_text(json.dumps(result,indent=2))
    return result


async def save_and_verify(folder: Path, driver, vision, stopped, *, expectations=None, source_folder=None) -> dict:
    target=(folder/'replica.blend').resolve()
    if target.exists():raise ValueError('Refusing to overwrite an existing artifact')
    if stopped():return {'verification':'failed','reason':'Stopped before saving artifact'}
    await asyncio.to_thread(driver.capture,folder/'replica-before-save.png')
    step={'id':'save-artifact','instruction':'Save this current scene as the exact save_target using the GUI. This is artifact capture, not a demonstrated tutorial step.',
          'expected':'Blender titlebar shows replica.blend without an unsaved asterisk AFTER Save As, and the file dialog has closed.',
          'save_target':str(target),'uncertainty':''}
    receipt=await execute_plan({'steps':[step]},folder/'save',driver,vision,stopped,max_actions=20,save_target=target)
    if receipt['status']!='observed_complete':return {'verification':'failed','reason':receipt.get('reason',receipt['status']),'save_receipt':receipt}
    return await asyncio.to_thread(inspect_replica,target,expectations=expectations,source_folder=source_folder)
