"""Regression protection for view-local coverage, not Blender-specific automation."""
import asyncio
import json
import pytest
from types import SimpleNamespace

from PIL import Image

from app.drivers.macos import WindowBounds
from app.engines import visual
from app.engines.controls import next_control
from app.providers.hcompany import HCompanyProvider


def test_current_view_is_drained_before_navigation():
    controls = [
        dict(label="Other workspace", role="navigation", documented=False),
        dict(label="Local menu", role="opener", documented=False),
    ]
    assert next_control(controls, set())["label"] == "Local menu"


def test_provider_preserves_navigation_role(monkeypatch):
    provider = HCompanyProvider("test-key", "https://example.invalid", "test-model")
    async def look(*args, **kwargs):
        return {"controls": [dict(label="Workspace", role="navigation", documented=False, cell=1, x=100, y=100)], "more": "none"}
    monkeypatch.setattr(provider, "_look", look)
    controls, _ = asyncio.run(provider.list_controls(software="Test", objective="learn", image_bytes=b"", already=[]))
    assert controls[0]["role"] == "navigation"


def test_live_loop_drains_view_before_changing_workspace(tmp_path, monkeypatch):
    class Driver:
        view = "A"
        clicked = []
        def focus(self, name): return WindowBounds(0, 0, 1001, 1001)
        def bounds(self, name): return WindowBounds(0, 0, 1001, 1001)
        def key(self, name): pass
        def capture(self, bounds, path):
            Image.new("RGB", (1001, 1001), "white").save(path)
            return path, 1001, 1001
        def click(self, x, y):
            self.clicked.append((self.view, x))
            if x == 100: self.view = "B"
        def scroll(self, bounds, direction): pass
    driver = Driver()
    class Reasoner:
        model = "test-model"
        async def list_controls(self, **kwargs):
            if driver.view == "B": return [], "none"
            return [dict(label="Workspace B", role="navigation", documented=False, cell=1, x=100, y=100),
                    dict(label="Local menu", role="opener", documented=False, cell=1, x=200, y=100)], "none"
        async def describe_click(self, **kwargs): return "Opened the selected interface."
    monkeypatch.setattr(visual.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(visual, "_remember", lambda *args: None)
    store = SimpleNamespace(log=lambda *args: None, add_evidence=lambda *args, **kwargs: None)
    asyncio.run(visual.explore_visually(store, SimpleNamespace(id="test", software_name="Test", learning_objective="learn"), Reasoner(), tmp_path, driver=driver))
    assert driver.clicked == [("A", 200), ("A", 100)]


@pytest.mark.parametrize("visible", [True, False])
def test_empty_inventory_is_rechecked_against_known_pending_controls(tmp_path, monkeypatch, visible):
    class Driver:
        clicked = []
        def focus(self, name): return WindowBounds(0, 0, 1001, 1001)
        def bounds(self, name): return WindowBounds(0, 0, 1001, 1001)
        def key(self, name): pass
        def capture(self, bounds, path):
            Image.new("RGB", (1001, 1001), "white").save(path)
            return path, 1001, 1001
        def click(self, x, y): self.clicked.append(x)
        def scroll(self, bounds, direction): pass
    driver = Driver()
    prompts = []
    class Reasoner:
        model = "test-model"
        async def list_controls(self, **kwargs):
            prompts.append(kwargs.get("pending", []))
            if not driver.clicked:
                return [dict(label="Alpha", role="opener", documented=False, cell=1, x=100, y=100),
                        dict(label="Beta", role="navigation", documented=False, cell=1, x=200, y=100)], "none"
            if visible and "Beta" in kwargs.get("pending", []):
                # Fresh grounding has moved: never replay the old x=200.
                return [dict(label="Invisible menu", role="opener", documented=False, cell=1, x=900, y=100),
                        dict(label="Beta", role="navigation", documented=False, cell=1, x=400, y=100)], "none"
            return [], "none"
        async def describe_click(self, **kwargs): return "Opened the selected menu."
    monkeypatch.setattr(visual.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(visual, "_remember", lambda *args: None)
    store = SimpleNamespace(log=lambda *args: None, add_evidence=lambda *args, **kwargs: None)
    asyncio.run(visual.explore_visually(store, SimpleNamespace(id="test", software_name="Test", learning_objective="learn"), Reasoner(), tmp_path, driver=driver))
    assert driver.clicked == ([100, 400] if visible else [100])
    assert any("Beta" in prompt for prompt in prompts)
    assert len(prompts) < 10, "Absent controls must not create an infinite retry loop"
    coverage = json.loads((tmp_path / "coverage.json").read_text())
    assert coverage["pending"] == ([] if visible else ["Beta"])
