import json
import os
import shutil
import subprocess
from pathlib import Path

from app.adapters.script_guard import validate_script
from app.util import strip_code_fence

INSPECT_SCRIPT = """
import bpy, json
objects = [{"name": obj.name, "type": obj.type} for obj in bpy.data.objects]
print("APPDNA_JSON:" + json.dumps({"objects": objects}))
"""

VERIFY_SCRIPT = """
import bpy, json, sys
argv = sys.argv[sys.argv.index("--") + 1 :]
blend_path, object_name, material_name, report_path = argv
report = {
    "passed": False,
    "checks": {
        "file_reopened": False,
        "object_exists": False,
        "object_type_mesh": False,
        "material_assigned": False,
    },
    "object_name": object_name,
    "material_name": material_name,
    "error": None,
}
try:
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    report["checks"]["file_reopened"] = True
    obj = bpy.data.objects.get(object_name)
    report["checks"]["object_exists"] = obj is not None
    if obj is not None and obj.type == "MESH":
        report["checks"]["object_type_mesh"] = True
        for slot in obj.material_slots:
            if slot.material and slot.material.name == material_name:
                report["checks"]["material_assigned"] = True
    report["passed"] = all(report["checks"].values())
except Exception as exc:
    report["error"] = str(exc)
with open(report_path, "w", encoding="utf-8") as handle:
    json.dump(report, handle)
"""

PREVIEW_SCRIPT = """
import bpy, sys
argv = sys.argv[sys.argv.index("--") + 1 :]
blend_path, object_name, material_name, image_path = argv
bpy.ops.wm.open_mainfile(filepath=blend_path)
obj = bpy.data.objects.get(object_name)
if obj is None:
    raise SystemExit("preview object missing")
mat = bpy.data.materials.get(material_name)
if mat is not None:
    mat.use_nodes = True
    principled = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if principled:
        principled.inputs["Base Color"].default_value = (0.15, 0.92, 0.78, 1)
        principled.inputs["Metallic"].default_value = 0.72
        principled.inputs["Roughness"].default_value = 0.18
world = bpy.context.scene.world or bpy.data.worlds.new("PreviewWorld")
bpy.context.scene.world = world
world.use_nodes = True
background = world.node_tree.nodes.get("Background")
if background:
    background.inputs[0].default_value = (0.015, 0.02, 0.035, 1)
    background.inputs[1].default_value = 1.0
light_data = bpy.data.lights.new("PreviewKey", "AREA")
light_data.energy = 1800
light_data.size = 3
key = bpy.data.objects.new("PreviewKey", light_data)
bpy.context.collection.objects.link(key)
key.location = (3.2, -2.4, 4.2)
rim_data = bpy.data.lights.new("PreviewRim", "AREA")
rim_data.energy = 900
rim_data.color = (0.35, 0.55, 1)
rim = bpy.data.objects.new("PreviewRim", rim_data)
bpy.context.collection.objects.link(rim)
rim.location = (-3.4, 2.8, 2.2)
bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, -1.05))
floor = bpy.context.active_object
floor_mat = bpy.data.materials.new("PreviewFloor")
floor_mat.use_nodes = True
floor_bsdf = next((node for node in floor_mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
if floor_bsdf:
    floor_bsdf.inputs["Base Color"].default_value = (0.02, 0.025, 0.035, 1)
    floor_bsdf.inputs["Metallic"].default_value = 0.55
    floor_bsdf.inputs["Roughness"].default_value = 0.22
floor.data.materials.append(floor_mat)
camera = bpy.data.objects.get("Camera")
if camera is None:
    camera_data = bpy.data.cameras.new("PreviewCamera")
    camera = bpy.data.objects.new("PreviewCamera", camera_data)
    bpy.context.collection.objects.link(camera)
camera.location = (4.6, -4.2, 2.8)
track = camera.constraints.new(type="TRACK_TO")
track.target = obj
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis = "UP_Y"
scene = bpy.context.scene
scene.camera = camera
engines = {item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items}
for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
    if candidate in engines:
        scene.render.engine = candidate
        break
if scene.render.engine == "CYCLES":
    scene.cycles.samples = 32
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = image_path
bpy.ops.render.render(write_still=True)
"""


class BlenderUnavailable(Exception):
    pass


class BlenderAdapter:
    def __init__(self, binary: str) -> None:
        self.binary = binary

    def available(self) -> bool:
        return bool(shutil.which(self.binary) or Path(self.binary).exists())

    def inspect(self, workdir: Path) -> dict:
        workdir.mkdir(parents=True, exist_ok=True)
        script_path = workdir / "inspect.py"
        script_path.write_text(INSPECT_SCRIPT, encoding="utf-8")
        completed = self._run(script_path, workdir)
        payload = _read_json_line(completed.stdout)
        payload["returncode"] = completed.returncode
        (workdir / "inspect_stdout.log").write_text(completed.stdout, encoding="utf-8")
        (workdir / "inspect_stderr.log").write_text(completed.stderr, encoding="utf-8")
        return payload

    def run_experiment(
        self,
        script: str,
        workdir: Path,
        object_name: str,
        material_name: str,
    ) -> dict:
        cleaned = strip_code_fence(script)
        if "import bpy" not in cleaned:
            cleaned = "import bpy\n" + cleaned
        validate_script(cleaned, object_name, material_name)
        workdir.mkdir(parents=True, exist_ok=True)
        blend_path = workdir / "scene.blend"
        wrapped = cleaned.rstrip() + "\n" + f"bpy.ops.wm.save_as_mainfile(filepath={str(blend_path)!r})\n"
        script_path = workdir / "experiment.py"
        script_path.write_text(wrapped, encoding="utf-8")
        completed = self._run(script_path, workdir)
        (workdir / "experiment_stdout.log").write_text(completed.stdout, encoding="utf-8")
        (workdir / "experiment_stderr.log").write_text(completed.stderr, encoding="utf-8")
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "blend_path": str(blend_path) if blend_path.exists() else None,
            "script_path": str(script_path),
        }

    def verify(self, blend_path: Path, object_name: str, material_name: str, workdir: Path) -> dict:
        workdir.mkdir(parents=True, exist_ok=True)
        script_path = workdir / "verify_scene.py"
        report_path = workdir / "verification_report.json"
        script_path.write_text(VERIFY_SCRIPT, encoding="utf-8")
        if report_path.exists():
            report_path.unlink()
        completed = self._run(
            script_path,
            workdir,
            extra_args=["--", str(blend_path), object_name, material_name, str(report_path)],
        )
        (workdir / "verify_stdout.log").write_text(completed.stdout, encoding="utf-8")
        (workdir / "verify_stderr.log").write_text(completed.stderr, encoding="utf-8")
        if not report_path.exists():
            return {
                "passed": False,
                "checks": {
                    "file_reopened": False,
                    "object_exists": False,
                    "object_type_mesh": False,
                    "material_assigned": False,
                },
                "error": completed.stderr[-1000:] or "verification report was not written",
                "returncode": completed.returncode,
            }
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["returncode"] = completed.returncode
        return report

    def render_preview(self, blend_path: Path, object_name: str, material_name: str, workdir: Path) -> Path:
        workdir = workdir.resolve()
        blend_path = blend_path.resolve()
        workdir.mkdir(parents=True, exist_ok=True)
        script_path = workdir / "preview.py"
        image_path = workdir / "preview.png"
        script_path.write_text(PREVIEW_SCRIPT, encoding="utf-8")
        completed = self._run(
            script_path,
            workdir,
            extra_args=["--", str(blend_path), object_name, material_name, str(image_path)],
            timeout=180,
        )
        (workdir / "preview_stdout.log").write_text(completed.stdout, encoding="utf-8")
        (workdir / "preview_stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0 or not image_path.exists():
            detail = (completed.stderr or completed.stdout or "preview was not written")[-800:]
            raise RuntimeError(detail)
        return image_path

    def _run(
        self,
        script_path: Path,
        workdir: Path,
        extra_args: list[str] | None = None,
        timeout: int = 120,
    ) -> subprocess.CompletedProcess:
        if not self.available():
            raise BlenderUnavailable(f"blender executable not found: {self.binary}")
        script_path = script_path.resolve()
        workdir = workdir.resolve()
        command = [
            self.binary,
            "--background",
            "--factory-startup",
            "--python",
            str(script_path),
            *(extra_args or []),
        ]
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"HCOMPANY_API_KEY", "LINKUP_API_KEY", "GLADIA_API_KEY", "HAI_API_KEY"}
        }
        return subprocess.run(
            command,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )


def _read_json_line(stdout: str) -> dict:
    for line in stdout.splitlines():
        if line.startswith("APPDNA_JSON:"):
            return json.loads(line.split(":", 1)[1])
    return {"objects": [], "error": "inspect output missing"}
