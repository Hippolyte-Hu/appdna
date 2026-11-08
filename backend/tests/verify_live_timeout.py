"""Manual fault-injection acceptance; real Blender, real GUI events and real H API.

Run only while no other AppDNA project is active:
PYTHONPATH=. .venv/bin/python tests/verify_live_timeout.py SOURCE_PROJECT reading|screen

Injects exactly two request failures at the selected stage. Reuses one saved
article (no invented source), limits GUI exploration to two controls, and saves
an explicitly partial project. This is recovery evidence, NOT coverage proof.
"""
import asyncio
import json
import sys
import urllib.request
from pathlib import Path
from unittest.mock import patch

from app import orchestrator
from app.config import get_settings
from app.db import session_scope
from app.engines import visual
from app.models import KnowledgeSource, Project
from app.providers.base import ProviderError
from app.providers.hcompany import HCompanyProvider
from app.store import Store
from app.util import new_id, utcnow


async def main(source_id, stage):
    assert stage in {"reading", "screen"}
    rows = json.load(urllib.request.urlopen("http://127.0.0.1:8787/api/projects"))
    assert all(p["status"] in {"completed", "failed"} for p in rows), "Another run is using the desktop"
    pid = new_id("project")
    with session_scope() as db:
        db.add(Project(id=pid, software_name="Blender", software_version="5.2", learning_objective="Learn the main controls of this application", status="created", created_at=utcnow(), updated_at=utcnow()))
        db.commit()

    async def saved_article(store, project, provider, folder):
        originals = store.sources(source_id)
        source = next(s for s in originals if "docs.blender.org" in s.url and Path(s.content_reference).is_file())
        store.db.add(KnowledgeSource(id=new_id("source"), project_id=project.id, title=source.title, url=source.url, source_type=source.source_type, software_version=source.software_version, retrieved_at=source.retrieved_at, license=source.license, content_reference=source.content_reference, reliability=source.reliability))
        store.db.commit()
        return 1

    real_post = HCompanyProvider._post
    failures = []
    schema_name = "capability_graph" if stage == "reading" else "document_check"
    async def injected_post(self, body, timeout=120):
        name = body.get("response_format", {}).get("json_schema", {}).get("name")
        if name == schema_name and len(failures) < 2:
            failures.append(name)
            raise ProviderError("H Company took too long to answer [manual fault injection]")
        return await real_post(self, body, timeout)

    print("PROJECT", pid, "STAGE", stage, flush=True)
    with patch.object(orchestrator, "collect_sources", saved_article), patch.object(HCompanyProvider, "_post", injected_post), patch.object(visual, "MAX_CLICKS", 2):
        await orchestrator.run_session(pid)
    result = json.load(urllib.request.urlopen("http://127.0.0.1:8787/api/projects/" + pid))
    clicks = [f for f in result["frames"] if f["action"] == "click" and f["executed"]]
    report = {"project": pid, "fault_injection": True, "stage": stage, "injected_failures": len(failures), "status": result["status"], "clicks": [f["text"] for f in clicks], "verdict": result["outcome"]["evaluation"]["verdict"], "scope": "Recovery only; exploration intentionally limited to two controls"}
    folder = get_settings().artifacts_dir / pid
    (folder / "timeout-acceptance.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
    assert len(failures) == 2
    assert result["status"] == "completed", result.get("error_message")
    assert clicks, "No real interface click survived the injected failures"
    assert report["verdict"] == "Incomplete", "Bounded recovery test must not claim full coverage"


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
