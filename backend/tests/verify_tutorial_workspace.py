"""Real browser acceptance against isolated LAN preview; no model/ASR stubs."""
import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
BASE='http://192.168.1.59:8788'
EVIDENCE=ROOT/'tasks/video-agent/evidence'
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(BASE,wait_until='networkidle')
    page.locator('.job').filter(has_text='ready for review').first.click()
    page.locator('.step').first.wait_for()
    assert page.locator('.step').count()>0
    page.wait_for_function('document.querySelector("video").readyState>0')
    page.locator('.step').last.click()
    assert page.locator('video').evaluate('(v)=>v.currentTime')>0
    locked=page.request.get(BASE+'/api/desktop').json()['locked']
    page.get_by_label('I reviewed the steps',exact=False).check()
    if locked:assert page.get_by_role('button',name='3. Run in Blender',exact=True).is_disabled()
    page.screenshot(path=str(EVIDENCE/'video-workspace-desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    page.screenshot(path=str(EVIDENCE/'video-workspace-mobile.png'),full_page=True)
    page.set_viewport_size({'width':1440,'height':1000})
    # Submit the real downloaded video through the actual upload form.
    youtube='--youtube' in sys.argv
    if youtube:page.locator('#url').fill('https://www.youtube.com/watch?v=l12k19-imCY')
    else:page.locator('#file').set_input_files(EVIDENCE/'tutorial.mp4')
    with page.expect_response(lambda r:r.url.endswith('/api/tutorials') and r.request.method=='POST') as response:
        page.get_by_role('button',name='Learn from video',exact=True).click()
    created=response.value.json();assert response.value.ok,created
    job_id=created['id']
    start=time.monotonic();job={}
    while time.monotonic()-start<240:
        job=page.request.get(BASE+'/api/tutorials/'+job_id).json()
        if job['status'] in {'ready_for_review','blocked'}:break
        page.wait_for_timeout(1500)
    assert job['status']=='ready_for_review', {k:job.get(k) for k in ('id','status','error')}
    assert len(job['plan']['steps'])>0 and len(job['transcript'])>0
    result={'base':BASE,'input':'youtube' if youtube else 'upload','job':job_id,'real_transcript_segments':len(job['transcript']),
        'real_plan_steps':len(job['plan']['steps']),'source_seek':True,'mobile_overflow':False,
        'locked_execution_blocked':locked,'page_errors':errors}
    assert not errors,errors
    (EVIDENCE/('browser-acceptance-youtube.json' if youtube else 'browser-acceptance-upload.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
    browser.close()
