from pathlib import Path
from PIL import Image
import pytest
from app.drivers.browser import BrowserDriver
from app.drivers.macos import VisualExploreError


def test_website_driver_captures_real_page_and_closes(tmp_path):
    # Real browser acceptance. Public example.com contains no account data.
    driver = BrowserDriver("https://example.com")
    try:
        bounds = driver.focus("Example")
        assert bounds.width == 1440
        path, width, height = driver.capture(bounds, tmp_path / "page.png")
        assert (width, height) == (1440, 900)
        assert Image.open(path).getbbox()
        assert driver.page_info()["url"].startswith("https://example.com")
        driver.key("escape")
        driver.scroll(bounds, "down")
    finally:
        driver.close()
    assert driver.process.poll() is not None


def test_browser_rejects_private_target_before_launch():
    with pytest.raises(ValueError):
        BrowserDriver("http://169.254.169.254/")
