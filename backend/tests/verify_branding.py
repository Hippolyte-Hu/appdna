"""Read-only browser acceptance for the Motion2Action display name."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for route in ("/", "/learning"):
            response = page.goto("http://127.0.0.1:3000" + route)
            assert response.status == 200
            expect(page).to_have_title("Motion2Action")
            expect(page.get_by_role("link", name="Motion2Action workspace")).to_be_visible()
            assert not re.search("appdna", page.locator("body").inner_text(), re.I)
        page.set_viewport_size({"width": 390, "height": 844})
        expect(page.get_by_role("link", name="Motion2Action workspace")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        output = Path(__file__).resolve().parents[2] / "tasks/video-agent/evidence/showcase/motion2action-branding.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output))
        assert not errors, errors
        browser.close()
        print("PASS: Motion2Action title and brand on home/learning; mobile layout; no page errors")


if __name__ == "__main__":
    main()
