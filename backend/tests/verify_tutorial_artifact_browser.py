"""Browser check against real saved evidence; no API stubs or GUI execution."""
import argparse,asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('job');args=parser.parse_args()
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        page=await browser.new_page(viewport={'width':1440,'height':1000});errors=[]
        page.on('pageerror',lambda exc:errors.append(str(exc)))
        await page.goto('http://192.168.1.59:8788')
        await page.evaluate('(id)=>select(id)',args.job)
        await page.get_by_text('Independent artifact check: verified',exact=True).wait_for()
        assert await page.locator('#run').is_disabled()
        checks=json.loads(await page.locator('#checks').inner_text());assert all(checks.values())
        link=page.get_by_role('link',name='Download Blender artifact (.blend)')
        response=await page.request.get('http://192.168.1.59:8788'+await link.get_attribute('href'))
        assert response.status==200 and len(await response.body())>1000
        await page.locator('#artifact').scroll_into_view_if_needed()
        output=Path('../tasks/video-agent/evidence/verified-workspace.png')
        await page.screenshot(path=str(output))
        await page.set_viewport_size({'width':390,'height':844})
        await page.screenshot(path=str(output.with_name('verified-workspace-mobile.png')))
        assert await page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        assert not errors,errors
        print(json.dumps({'job':args.job,'artifact_http':response.status,'checks':checks,'page_errors':errors,'mobile_overflow':False}))
        await browser.close()
asyncio.run(main())
