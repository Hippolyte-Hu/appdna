"""Opt-in REAL showcase launch check. May open Blender; never unlocks the Mac.
A locked Mac is recorded as an expected denial, not a successful GUI launch.
"""
import argparse
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser=argparse.ArgumentParser()
parser.add_argument('--base',default='http://127.0.0.1:3000')
args=parser.parse_args()
base=args.base.rstrip('/')
out=Path(__file__).resolve().parents[2]/'tasks/video-agent/evidence/showcase'
out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.goto(base+'/learning',wait_until='networkidle')
    expect(page.get_by_test_id('learned-step').first).to_be_visible()
    source=page.get_by_test_id('knowledge-package').get_attribute('data-source-id')
    original=page.request.get(base+'/api/learning/video-sources/'+source).json()
    desktop=page.request.get(base+'/api/learning/desktop').json()
    with page.expect_response(lambda r:r.url.endswith('/run') and r.request.method=='POST',timeout=30000) as response:
        page.get_by_role('button',name='Run with Agent',exact=True).click()
    status=response.value.status
    run_id=page.url.split('run=')[1].split('&')[0]
    result={'source_id':source,'run_id':run_id,'launch_http_status':status,'desktop_locked':desktop['locked'],'gui_started':False}
    if desktop['locked']:
        assert status==409,response.value.text()
        expect(page.get_by_role('alert').filter(has_text='Mac is locked')).to_be_visible()
        result['blocked_reason']=response.value.json()['detail']
    else:
        assert status==200,response.value.text()
        receipt=page.request.get(base+'/api/learning/tutorials/'+run_id).json()
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            receipt=page.request.get(base+'/api/learning/tutorials/'+run_id).json()
            if receipt.get('run',{}).get('events'):break
            if receipt['status'] not in ['starting_blender','checking_artifact_targets','running','saving_artifact']:break
            time.sleep(2)
        result['recorded_events']=len(receipt.get('run',{}).get('events',[]))
        result['gui_started']=bool(result['recorded_events'])
        if receipt['status'] in ['starting_blender','checking_artifact_targets','running','saving_artifact']:
            page.get_by_role('button',name='Stop Agent',exact=True).click()
            expect(page.get_by_role('button',name='Stop requested',exact=True)).to_be_visible()
            result['stop_requested']=True
    receipt=page.request.get(base+'/api/learning/tutorials/'+run_id).json()
    assert receipt['source_job_id']==source
    assert page.request.get(base+'/api/learning/video-sources/'+source).json()==original
    if desktop['locked']:
        assert receipt['status']=='ready_for_review' and 'run' not in receipt
    result['readback_status']=receipt['status']
    result['source_knowledge_unchanged']=True
    page.screenshot(path=str(out/'real-launch.png'),full_page=True)
    (out/'real-launch.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    browser.close()
