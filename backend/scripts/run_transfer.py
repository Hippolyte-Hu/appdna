"""Run the production orchestrator with an isolated synthetic sandbox connection."""

import argparse
import asyncio
import json
import os
import runpy
import sys
from pathlib import Path

from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def configure_profile(folder: Path):
    env = dotenv_values(folder / ".env")
    connection = json.loads((folder / "connection.json").read_text())
    os.environ.update({
        "CHATWOOT_BASE_URL": env["FRONTEND_URL"],
        "CHATWOOT_ACCOUNT_ID": str(connection["account_id"]),
        "CHATWOOT_INBOX_ID": str(connection["inbox_id"]),
        "CHATWOOT_API_TOKEN": connection["api_token"],
        "CHATWOOT_STORAGE_STATE": f"data/sessions/{folder.name}.json",
        "CHATWOOT_TEST_ENVIRONMENT": "true",
    })


async def run(args):
    # Import after profile selection. No shared .env edits or API restarts.
    from app.config import get_settings
    from app.db import init_db
    from app.tasks import persistence as store
    from app.tasks.catalog import BASE_REQUEST, VIP_REQUEST
    from app.tasks.runner import applicable_knowledge, execute_run
    from app.tasks.verification import ChatwootVerifier
    from app.util import utcnow

    settings = get_settings()
    init_db()  # Never recover/restart another API process's active run.
    requested = None if args.no_reuse else args.knowledge_ids
    if not args.no_reuse and not requested:
        raise SystemExit("Freeze the source skills with --knowledge-ids, or use --no-reuse for the cold control.")
    selected = applicable_knowledge({"reuse_knowledge": not args.no_reuse, "requested_knowledge_ids": requested},
                                    settings.chatwoot_version)
    if args.retry_task:
        task = store.get_task(args.retry_task)
        if not task:
            raise SystemExit("Retry task does not exist.")
        if not any(previous.get("experiment", {}).get("profile") == args.profile.name
                   and previous.get("environment", {}).get("url") == settings.chatwoot_base_url
                   for previous in task.get("runs", [])):
            raise SystemExit("The retry task belongs to a different sandbox profile. No run was started.")
    else:
        verifier = ChatwootVerifier(settings.chatwoot_base_url, settings.chatwoot_account_id,
                                   settings.chatwoot_inbox_id, settings.chatwoot_api_token)
        try:
            await verifier.preflight()
            rules = await verifier.configuration_snapshot()
            if rules:
                raise SystemExit("Fresh transfer/control runs require zero automation rules. No rules were changed.")
        finally:
            await verifier.close()
        role = "Cold control" if args.no_reuse else "Saved skill transfer"
        task = store.create_task(role + " · fresh installation", BASE_REQUEST + "\n\nAdditional requirement: " + VIP_REQUEST,
                                 "vip", settings.chatwoot_version)

    for _ in range(300):
        try:
            started = store.new_run(task["id"], args.max_actions, args.timeout_seconds, not args.no_reuse, requested)
            break
        except ValueError:
            await asyncio.sleep(2)
    else:
        raise SystemExit("The shared sandbox execution slot remained busy. No run was started.")
    store.update_run(started["id"], experiment={
        "role": "cold" if args.no_reuse else "reuse", "profile": args.profile.name,
        "fresh_start": not bool(args.retry_task), "initial_rule_count": 0 if not args.retry_task else None,
        "checked_at": utcnow(), "frozen_source_skills": [entry["id"] for entry in selected],
        "entry_point": "Production execute_run; profile-scoped connection; shared UI evidence/control API",
    })
    print(json.dumps({"task_id": task["id"], "run_id": started["id"], "url": settings.chatwoot_base_url,
                      "knowledge_ids": [entry["id"] for entry in selected]}), flush=True)
    await execute_run(started["id"])
    final = store.get_run(started["id"])
    print(json.dumps({"run_id": final["id"], "status": final["status"], "actions": len(final["actions"]),
                      "checks": [{"id": row["id"], "status": row["status"], "actual": row.get("actual")}
                                 for row in final["verifications"]], "saved_knowledge_id": final.get("saved_knowledge_id")}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["login", "run"])
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--knowledge-ids", nargs="+", default=None)
    parser.add_argument("--no-reuse", action="store_true")
    parser.add_argument("--retry-task")
    parser.add_argument("--max-actions", type=int, default=150, choices=range(5, 151), metavar="5–150")
    parser.add_argument("--timeout-seconds", type=int, default=1200, choices=range(60, 1201), metavar="60–1200")
    args = parser.parse_args()
    if args.knowledge_ids and (args.no_reuse or len(args.knowledge_ids) > 3
                              or len(args.knowledge_ids) != len(set(args.knowledge_ids))):
        parser.error("Choose up to three distinct source skills, or disable reuse, not both.")
    configure_profile(args.profile)
    if args.mode == "login":
        runpy.run_path(str(BACKEND / "scripts/chatwoot_login.py"), run_name="__main__")
    else:
        asyncio.run(run(args))


if __name__ == "__main__":
    main()
