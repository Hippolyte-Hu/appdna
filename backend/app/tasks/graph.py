"""A read-only graph of persisted knowledge and its actual evidence relationships."""

import hashlib
import json
import re
from collections import Counter
from urllib.parse import urlsplit

from app.db import session_scope
from app.models import OperationalKnowledge, TaskRecord, TaskRun
from app.tasks.persistence import knowledge_dict, run_dict, task_dict
from app.util import utcnow


def _key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _public_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not (
            parsed.username or parsed.password or parsed.query)
    except ValueError:
        return False


def assemble_graph(knowledge: list[dict], tasks: list[dict], runs: list[dict]) -> dict:
    entries = [item for item in knowledge if not item.get("superseded_by")]
    tasks_by_id = {item["id"]: item for item in tasks}
    runs_by_id = {item["id"]: item for item in runs}
    nodes, links = {}, {}

    def node(identifier, kind, label, **extra):
        nodes.setdefault(identifier, {"id": identifier, "kind": kind, "label": label, **extra})
        return identifier

    def edge(source, target, relation, **extra):
        identifier = f"{source}|{relation}|{target}"
        links[identifier] = {"id": identifier, "source": source, "target": target, "relation": relation, **extra}

    known_ids = {item["id"] for item in entries}
    included_runs = {item["run_id"] for item in entries}
    included_runs.update(item["id"] for item in runs if known_ids.intersection(item.get("knowledge_refs", [])))
    check_statuses: dict[str, list[str]] = {}

    for run in runs:
        if run["id"] not in included_runs:
            continue
        task = tasks_by_id.get(run["task_id"])
        if not task:
            continue
        checks = run.get("verifications", [])
        passed = sum(item.get("status") == "passed" for item in checks)
        run_id = node(run["id"], "run", f'{passed}/{len(task["criteria"])} · {task["title"]}',
                      status=run["status"], task_id=task["id"], title=task["title"],
                      created_at=run["created_at"], passed=passed, total=len(task["criteria"]),
                      action_count=len(run.get("actions", [])), checks=[],
                      result_url=f'/tasks/{task["id"]}/results?run={run["id"]}')
        observation = run.get("observation", {})
        image = observation.get("image", "")
        if re.fullmatch(r"step_\d{3}\.png", image) and re.fullmatch(r"run_[a-f0-9]{12}", run["id"]):
            nodes[run_id]["image_url"] = f'/api/task-runs/{run["id"]}/evidence/{image}'
        expected_by_id = {item["id"]: item for item in task["criteria"]}
        for result in checks:
            requirement = expected_by_id.get(result.get("id"))
            if not requirement:
                continue
            expected = {"team": requirement["team"], "priority": requirement["priority"]}
            identity = json.dumps([task["software"], task["software_version"], requirement["id"], expected], sort_keys=True)
            check_id = node("check_" + _key(identity), "check", requirement["requirement"],
                            expected=expected, software=task["software"], version=task["software_version"])
            status = result.get("status", "unverified")
            # Exact fixtures, raw target records, tokens and browser state never enter this DTO.
            actual = result.get("actual")
            evidence = {"check_id": check_id, "requirement": requirement["requirement"],
                        "expected": expected, "actual": {key: actual.get(key) for key in ("team", "priority")}
                        if isinstance(actual, dict) else None, "status": status,
                        "checked_at": result.get("checked_at")}
            nodes[run_id]["checks"].append(evidence)
            edge(run_id, check_id, "checked", **{key: value for key, value in evidence.items()
                                                if key not in {"check_id", "requirement"}})
            check_statuses.setdefault(check_id, []).append(status)

    for item in entries:
        run = runs_by_id.get(item["run_id"], {})
        task = tasks_by_id.get(run.get("task_id"), {})
        app_id = node("app_" + _key(item["software"] + ":" + item["software_version"]),
                      "app", item["software"], version=item["software_version"])
        required = {row["id"] for row in task.get("criteria", [])}
        checks = run.get("verifications", [])
        verified = bool(required and len(checks) == len(required)
                        and {row.get("id") for row in checks} == required
                        and all(row.get("status") == "passed" for row in checks))
        skill_id = node(item["id"], "skill", task.get("title") or item["operation"],
                        status="verified" if verified else "unverified", operation=item["operation"],
                        software=item["software"], version=item["software_version"],
                        validated_at=item["validated_at"], step_count=len(item["procedure"]),
                        run_id=item["run_id"], knowledge_id=item["id"])
        edge(app_id, skill_id, "contains")
        if item["run_id"] in nodes:
            edge(skill_id, item["run_id"], "learned_in")
        for url in dict.fromkeys(item["source_refs"]):
            if not _public_url(url):
                continue
            slug = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
            label = re.sub(r"^\d+-?", "", slug).replace("-", " ").strip().capitalize()
            source_id = node("source_" + _key(url), "source", label or urlsplit(url).hostname,
                             url=url)
            edge(skill_id, source_id, "references")
        for candidate in runs:
            if candidate["id"] in nodes and item["id"] in candidate.get("knowledge_refs", []):
                edge(skill_id, candidate["id"], "reused_in")

    for identifier, statuses in check_statuses.items():
        counts = dict(Counter(statuses))
        nodes[identifier]["outcomes"] = counts
        nodes[identifier]["status"] = statuses[0] if len(counts) == 1 else "mixed"
    ordered_nodes = list(nodes.values())
    return {"schema_version": 1, "generated_at": utcnow(), "nodes": ordered_nodes,
            "links": list(links.values()), "counts": dict(Counter(item["kind"] for item in ordered_nodes))}


def knowledge_graph() -> dict:
    with session_scope() as db:
        entries = [knowledge_dict(row) for row in db.query(OperationalKnowledge)
                   .order_by(OperationalKnowledge.validated_at.desc(), OperationalKnowledge.id).all()]
        tasks = [task_dict(row) for row in db.query(TaskRecord).all()]
        runs = [run_dict(row) for row in db.query(TaskRun).order_by(TaskRun.created_at.desc(), TaskRun.id).all()]
    return assemble_graph(entries, tasks, runs)
