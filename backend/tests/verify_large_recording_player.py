"""Real media-review readability/keyboard acceptance; no mocked responses."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
with sync_playwright() as p:
    browser=p.chromium.launch(args=['--mute-audio'])
    page=browser.new_page(viewport={'width':1600,'height':840},locale='en-US')
    try:
        page.goto('http://127.0.0.1:3000/projects/project_c8ea41f2c86e',wait_until='domcontentloaded')
        region=page.get_by_role('region',name='Recording evidence',exact=True)
        region.wait_for()
        expand=region.get_by_role('button',name='Expand recording',exact=True)
        assert expand.count()==1,'Recorded software UI needs a genuinely usable large player'
        video=region.locator('video');video.wait_for()
        page.wait_for_function("document.querySelector('video').readyState>0")
        original=video.element_handle();assert original
        source=video.get_attribute('src')
        frame=region.get_by_role('button',name='Seek recording to 16.3 seconds')
        if not frame.count():frame=region.get_by_role('button').filter(has=page.locator('img')).nth(2)
        frame.scroll_into_view_if_needed();frame.click()
        before=video.evaluate('(v)=>v.currentTime')
        expand.scroll_into_view_if_needed();expand.click()
        dialog=page.get_by_role('dialog',name='Expanded recording',exact=True)
        dialog.wait_for()
        big=dialog.locator('video');box=big.bounding_box();assert box
        assert box['width']>=1400 and box['height']>=790,box
        assert big.get_attribute('src')==source
        assert page.evaluate('(element)=>document.querySelector("video")===element',original)
        assert abs(big.evaluate('(v)=>v.currentTime')-before)<1
        assert page.evaluate('document.fullscreenElement===null'),'Do not change browser capture geometry'
        page.screenshot(path=str(ROOT/'tasks/overnight/evidence/recordings/large-player-ui.png'))
        page.keyboard.press('Escape')
        assert not dialog.count() or not dialog.is_visible()
        assert page.evaluate('document.body.style.overflow')!='hidden'
        print({'real_expansion':True,'same_media_element':True,'timestamp_preserved':True,'escape_return':True,'viewport_unchanged':True,'box':box})
    finally:browser.close()
