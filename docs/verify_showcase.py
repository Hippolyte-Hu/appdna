"""Validate documentation links and render Mermaid using a pinned browser library."""
from pathlib import Path
import re
import urllib.request
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
blocks = []
for relative in ['README.md', 'docs/WORKFLOWS.md']:
    path = root / relative
    text = path.read_text()
    for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
        target = link.split('#')[0]
        if target and not re.match(r'\w+://', target):
            assert (path.parent / target).exists(), (relative, link)
    blocks += re.findall(r'```mermaid\n(.*?)```', text, re.S)
script = urllib.request.urlopen('https://cdn.jsdelivr.net/npm/mermaid@11.12.0/dist/mermaid.min.js', timeout=30).read().decode()
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.set_content('<html><body></body></html>')
    page.add_script_tag(content=script)
    page.evaluate('mermaid.initialize({startOnLoad:false,securityLevel:"strict"})')
    for i, block in enumerate(blocks):
        length = page.evaluate('async ({text,id}) => {const r=await mermaid.render(id,text);return r.svg.length}', {'text': block, 'id': f'diagram{i}'})
        print(f'Mermaid {i+1}: rendered SVG ({length} chars)')
    browser.close()
print('PASS: all relative document/image targets exist; all Mermaid blocks rendered.')
