"""Manual recovery smoke: inject a missing inventory, not fake coordinates/results.
Uses the real H API and Mac mouse driver. Intentionally limited to two clicks.
Run only when all API projects are idle, from backend with PYTHONPATH=.
"""
import asyncio
import json
from urllib.request import urlopen
from unittest.mock import patch

from app.config import get_settings
from app.db import session_scope
from app.engines import visual
from app.models import Project
from app.providers.hcompany import HCompanyProvider
from app.store import Store
from app.util import new_id, utcnow


async def main():
    assert all(p['status'] in {'completed', 'failed'} for p in json.load(urlopen('http://127.0.0.1:8787/api/projects')))
    s = get_settings()
    provider = HCompanyProvider(s.hcompany_api_key, s.hcompany_base_url, s.hcompany_model)
    original = provider.list_controls
    selected = []
    calls = []
    async def inventory(**kwargs):
        calls.append(kwargs.get('pending', []))
        if len(calls) == 1:
            controls, more = await original(**kwargs)
            local = next(c for c in controls if c['role'] == 'opener' and visual.should_click(c, covered_docs=False))
            tab = next(c for c in controls if c['role'] == 'navigation' and visual.should_click(c, covered_docs=False))
            selected.extend([local['label'], tab['label']])
            return [local, tab], 'none'
        if kwargs.get('pending'):
            return await original(**kwargs)
        return [], 'none'  # Explicit fault injection: model forgot a known tab.
    pid = new_id('project')
    print('PROJECT', pid, flush=True)
    with session_scope() as db:
        project = Project(id=pid, software_name='Blender', learning_objective='Navigation recovery smoke; inventory omission injected', status='exploring', created_at=utcnow(), updated_at=utcnow())
        db.add(project)
        db.commit()
        store = Store(db)
        folder = s.artifacts_dir / pid / 'explore'
        with patch.object(provider, 'list_controls', inventory), patch.object(visual, 'MAX_CLICKS', 2):
            trace = await visual.explore_visually(store, project, provider, folder)
        store.set_status(project, 'completed')
        clicks = [f for f in trace if f['action'] == 'click' and f['executed']]
        report = {'project': pid, 'fault_injection': 'one missing control inventory; no injected locations/results', 'selected_from_real_model': selected, 'clicked': [f['text'] for f in clicks], 'pending_queries': calls, 'scope': 'two-click recovery only, not application-wide coverage'}
        (folder.parent / 'navigation-acceptance.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)
        assert len(selected) == len(clicks) == 2
        assert report['clicked'] == selected
        assert any(selected[1] in labels for labels in calls)
        assert not visual.click_missed(clicks[-1]['learned'])


if __name__ == '__main__':
    asyncio.run(main())
