"""Continuation must append evidence, not restart research or replay coordinates."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from PIL import Image
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import main
from app.engines import visual
from app.models import Base, Project
from app.util import utcnow


def test_resume_keeps_history_skips_successes_and_retries_misses(tmp_path, monkeypatch):
    previous = [
        dict(step=1, image="step_01.png", action="click", text="File", executed=True, learned="Opened File."),
        dict(step=2, image="step_02.png", action="click", text="Edit", executed=True, learned="Missed: no visible change."),
    ]
    (tmp_path / "trace.json").write_text(json.dumps(previous))
    Image.new("RGB", (10, 10), "red").save(tmp_path / "step_09.png")
    original_image = (tmp_path / "step_09.png").read_bytes()
    inventory = [dict(label="File", role="opener", documented=False, requires_click=True, first_seen=1),
                 dict(label="Edit", role="opener", documented=False, requires_click=True, first_seen=1),
                 dict(label="Hidden", role="opener", documented=False, requires_click=True, first_seen=1),
                 dict(label="Written", role="opener", documented=True, requires_click=False, first_seen=1)]
    (tmp_path / "control_inventory.json").write_text(json.dumps(inventory))
    (tmp_path / "source_relevance.json").write_text(json.dumps({"checked": True, "sources": [{"id": "source_a", "relevant": True}]}))
    calls = []
    class Driver:
        def focus(self, name): return visual.WindowBounds(0, 0, 1001, 1001)
        def bounds(self, name): return self.focus(name)
        def key(self, name): pass
        def capture(self, bounds, path):
            Image.new("RGB", (1001, 1001), "white").save(path)
            return path, 1001, 1001
        def click(self, x, y): calls.append((x, y))
        def scroll(self, *args): pass
    class Reasoner:
        model = "test"
        async def list_controls(self, **kwargs):
            assert "file" in kwargs["already"]
            assert "Written instructions" in kwargs["covered"]
            return [dict(label=label, role="opener", documented=label == "Written", cell=1, x=x, y=100)
                    for label, x in [("File", 100), ("Edit", 400), ("Written", 900)]], "none"
        async def describe_click(self, **kwargs): return "Opened Edit."
    monkeypatch.setattr(visual.time, "sleep", lambda _: None)
    monkeypatch.setattr(visual, "_remember", lambda *args: None)
    store = SimpleNamespace(log=lambda *args: None, add_evidence=lambda *args, **kwargs: None)
    trace = asyncio.run(visual.explore_visually(store, SimpleNamespace(id="p", software_name="Test", learning_objective="learn"),
                       Reasoner(), tmp_path, driver=Driver(), documents="[source_a] Written instructions", resume=True))
    assert trace[:len(previous)] == previous
    assert calls == [(400, 100)], "Only the unconfirmed control is clicked at fresh coordinates"
    assert (tmp_path / "step_09.png").read_bytes() == original_image
    assert min(frame["step"] for frame in trace[len(previous):]) >= 10
    coverage = json.loads((tmp_path / "coverage.json").read_text())
    assert coverage["pending"] == ["Hidden"]
    assert coverage["missed"] == []
    assert any(frame.get("action") == "resume" for frame in trace)


def test_resume_revisits_navigation_to_reach_unfinished_controls(tmp_path, monkeypatch):
    (tmp_path / "trace.json").write_text(json.dumps([
        dict(step=1, action="click", text="Layout", executed=True, learned="Switched to Layout."),
        dict(step=2, action="click", text="File", executed=True, learned="Opened File."),
    ]))
    (tmp_path / "control_inventory.json").write_text(json.dumps([
        dict(label="Layout", role="navigation", documented=False, requires_click=True, first_seen=1),
        dict(label="Hidden menu", role="opener", documented=False, requires_click=True, first_seen=1),
    ]))
    class Driver:
        view = "Other"
        clicked = []
        def focus(self, name): return visual.WindowBounds(0, 0, 1001, 1001)
        def bounds(self, name): return self.focus(name)
        def key(self, name): pass
        def capture(self, bounds, path):
            Image.new("RGB", (1001, 1001), "white").save(path)
            return path, 1001, 1001
        def click(self, x, y):
            self.clicked.append(x)
            if x == 400: self.view = "Layout"
        def scroll(self, *args): pass
    driver = Driver()
    class Reasoner:
        model = "test"
        async def list_controls(self, **kwargs):
            if kwargs.get("pending"):
                return [dict(label="Layout", role="navigation", documented=False, cell=1, x=400, y=100)], "none"
            if driver.view == "Layout":
                return [dict(label="Hidden menu", role="opener", documented=False, cell=1, x=600, y=100)], "none"
            return [dict(label="File", role="opener", documented=False, cell=1, x=100, y=100)], "none"
        async def describe_click(self, **kwargs): return "Opened the selected interface."
    monkeypatch.setattr(visual.time, "sleep", lambda _: None)
    monkeypatch.setattr(visual, "_remember", lambda *args: None)
    store = SimpleNamespace(log=lambda *args: None, add_evidence=lambda *args, **kwargs: None)
    asyncio.run(visual.explore_visually(store, SimpleNamespace(id="p", software_name="Test", learning_objective="learn"),
                Reasoner(), tmp_path, driver=driver, resume=True))
    assert driver.clicked == [400, 600]
    assert json.loads((tmp_path / "coverage.json").read_text())["pending"] == []


def test_continuation_keeps_old_gaps_until_new_coverage_is_saved():
    from app.engines.outcome import build_outcome
    base = dict(software_name="Test", objective="learn", capabilities=[], claims=[], source_count=1)
    history = [dict(action="wait", thought="Coverage incomplete: Old menu"), dict(action="resume")]
    outcome = build_outcome(**base, frames=history)
    assert "Coverage incomplete: Old menu" in outcome["evaluation"]["gaps"]
    outcome = build_outcome(**base, frames=history + [dict(action="coverage", thought="Coverage incomplete: New menu")])
    assert "Coverage incomplete: Old menu" not in outcome["evaluation"]["gaps"]
    assert "Coverage incomplete: New menu" in outcome["evaluation"]["gaps"]


def test_frame_names_continue_beyond_two_digits(resume_api):
    _, _, folder = resume_api
    path = folder / "step_100.png"
    path.write_bytes(b"test")
    assert str(main.project_frame("p", "step_100.png").path) == str(path)
    with pytest.raises(HTTPException):
        main.project_frame("p", "../step_100.png")


def test_resume_orchestrator_does_not_repeat_research_or_checks(resume_api, tmp_path, monkeypatch):
    from app import orchestrator
    db, project, _ = resume_api
    monkeypatch.setattr(orchestrator, "session_scope", main.session_scope)
    monkeypatch.setattr(orchestrator, "get_settings", lambda: SimpleNamespace(
        artifacts_dir=tmp_path, hcompany_api_key="test", hcompany_base_url="https://example.invalid", hcompany_model="test"))  # pragma: allowlist secret -- synthetic fixture
    calls = []
    async def fail_if_called(*args, **kwargs): raise AssertionError("Continuation must not restart research or bpy")
    async def explore(store, row, reasoner, folder, **kwargs):
        assert row.id == project.id
        assert kwargs["resume"] is True
        calls.append("explore")
        return []
    monkeypatch.setattr(orchestrator, "collect_sources", fail_if_called)
    monkeypatch.setattr(orchestrator, "understand", fail_if_called)
    monkeypatch.setattr(orchestrator, "explore_and_experiment", fail_if_called)
    monkeypatch.setattr(orchestrator, "explore_visually", explore)
    monkeypatch.setattr(orchestrator, "export_package", lambda *args: str(tmp_path / "continued.zip"))
    asyncio.run(orchestrator.resume_session("p"))
    assert calls == ["explore"]
    assert project.status == "completed"
    assert project.package_path.endswith("continued.zip")


@pytest.fixture
def resume_api(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    now = utcnow()
    project = Project(id="p", software_name="Test", learning_objective="learn", status="completed", created_at=now, updated_at=now)
    db.add(project)
    db.commit()
    from contextlib import contextmanager
    @contextmanager
    def scope(): yield db
    monkeypatch.setattr(main, "session_scope", scope)
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(artifacts_dir=tmp_path))
    folder = tmp_path / "p" / "explore"
    folder.mkdir(parents=True)
    (folder / "trace.json").write_text('[{"step":1,"action":"wait"}]')
    yield db, project, folder
    db.close()
    engine.dispose()


def test_resume_api_reserves_same_project_and_rejects_double_start(resume_api):
    db, project, _ = resume_api
    background = BackgroundTasks()
    response = main.resume_project("p", background)
    assert response["id"] == "p"
    assert response["status"] == "resuming"
    assert len(background.tasks) == 1
    assert background.tasks[0].func is main.resume_session
    assert background.tasks[0].args == ("p",)
    with pytest.raises(HTTPException) as error:
        main.resume_project("p", BackgroundTasks())
    assert error.value.status_code == 409
    assert db.query(Project).count() == 1


def test_resume_api_rejects_missing_checkpoint_and_other_active_session(resume_api):
    db, project, folder = resume_api
    other = Project(id="other", software_name="Test", learning_objective="learn", status="exploring", created_at=utcnow(), updated_at=utcnow())
    db.add(other)
    db.commit()
    with pytest.raises(HTTPException) as error:
        main.resume_project("p", BackgroundTasks())
    assert error.value.status_code == 409
    other.status = "completed"
    db.commit()
    (folder / "trace.json").unlink()
    with pytest.raises(HTTPException) as error:
        main.resume_project("p", BackgroundTasks())
    assert error.value.status_code == 409
    assert project.status == "completed"
