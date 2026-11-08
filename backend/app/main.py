import re
from threading import Lock
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import ValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from app.adapters.blender import BlenderAdapter
from app.config import get_settings
from app.engines.outcome import build_outcome, load_source_relevance
from app.engines.report import render_report
from app.db import init_db, session_scope
from app.models import Project
from app.orchestrator import run_session, resume_session
from app.schemas import ProjectCreate
from app.store import Store
from app.util import loads, new_id, utcnow

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac"}
MAX_AUDIO_BYTES = 25 * 1024 * 1024
_session_start_lock = Lock()

app = FastAPI(title="AppDNA", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "blender": BlenderAdapter(settings.blender_bin).available(),
        "providers": {
            "linkup": bool(settings.linkup_api_key),
            "gladia": bool(settings.gladia_api_key),
            "hcompany": bool(settings.hcompany_api_key),
            "devin": False,
        },
    }


@app.post("/api/projects", status_code=201)
async def create_project(request: Request, background: BackgroundTasks) -> dict:
    content_type = request.headers.get("content-type", "")
    audio_bytes = None
    audio_name = None
    if "multipart/form-data" in content_type:
        form = await request.form()
        body = _parse_project(
            {
                "software_name": str(form.get("software_name") or ""),
                "software_version": str(form.get("software_version") or "") or None,
                "learning_objective": str(form.get("learning_objective") or ""),
                "audio_url": str(form.get("audio_url") or "") or None,
                "target_url": str(form.get("target_url") or "") or None,
            }
        )
        upload = form.get("audio")
        if upload is not None and getattr(upload, "filename", None):
            audio_name = Path(upload.filename).name
            audio_bytes = await upload.read()
    else:
        body = _parse_project(await request.json())

    now = utcnow()
    project = Project(
        id=new_id("project"),
        software_name=body.software_name.strip(),
        target_url=body.target_url,
        software_version=(body.software_version or "").strip() or None,
        learning_objective=body.learning_objective.strip(),
        status="created",
        error_message=None,
        audio_url=body.audio_url,
        audio_path=None,
        package_path=None,
        created_at=now,
        updated_at=now,
    )
    if audio_bytes is not None:
        extension = Path(audio_name or "").suffix.lower()
        if extension not in AUDIO_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Audio must be mp3, wav, m4a, mp4, webm, ogg, or flac")
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio file is larger than 25MB")
        folder = get_settings().artifacts_dir / project.id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"audio{extension}"
        path.write_bytes(audio_bytes)
        project.audio_path = str(path)

    with _session_start_lock, session_scope() as db:
        _require_idle_desktop(db)
        db.add(project)
        db.commit()
    background.add_task(run_session, project.id)
    return _summary(project)


@app.get("/api/projects")
def list_projects() -> list[dict]:
    with session_scope() as db:
        rows = db.query(Project).order_by(Project.created_at.desc()).all()
        return [_summary(row) for row in rows]


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict:
    with session_scope() as db:
        store = Store(db)
        project = store.project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return _detail(store, project)


def _require_idle_desktop(db) -> None:
    if db.query(Project).filter(Project.status.notin_(["completed", "failed"])).first() is not None:
        raise HTTPException(status_code=409, detail="Another learning session is running. Wait until it finishes before using the desktop again.")


@app.post("/api/projects/{project_id}/resume", status_code=202)
def resume_project(project_id: str, background: BackgroundTasks) -> dict:
    with _session_start_lock, session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        _require_idle_desktop(db)
        if not _frames(project_id):
            raise HTTPException(status_code=409, detail="No saved interface exploration to continue yet.")
        store = Store(db)
        store.set_status(project, "resuming", "")
        store.log(project_id, "resuming", "Continuing this project from saved exploration; keeping sources, skills, and prior evidence.")
        background.add_task(resume_session, project_id)
        return _summary(project)


@app.get("/api/projects/{project_id}/package")
def download_package(project_id: str) -> FileResponse:
    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None or not project.package_path:
            raise HTTPException(status_code=404, detail="Package is not ready")
        path = Path(project.package_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Package file is missing")
    return FileResponse(path, filename=f"{project_id}-package.zip", media_type="application/zip")


@app.get("/api/projects/{project_id}/frames/{name}")
def project_frame(project_id: str, name: str) -> FileResponse:
    if not re.fullmatch(r"step_\d{2,}\.png", name):
        raise HTTPException(status_code=404, detail="Frame not found")
    path = get_settings().artifacts_dir / project_id / "explore" / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Frame not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/projects/{project_id}/preview")
def project_preview(project_id: str) -> FileResponse:
    path = _preview_path(project_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Preview is not ready")
    return FileResponse(path, media_type="image/png")


def _media_summary(project_id: str) -> dict | None:
    folder = get_settings().artifacts_dir / project_id / "media"
    manifest = folder / "manifest.json"
    if not manifest.is_file():
        return None
    media = loads(manifest.read_text(), {})
    analysis = loads((folder / "analysis.json").read_text(), {}) if (folder / "analysis.json").is_file() else {}
    return {"duration": media.get("duration"), "has_video": media.get("has_video"),
            "has_audio": media.get("has_audio"), "frames": media.get("frames", []),
            "observations": [{"timestamp": item["timestamp"], "result": item.get("analysis", {}), "error": item.get("error")} for item in analysis.get("frames", [])], "source_sha256": media.get("source_sha256")}


@app.get("/api/projects/{project_id}/report", response_class=HTMLResponse)
def project_report(project_id: str) -> HTMLResponse:
    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        content = render_report(_detail(Store(db), project))
    return HTMLResponse(content, headers={"Cache-Control": "no-store",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"})


@app.get("/api/projects/{project_id}/media/{name}")
def project_media(project_id: str, name: str) -> FileResponse:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project_id):
        raise HTTPException(status_code=404, detail="Recording not found")
    with session_scope() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if name == "original" and project.audio_path:
            path = Path(project.audio_path)
        elif re.fullmatch(r"frame_\d{3}\.jpg|audio\.wav", name):
            path = get_settings().artifacts_dir / project_id / "media" / name
        else:
            raise HTTPException(status_code=404, detail="Recording not found")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording not found")
    return FileResponse(path)


def _parse_project(payload: dict) -> ProjectCreate:
    try:
        return ProjectCreate.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


def _summary(project: Project) -> dict:
    return {
        "id": project.id,
        "software_name": project.software_name,
        "target_url": project.target_url,
        "target_kind": "website" if project.target_url else "desktop",
        "software_version": project.software_version,
        "learning_objective": project.learning_objective,
        "status": project.status,
        "error_message": project.error_message,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "package_ready": bool(project.package_path),
        "preview_ready": _preview_path(project.id).exists(),
    }


def _detail(store: Store, project: Project) -> dict:
    payload = _summary(project)
    payload["activities"] = [
        {"phase": row.phase, "message": row.message, "created_at": row.created_at}
        for row in store.activities(project.id)
    ]
    payload["sources"] = [_source_payload(row) for row in store.sources(project.id)]
    payload["claims"] = [
        {
            "id": row.id,
            "claim": row.claim,
            "claim_type": row.claim_type,
            "software_version": row.software_version,
            "evidence_ids": loads(row.evidence_ids_json, []),
            "confidence": row.confidence,
            "verification_status": row.verification_status,
        }
        for row in store.claims(project.id)
    ]
    payload["capabilities"] = [
        {
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
        for row in store.capabilities(project.id)
    ]
    payload["experiments"] = [
        {
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
        for row in store.experiments(project.id)
    ]
    payload["checks"] = _checks(store, project.id)
    payload["frames"] = _frames(project.id)
    payload["can_resume"] = project.status in {"completed", "failed"} and bool(payload["frames"])
    payload["evidence"] = [
        {
            "id": row.id,
            "origin": row.origin,
            "kind": row.kind,
            "summary": row.summary,
            "created_at": row.created_at,
        }
        for row in store.evidence(project.id)
    ]
    payload["transcripts"] = [{"id": row.id, **loads(row.payload_json, {})} for row in store.evidence(project.id) if row.kind == "transcript" and "text" in loads(row.payload_json, {})]
    payload["media"] = _media_summary(project.id)
    relevance = _source_relevance(project.id, payload["activities"], payload["sources"])
    video_relevance = load_source_relevance(get_settings().artifacts_dir / project.id / "media" / "relevance.json")
    if video_relevance and video_relevance.get("sources"):
        existing = list((relevance or {}).get("sources", []))
        known = {item.get("id") for item in existing}
        relevance = {"checked": True, "sources": existing + [item for item in video_relevance["sources"] if item.get("id") not in known]}
    for source in payload["sources"]:
        source["relevant"] = _relevant_flag(relevance, source["id"])
    payload["outcome"] = build_outcome(
        software_name=project.software_name,
        objective=project.learning_objective,
        capabilities=payload["capabilities"],
        claims=payload["claims"],
        frames=payload["frames"],
        source_count=len(payload["sources"]),
        source_relevance=relevance,
        run_status=project.status,
        run_error=project.error_message,
    )
    admitted = {skill["id"] for skill in payload["outcome"]["skills"]}
    payload["capabilities"] = [item for item in payload["capabilities"] if item["id"] in admitted]
    return payload


def _source_relevance(project_id: str, activities: list[dict], sources: list[dict]) -> dict | None:
    stored = load_source_relevance(get_settings().artifacts_dir / project_id / "explore" / "source_relevance.json")
    if stored is not None:
        return stored
    for activity in activities:
        message = activity.get("message") or ""
        if "Documents match the screen: False" in message:
            return {"checked": True, "sources": []}
        if "Documents match the screen: True" in message:
            return {
                "checked": True,
                "sources": [
                    {"id": source["id"], "relevant": True, "summary": source.get("title") or ""}
                    for source in sources
                ],
            }
    return None


def _relevant_flag(relevance: dict | None, source_id: str) -> bool | None:
    if not relevance or not relevance.get("checked"):
        return None
    for item in relevance.get("sources") or []:
        if isinstance(item, dict) and item.get("id") == source_id:
            value = item.get("relevant")
            return value if isinstance(value, bool) else None
    return None


def _frames(project_id: str) -> list[dict]:
    path = get_settings().artifacts_dir / project_id / "explore" / "trace.json"
    if not path.exists():
        return []
    payload = loads(path.read_text(encoding="utf-8"), [])
    return payload if isinstance(payload, list) else []


def _preview_path(project_id: str) -> Path:
    return get_settings().artifacts_dir / project_id / "run" / "preview.png"


def _checks(store: Store, project_id: str) -> dict | None:
    rows = [row for row in store.evidence(project_id) if row.kind == "test_result"]
    rows.sort(key=lambda row: row.created_at)
    for row in reversed(rows):
        payload = loads(row.payload_json, {})
        checks = payload.get("checks")
        if isinstance(checks, dict):
            return checks
    return None


def _source_payload(row) -> dict:
    file = Path(row.content_reference)
    content = file.read_text(encoding="utf-8", errors="replace") if file.is_file() else ""
    return {
        "id": row.id,
        "title": row.title,
        "url": row.url,
        "source_type": row.source_type,
        "software_version": row.software_version,
        "retrieved_at": row.retrieved_at,
        "license": row.license,
        "reliability": row.reliability,
        "excerpt": content[:400],
        "content": content,
    }
