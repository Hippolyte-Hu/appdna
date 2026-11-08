"""Upload the actual English-checked recording through the real AppDNA form."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[2]
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':1000}, locale='en-US')
    errors=[]
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:3000', wait_until='networkidle')
    page.get_by_label('Application name or website URL').fill('VoiceCue')
    page.get_by_label('Version (optional)').fill('English-localized browser demo build')
    page.get_by_label('Assessment objective').fill('Procurement and pre-UAT review of the English-localized VoiceCue demo build. Learn the editor, script library, recognition settings and prompting workflow from the authorized recording. Separate narration claims, recorded observations and genuine live actions. Keep untested workflows explicit; do not treat a recording as independent verification.')
    page.locator('summary').click()
    page.get_by_label('Or upload a recording').set_input_files(str(ROOT/'deliverables/VoiceCue-demo.mp4'))
    page.get_by_role('button',name='Start assessment').click()
    page.wait_for_url('**/projects/project_*',timeout=60000)
    project_id=page.url.rsplit('/',1)[-1]
    page.screenshot(path=str(ROOT/'tasks/overnight/evidence/voicecue-upload-started.png'),full_page=True)
    result={'project_id':project_id,'url':page.url,'uploaded_file':'deliverables/VoiceCue-demo.mp4','page_errors':errors}
    (ROOT/'tasks/overnight/evidence/voicecue-upload.json').write_text(json.dumps(result,indent=2))
    browser.close()
    assert not errors, errors
    print(json.dumps(result))
