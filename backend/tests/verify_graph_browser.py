"""Real-browser regression: graph drag/zoom/source reading, no mocked API."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tasks/overnight/evidence"
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:3000/projects/project_934cb111315a")
    page.locator(".react-flow").wait_for(timeout=15000)
    page.locator(".react-flow").scroll_into_view_if_needed()
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / "graph-readable-start.png"), full_page=True)
    nodes = page.locator(".react-flow__node")
    assert nodes.count() > 0
    node = nodes.first
    initial = node.get_attribute("style")
    box = node.bounding_box()
    assert box
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2 + 80, box["y"] + box["height"] / 2 + 45, steps=12)
    page.mouse.up()
    assert node.get_attribute("style") != initial, "Node position must change after actual mouse drag"
    transform = page.locator(".react-flow__viewport").get_attribute("style")
    page.get_by_role("button", name="Zoom in", exact=True).click()
    page.wait_for_timeout(500)
    assert page.locator(".react-flow__viewport").get_attribute("style") != transform
    page.get_by_role("button", name="Fit view", exact=True).click()
    page.wait_for_timeout(500)
    sources = page.locator('.react-flow__node[data-id^="source:"]')
    for source in sources.all():
        source.click(force=True)
        text = page.get_by_test_id("article-content").inner_text()
        assert text.strip(), "Every article keeps readable collected full text"
    page.screenshot(path=str(OUT / "interactive-graph.png"), full_page=True)
    assert not errors, errors
    print(json.dumps({"drag": True, "zoom": True, "articles_read": sources.count(), "nodes": nodes.count(), "page_errors": errors}))
    browser.close()
