"""Initial graph must be readable at recording size, while all evidence stays reachable."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[2]
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={"width":1440,"height":1000})
    page.goto('http://127.0.0.1:3000/projects/project_934cb111315a')
    page.locator('.graph-canvas').scroll_into_view_if_needed()
    page.locator('.react-flow__node strong').first.wait_for()
    info=page.evaluate('''() => {
      const viewport=document.querySelector('.react-flow__viewport');
      const node=document.querySelector('.react-flow__node strong');
      const control=document.querySelector('.react-flow__controls button');
      const scale=new DOMMatrix(getComputedStyle(viewport).transform).a;
      return {readableFontPixels:parseFloat(getComputedStyle(node).fontSize)*scale,controlWidth:control.getBoundingClientRect().width,minimap:!!document.querySelector('.react-flow__minimap'),nodes:document.querySelectorAll('[data-node-id]').length};
    }''')
    assert info['readableFontPixels'] >= 13, info
    assert info['controlWidth'] >= 44, info
    assert not info['minimap'], info
    assert info['nodes'] == 145, info
    page.get_by_role('button',name='Show minimap',exact=True).click()
    assert page.locator('.react-flow__minimap').count()==1
    page.get_by_role('button',name='Hide minimap',exact=True).click()
    page.locator('.graph-canvas').screenshot(path=str(ROOT/'tasks/overnight/evidence/workspace-graph-recording-ready.png'))
    print(json.dumps(info))
    browser.close()
