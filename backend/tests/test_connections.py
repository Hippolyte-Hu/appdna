"""Exercise credential setup against a temporary env file, never the user's keys."""

from functools import lru_cache
import json
import stat

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import connections
from app.config import Settings


@pytest.fixture
def local_setup(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    session = tmp_path / "session.json"
    env.write_text(f'# Keep this comment\nHCOMPANY_MODEL=holo4-27b\nCHATWOOT_STORAGE_STATE={session}\n')
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)

    @lru_cache
    def settings():
        return Settings(_env_file=env)

    monkeypatch.setattr(connections, "ENV_PATH", env)
    monkeypatch.setattr(connections, "get_settings", settings)
    monkeypatch.setattr(connections, "_login_task", None)
    monkeypatch.setattr(connections, "_login_state", {"status": "idle", "message": ""})
    app = FastAPI()
    app.include_router(connections.router)
    with TestClient(app) as client:
        yield client, env, session, settings


def target(**updates):
    return {"url": "http://127.0.0.1:3001", "account_id": 1, "inbox_id": 1,
            "test_environment": True, **updates}


def test_keys_save_without_restart_and_responses_are_secret_free(local_setup):
    client, env, _, settings = local_setup
    assert not client.get("/api/connections").json()["model"]["api_key_saved"]
    first = 'test-credential-with-"quotes"-and-\\slashes'
    response = client.put("/api/connections/model", json={"api_key": first})
    assert response.status_code == 200
    assert response.json()["model"]["api_key_saved"]
    assert first not in response.text
    assert settings().hcompany_api_key == first
    assert env.read_text().startswith("# Keep this comment\nHCOMPANY_MODEL=holo4-27b\n")
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert not list(env.parent.glob(".connection-*.tmp"))
    client.put("/api/connections/model", json={"api_key": "replacement-test-key"})
    assert settings().hcompany_api_key == "replacement-test-key"
    assert env.read_text().count("HCOMPANY_API_KEY=") == 1
    response = client.put("/api/connections/search", json={"api_key": "search-test-key"})
    assert response.json()["search"]["api_key_saved"]
    assert "search-test-key" not in response.text
    assert settings().linkup_api_key == "search-test-key"


@pytest.mark.parametrize("key", [" ", "secret\nCHATWOOT_TEST_ENVIRONMENT=true", "secret\rvalue", "${SECRET}", "x" * 4097])
def test_invalid_key_is_rejected_without_echo_or_disk_change(local_setup, key):
    client, env, _, _ = local_setup
    before = env.read_text()
    response = client.put("/api/connections/model", json={"api_key": key})
    assert response.status_code == 422
    assert response.json() == {"detail": "Enter a valid H Company API key on one line."}
    assert env.read_text() == before


def test_external_origin_cannot_write_credentials(local_setup):
    client, env, _, _ = local_setup
    before = env.read_text()
    response = client.put("/api/connections/model", json={"api_key": "origin-test-key"}, headers={"Origin": "https://unrelated.example"})
    assert response.status_code == 403
    assert env.read_text() == before
    assert client.put("/api/connections/model", json={"api_key": "local-test-key"}, headers={"Origin": "http://127.0.0.1:3000"}).status_code == 200


def test_account_change_invalidates_old_credentials_and_preserves_session_backup(local_setup):
    client, _, session, settings = local_setup
    client.put("/api/connections/chatwoot", json=target(api_token="chatwoot-test-token"))
    session.write_text(json.dumps({"cookies": []}))
    response = client.put("/api/connections/chatwoot", json=target(api_token=""))
    assert response.json()["chatwoot"]["api_token_saved"]
    assert settings().chatwoot_api_token == "chatwoot-test-token"
    assert session.exists()
    response = client.put("/api/connections/chatwoot", json=target(account_id=2))
    assert not response.json()["chatwoot"]["api_token_saved"]
    assert not response.json()["chatwoot"]["session_saved"]
    assert not session.exists()
    assert session.with_suffix(".previous.json").exists()
    assert settings().chatwoot_api_token == ""


@pytest.mark.parametrize("url", ["file:///tmp/demo", "https://user:password@example.com", "http://localhost:bad", "https://example.com/app", "https://example.com?token=secret"])
def test_invalid_target_is_not_saved(local_setup, url):
    client, env, _, _ = local_setup
    before = env.read_text()
    response = client.put("/api/connections/chatwoot", json=target(url=url))
    assert response.status_code == 422
    assert url not in response.text
    assert env.read_text() == before


def test_sign_in_requires_test_account_and_reports_unreachable_server(local_setup, monkeypatch):
    client, _, _, _ = local_setup
    assert client.post("/api/connections/chatwoot/login").status_code == 400
    client.put("/api/connections/chatwoot", json=target())

    async def offline(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "get", offline)
    response = client.post("/api/connections/chatwoot/login")
    assert response.status_code == 503
    assert "not reachable" in response.json()["detail"]
    assert client.get("/api/connections/chatwoot/login").json()["status"] == "idle"
    assert connections._login_task is None
