import logging
import subprocess
from pathlib import Path

from app.adapters.blender import BlenderAdapter, BlenderUnavailable
from app.config import get_settings
from app.db import session_scope
from app.drivers.macos import VisualExploreError
from app.engines.exploration import explore_and_experiment
from app.engines.learning import LearningError, blender_objective_capability, understand
from app.engines.visual import explore_visually
from app.engines.media import prepare_media
from app.engines.video_knowledge import ingest_video
from app.engines.packager import export_package
from app.engines.research import collect_sources
from app.engines.verification import verify_scene
from app.providers.base import ProviderError
from app.providers.gladia import GladiaProvider
from app.providers.hcompany import HCompanyProvider
from app.providers.linkup import LinkupProvider
from app.store import Store

logger = logging.getLogger("appdna")


async def run_session(project_id: str) -> None:
    settings = get_settings()
    linkup = LinkupProvider(settings.linkup_api_key, settings.linkup_base_url)
    gladia = GladiaProvider(settings.gladia_api_key, settings.gladia_base_url)
    reasoner = HCompanyProvider(
        settings.hcompany_api_key,
        settings.hcompany_base_url,
        settings.hcompany_model,
    )
    blender = BlenderAdapter(settings.blender_bin)
    root = settings.artifacts_dir / project_id
    try:
        with session_scope() as db:
            store = Store(db)
            project = store.project(project_id)
            if project is None:
                return
            store.set_status(project, "researching", "")
            store.log(
                project.id,
                "researching",
                f"Searching documentation, tutorials, videos, and GitHub for {project.software_name}.",
            )
            found = await collect_sources(store, project, linkup, root / "sources")

            store.set_status(project, "understanding")
            media = _prepare_recording(store, project, root / "media")
            transcripts = await _transcribe(store, project, gladia, media)
            if media.get("has_video"):
                admitted = await ingest_video(store, project, reasoner, media, transcripts, root / "media")
                found = found or bool(admitted.get("sources"))
            capability = None
            documented = False
            if found:
                try:
                    store.log(project.id, "understanding", "Reading the documents. The app opens after this step.")
                    capability, documented = await understand(store, project, reasoner, transcripts, root / "understanding")
                except (LearningError, ProviderError) as exc:
                    store.log(
                        project.id,
                        "understanding",
                        f"{exc}. Opening {project.software_name} and learning from the live interface.",
                    )
            else:
                store.log(
                    project.id,
                    "understanding",
                    f"No public documents for {project.software_name}. The agent will learn from the live interface.",
                )
            if project.software_name.lower() == "blender" and capability is None:
                capability = blender_objective_capability(store, project)

            visual_steps: list[dict] = []
            visual_error = ""
            store.set_status(project, "exploring")
            visual_steps, visual_error = await _watch_and_click(
                store,
                project,
                reasoner,
                root / "explore",
                *_document_brief(store, project),
            )
            report = None
            run = None
            if project.software_name.lower() == "blender" and blender.available():
                try:
                    store.set_status(project, "experimenting")
                    experiment, run = await explore_and_experiment(
                        store,
                        project,
                        capability,
                        blender,
                        reasoner,
                        root / "run",
                    )
                    if run and run.get("blend_path"):
                        store.set_status(project, "verifying")
                        report = verify_scene(
                            store,
                            project,
                            capability,
                            experiment,
                            blender,
                            Path(run["blend_path"]),
                            root / "run",
                        )
                        if report.get("passed"):
                            _render_preview(store, project, experiment, blender, Path(run["blend_path"]), root / "run")
                except (ProviderError, BlenderUnavailable, OSError) as exc:
                    store.log(project.id, "experimenting", f"Independent Blender check stopped: {exc}")
                    run = None
            elif visual_steps and not any(step.get("action") == "click" and step.get("executed") for step in visual_steps):
                store.log(
                    project.id,
                    "verifying",
                    "The live app matches the documents, so there were no clicks to verify.",
                )
            elif project.software_name.lower() == "blender":
                store.log(project.id, "verifying", "Blender is not installed, so the click trace cannot be independently verified.")
            else:
                store.log(
                    project.id,
                    "verifying",
                    "No independent verifier exists for this application yet. The click trace stays observed.",
                )
            store.set_status(project, "packaging")
            archive = export_package(store, project, root / "run", root / "package")
            project.package_path = archive
            clicked = any(step.get("action") == "click" and step.get("executed") for step in visual_steps)
            if report and report.get("passed"):
                store.set_status(project, "completed", "")
                store.log(project.id, "completed", "The agent used the app, and an independent test verified the capability.")
            elif visual_steps and not clicked:
                store.set_status(project, "completed", "")
                store.log(
                    project.id,
                    "completed",
                    "Opened the app and compared it with the documents. They match and the documents are complete, so nothing was clicked.",
                )
            elif visual_steps:
                store.set_status(project, "completed", "")
                store.log(project.id, "completed", "The agent looked at the live app and learned by clicking. Nothing was marked verified.")
            else:
                reason = visual_error or _failure_reason(report, run)
                store.set_status(project, "failed", reason)
                store.log(project.id, "failed", reason)
    except (ProviderError, LearningError, BlenderUnavailable, OSError) as exc:
        _fail(project_id, str(exc))
    except Exception as exc:
        logger.exception("Learning session failed")
        _fail(project_id, str(exc))


async def resume_session(project_id: str) -> None:
    """Continue GUI learning only: no new research, transcription or bpy experiment."""
    settings = get_settings()
    reasoner = HCompanyProvider(settings.hcompany_api_key, settings.hcompany_base_url, settings.hcompany_model)
    root = settings.artifacts_dir / project_id
    try:
        with session_scope() as db:
            store = Store(db)
            project = store.project(project_id)
            if project is None:
                return
            store.set_status(project, "exploring", "")
            documents, source_ids = _document_brief(store, project)
            await explore_visually(store, project, reasoner, root / "explore",
                                   documents=documents, source_ids=source_ids, resume=True)
            store.set_status(project, "packaging")
            project.package_path = export_package(store, project, root / "run", root / "package")
            store.set_status(project, "completed", "")
            store.log(project_id, "completed", "Continuation saved. Prior evidence and independent checks were retained; new GUI skills remain observed, not independently verified.")
    except Exception as exc:
        logger.exception("Continuation failed")
        _fail(project_id, str(exc))


def _document_brief(store: Store, project) -> tuple[str, list[str]]:
    parts = []
    source_ids = []
    for source in store.sources(project.id):
        source_ids.append(source.id)
        path = Path(source.content_reference or "")
        body = path.read_text(encoding="utf-8") if path.is_file() else ""
        parts.append(f"[{source.id}] {source.title}\n{source.url}\n{body}")
    return "\n\n".join(parts), source_ids


async def _watch_and_click(
    store: Store,
    project,
    reasoner: HCompanyProvider,
    folder: Path,
    documents: str = "",
    source_ids: list[str] | None = None,
) -> tuple[list[dict], str]:
    try:
        return await explore_visually(
            store, project, reasoner, folder, documents=documents, source_ids=source_ids or []
        ), ""
    except VisualExploreError as exc:
        store.log(project.id, "exploring", str(exc))
        return [], str(exc)


def _prepare_recording(store, project, folder):
    if not project.audio_path:
        return {}
    try:
        media = prepare_media(Path(project.audio_path), folder)
        store.add_evidence(project.id, origin="ffmpeg", kind="media_extraction",
            summary=f"Separated recording streams and sampled {len(media['frames'])} timestamped frames.",
            payload=media, artifact_path=str(folder / "manifest.json"))
        return media
    except (ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        store.log(project.id, "understanding", f"Recording extraction failed: {exc}")
        store.add_evidence(project.id, origin="ffmpeg", kind="media_error", summary=str(exc))
        return {"error": str(exc)}


async def _transcribe(store: Store, project, gladia: GladiaProvider, media: dict | None = None) -> list[dict]:
    if not project.audio_path and not project.audio_url:
        store.log(project.id, "understanding", "No audio attachment. Continuing from documents.")
        return []
    if media and (media.get("error") or not media.get("has_audio")):
        store.log(project.id, "understanding", "No usable extracted audio; video observations can continue without narration.")
        return []
    try:
        if project.audio_path:
            segments = await gladia.transcribe_file(Path((media or {}).get("audio_path") or project.audio_path))
            origin = project.audio_path
        else:
            segments = await gladia.transcribe_url(project.audio_url)
            origin = project.audio_url
    except ProviderError as exc:
        store.log(project.id, "understanding", f"Transcription failed and was recorded. {exc}")
        store.add_evidence(
            project.id,
            origin=project.audio_url or project.audio_path or "gladia",
            kind="transcript",
            summary=f"Gladia transcription failed: {exc}",
            payload={"error": str(exc)},
        )
        return []
    stored = []
    for segment in segments:
        evidence = store.add_evidence(
            project.id,
            origin=origin,
            kind="transcript",
            summary=segment["text"][:240],
            payload=segment,
        )
        stored.append({**segment, "evidence_id": evidence.id, "origin": origin})
    store.log(project.id, "understanding", f"Stored {len(stored)} transcript segments.")
    return stored


def _render_preview(store: Store, project, experiment, blender: BlenderAdapter, blend_path: Path, workdir: Path) -> None:
    try:
        image = blender.render_preview(
            blend_path,
            experiment.object_name or "",
            experiment.material_name or "",
            workdir,
        )
    except (BlenderUnavailable, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        store.log(project.id, "verifying", f"Preview render was skipped. {exc}")
        return
    store.add_evidence(
        project.id,
        origin="blender",
        kind="preview",
        summary="Rendered preview of the verified scene",
        payload={"path": str(image)},
        artifact_path=str(image),
    )
    store.log(project.id, "verifying", "Rendered a preview of the verified scene.")


def _failure_reason(report: dict | None, run: dict | None) -> str:
    if report and not report.get("passed"):
        checks = report.get("checks") or {}
        failed = [name for name, ok in checks.items() if not ok]
        return "Verification failed: " + ", ".join(failed or ["unknown"])
    if not run:
        return "The experiment did not produce a scene file. See the execution log."
    return "The capability was not independently verified."


def _fail(project_id: str, message: str) -> None:
    with session_scope() as db:
        store = Store(db)
        project = store.project(project_id)
        if project is None or project.status in {"completed", "failed"}:
            return
        store.set_status(project, "failed", message[:2000])
        store.log(project_id, "failed", message[:1000])
