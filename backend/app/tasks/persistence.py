import json
from datetime import datetime, timezone

from sqlalchemy import text

from app.db import session_scope
from app.models import OperationalKnowledge, TaskRecord, TaskRun
from app.tasks.catalog import criteria
from app.util import new_id, utcnow

TERMINAL = {"completed", "failed", "blocked", "cancelled"}
STAGES = ["understand", "research", "explore", "execute", "verify", "save"]


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def task_dict(task: TaskRecord) -> dict:
    return {"id": task.id, "title": task.title, "request": task.request,
            "scenario": task.scenario, "software": task.software,
            "software_version": task.software_version, "parent_id": task.parent_id,
            "criteria": json.loads(task.criteria_json), "created_at": task.created_at}


def run_dict(run: TaskRun) -> dict:
    return {**json.loads(run.state_json), "id": run.id, "task_id": run.task_id,
            "status": run.status, "stage": run.stage, "control": run.control,
            "max_actions": run.max_actions, "timeout_seconds": run.timeout_seconds,
            "reuse_knowledge": run.reuse_knowledge, "created_at": run.created_at,
            "updated_at": run.updated_at, "ended_at": run.ended_at}


def knowledge_dict(row: OperationalKnowledge) -> dict:
    return {**json.loads(row.content_json), "id": row.id, "software": row.software,
            "software_version": row.software_version, "operation": row.operation,
            "run_id": row.run_id, "validated_at": row.validated_at}


def create_task(title: str, request: str, scenario: str, version: str, parent_id: str | None = None) -> dict:
    with session_scope() as db:
        row = TaskRecord(id=new_id("task"), title=title.strip(), request=request.strip(),
                         scenario=scenario, software="Chatwoot", software_version=version,
                         parent_id=parent_id, criteria_json=json.dumps(criteria(scenario)), created_at=timestamp())
        db.add(row)
        db.commit()
        return {**task_dict(row), "runs": [], "latest_run": None}


def list_tasks() -> list[dict]:
    with session_scope() as db:
        tasks = db.query(TaskRecord).order_by(TaskRecord.created_at.desc(), TaskRecord.id).all()
        runs = db.query(TaskRun).order_by(TaskRun.created_at.desc(), TaskRun.id).all()
        latest: dict = {}
        for run in runs:
            if run.task_id not in latest:
                latest[run.task_id] = run_dict(run)
        return [{**task_dict(task), "latest_run": latest.get(task.id)} for task in tasks]


def get_task(task_id: str) -> dict | None:
    with session_scope() as db:
        task = db.get(TaskRecord, task_id)
        if not task:
            return None
        runs = [run_dict(row) for row in db.query(TaskRun).filter_by(task_id=task_id)
                .order_by(TaskRun.created_at.desc(), TaskRun.id).all()]
        return {**task_dict(task), "runs": runs, "latest_run": runs[0] if runs else None}


def new_run(task_id: str, max_actions: int, timeout_seconds: int, reuse_knowledge: bool) -> dict:
    with session_scope() as db:
        # Serialize competing start requests across threads/processes sharing the SQLite database.
        db.execute(text("BEGIN IMMEDIATE"))
        task = db.get(TaskRecord, task_id)
        if task is None:
            raise LookupError("Task not found")
        active = db.query(TaskRun).filter(TaskRun.status.notin_(TERMINAL)).first()
        if active:
            raise ValueError("Another run owns the test environment. Stop it before starting a new run.")
        now = timestamp()
        state = {"activities": [], "actions": [], "sources": [], "verifications": [],
                 "knowledge_refs": [], "stages": {stage: "pending" for stage in STAGES},
                 "summary": "Waiting for environment checks.", "blockers": [], "plan": []}
        row = TaskRun(id=new_id("run"), task_id=task_id, status="created", stage="understand",
                      control="run", max_actions=max_actions, timeout_seconds=timeout_seconds,
                      reuse_knowledge=reuse_knowledge, state_json=json.dumps(state),
                      created_at=now, updated_at=now)
        db.add(row)
        db.commit()
        return run_dict(row)


def get_run(run_id: str) -> dict | None:
    with session_scope() as db:
        row = db.get(TaskRun, run_id)
        return run_dict(row) if row else None


def update_run(run_id: str, *, status: str | None = None, stage: str | None = None, **state) -> dict:
    with session_scope() as db:
        row = db.get(TaskRun, run_id)
        if row is None:
            raise LookupError("Run not found")
        payload = json.loads(row.state_json)
        payload.update(state)
        row.state_json = json.dumps(payload)
        if status:
            row.status = status
            if status in TERMINAL:
                row.ended_at = utcnow()
        if stage:
            row.stage = stage
        row.updated_at = utcnow()
        db.commit()
        return run_dict(row)


def log(run_id: str, stage: str, message: str, kind: str = "observation", **extra) -> None:
    run = get_run(run_id)
    activities = run["activities"]
    activities.append({"id": new_id("event"), "stage": stage, "message": message[:1000],
                       "kind": kind, "timestamp": utcnow(), **extra})
    update_run(run_id, activities=activities)


def control_run(run_id: str, control: str) -> dict:
    with session_scope() as db:
        row = db.get(TaskRun, run_id)
        if row is None:
            raise LookupError("Run not found")
        if row.status in TERMINAL:
            raise ValueError("This run has ended. Start a new run to retry.")
        row.control = {"pause": "pause", "resume": "run", "stop": "stop"}[control]
        row.updated_at = utcnow()
        db.commit()
        return run_dict(row)


def recover_interrupted_runs() -> None:
    with session_scope() as db:
        ids = [row.id for row in db.query(TaskRun).filter(TaskRun.status.notin_(TERMINAL)).all()]
    for run_id in ids:
        update_run(run_id, status="blocked", summary="The API restarted during this run. Start a new run to recover.",
                   blockers=["Execution was interrupted by a server restart. Evidence has been preserved."])


def list_knowledge(version: str | None = None) -> list[dict]:
    with session_scope() as db:
        query = db.query(OperationalKnowledge).order_by(OperationalKnowledge.validated_at.desc())
        if version is not None:
            query = query.filter_by(software="Chatwoot", software_version=version)
        return [knowledge_dict(row) for row in query.all()]


def save_knowledge(run_id: str, version: str, content: dict) -> dict:
    run = get_run(run_id)
    checks = run["verifications"]
    task = get_task(run["task_id"])
    required_ids = {row["id"] for row in task["criteria"]}
    if (len(checks) != len(required_ids) or {row.get("id") for row in checks} != required_ids
            or not all(row["status"] == "passed" for row in checks)
            or not run.get("configuration_changed")
            or not any(row.get("outcome") == "executed" and row.get("kind") in {"click", "type", "select"} for row in run["actions"])):
        raise ValueError("Operational knowledge can only be saved after independent verification passes.")
    for key in ("preconditions", "procedure", "completion_check", "unresolved", "permissions", "source_refs", "related_runs"):
        value = content.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"Knowledge must contain a structured {key} list.")
        content[key] = [item[:2000] for item in value[:50]]
    if not content["procedure"] or not content["completion_check"] or not content["permissions"]:
        raise ValueError("Knowledge needs a procedure, completion check and required permissions.")
    with session_scope() as db:
        row = OperationalKnowledge(id=new_id("knowledge"), software="Chatwoot", software_version=version,
                                   operation="Configure conversation routing and priority", run_id=run_id,
                                   content_json=json.dumps(content), validated_at=utcnow())
        db.add(row)
        db.commit()
        return knowledge_dict(row)
