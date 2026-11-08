"""Fault injection: two failed document requests must not prevent live exploration."""
import asyncio
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import orchestrator
from app.models import Base, KnowledgeSource, Project
from app.providers.base import ProviderError
from app.providers.hcompany import HCompanyProvider
from app.store import Store
from app.util import utcnow


@pytest.mark.parametrize("stage", ["reading", "screen_comparison"])
def test_two_timeouts_continue_to_interface(tmp_path, monkeypatch, stage):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(Project(id="timeout_project", software_name="TestApp", learning_objective="Learn controls", status="created", created_at=utcnow(), updated_at=utcnow()))
        db.commit()

    @contextmanager
    def session_scope():
        with Session() as db:
            yield db
    monkeypatch.setattr(orchestrator, "session_scope", session_scope)
    monkeypatch.setattr(orchestrator, "get_settings", lambda: type("Settings", (), dict(
        linkup_api_key="test", linkup_base_url="https://example.invalid", gladia_api_key="test", gladia_base_url="https://example.invalid",  # pragma: allowlist secret -- synthetic fixtures
        hcompany_api_key="test", hcompany_base_url="https://example.invalid", hcompany_model="test", blender_bin="/missing/blender", artifacts_dir=tmp_path))())  # pragma: allowlist secret -- synthetic fixture
    async def collect(store, project, provider, folder):
        folder.mkdir(parents=True)
        content = folder / "article.txt"
        content.write_text("TestApp documentation for this synthetic regression.")
        store.db.add(KnowledgeSource(id="source_timeout", project_id=project.id, title="TestApp", url="https://example.invalid", source_type="official_documentation", content_reference=str(content), reliability="high", retrieved_at=utcnow()))
        store.db.commit()
        return 1
    monkeypatch.setattr(orchestrator, "collect_sources", collect)
    calls = []
    async def post(self, body, timeout=120):
        calls.append(body)
        raise ProviderError("H Company took too long to answer [injected]")
    monkeypatch.setattr(HCompanyProvider, "_post", post)
    seen = []
    async def explore(store, project, provider, folder, **kwargs):
        # Reading times out through the real provider retry path before this entrypoint.
        seen.append(project.software_name)
        if stage == "screen_comparison":
            from app.engines.visual import _documents_match_screen
            from PIL import Image
            folder.mkdir(parents=True)
            image = folder / "synthetic.png"
            Image.new("RGB", (100, 100), "white").save(image)
            covered = await _documents_match_screen(store, project, provider, kwargs["documents"], kwargs["source_ids"], folder, image, 100, 100, [])
            assert covered == ""
        return [{"action": "click", "executed": True, "text": "Test control"}]
    monkeypatch.setattr(orchestrator, "explore_visually", explore)
    async def no_audio(*args): return []
    monkeypatch.setattr(orchestrator, "_transcribe", no_audio)
    monkeypatch.setattr(orchestrator, "export_package", lambda *args: str(tmp_path / "synthetic.zip"))
    asyncio.run(orchestrator.run_session("timeout_project"))
    assert seen == ["TestApp"]
    assert len(calls) == (4 if stage == "screen_comparison" else 2)
    with Session() as db:
        project = Store(db).project("timeout_project")
        assert project.status == "completed"
        assert not project.error_message
