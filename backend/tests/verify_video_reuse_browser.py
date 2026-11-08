"""Real workbench reuse acceptance; creates a job, but never starts GUI execution."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('source_id');parser.add_argument('--base',default='http://127.0.0.1:8788');args=parser.parse_args()
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(args.base,wait_until='networkidle')
    page.locator('.job[data-id="'+args.source_id+'"]').click()
    page.locator('#reuse').wait_for(state='visible')
    original=page.request.get(args.base+'/api/tutorials/'+args.source_id).json()
    with page.expect_response(lambda r:r.url.endswith('/executions') and r.request.method=='POST') as response:
        page.locator('#reuse').click()
    assert response.value.status==200,response.value.text()
    job=response.value.json();new_id=job['id']
    page.wait_for_function("source=>document.querySelector('#reusehint').textContent.includes('Original source: '+source)",arg=args.source_id)
    assert not page.locator('#approve').is_checked() and page.locator('#run').is_disabled()
    assert not page.locator('#execution').is_visible() and not page.locator('#artifact').is_visible()
    detail=page.request.get(args.base+'/api/tutorials/'+new_id).json()
    assert detail['knowledge']==original['knowledge'] and detail['plan']==original['plan']
    assert detail.get('artifact_targets')==original.get('artifact_targets')
    assert 'run' not in detail and 'verification' not in detail
    assert page.locator('.step').count()==len(detail['knowledge']['steps'])
    page.wait_for_function('document.querySelector("video").readyState>=1')
    sources=page.request.get(args.base+'/api/video-sources?limit=100').json()['items']
    assert args.source_id in [s['id'] for s in sources] and new_id not in [s['id'] for s in sources]
    folder=ROOT/'tasks/video-agent/evidence/jobs'/new_id/'ui';folder.mkdir()
    page.evaluate('window.scrollTo(0,0)');page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    page.screenshot(path=str(folder/'reuse-desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.evaluate('window.scrollTo(0,0)');page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(folder/'reuse-mobile.png'),full_page=True)
    assert not errors,errors
    result={'source_id':args.source_id,'execution_id':new_id,'status':detail['status'],'knowledge_unchanged':True,
        'approval_reset':True,'prior_run_not_copied':True,'mobile_overflow':False,'page_errors':errors,'gui_started':False}
    (folder/'reuse-browser.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    browser.close()
