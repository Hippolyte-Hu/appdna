"""A URL is a browser target, never an AppleScript application name."""
import pytest
from pydantic import ValidationError
from app.schemas import ProjectCreate

OBJECTIVE = "Review the main controls for a procurement evaluation"

def test_name_remains_compatible():
    body = ProjectCreate(software_name="  Blender  ", learning_objective=OBJECTIVE)
    assert body.software_name == "Blender"
    assert body.target_url is None

def test_url_preserves_exact_account_page_but_names_product():
    url = "https://www.canva.com/settings/your-account?tab=profile"
    body = ProjectCreate(software_name=url, learning_objective=OBJECTIVE)
    assert body.software_name == "Canva"
    assert body.target_url == url

@pytest.mark.parametrize("value", ["file:///etc/passwd", "javascript:alert(1)", "ftp://example.com", "https://user:secret@example.com", "https://169.254.169.254/latest/meta-data", "https://10.0.0.1", "https://[::1]", "https://example.com\nattacker", "   "])
def test_rejects_unsafe_target(value):
    with pytest.raises(ValidationError):
        ProjectCreate(software_name=value, learning_objective=OBJECTIVE)

def test_driver_factory_uses_browser_for_url_only(monkeypatch):
    from types import SimpleNamespace
    from app.engines import visual
    monkeypatch.setattr(visual, "BrowserDriver", lambda url: ("browser", url))
    monkeypatch.setattr(visual, "MacOSDriver", lambda: "desktop")
    assert visual.make_driver(SimpleNamespace(target_url="https://www.canva.com/settings/")) == ("browser", "https://www.canva.com/settings/")
    assert visual.make_driver(SimpleNamespace(target_url=None)) == "desktop"


def test_explicit_url_with_human_name():
    body = ProjectCreate(software_name="Canva", target_url="https://www.canva.com/settings/", learning_objective=OBJECTIVE)
    assert body.software_name == "Canva"
    assert body.target_url == "https://www.canva.com/settings/"
