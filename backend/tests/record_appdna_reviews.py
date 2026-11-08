"""Record real saved-case reviews after UI approval; no mocked product responses.

Intentionally does NOT start a new agent run or open a personal native app.
The two latest native-window failures and evidence levels remain visible.
"""
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'deliverables'
RAW=OUT/'appdna-review-raw'
QA=ROOT/'tasks/overnight/evidence/recordings'
RAW.mkdir(exist_ok=True);QA.mkdir(parents=True,exist_ok=True)
CASES={'Blender':'project_934cb111315a','VoiceCue':'project_c8ea41f2c86e'}
if os.environ.get('APPDNA_CAPTURE_CASE'):
    chosen=os.environ['APPDNA_CAPTURE_CASE'];assert chosen in CASES
    CASES={chosen:CASES[chosen]}

def duration(path):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)]))

# A visible Han-character check, including ancestor clipping; final frames also get visual QA.
LANGUAGE_JS=r'''() => {
 const found=[];const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 while(walker.nextNode()) {
  const n=walker.currentNode;const matches=[...n.textContent.matchAll(/[\u3400-\u9fff]/g)];
  for(const m of matches) {
   const range=document.createRange();range.setStart(n,m.index);range.setEnd(n,m.index+1);
   const r=range.getBoundingClientRect();if(!r.width||!r.height)continue;
   let clip={left:0,top:0,right:innerWidth,bottom:innerHeight},visible=true;
   for(let e=n.parentElement;e;e=e.parentElement) {
    const s=getComputedStyle(e);if(s.visibility==='hidden'||s.display==='none'){visible=false;break;}
    const b=e.getBoundingClientRect();
    if(/auto|scroll|hidden|clip/.test(s.overflowY)){clip.top=Math.max(clip.top,b.top);clip.bottom=Math.min(clip.bottom,b.bottom);}
    if(/auto|scroll|hidden|clip/.test(s.overflowX)){clip.left=Math.max(clip.left,b.left);clip.right=Math.min(clip.right,b.right);}
   }
   if(visible&&r.right>clip.left&&r.left<clip.right&&r.bottom>clip.top&&r.top<clip.bottom)found.push(n.textContent.trim().slice(0,160));
  }
 }return [...new Set(found)];
}'''

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--mute-audio'])
    for name,pid in CASES.items():
        detail=json.load(urllib.request.urlopen(f'http://127.0.0.1:8787/api/projects/{pid}'))
        assert detail['status']=='failed', 'Review script must not mislabel an active or changed case'
        assert detail['outcome']['evaluation']['verdict']=='Incomplete'
        narration=OUT/f'AppDNA-{name}-narration.mp3'
        seconds=duration(narration)
        events=[];errors=[]
        context=browser.new_context(viewport={'width':1600,'height':840},locale='en-US',record_video_dir=str(RAW),record_video_size={'width':1600,'height':840})
        started=time.monotonic();page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        main_video=page.video
        def hold(fraction):
            remaining=started+seconds*fraction-time.monotonic()
            if remaining>0:page.wait_for_timeout(remaining*1000)
        def mark(label,current=page,**proof):
            violations=current.evaluate(LANGUAGE_JS)
            assert not violations,{'scene':label,'visible_non_English':violations}
            current.screenshot(path=str(QA/f'{name}-{len(events):02}-{label}.png'))
            events.append({'time':round(time.monotonic()-started,3),'scene':label,**proof})
        def open_case():
            page.goto(f'http://127.0.0.1:3000/projects/{pid}',wait_until='domcontentloaded')
            page.get_by_text('Stopped',exact=True).first.wait_for(timeout=20000)
            mark('stopped-case',status=detail['status'],verdict='Incomplete')
        def graph_review():
            canvas=page.locator('.react-flow').first
            canvas.scroll_into_view_if_needed();page.wait_for_timeout(500)
            node=page.locator('.react-flow__node.selected').first
            node.wait_for();box=node.bounding_box();assert box
            before=node.get_attribute('style')
            page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
            page.mouse.down();page.mouse.move(box['x']+box['width']/2+48,box['y']+box['height']/2+22,steps=12);page.mouse.up()
            assert node.get_attribute('style')!=before
            old=page.locator('.react-flow__viewport').get_attribute('style')
            page.get_by_role('button',name='Zoom in',exact=True).click();page.wait_for_timeout(350)
            assert old!=page.locator('.react-flow__viewport').get_attribute('style')
            mark('interactive-graph',drag=True,zoom=True,nodes=page.locator('.react-flow__node').count())
        if name=='Blender':
            page.goto('http://127.0.0.1:3000',wait_until='domcontentloaded')
            page.locator('input[name="software_name"]').fill('Blender')
            mark('procurement-workspace')
            hold(.16);open_case()
            hold(.42);graph_review()
            hold(.53)
            page.get_by_role('button',name='Fit all',exact=True).click()
            page.wait_for_timeout(300)
            page.locator('.react-flow__node[data-id^="source:"]').last.click()
            article=page.get_by_test_id('article-content');article.wait_for()
            assert len(article.inner_text())>200
            article.scroll_into_view_if_needed();article.hover();page.mouse.wheel(0,280);page.wait_for_timeout(300)
            mark('full-matched-source',collected_characters=len(article.inner_text()))
            hold(.68)
        else:
            open_case();hold(.075)
            recording=page.get_by_role('region',name='Recording evidence',exact=True)
            recording.scroll_into_view_if_needed()
            # Clicking a transcript entry is the real product's seek control.
            transcript=recording.get_by_role('button').filter(has_text=re.compile(r'Welcome|demonstration|VoiceCue')).first
            transcript.click()
            video=recording.locator('video')
            video.scroll_into_view_if_needed();box=video.bounding_box();assert box
            video.click(position={'x':24,'y':box['height']-48})
            page.wait_for_function("!document.querySelector('video').paused",timeout=5000)
            page.wait_for_timeout(800)
            # Actual native fullscreen entry keeps the embedded application's text readable.
            box=video.bounding_box();assert box
            video.click(position={'x':box['width']-68,'y':box['height']-48})
            page.wait_for_function("document.fullscreenElement!==null")
            box=video.bounding_box();assert box and box['width']>=1200
            mark('uploaded-recording',segments=len(detail['transcripts']),analysed_frames=len(detail['media']['observations']),native_fullscreen=True)
            hold(.25)
            # Headless Chrome does not route Escape to its chrome. Exit through
            # the official browser API, never by altering product state or evidence.
            page.evaluate("document.exitFullscreen()")
            page.wait_for_function("document.fullscreenElement===null")
            video.scroll_into_view_if_needed();box=video.bounding_box();assert box
            video.hover(position={'x':24,'y':box['height']-48});page.wait_for_timeout(300)
            video.click(position={'x':24,'y':box['height']-48})
            page.wait_for_function("document.querySelector('video').paused",timeout=5000)
            recording.locator('summary').filter(has_text='H Company frame interpretation').click()
            summary=recording.locator('summary').filter(has_text='H Company frame interpretation')
            summary.scroll_into_view_if_needed();page.mouse.wheel(0,200);page.wait_for_timeout(300)
            mark('actual-frame-interpretations',observed=55,independently_verified=0)
            hold(.43);graph_review()
            hold(.56)
            recording.scroll_into_view_if_needed()
            frame_button=recording.get_by_role('button',name=re.compile(r'Seek recording to')).nth(4)
            frame_button.scroll_into_view_if_needed();frame_button.click()
            recording.locator('video').scroll_into_view_if_needed()
            mark('timestamp-linked-recording',selected_timestamp=frame_button.get_attribute('aria-label'))
            hold(.72)
        report_link=page.get_by_role('link',name='Open assessment report',exact=True)
        report_link.scroll_into_view_if_needed()
        report_started=time.monotonic()-started
        with page.expect_popup() as info:report_link.click()
        report=info.value;report.on('pageerror',lambda e:errors.append(str(e)))
        report.wait_for_load_state('domcontentloaded')
        assert 'Incomplete' in report.locator('body').inner_text()
        mark('actual-assessment-report',report,verdict='Incomplete')
        remaining=started+seconds-time.monotonic()
        if remaining>0:report.wait_for_timeout(remaining*1000)
        report_video=report.video
        context.close()
        main_path=RAW/f'{name}-workspace.webm';report_path=RAW/f'{name}-report.webm'
        assert main_video and report_video
        main_video.save_as(str(main_path));report_video.save_as(str(report_path))
        assert not errors,errors
        manifest={'case':pid,'review_type':'Saved experiment evidence review; not a fresh completed GUI run','duration':seconds,'main_cut':round(report_started,3),'main':str(main_path),'report':str(report_path),'narration':str(narration),'events':events,'page_errors':errors,'viewport':{'width':1600,'height':840}}
        (QA/f'{name}-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(json.dumps({'case':name,'duration':seconds,'events':len(events),'page_errors':errors}),flush=True)
    browser.close()
