"""Browser acceptance against real source-Agent receipts; never stub model/API."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('job_id')
parser.add_argument('--base',default='http://127.0.0.1:3000/video')
parser.add_argument('--check-project',action='store_true',help='Import checked knowledge and verify the real project graph/package')
args=parser.parse_args()
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    base=args.base.rstrip('/')
    page.goto(base,wait_until='networkidle')
    page.locator('.job[data-id="'+args.job_id+'"]').click(timeout=5000)
    page.locator('#sourceagent').wait_for(state='visible',timeout=5000)
    job=page.request.get(base+'/api/tutorials/'+args.job_id).json()
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
        sources=page.request.get(base+'/api/video-sources?q=Bevel').json()['items']
        assert args.job_id in [s['id'] for s in sources]
    else:
        page.locator('#approve').check()
        assert page.locator('#run').is_disabled()
    folder=ROOT/'tasks/video-agent/evidence'
    folder.mkdir(parents=True,exist_ok=True)
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(folder/'source-agent-desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(folder/'source-agent-mobile.png'),full_page=True)
    assert not errors,errors
    result={'job_id':args.job_id,'knowledge_status':job['knowledge']['status'],
        'actions_displayed':page.locator('#agenttrace li').count(),'page_errors':errors,'mobile_overflow':False,
        'independent_artifact_verification':job.get('verification',{}).get('verification','not_run')}
    if job.get('verification',{}).get('artifact'):
        import hashlib
        artifact=page.request.get(base+'/assets/'+args.job_id+'/run/replica.blend')
        assert artifact.ok,artifact.status
        assert hashlib.sha256(artifact.body()).hexdigest()==job['verification']['sha256']
        assert job['verification']['read_only_hash_unchanged'] is True
        result['artifact_download']=True
    if args.check_project:
        import io
        import zipfile
        from urllib.parse import urlsplit
        origin=urlsplit(base);origin=origin.scheme+'://'+origin.netloc
        page.set_viewport_size({'width':1440,'height':1000})
        page.locator('#project').click()
        page.locator('#projectlink').wait_for(state='visible')
        page.locator('#projectlink').click()
        page.get_by_role('region',name='Interactive application knowledge graph').wait_for()
        project_id='video_'+args.job_id
        response=page.request.get(origin+'/api/projects/'+project_id)
        assert response.ok,response.status
        project=response.json()
        assert project['package_ready'] is True
        assert len(project['capabilities'])==len(job['knowledge']['steps'])
        assert all(c['verification_status']=='observed' for c in project['capabilities'])
        assert all(s['relevant'] is True for s in project['sources'])
        package=page.request.get(origin+'/api/projects/'+project_id+'/package')
        assert package.ok,package.status
        with zipfile.ZipFile(io.BytesIO(package.body())) as archive:
            knowledge_path=next(name for name in archive.namelist() if name.endswith('/evidence/video-source/knowledge.json'))
            assert json.loads(archive.read(knowledge_path))['source_sha256']==job['knowledge']['source_sha256']
        page.screenshot(path=str(folder/'video-project-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(folder/'video-project-mobile.png'),full_page=True)
        result['project']={'id':project_id,'capabilities':len(project['capabilities']),
                           'matched_sources':len(project['sources']),'package_download':True,'mobile_overflow':False}
        assert not errors,errors
    (folder/'source-agent-browser.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    browser.close()
