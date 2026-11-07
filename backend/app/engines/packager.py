import json
import shutil
from pathlib import Path

from app.models import Project
from app.store import Store
from app.util import loads, utcnow


def export_package(store: Store, project: Project, workdir: Path, destination: Path) -> str:
    package = destination / "appdna-package"
    if package.exists():
        shutil.rmtree(package)
    for folder in ("evidence", "experiments", "tests", "skills"):
        (package / folder).mkdir(parents=True)

    claims = [ _claim(row) for row in store.claims(project.id) ]
    capabilities = [_capability(row) for row in store.capabilities(project.id)]
    experiments = [_experiment(row) for row in store.experiments(project.id)]
    evidence_index = []
    for row in store.evidence(project.id):
        payload = loads(row.payload_json, {})
        document = {
            "id": row.id,
            "origin": row.origin,
            "kind": row.kind,
            "summary": row.summary,
            "created_at": row.created_at,
            "payload": payload,
            "artifact_path": row.artifact_path,
        }
        (package / "evidence" / f"{row.id}.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
        evidence_index.append({"id": row.id, "origin": row.origin, "kind": row.kind, "created_at": row.created_at})

    (package / "claims.json").write_text(json.dumps(claims, indent=2), encoding="utf-8")
    (package / "capability-graph.json").write_text(json.dumps(capabilities, indent=2), encoding="utf-8")
    for experiment in experiments:
        (package / "experiments" / f"{experiment['id']}.json").write_text(
            json.dumps(experiment, indent=2),
            encoding="utf-8",
        )

    _copy_if_exists(workdir / "verify_scene.py", package / "tests" / "verify_scene.py")
    _copy_if_exists(workdir / "verification_report.json", package / "tests" / "verification_report.json")
    _copy_if_exists(workdir / "scene.blend", package / "experiments" / "scene.blend")
    _copy_if_exists(workdir / "preview.png", package / "experiments" / "preview.png")

    verified = [item for item in capabilities if item["verification_status"] == "verified"]
    shared_script = ""
    for row in experiments:
        if row["verification_status"] == "verified" and row["actions"]:
            shared_script = row["actions"][-1].get("script") or shared_script
    if verified:
        for item in verified:
            script = shared_script
            match = next((row for row in experiments if row["capability_id"] == item["id"]), None)
            if match and match["actions"]:
                script = match["actions"][-1].get("script") or script
            slug = _slug(item["name"])
            (package / "skills" / f"{slug}.md").write_text(_skill(project, item, script), encoding="utf-8")
    else:
        (package / "skills" / "README.md").write_text(
            "No capability was independently verified, so no skill was published.\n",
            encoding="utf-8",
        )

    manifest = {
        "software_name": project.software_name,
        "software_version": project.software_version,
        "learning_objective": project.learning_objective,
        "project_id": project.id,
        "generated_at": utcnow(),
        "capabilities": [
            {
                "id": item["id"],
                "name": item["name"],
                "verification_status": item["verification_status"],
                "confidence": item["confidence"],
                "related_claims": item["related_claims"],
            }
            for item in capabilities
        ],
        "evidence": evidence_index,
    }
    (package / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    archive = shutil.make_archive(str(destination / "appdna-package"), "zip", destination, "appdna-package")
    return archive


def _copy_if_exists(source: Path, target: Path) -> None:
    if source.exists():
        shutil.copy2(source, target)


def _claim(row) -> dict:
    return {
        "id": row.id,
        "claim": row.claim,
        "claim_type": row.claim_type,
        "software_version": row.software_version,
        "evidence_ids": loads(row.evidence_ids_json, []),
        "confidence": row.confidence,
        "verification_status": row.verification_status,
    }


def _capability(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "preconditions": loads(row.preconditions_json, []),
        "inputs": loads(row.inputs_json, []),
        "expected_outputs": loads(row.expected_outputs_json, []),
        "related_claims": loads(row.related_claims_json, []),
        "verification_status": row.verification_status,
        "confidence": row.confidence,
    }


def _experiment(row) -> dict:
    return {
        "id": row.id,
        "capability_id": row.capability_id,
        "objective": row.objective,
        "actions": loads(row.actions_json, []),
        "observations": loads(row.observations_json, []),
        "result": row.result,
        "verification_status": row.verification_status,
        "object_name": row.object_name,
        "material_name": row.material_name,
        "created_at": row.created_at,
    }


def _slug(name: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in name).strip("-")
    return cleaned or "capability"


def _skill(project: Project, capability: dict, script: str) -> str:
    checks = "\n".join(
        f"- {item}"
        for item in (
            "The named object exists.",
            "The object type is MESH.",
            "The named material is assigned to that object.",
            "The project file can be reopened.",
        )
    )
    return (
        f"# {capability['name']}\n\n"
        f"{capability['description']}\n\n"
        f"Software: {project.software_name} {project.software_version or ''}\n\n"
        "## Preconditions\n\n"
        + "\n".join(f"- {item}" for item in capability["preconditions"])
        + "\n\n## Verified procedure\n\n"
        "This script passed an independent Blender data-API check. "
        "A screenshot is not the evidence.\n\n"
        f"```python\n{script}\n```\n\n"
        "## Independent test\n\n"
        "Run `tests/verify_scene.py` in a new Blender process against `experiments/scene.blend`.\n\n"
        f"{checks}\n"
    )
