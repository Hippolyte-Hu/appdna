"""Real responsive/keyboard/report checks; never mocks an assessment response."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'tasks/overnight/evidence'
OUT.mkdir(parents=True, exist_ok=True)
checks = []
errors = []
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(locale='en-US')
    page.on('pageerror', lambda error: errors.append(str(error)))
    for width in [320, 768, 1024, 1440]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.goto('http://127.0.0.1:3000', wait_until='networkidle')
        page.get_by_role('heading', name='Recent runs').wait_for()
        assert page.get_by_role('button', name='Start assessment', exact=True).is_visible()
        assert page.locator('summary').count() == 1, 'Optional recording evidence needs a keyboard-accessible disclosure'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Home overflow at {width}'
        page.locator('summary').click()
        assert page.get_by_label('Or upload a recording').is_visible()
        page.locator('summary').click()
        page.get_by_label('Application name or website URL').focus()
        page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.name') == 'software_version'
        page.screenshot(path=str(OUT / f'workspace-home-{width}.png'), full_page=True)
        checks.append({'screen': 'home', 'width': width, 'overflow': False, 'keyboard': True, 'recording_disclosure': True})
        page.goto('http://127.0.0.1:3000/projects/project_934cb111315a', wait_until='networkidle')
        page.get_by_role('heading', name='Stopped', exact=True).wait_for()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Project overflow at {width}'
        assert page.get_by_role('button', name='Continue learning', exact=True).is_enabled()
        assert page.get_by_role('link', name='View full-size evidence', exact=True).is_visible()
        assert page.get_by_text('Retained checks apply to saved Blender artifacts, not the latest GUI attempt.').is_visible()
        page.screenshot(path=str(OUT / f'workspace-project-{width}.png'), full_page=True)
        checks.append({'screen': 'project', 'width': width, 'overflow': False, 'honest_stopped_state': True})
    page.goto('http://127.0.0.1:8787/api/projects/project_934cb111315a/report', wait_until='networkidle')
    text = page.locator('body').inner_text()
    assert 'procurement' in text.lower() and 'Incomplete' in text
    page.screenshot(path=str(OUT / 'blender-report-screen.png'), full_page=True)
    page.pdf(path=str(ROOT / 'deliverables/Blender-assessment.pdf'), format='A4', print_background=True)
    browser.close()
assert not errors, errors
result = {'checks': checks, 'report_printed': True, 'page_errors': errors}
(OUT / 'workspace-browser-qa.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
