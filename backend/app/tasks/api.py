import asyncio
import json
import re
from typing import Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.tasks import persistence as store
from app.tasks.environment import environment_status
from app.tasks.runner import execute_run

router = APIRouter(prefix="/api", tags=["Business tasks"])


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    request: str = Field(min_length=20, max_length=4000)
    scenario: Literal["routing", "vip"] = "routing"
    parent_id: str | None = None

    @field_validator("title", "request")
    @classmethod
    def trim(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field must contain text")
        return value.strip()


class RunCreate(BaseModel):
    max_actions: int = Field(default=80, ge=5, le=150)
    timeout_seconds: int = Field(default=600, ge=60, le=1200)
    reuse_knowledge: bool = True


class RunControl(BaseModel):
    action: Literal["pause", "resume", "stop"]


@router.get("/tasks")
def list_tasks():
    return store.list_tasks()


@router.post("/tasks", status_code=201)
def create_task(body: TaskCreate):
    if body.parent_id and not store.get_task(body.parent_id):
        raise HTTPException(404, "The parent task does not exist")
    return store.create_task(body.title, body.request, body.scenario,
                             get_settings().chatwoot_version, body.parent_id)


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/tasks/{task_id}/runs", status_code=201)
def start_run(task_id: str, body: RunCreate, background: BackgroundTasks):
    try:
        run = store.new_run(task_id, body.max_actions, body.timeout_seconds, body.reuse_knowledge)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    background.add_task(execute_run, run["id"])
    return run


@router.post("/task-runs/{run_id}/control")
def control(run_id: str, body: RunControl):
    try:
        return store.control_run(run_id, body.action)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/task-runs/{run_id}/events")
async def run_events(run_id: str, request: Request):
    if not store.get_run(run_id):
        raise HTTPException(404, "Run not found")

    async def events():
        previous = ""
        while not await request.is_disconnected():
            run = store.get_run(run_id)
            payload = json.dumps(run)
            if payload != previous:
                yield f"data: {payload}\n\n"
                previous = payload
            else:
                yield ": heartbeat\n\n"
            if run["status"] in store.TERMINAL:
                return
            await asyncio.sleep(0.8)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/task-runs/{run_id}/evidence/{name}")
def screenshot(run_id: str, name: str):
    if not re.fullmatch(r"run_[a-f0-9]{12}", run_id) or not re.fullmatch(r"step_\d{3}\.png", name):
        raise HTTPException(404, "Evidence not found")
    if not store.get_run(run_id):
        raise HTTPException(404, "Run not found")
    path = get_settings().artifacts_dir / run_id / "browser" / name
    if not path.is_file():
        raise HTTPException(404, "Evidence not found")
    return FileResponse(path, media_type="image/png")


@router.get("/task-runs/{run_id}/report")
def report(run_id: str):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    task = store.get_task(run["task_id"])
    return {"schema_version": 1, "task": {key: task[key] for key in ("id", "title", "request", "criteria")},
            "run": run, "provenance": {"configuration": "Browser UI only", "execution": "H Company model and scoped Playwright browser",
                                       "verification": "Independent server-side fixtures; only synthetic input creation and result reads"}}


@router.get("/knowledge")
def knowledge():
    return store.list_knowledge()


@router.get("/environments")
def environments():
    return environment_status()


@router.post("/environments/probe")
async def probe():
    state = environment_status()
    try:
        async with httpx.AsyncClient(timeout=4, follow_redirects=False) as client:
            response = await client.get(f"{get_settings().chatwoot_base_url.rstrip('/')}/auth/sign_in")
        reachable = response.status_code < 400
    except (httpx.HTTPError, ValueError):
        reachable = False
    return {**state, "reachable": reachable,
            "probe_message": "Chatwoot responded. Model, session and verifier checks still apply." if reachable
            else "Chatwoot did not respond. Start the isolated environment on the configured URL."}
