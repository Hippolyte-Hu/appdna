"""Read-only/native lock rejection and current rendered preview checks."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from app.drivers.blender_tutorial import BlenderTutorialDriver,guard
ROOT=Path(__file__).resolve().parents[2]
EVIDENCE=ROOT/'tasks/video-agent/evidence'
result={'desktop':guard('lock')}
if result['desktop']['locked']:
    target=EVIDENCE/'native-lock-test'
    try:BlenderTutorialDriver.launch(target)
    except RuntimeError as exc:result['launch_rejected']=str(exc)
    else:raise AssertionError('Blender launched while locked')
    assert not target.exists(),'Launch rejected before creating run folder'
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://192.168.1.59:8788',wait_until='networkidle')
    page.locator('.job').filter(has_text='ready for review').first.click()
    page.locator('.step').first.wait_for()
    for width,height,label in [(1440,1000,'desktop'),(390,844,'mobile')]:
        page.set_viewport_size({'width':width,'height':height})
        page.screenshot(path=str(EVIDENCE/f'video-workspace-{label}.png'),full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
        box=page.locator('#topstop').bounding_box();assert box and 0<=box['y']<height
        assert page.locator('#runhint').inner_text() if result['desktop']['locked'] else True
        page.evaluate('window.scrollTo(0,0)')
    assert not errors,errors
    result['browser_errors']=errors
    result['sticky_stop_on_mobile']=True
    browser.close()
(EVIDENCE/'guard-and-layout-acceptance.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
