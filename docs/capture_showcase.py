"""Capture real, read-only product views for the repository. Never starts execution.
Run from repository root: backend/.venv/bin/python docs/capture_showcase.py
Requires the existing local frontend and retained demo source/execution.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
SOURCE = '825b2bf417154c019c55f869fd9567cc'
RUN = '66242a46bc0b45f9ab42961da01bbcd6'
OUT = ROOT / 'images'
OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def navigate(path):
        page.goto('http://127.0.0.1:3000' + path, wait_until='networkidle')
        page.evaluate('document.fonts.ready')
    navigate('/')
    page.screenshot(path=str(OUT / 'assessment-workspace.png'))
    navigate('/learning?source=' + SOURCE)
    page.get_by_text('Source checked · reusable knowledge').wait_for()
    page.locator('.showcase-steps').screenshot(path=str(OUT / 'learned-workflow.png'))
    navigate('/learning?source=' + SOURCE + '&run=' + RUN)
    receipt = page.locator('[data-testid="execution-receipt"]')
    receipt.wait_for()
    page.wait_for_timeout(1000)
    text = receipt.inner_text()
    assert 'saved artifact passed independent, source-bound checks' in text.lower(), text
    receipt.screenshot(path=str(OUT / 'verified-execution.png'))
    print('Actual receipt:', text)
    assert not errors, errors
    print('Saved three real UI captures; no execution/control requests sent.')
    browser.close()
