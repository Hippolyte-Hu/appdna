import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.drivers.browser import BrowserBlocked, safe_ui_url
from app.models import Base
from app.tasks import persistence as store
from app.tasks.catalog import BASE_REQUEST, criteria
from app.tasks.runner import agent_context, execute_run
from app.tasks.verification import ChatwootVerifier, _INPUTS, actual_result, compare


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'tasks.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(store, "session_scope", session)
    yield
    engine.dispose()


def make_task(scenario="routing", parent=None):
    return store.create_task("Support routing", BASE_REQUEST, scenario, "4.8.0", parent)


def test_task_run_history_and_restart_recovery(database):
    task = make_task()
    first = store.new_run(task["id"], 80, 600, True)
    store.log(first["id"], "execute", "Observed a configuration form.")
    store.update_run(first["id"], actions=[{"kind": "click", "outcome": "executed"}])
    store.recover_interrupted_runs()
    recovered = store.get_task(task["id"])
    assert recovered["latest_run"]["status"] == "blocked"
    assert recovered["latest_run"]["actions"][0]["kind"] == "click"
    assert recovered["latest_run"]["activities"][0]["message"].startswith("Observed")
    second = store.new_run(task["id"], 20, 300, False)
    assert store.get_task(task["id"])["latest_run"]["id"] == second["id"]
    assert len(store.get_task(task["id"])["runs"]) == 2


def test_exclusive_environment_and_controls(database):
    task = make_task()
    run = store.new_run(task["id"], 80, 600, True)
    with pytest.raises(ValueError, match="owns the test environment"):
        store.new_run(task["id"], 80, 600, True)
    assert store.control_run(run["id"], "pause")["control"] == "pause"
    store.update_run(run["id"], summary="An observation was saved.")
    assert store.get_run(run["id"])["control"] == "pause"  # Executor updates cannot overwrite controls.
    assert store.control_run(run["id"], "resume")["control"] == "run"
    assert store.control_run(run["id"], "stop")["control"] == "stop"
    store.update_run(run["id"], status="cancelled")
    with pytest.raises(ValueError, match="has ended"):
        store.control_run(run["id"], "resume")


def test_missing_dependencies_stay_blocked_without_fake_evidence(database, monkeypatch):
    monkeypatch.setattr("app.tasks.runner.environment_status", lambda: {
        "software": "Chatwoot", "version": "4.8.0", "url": "http://127.0.0.1:3001",
        "account_id": 1, "inbox_id": 1,
        "checks": [{"ready": False, "detail": "Configure the test model."}],
    })
    run = store.new_run(make_task()["id"], 80, 600, True)
    asyncio.run(execute_run(run["id"]))
    result = store.get_run(run["id"])
    assert result["status"] == "blocked"
    assert result["actions"] == result["verifications"] == []
    assert not result.get("observation")
    assert result["blockers"] == ["Configure the test model."]
    assert store.list_knowledge() == []


def test_only_independently_passed_knowledge_is_reusable(database):
    run = store.new_run(make_task()["id"], 80, 600, True)
    with pytest.raises(ValueError):
        store.save_knowledge(run["id"], "4.8.0", {})
    store.update_run(run["id"], verifications=[{"id": "refund", "status": "passed"}])
    with pytest.raises(ValueError):
        store.save_knowledge(run["id"], "4.8.0", {})
    store.update_run(run["id"], verifications=[{"status": "passed"}, {"status": "failed"}])
    with pytest.raises(ValueError):
        store.save_knowledge(run["id"], "4.8.0", {})
    store.update_run(run["id"], verifications=[{"id": c["id"], "status": "passed"} for c in criteria("routing")])
    with pytest.raises(ValueError):
        store.save_knowledge(run["id"], "4.8.0", {})
    store.update_run(run["id"], configuration_changed=True, actions=[{"kind": "type", "outcome": "executed"}])
    content = {"procedure": ["Re-observe the automation controls."], "completion_check": ["Run independent outcome checks."],
               "permissions": ["Account administrator"], "preconditions": [], "unresolved": [], "source_refs": [], "related_runs": [run["id"]]}
    row = store.save_knowledge(run["id"], "4.8.0", content)
    assert store.list_knowledge("4.8.0")[0]["id"] == row["id"]
    assert store.list_knowledge("4.9.0") == []


def test_follow_up_keeps_all_original_assertions(database):
    parent = make_task()
    followup = make_task("vip", parent["id"])
    assert followup["criteria"][:4] == parent["criteria"]
    assert followup["criteria"][-1] == {"id": "vip_complaint", "requirement": "VIP serious complaints", "team": "Customer Care", "priority": "urgent"}
    assert len(followup["criteria"]) == 7


@pytest.mark.parametrize("url", [
    "https://evil.invalid/app/accounts/1", "http://127.0.0.1:3001/api/v1/accounts/1/automation_rules",
    "http://127.0.0.1:3001/app/accounts/11", "http://127.0.0.1:3001/auth/sign_in",
    "http://127.0.0.1:3001/app/accounts/1?api_token=secret", "file:///etc/passwd",
    "http://127.0.0.1:3001/app/accounts/1/../2/settings", "http://127.0.0.1:3001/app/accounts/1/%2e%2e/2",
])
def test_browser_navigation_scope(url):
    with pytest.raises(BrowserBlocked):
        safe_ui_url(url, "http://127.0.0.1:3001", 1)


def test_browser_allows_real_ui_paths_only():
    url = "http://127.0.0.1:3001/app/accounts/1/settings/automation/list"
    assert safe_ui_url(url, "http://127.0.0.1:3001", 1) == url


def test_actual_verification_distinguishes_wrong_missing_and_unassigned():
    expected = criteria("routing")[0]
    assert compare(expected, {"team": "Billing", "priority": "default"}) == "passed"
    assert compare(expected, {"team": "Logistics", "priority": "default"}) == "failed"
    assert compare(criteria("vip")[-1], {"team": "Customer Care", "priority": "high"}) == "failed"
    assert compare(criteria("routing")[-1], {"team": "Billing", "priority": "default"}) == "failed"
    assert actual_result({"meta": {"team": None}}, {}) is None
    assert actual_result({"priority": None}, {}) is None
    assert actual_result({"priority": None, "meta": {"team": None}}, {}) == {"team": None, "priority": "default"}
    assert actual_result({"priority": 2, "team_id": 7}, {7: "Billing"}) == {"team": "Billing", "priority": "high"}


def test_verifier_accepts_chatwoot_lowercase_team_names_without_weakening_outcomes():
    def handler(request):
        if request.url.path.endswith("/teams"):
            return httpx.Response(200, json=[{"id": 1, "name": "billing"}, {"id": 2, "name": "logistics"},
                                             {"id": 3, "name": "customer care"}])
        return httpx.Response(200, json={"channel_type": "Channel::Api", "enable_auto_assignment": False})

    async def check():
        verifier = ChatwootVerifier("http://sandbox.invalid", 1, 1, "test-token", transport=httpx.MockTransport(handler))
        try:
            assert await verifier.preflight() == {1: "billing", 2: "logistics", 3: "customer care"}
        finally:
            await verifier.close()

    asyncio.run(check())
    assert compare(criteria("routing")[0], {"team": "billing", "priority": "default"}) == "passed"
    assert compare(criteria("routing")[0], {"team": "logistics", "priority": "default"}) == "failed"
    assert compare(criteria("routing")[2], {"team": "customer care", "priority": "high"}) == "failed"
    assert compare(criteria("routing")[3], {"team": "billing", "priority": "default"}) == "failed"


def test_chatwoot_unassigned_conversation_omits_team_only_in_complete_response():
    record = {"id": 1, "account_id": 2, "inbox_id": 2, "status": "open", "priority": None,
              "meta": {"channel": "Channel::Api", "sender": {"id": 1}, "hmac_verified": False}}
    actual = actual_result(record, {1: "billing"})
    assert actual == {"team": None, "priority": "default"}
    assert compare(criteria("routing")[3], actual) == "passed"
    assert compare(criteria("routing")[0], actual) == "failed"
    assert actual_result({key: value for key, value in record.items() if key != "account_id"}, {}) is None
    assert actual_result({**record, "inbox_id": None}, {}) is None
    assert actual_result({**record, "meta": {}}, {}) is None


def test_hidden_inputs_and_verifier_credentials_never_enter_agent_context(database):
    task = make_task()
    run = store.new_run(task["id"], 80, 600, True)
    context = agent_context(task, run, {"controls": [{"label": "Add rule"}]}, [])
    assert all(message not in context for message, _ in _INPUTS.values())
    assert "api_token" not in context and "contact_inboxes" not in context


@pytest.mark.parametrize("wrong_team,expected_status", [(False, "passed"), (True, "failed")])
def test_verifier_writes_only_synthetic_inputs_and_reads_real_contract(wrong_team, expected_status):
    calls = []
    cases = list(criteria("vip"))
    sequence = {"conversation": -1}

    def handler(request):
        calls.append((request.method, request.url.path, json.loads(request.content) if request.content else None))
        path = request.url.path
        if path.endswith("/teams"):
            return httpx.Response(200, json=[{"id": 1, "name": "Billing"}, {"id": 2, "name": "Logistics"}, {"id": 3, "name": "Customer Care"}])
        if path.endswith("/inboxes/1"):
            return httpx.Response(200, json={"channel_type": "Channel::Api", "enable_auto_assignment": False})
        if path.endswith("/contacts"):
            body = json.loads(request.content)
            assert body["email"].endswith("@northstar.invalid")
            return httpx.Response(200, json={"payload": {"contact": {"id": 42, "contact_inboxes": [{"source_id": "synthetic-source", "inbox": {"id": 1}}]}}})
        if request.method == "POST" and path.endswith("/conversations"):
            body = json.loads(request.content)
            assert body["message"]["message_type"] == "incoming"
            assert not any(key in body for key in ("team_id", "priority", "assignee_id"))
            sequence["conversation"] += 1
            return httpx.Response(200, json={"id": 100 + sequence["conversation"]})
        case = cases[sequence["conversation"]]
        team = "Wrong team" if wrong_team else case["team"]
        return httpx.Response(200, json={"id": 100 + sequence["conversation"], "priority": None if case["priority"] == "default" else case["priority"], "meta": {"team": {"name": team} if team else None}})

    async def scenario():
        verifier = ChatwootVerifier("http://sandbox.invalid", 1, 1, "not-a-real-token", transport=httpx.MockTransport(handler), settle_seconds=0, timeout_seconds=0)
        teams = await verifier.preflight()
        async def checkpoint(): pass
        rows = await verifier.verify("vip", teams, lambda _: None, checkpoint)
        await verifier.close()
        return rows

    rows = asyncio.run(scenario())
    assert len(rows) == 7
    assert all(row["status"] == expected_status for row in rows)
    assert all(method == "GET" or path.endswith(("/contacts", "/conversations")) for method, path, _ in calls)
    assert not any("automation" in path or "assignment" in path or "priority" in path for _, path, _ in calls)


def test_task_api_validation_and_durable_report(database, monkeypatch):
    from app.main import app
    import app.main as main
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr("app.tasks.runner.environment_status", lambda: {
        "software": "Chatwoot", "version": "4.8.0", "url": "http://127.0.0.1:3001", "account_id": 1, "inbox_id": 1,
        "checks": [{"ready": False, "detail": "Test dependency unavailable."}],
    })
    with TestClient(app) as client:
        assert client.post("/api/tasks", json={"title": "x", "request": "short"}).status_code == 422
        task = client.post("/api/tasks", json={"title": "Route Northstar support", "request": BASE_REQUEST}).json()
        assert client.post(f"/api/tasks/{task['id']}/runs", json={"max_actions": 0}).status_code == 422
        response = client.post(f"/api/tasks/{task['id']}/runs", json={"max_actions": 20, "timeout_seconds": 60})
        assert response.status_code == 201
        run_id = response.json()["id"]
        detail = client.get(f"/api/tasks/{task['id']}").json()
        assert detail["latest_run"]["status"] == "blocked"
        report = client.get(f"/api/task-runs/{run_id}/report").json()
        assert report["run"]["verifications"] == []
        assert report["provenance"]["configuration"] == "Browser UI only"
        assert client.get(f"/api/task-runs/{run_id}/evidence/step_001.png").status_code == 404
        assert client.get("/api/knowledge").json() == []


def test_stop_cancels_an_inflight_model_request(database, monkeypatch):
    monkeypatch.setattr("app.tasks.runner.environment_status", lambda: {
        "software": "Chatwoot", "version": "4.8.0", "url": "http://127.0.0.1:3001",
        "account_id": 1, "inbox_id": 1, "checks": [{"ready": True}],
    })
    class Verifier:
        def __init__(self, *_): pass
        async def preflight(self): return {1: "Billing", 2: "Logistics", 3: "Customer Care"}
        async def configuration_snapshot(self): return []
        async def close(self): pass
    monkeypatch.setattr("app.tasks.verification.ChatwootVerifier", Verifier)
    async def scenario():
        began = asyncio.Event()
        cancelled = asyncio.Event()
        class SlowProvider:
            def __init__(self, *_): pass
            async def complete_json(self, *_):
                began.set()
                try:
                    await asyncio.sleep(30)
                finally:
                    cancelled.set()
        monkeypatch.setattr("app.tasks.runner.HCompanyProvider", SlowProvider)
        run = store.new_run(make_task()["id"], 80, 600, True)
        pending = asyncio.create_task(execute_run(run["id"]))
        await asyncio.wait_for(began.wait(), timeout=2)
        store.control_run(run["id"], "stop")
        await asyncio.wait_for(pending, timeout=2)
        assert cancelled.is_set()
        assert store.get_run(run["id"])["status"] == "cancelled"
    asyncio.run(scenario())


@pytest.mark.parametrize("status,expected", [(401, "denied access"), (403, "denied access"), (429, "rate-limiting"), (None, "did not respond in time")])
def test_model_failure_is_actionable_and_never_creates_evidence(database, monkeypatch, status, expected):
    from app.providers.base import ProviderError, ProviderTimeout

    monkeypatch.setattr("app.tasks.runner.environment_status", lambda: {
        "software": "Chatwoot", "version": "4.8.0", "url": "http://127.0.0.1:3001",
        "account_id": 1, "inbox_id": 1, "checks": [{"ready": True}],
    })
    class Verifier:
        def __init__(self, *_): pass
        async def preflight(self): return {1: "Billing", 2: "Logistics", 3: "Customer Care"}
        async def configuration_snapshot(self): return []
        async def close(self): pass
    class Provider:
        def __init__(self, *_): pass
        async def complete_json(self, *_):
            if status is None:
                raise ProviderTimeout("private diagnostic")
            raise ProviderError("private diagnostic", status=status)
    monkeypatch.setattr("app.tasks.verification.ChatwootVerifier", Verifier)
    monkeypatch.setattr("app.tasks.runner.HCompanyProvider", Provider)
    run = store.new_run(make_task()["id"], 80, 600, True)
    asyncio.run(execute_run(run["id"]))
    result = store.get_run(run["id"])
    assert result["status"] == "blocked"
    assert expected in result["summary"]
    assert "private diagnostic" not in json.dumps(result)
    assert result["actions"] == result["verifications"] == []
    assert not result.get("observation")
    assert store.list_knowledge() == []


def test_superseded_skill_is_retained_but_not_reused(database):
    from app.models import OperationalKnowledge
    run=store.new_run(make_task()['id'],80,600,True)
    checks=[{'id':item['id'],'status':'passed'} for item in criteria('routing')]
    store.update_run(run['id'],verifications=checks,configuration_changed=True,actions=[{'kind':'type','outcome':'executed'}])
    content={'preconditions':[],'procedure':['Observed UI action'],'completion_check':['Independent checks passed'],
             'unresolved':[],'permissions':['Administrator'],'source_refs':[],'related_runs':[run['id']]}
    previous=store.save_knowledge(run['id'],'4.8.0',dict(content))
    replacement=store.save_knowledge(run['id'],'4.8.0',{**content,'grounding_version':2})
    store.supersede_knowledge(previous['id'],replacement['id'])
    assert [row['id'] for row in store.list_knowledge()]==[replacement['id']]
    assert store.get_run(run['id'])['verifications']==checks
    with store.session_scope() as session:
        original=session.get(OperationalKnowledge,previous['id'])
        assert json.loads(original.content_json)['superseded_by']==replacement['id']


def test_recovered_run_cannot_be_revived_by_its_old_executor(database, monkeypatch):
    monkeypatch.setattr('app.tasks.runner.environment_status', lambda: {
        'software': 'Chatwoot', 'version': '4.8.0', 'url': 'http://127.0.0.1:3001',
        'account_id': 1, 'inbox_id': 1, 'checks': [{'ready': True}],
    })

    class Verifier:
        def __init__(self, *_): pass
        async def preflight(self): return {1: 'Billing', 2: 'Logistics', 3: 'Customer Care'}
        async def configuration_snapshot(self): return []
        async def close(self): pass

    monkeypatch.setattr('app.tasks.verification.ChatwootVerifier', Verifier)

    async def scenario():
        began, cancelled = asyncio.Event(), asyncio.Event()

        class SlowProvider:
            def __init__(self, *_): pass
            async def complete_json(self, *_):
                began.set()
                try:
                    await asyncio.sleep(30)
                finally:
                    cancelled.set()

        monkeypatch.setattr('app.tasks.runner.HCompanyProvider', SlowProvider)
        task = make_task()
        old = store.new_run(task['id'], 80, 600, True)
        executor = asyncio.create_task(execute_run(old['id']))
        await asyncio.wait_for(began.wait(), timeout=2)
        store.recover_interrupted_runs()
        recovered = store.get_run(old['id'])
        new = store.new_run(task['id'], 80, 600, True)
        await asyncio.wait_for(executor, timeout=2)
        assert cancelled.is_set()
        assert store.get_run(old['id']) == recovered
        assert store.get_run(new['id'])['status'] == 'created'
        assert store.get_run(old['id'])['actions'] == []

    asyncio.run(scenario())
