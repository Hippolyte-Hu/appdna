import json
import shutil
from pathlib import Path

from app.engines.outcome import build_outcome, combined_source_relevance
from app.engines.report import render_report
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
    outcome = build_outcome(
        software_name=project.software_name,
        objective=project.learning_objective,
        capabilities=capabilities,
        claims=claims,
        frames=_trace(workdir),
        source_count=len(store.sources(project.id)),
        source_relevance=combined_source_relevance(workdir.parent),
        run_status=project.status,
        run_error=project.error_message,
    )
    scripts = {}
    if verified:
        for item in verified:
            script = shared_script
            match = next((row for row in experiments if row["capability_id"] == item["id"]), None)
            if match and match["actions"]:
                script = match["actions"][-1].get("script") or script
            scripts[item["id"]] = script
    for skill in outcome["skills"]:
        (package / "skills" / f"{_slug(skill['name'])}.md").write_text(
            _skill(project, skill, scripts.get(skill["id"], "")),
            encoding="utf-8",
        )
    if not outcome["skills"]:
        (package / "skills" / "README.md").write_text(
            "No tool skill was learned for this application.\n",
            encoding="utf-8",
        )
    media_folder = workdir.parent / "media"
    if media_folder.is_dir():
        shutil.copytree(media_folder, package / "evidence" / "recording", dirs_exist_ok=True)
    relevance = combined_source_relevance(workdir.parent)
    relevance_rows = {item.get("id"): item.get("relevant") for item in (relevance or {}).get("sources", [])}
    report_data = {column.name: getattr(project, column.name) for column in project.__table__.columns}
    report_data.update({"outcome": outcome, "capabilities": capabilities,
        "evidence": [{"id": row.id, "origin": row.origin, "kind": row.kind, "summary": row.summary} for row in store.evidence(project.id)],
        "transcripts": [{"id": row.id, **loads(row.payload_json, {})} for row in store.evidence(project.id) if row.kind == "transcript" and "text" in loads(row.payload_json, {})],
        "sources": [{"id": row.id, "title": row.title, "url": row.url, "is_relevant": relevance_rows.get(row.id)} for row in store.sources(project.id)]})
    media_manifest = media_folder / "manifest.json"
    if media_manifest.is_file():
        report_data["media"] = loads(media_manifest.read_text(), {})
    (package / "assessment-report.html").write_text(render_report(report_data))
    (package / "evaluation.md").write_text(_evaluation_markdown(project, outcome["evaluation"]), encoding="utf-8")
    (package / "knowledge-graph.json").write_text(json.dumps(outcome["graph"], indent=2), encoding="utf-8")

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


def _trace(workdir: Path) -> list[dict]:
    path = workdir.parent / "explore" / "trace.json"
    if not path.exists():
        return []
    payload = loads(path.read_text(encoding="utf-8"), [])
    return payload if isinstance(payload, list) else []


def _skill(project: Project, skill: dict, script: str) -> str:
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(skill["steps"], start=1))
    tools = "\n".join(f"- {item}" for item in skill["tools"]) or "- The application itself."
    procedure = f"```python\n{script}\n```\n\n" if script else ""
    return (
        f"# {skill['name']}\n\n"
        f"Status: {skill['status']}\n\n"
        f"Use when: {skill['use_when']}\n\n"
        f"Software: {project.software_name} {project.software_version or ''}\n\n"
        "## Tools\n\n"
        f"{tools}\n\n"
        "## How to use it\n\n"
        f"{steps}\n\n"
        f"{procedure}"
    )


def _evaluation_markdown(project: Project, evaluation: dict) -> str:
    strengths = "\n".join(f"- {item}" for item in evaluation["strengths"]) or "- None yet."
    gaps = "\n".join(f"- {item}" for item in evaluation["gaps"]) or "- None recorded."
    return (
        f"# {project.software_name} evaluation\n\n"
        f"Verdict: {evaluation['verdict']}\n\n"
        f"{evaluation['summary']}\n\n"
        "## Strengths\n\n"
        f"{strengths}\n\n"
        "## Gaps\n\n"
        f"{gaps}\n"
    )
