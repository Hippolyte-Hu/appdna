"""Exercise the real form and live API; do not mock a learning run."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parents[2] / "tasks/overnight/evidence"
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:3000")
    page.get_by_label("Application name or website URL").fill("https://example.com")
    page.get_by_label("Assessment objective").fill("Observe this public example page and evaluate whether its visible navigation is testable. Keep limitations visible.")
    page.screenshot(path=str(out / "url-input.png"))
    with page.expect_response(lambda response: response.url.endswith("/api/projects") and response.request.method == "POST") as created:
        page.get_by_role("button", name="Start assessment").click()
    response = created.value
    assert response.status == 201, response.text()
    project = response.json()
    assert project["target_url"] == "https://example.com"
    assert project["target_kind"] == "website"
    assert project["software_name"] == "Example"
    page.wait_for_url(f"**/projects/{project['id']}")
    assert not errors, errors
    (out / "url-project.json").write_text(json.dumps(project, indent=2))
    print(json.dumps({"form_submit": True, "project_id": project["id"], "target_url": project["target_url"], "page_errors": errors}))
    browser.close()
