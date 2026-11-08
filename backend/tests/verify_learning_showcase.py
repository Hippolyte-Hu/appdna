"""Real AppDNA navigation/read/export acceptance. No GUI actions are launched.
The denied-run check injects a clearly labelled 409 only at the launch boundary.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument('--base', default='http://127.0.0.1:3000')
args = parser.parse_args()
base = args.base.rstrip('/')
out = Path(__file__).resolve().parents[2] / 'tasks/video-agent/evidence/showcase'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(base, wait_until='networkidle')
    expect(page.get_by_role('link', name='Learning Showcase', exact=True).first).to_be_visible()
    page.get_by_role('link', name='Learning Showcase', exact=True).first.click()
    expect(page.get_by_role('heading', name='Learning Showcase', exact=True)).to_be_visible()
    expect(page.get_by_test_id('learned-step').first).to_be_visible(timeout=30000)
    source = page.get_by_test_id('knowledge-package').get_attribute('data-source-id')
    upstream = page.request.get('http://127.0.0.1:8788/api/tutorials/'+source).json()
    expect(page.get_by_test_id('learned-step')).to_have_count(len(upstream['knowledge']['steps']))
    expect(page.get_by_role('button', name='Run with Agent', exact=True)).to_be_enabled()
    page.get_by_role('button', name='Play step 1').click()
    assert page.locator('video').evaluate('(v)=>v.currentTime') >= upstream['knowledge']['steps'][0]['start']-0.1
    page.get_by_text('How this learning is saved', exact=True).click()
    expect(page.get_by_text('knowledge.json', exact=True)).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role('link', name='Download knowledge JSON').click()
    downloaded = json.loads(Path(download.value.path()).read_text())
    assert downloaded == upstream['knowledge']
    for width in [1440,390,320]:
        page.set_viewport_size({'width':width,'height':900})
        page.evaluate('window.scrollTo(0,0)')
        page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), width
        page.screenshot(path=str(out/f'showcase-{width}.png'),full_page=True)
    page.reload(wait_until='networkidle')
    expect(page.get_by_test_id('learned-step')).to_have_count(len(downloaded['steps']))
    # Exercise creation through the real bridge, but NEVER launch GUI in this regression.
    page.route('**/api/learning/tutorials/*/run', lambda route: route.fulfill(status=409,json={'detail':'Synthetic acceptance check: desktop locked'}))
    page.get_by_role('button', name='Run with Agent', exact=True).click()
    expect(page.get_by_role('alert').filter(has_text='Synthetic acceptance check')).to_be_visible()
    assert 'run=' in page.url
    run_id = page.url.split('run=')[1].split('&')[0]
    receipt = page.request.get(base+'/api/learning/tutorials/'+run_id).json()
    assert receipt['source_job_id']==source and receipt['status']=='ready_for_review'
    assert 'run' not in receipt and 'verification' not in receipt
    page.reload(wait_until='networkidle')
    expect(page.get_by_test_id('execution-receipt')).to_contain_text(run_id)
    # Synthetic RUNNING is isolated to this test browser; no actual GUI job exists.
    synthetic={**receipt,'status':'running','run':{'events':[]}}
    page.route('**/api/learning/tutorials/'+run_id,lambda route:route.fulfill(json=synthetic))
    page.route('**/api/learning/tutorials/'+run_id+'/stop',lambda route:route.fulfill(status=503,json={'detail':'Synthetic stop denial'}))
    page.reload(wait_until='networkidle')
    page.get_by_role('button',name='Stop Agent',exact=True).click()
    expect(page.get_by_role('alert').filter(has_text='Synthetic stop denial')).to_be_visible()
    expect(page.get_by_role('button',name='Run with Agent',exact=True)).to_be_disabled()
    page.unroute('**/api/learning/tutorials/'+run_id+'/stop')
    page.route('**/api/learning/tutorials/'+run_id+'/stop',lambda route:route.fulfill(json={'stop_requested':True}))
    page.get_by_role('button',name='Stop Agent',exact=True).click()
    expect(page.get_by_role('button',name='Stop requested',exact=True)).to_be_visible()
    page.unroute('**/api/learning/tutorials/'+run_id)
    page.unroute('**/api/learning/tutorials/'+run_id+'/stop')
    # Read failure, not "empty". Remove interception to exercise Retry recovery.
    page.route('**/api/learning/video-sources?*',lambda route:route.fulfill(status=503,json={'detail':'Synthetic catalog failure'}))
    page.reload(wait_until='networkidle')
    expect(page.get_by_role('alert').filter(has_text='Synthetic catalog failure')).to_be_visible()
    page.unroute('**/api/learning/video-sources?*')
    page.get_by_role('button',name='Retry',exact=True).first.click()
    expect(page.get_by_test_id('learned-step').first).to_be_visible()
    page.route('**/api/learning/video-sources?*',lambda route:route.fulfill(json={'items':[],'has_more':False}))
    page.reload(wait_until='networkidle')
    expect(page.get_by_text('No checked workflows yet.',exact=True)).to_be_visible()
    assert page.request.get(base+'/api/learning/health').status==404
    assert page.request.post(base+'/api/learning/video-sources/'+source+'/executions',headers={'Origin':'https://untrusted.invalid'}).status==403
    assert not errors,errors
    result={'source_id':source,'steps':len(downloaded['steps']),'download_matches_saved_knowledge':True,
        'widths':[1440,390,320],'page_errors':errors,'denied_run_id':run_id,'gui_started':False}
    (out/'browser-acceptance.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    browser.close()
