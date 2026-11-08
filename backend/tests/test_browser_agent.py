import asyncio
import copy
import json

from app.providers.browser_agent import BrowserAgent, browser_tools
from app.providers.hcompany import HCompanyProvider
from app.tasks.research import documentation_text


def context(index):
    state = {"business_request": "Route support requests", "acceptance_criteria": [], "plan": [],
             "official_sources": [], "applicable_knowledge": [],
             "observation": {"step": index, "controls": [{"id": 1, "label": "Settings"}]},
             "recent_actions": [], "remaining_research_requests": 0}
    return 'Operate the designated test account through its visible UI.\n' + json.dumps(state)


def test_documentation_uses_article_instead_of_navigation_budget():
    html = '<header>Top navigation</header><main><aside>' + ('Many menu links ' * 3000) + '</aside><article><h1>Automation guide</h1><p>Open the rule form, choose conditions and actions, and save.</p><footer>Newsletter</footer></article></main>'
    result = documentation_text(html, limit=200)
    assert result.startswith('Automation guide')
    assert 'choose conditions and actions' in result
    assert 'menu links' not in result and 'Newsletter' not in result


def test_native_protocol_records_matching_results_and_bounds_screenshots():
    class Provider:
        def __init__(self): self.requests = []
        async def complete_browser_tool(self, messages, tools):
            self.requests.append(copy.deepcopy(messages))
            assert 'research' not in {tool['function']['name'] for tool in tools}
            return {'id': f'call_{len(self.requests)}', 'type': 'function', 'function': {'name': 'click', 'arguments': json.dumps({'target': 1, 'summary': 'Open a visible setting'})}}
    async def check():
        provider = Provider()
        agent = BrowserAgent(provider)
        for index in range(6):
            action = await agent.decide(context(index), b'test-image', allow_research=False)
            assert action['kind'] == 'click' and action['target'] == 1
            agent.record_result({**action, 'outcome': 'executed', 'detail': 'UI action executed'})
        messages = provider.requests[-1]
        images = [chunk for message in messages if isinstance(message.get('content'), list) for chunk in message['content'] if chunk['type'] == 'image_url']
        assert len(images) == 3
        for index, message in enumerate(messages):
            if message['role'] == 'tool':
                assert messages[index - 1]['tool_calls'][0]['id'] == message['tool_call_id']
        assert any('[screenshot evicted]' in str(message) for message in messages)
    asyncio.run(check())


def test_holo_native_request_uses_tools_and_does_not_replay_reasoning(monkeypatch):
    provider = HCompanyProvider('test-key', 'https://api.hcompany.ai/v1', 'holo4-27b')
    captured = []
    async def request(body):
        captured.append(body)
        return {'choices': [{'message': {'reasoning': 'private thinking must not be replayed', 'tool_calls': [{'id': 'call_1', 'type': 'function', 'function': {'name': 'answer', 'arguments': '{"content":"Configuration saved"}'}}]}}]}
    monkeypatch.setattr(provider, '_request', request)
    result = asyncio.run(provider.complete_browser_tool([{'role': 'user', 'content': 'Observe the test account'}], browser_tools(False)))
    assert captured[0]['tool_choice'] == 'required'
    assert captured[0]['chat_template_kwargs']['enable_thinking'] is True
    assert 'response_format' not in captured[0]
    assert 'private thinking' not in json.dumps(result)
    assert result['function']['name'] == 'answer'


def test_opening_action_select_is_safe_but_outbound_selection_is_rejected(tmp_path):
    import pytest
    from app.drivers.browser import BrowserBlocked, BrowserDriver
    class Locator:
        async def click(self): pass
    class Page:
        url='http://127.0.0.1:3001/app/accounts/1/settings'
        def locator(self,*_):return Locator()
        async def wait_for_timeout(self,*_):pass
    async def check():
        driver=BrowserDriver('http://127.0.0.1:3001',1,tmp_path/'state.json',tmp_path)
        driver.page=Page()
        driver.controls={1:{'tag':'select','label':'Assign a Team Send an Email to Team Send a Message'}}
        await driver.execute({'kind':'click','target':1,'text':''})
        with pytest.raises(BrowserBlocked,match='outside routing'):
            await driver.execute({'kind':'select','target':1,'text':'Send an Email to Team'})
        with pytest.raises(BrowserBlocked,match='outside routing'):
            await driver.execute({'kind':'select','target':1,'text':'Send a Message'})
    asyncio.run(check())


def test_prior_outcome_feedback_excludes_withheld_inputs_and_records():
    from app.tasks.runner import prior_outcomes
    task={'runs':[{'id':'current','verifications':[]},{'id':'previous','verifications':[
        {'id':'refund','requirement':'Refund requests','expected':{'team':'Billing','priority':'default'},
         'actual':{'team':None,'priority':'default'},'status':'failed',
         'input':{'message':'withheld exact message'},'record':{'private':'conversation data'}}]}]}
    feedback=prior_outcomes(task,'current')
    assert feedback[0]['status']=='failed'
    assert 'withheld exact message' not in json.dumps(feedback)
    assert 'conversation data' not in json.dumps(feedback)
    assert 'input' not in feedback[0] and 'record' not in feedback[0]


def test_stale_target_recovers_without_attempting_an_unobserved_control(tmp_path):
    import pytest
    from app.drivers.browser import BrowserDriver

    class Page:
        url = 'http://127.0.0.1:3001/app/accounts/1/settings/automation/list'

        def locator(self, selector):
            raise AssertionError('A stale target must never execute a UI operation')

    driver = BrowserDriver('http://127.0.0.1:3001', 1, tmp_path/'session.json', tmp_path)
    driver.page = Page()
    with pytest.raises(ValueError, match='current observation'):
        asyncio.run(driver.execute({'kind':'click','target':999,'text':''}))


def test_retry_entry_uses_only_a_same_account_previously_observed_setting():
    from app.tasks.runner import observed_settings_entry
    task = {'runs': [{'id': 'failed', 'verifications': [{'status': 'failed'}],
                      'observation': {'url': 'http://127.0.0.1:3004/app/accounts/1/settings/automation/list'}}]}
    url, protected = observed_settings_entry(task, 'http://127.0.0.1:3004', 1)
    assert protected and url.endswith('/settings/automation/list')
    assert observed_settings_entry(task, 'http://127.0.0.1:3003', 1) == (None, False)
    assert observed_settings_entry(task, 'http://127.0.0.1:3004', 2) == (None, False)
    assert observed_settings_entry({'runs': []}, 'http://127.0.0.1:3004', 1) == (None, False)


def test_retry_never_captures_a_dashboard_or_conversation_with_heldout_inputs(tmp_path):
    import pytest
    from app.drivers.browser import BrowserBlocked, BrowserDriver
    driver = BrowserDriver('http://127.0.0.1:3004', 1, tmp_path/'state.json', tmp_path,
                           protect_conversations=True)
    driver.validate_observation_url('http://127.0.0.1:3004/app/accounts/1/settings/automation/list')
    for suffix in ['dashboard', 'conversations/1', 'inbox/1']:
        with pytest.raises(BrowserBlocked, match='Verification inputs are protected'):
            driver.validate_observation_url('http://127.0.0.1:3004/app/accounts/1/' + suffix)


def test_followup_resumes_parent_landmark_without_supplying_a_new_path(monkeypatch):
    from app.tasks import persistence as store
    from app.tasks.runner import observed_settings_entry
    url = 'http://127.0.0.1:3004/app/accounts/1/settings/automation/list'
    parent = {'runs': [{'verifications': [{'status': 'passed'}], 'observation': {'url': url}}]}
    monkeypatch.setattr(store, 'get_task', lambda task_id: parent if task_id == 'parent' else None)
    assert observed_settings_entry({'runs': [], 'parent_id': 'parent'}, 'http://127.0.0.1:3004', 1) == (url, True)
