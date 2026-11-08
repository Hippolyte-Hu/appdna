from pathlib import Path

from app.adapters.blender import BlenderAdapter
from app.models import Capability, Experiment, Project
from app.store import Store


def verify_scene(
    store: Store,
    project: Project,
    capability: Capability,
    experiment: Experiment,
    blender: BlenderAdapter,
    blend_path: Path,
    workdir: Path,
) -> dict:
    report = blender.verify(
        blend_path,
        experiment.object_name or "",
        experiment.material_name or "",
        workdir,
    )
    passed = bool(report.get("passed"))
    status = "verified" if passed else "contradicted"
    experiment.verification_status = status
    covered = _covered_capabilities(store.capabilities(project.id), capability, report)
    for item in covered:
        item.verification_status = "verified"
        for claim_id in _related(item):
            claim = next((row for row in store.claims(project.id) if row.id == claim_id), None)
            if claim is not None:
                claim.verification_status = "verified"
    if not passed:
        capability.verification_status = status
    store.add_evidence(
        project.id,
        origin="blender",
        kind="test_result",
        summary="Independent scene verification " + ("passed" if passed else "failed"),
        payload=report,
        artifact_path=str(workdir / "verification_report.json"),
    )
    store.db.commit()
    failed = [name for name, ok in (report.get("checks") or {}).items() if not ok]
    if passed:
        store.log(project.id, "verifying", "Independent checks passed. A screenshot was not used.")
    else:
        store.log(
            project.id,
            "verifying",
            "Independent checks failed: " + (", ".join(failed) or report.get("error") or "unknown"),
        )
    return report


def _covered_capabilities(capabilities: list[Capability], selected: Capability, report: dict) -> list[Capability]:
    if not report.get("passed"):
        return []
    checks = report.get("checks") or {}
    covered = []
    for item in capabilities:
        # A scene created by a separate bpy experiment cannot validate a GUI action.
        if getattr(item, "verification_status", "") in {"experimented", "observed"}:
            continue
        text = f"{item.name} {item.description}".lower()
        mesh_hit = bool(checks.get("object_type_mesh")) and any(token in text for token in ("cube", "primitive"))
        material_hit = bool(checks.get("material_assigned")) and "material" in text
        if item.id == selected.id or mesh_hit or material_hit:
            covered.append(item)
    return covered


def _related(capability: Capability) -> list[str]:
    import json

    try:
        value = json.loads(capability.related_claims_json)
    except json.JSONDecodeError:
        return []
    return [item for item in value if isinstance(item, str)]
