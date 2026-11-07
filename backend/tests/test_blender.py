from pathlib import Path

from app.adapters.blender import BlenderAdapter

SCRIPT = """
import bpy
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
obj = bpy.context.active_object
obj.name = "AppDNACube"
mat = bpy.data.materials.new(name="AppDNAMaterial")
obj.data.materials.append(mat)
"""


def test_independent_verification(tmp_path: Path):
    adapter = BlenderAdapter("blender")
    assert adapter.available()
    run = adapter.run_experiment(SCRIPT, tmp_path, "AppDNACube", "AppDNAMaterial")
    assert run["returncode"] == 0, run["stderr"]
    assert run["blend_path"]
    report = adapter.verify(Path(run["blend_path"]), "AppDNACube", "AppDNAMaterial", tmp_path)
    assert report["passed"], report
    assert report["checks"]["object_type_mesh"]
    assert report["checks"]["material_assigned"]
    assert report["checks"]["file_reopened"]
