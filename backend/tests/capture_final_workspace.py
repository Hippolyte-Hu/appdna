from pathlib import Path
import json
from playwright.sync_api import sync_playwright
r=Path(__file__).resolve().parents[2]
with sync_playwright() as p:
 b=p.chromium.launch()
 page=b.new_page(viewport={"width":1440,"height":1000}, device_scale_factor=1)
 page.goto("http://127.0.0.1:3000");page.wait_for_selector("button[type=submit]");page.screenshot(path=str(r/"tasks/overnight/evidence/workspace-home-viewport.png"))
 page.goto("http://127.0.0.1:3000/projects/project_934cb111315a");page.get_by_role("heading",name="Stopped",exact=True).wait_for();page.screenshot(path=str(r/"tasks/overnight/evidence/workspace-project-viewport.png"))
 page.locator(".graph-canvas").scroll_into_view_if_needed();page.locator(".graph-canvas").screenshot(path=str(r/"tasks/overnight/evidence/workspace-graph-native.png"))
 page.goto("http://127.0.0.1:3000/projects/project_c8ea41f2c86e");page.get_by_role("heading",name="Stopped",exact=True).wait_for();page.locator("video").wait_for();page.locator("video").evaluate("v=>{v.currentTime=30;v.pause()}");page.wait_for_timeout(300)
 links=page.locator('a[href="http://127.0.0.1:8787/api/projects/project_c8ea41f2c86e/media/original"]').count();assert links>=1
 page.screenshot(path=str(r/"tasks/overnight/evidence/voicecue-project-ui.png"),full_page=True)
 page.goto("http://127.0.0.1:8787/api/projects/project_c8ea41f2c86e/report");assert "Evidence verdict: Incomplete" in page.inner_text("body");page.pdf(path=str(r/"deliverables/VoiceCue-assessment.pdf"),format="A4",print_background=True)
 print(json.dumps({"same_origin_media_link":links,"voicecue_printed":True}))
 b.close()
