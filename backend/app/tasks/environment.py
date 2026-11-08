from importlib.util import find_spec
from urllib.parse import urlsplit

from app.config import get_settings


def environment_status() -> dict:
    settings = get_settings()
    storage = settings.browser_state_path
    target = urlsplit(settings.chatwoot_base_url)
    valid_target = target.scheme in {"http", "https"} and bool(target.netloc) and not target.username and not target.password
    checks = [
        {"id": "sandbox", "label": "Isolated test environment", "ready": settings.chatwoot_test_environment,
         "detail": "Set CHATWOOT_TEST_ENVIRONMENT=true only for a synthetic-data sandbox."},
        {"id": "model", "label": "Computer-use model", "ready": bool(settings.hcompany_api_key),
         "detail": "Configure HCOMPANY_API_KEY in backend/.env."},
        {"id": "browser", "label": "Browser driver", "ready": find_spec("playwright") is not None,
         "detail": "Install backend requirements and run python -m playwright install chromium."},
        {"id": "session", "label": "Administrator browser session", "ready": bool(storage and storage.is_file()),
         "detail": "Run python scripts/chatwoot_login.py; session data stays on your machine."},
        {"id": "verifier", "label": "Independent verifier", "ready": bool(settings.chatwoot_api_token),
         "detail": "Configure CHATWOOT_API_TOKEN for the sandbox account."},
        {"id": "target", "label": "Chatwoot target URL", "ready": valid_target,
         "detail": "The executor is restricted to CHATWOOT_BASE_URL and CHATWOOT_ACCOUNT_ID."},
    ]
    return {"id": "chatwoot", "name": "Northstar Goods", "software": "Chatwoot",
            "version": settings.chatwoot_version, "url": settings.chatwoot_base_url if valid_target else "",
            "account_id": settings.chatwoot_account_id, "inbox_id": settings.chatwoot_inbox_id,
            "ready": all(item["ready"] for item in checks), "checks": checks,
            "research": "Linkup search" if settings.linkup_api_key else "Official documentation fallback",
            "permissions": ["Operate the designated account through its UI", "Create synthetic verification conversations",
                            "Read resulting assignments and priorities", "Save evidence and validated operational knowledge"]}
