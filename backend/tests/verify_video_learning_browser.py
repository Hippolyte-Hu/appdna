"""Browser acceptance against real source-Agent receipts; never stub model/API."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('job_id')
parser.add_argument('--base',default='http://192.168.1.59:8788')
args=parser.parse_args()
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(args.base,wait_until='networkidle')
    page.locator('.job[data-id="'+args.job_id+'"]').click(timeout=5000)
    page.locator('#sourceagent').wait_for(state='visible',timeout=5000)
    job=page.request.get(args.base+'/api/tutorials/'+args.job_id).json()
    assert page.locator('#agenttrace li').count()==len(job['agent']['events'])
    assert job['agent']['model'] in page.locator('#learningstatus').inner_text()
    assert 'not independent artifact verification' in page.locator('#sourceagent').inner_text()
    assert job['knowledge']['verification']=='not_executed'
    if job.get('artifact_targets'):
        assert page.locator('#targetpanel').is_visible()
        assert job['artifact_targets']['scope'] in page.locator('#targets').text_content()
    if job['knowledge']['status']=='source_checked':
        assert page.locator('.step').count()==len(job['knowledge']['steps'])
        with page.expect_download() as event:
            page.locator('#knowledgeDownload').click()
        download=event.value
        data=json.loads(Path(download.path()).read_text())
        assert data['source_sha256']==job['knowledge']['source_sha256']
        page.locator('.step').last.click()
        page.wait_for_function('document.querySelector("video").currentTime>0')
        sources=page.request.get(args.base+'/api/video-sources?q=Bevel').json()['items']
        assert args.job_id in [s['id'] for s in sources]
    else:
        page.locator('#approve').check()
        assert page.locator('#run').is_disabled()
    folder=ROOT/'tasks/video-agent/evidence'
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(folder/'source-agent-desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(folder/'source-agent-mobile.png'),full_page=True)
    assert not errors,errors
    result={'job_id':args.job_id,'knowledge_status':job['knowledge']['status'],
        'actions_displayed':page.locator('#agenttrace li').count(),'page_errors':errors,'mobile_overflow':False,
        'independent_artifact_verification':'not_run'}
    (folder/'source-agent-browser.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    browser.close()
