"""Local connection setup. Secrets are written to the ignored .env, never returned."""

import asyncio
import json
import os
import re
import tempfile
from importlib.util import find_spec
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import BACKEND_ROOT, get_settings

router = APIRouter(prefix="/api/connections", tags=["Local connections"])
ENV_PATH = BACKEND_ROOT / ".env"
_write_lock = RLock()
_login_task: asyncio.Task | None = None
_login_state = {"status": "idle", "message": ""}


class ApiKey(BaseModel):
    api_key: str = Field(min_length=1, max_length=4096)

    @field_validator("api_key")
    @classmethod
    def single_line(cls, value):
        value = value.strip()
        if not value or any(item in value for item in ("\r", "\n", "${")):
            raise ValueError("Use a single-line API key")
        return value


class ChatwootConnection(BaseModel):
    url: str = Field(max_length=2000)
    account_id: int = Field(ge=1)
    inbox_id: int = Field(ge=1)
    api_token: str | None = Field(default=None, max_length=4096)
    test_environment: bool = False

    @field_validator("url")
    @classmethod
    def origin_only(cls, value):
        value = value.strip().rstrip("/")
        parsed = urlsplit(value)
        parsed.port  # Reject malformed port numbers before saving the address.
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or parsed.path):
            raise ValueError("Use the Chatwoot base address")
        return value

    @field_validator("api_token")
    @classmethod
    def safe_token(cls, value):
        if value is None or not value.strip():
            return None  # A blank field preserves the saved token.
        return ApiKey(api_key=value).api_key


def refresh_settings():
    get_settings.cache_clear()
    return get_settings()


def connection_state() -> dict:
    settings = refresh_settings()
    browser = find_spec("playwright") is not None
    session = settings.browser_state_path.is_file()
    ready = all((settings.hcompany_api_key, settings.chatwoot_api_token, session,
                 settings.chatwoot_test_environment, browser))
    return {
        "model": {"provider": "H Company", "model": settings.hcompany_model,
                  "api_key_saved": bool(settings.hcompany_api_key)},
        "search": {"provider": "Linkup", "api_key_saved": bool(settings.linkup_api_key)},
        "chatwoot": {"url": settings.chatwoot_base_url, "account_id": settings.chatwoot_account_id,
                     "inbox_id": settings.chatwoot_inbox_id, "version": settings.chatwoot_version,
                     "api_token_saved": bool(settings.chatwoot_api_token), "session_saved": session,
                     "test_environment": settings.chatwoot_test_environment},
        "browser_installed": browser, "ready": bool(ready),
    }


def save_values(values: dict[str, str]) -> None:
    """One atomic replacement; preserve every unrelated setting and keep mode 0600."""
    with _write_lock:
        content = ENV_PATH.read_text() if ENV_PATH.exists() else ""
        for key, value in values.items():
            line = f"{key}={json.dumps(value)}"
            pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
            if pattern.search(content):
                content = pattern.sub(lambda _: line, content)
            else:
                content = content.rstrip("\n") + "\n" + line + "\n"
        ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=ENV_PATH.parent, prefix=".connection-", suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w") as file:
                file.write(content)
            os.chmod(temporary, 0o600)
            os.replace(temporary, ENV_PATH)
        finally:
            Path(temporary).unlink(missing_ok=True)
        get_settings.cache_clear()


def local_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin not in {"http://localhost:3000", "http://127.0.0.1:3000"}:
        raise HTTPException(403, "Open Connections in the local AppDNA app.")


async def parse_body(request: Request, model, message: str):
    local_origin(request)
    try:
        return model.model_validate(await request.json())
    except (ValidationError, ValueError, TypeError):
        # FastAPI's default validation errors can echo credential input. Keep this response secret-free.
        raise HTTPException(422, message) from None


@router.get("")
def connections():
    return connection_state()


@router.put("/model")
async def save_model(request: Request):
    body = await parse_body(request, ApiKey, "Enter a valid H Company API key on one line.")
    try:
        save_values({"HCOMPANY_API_KEY": body.api_key})
    except OSError:
        raise HTTPException(500, "The API key could not be saved. Check the backend folder permissions.") from None
    return connection_state()


@router.put("/search")
async def save_search(request: Request):
    body = await parse_body(request, ApiKey, "Enter a valid Linkup API key on one line.")
    try:
        save_values({"LINKUP_API_KEY": body.api_key})
    except OSError:
        raise HTTPException(500, "The search API key could not be saved.") from None
    return connection_state()


@router.put("/chatwoot")
async def save_chatwoot(request: Request):
    body = await parse_body(request, ChatwootConnection, "Check the Chatwoot address and account/inbox numbers.")
    settings = refresh_settings()
    if _login_task and not _login_task.done():
        raise HTTPException(409, "Finish or cancel the current sign-in first.")
    values = {"CHATWOOT_BASE_URL": body.url, "CHATWOOT_ACCOUNT_ID": str(body.account_id),
              "CHATWOOT_INBOX_ID": str(body.inbox_id),
              "CHATWOOT_TEST_ENVIRONMENT": str(body.test_environment).lower()}
    if body.api_token:
        values["CHATWOOT_API_TOKEN"] = body.api_token
    target_changed = (settings.chatwoot_base_url.rstrip("/"), settings.chatwoot_account_id) != (body.url, body.account_id)
    if target_changed and not body.api_token:
        values["CHATWOOT_API_TOKEN"] = ""  # Never reuse the previous account's verifier token.
    try:
        save_values(values)
        if target_changed and settings.browser_state_path.is_file():
            settings.browser_state_path.replace(settings.browser_state_path.with_suffix(".previous.json"))
    except OSError:
        raise HTTPException(500, "The Chatwoot connection could not be saved.") from None
    return connection_state()


async def browser_sign_in(settings):
    global _login_state
    _login_state = {"status": "opening", "message": "Opening Chatwoot…"}
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as runtime:
            browser = await runtime.chromium.launch(headless=False)
            try:
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(settings.chatwoot_base_url.rstrip("/") + "/auth/sign_in", timeout=15000)
                _login_state = {"status": "waiting", "message": "Finish signing in in the browser window."}
                target = re.escape(settings.chatwoot_base_url.rstrip("/")) + rf"/app/accounts/{settings.chatwoot_account_id}(?:/.*)?$"
                await page.wait_for_url(re.compile(target), timeout=180000)
                path = settings.browser_state_path
                path.parent.mkdir(parents=True, exist_ok=True)
                await context.storage_state(path=str(path))
                path.chmod(0o600)
                _login_state = {"status": "connected", "message": "Chatwoot sign-in saved."}
            finally:
                await browser.close()
    except asyncio.CancelledError:
        _login_state = {"status": "idle", "message": "Sign-in cancelled."}
        raise
    except Exception:
        _login_state = {"status": "failed", "message": "Sign-in was not completed. Check the Chatwoot address and try again."}


@router.post("/chatwoot/login")
async def start_login(request: Request):
    global _login_task, _login_state
    local_origin(request)
    settings = refresh_settings()
    if not settings.chatwoot_test_environment:
        raise HTTPException(400, "Select a test account before signing in.")
    if _login_task and not _login_task.done():
        raise HTTPException(409, "A Chatwoot sign-in is already open.")
    try:
        async with httpx.AsyncClient(timeout=4, follow_redirects=True) as client:
            response = await client.get(settings.chatwoot_base_url.rstrip("/") + "/auth/sign_in")
            response.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(503, "Chatwoot is not reachable at this address. Start Chatwoot or update its address.") from None
    if _login_task and not _login_task.done():
        raise HTTPException(409, "A Chatwoot sign-in is already open.")
    _login_state = {"status": "opening", "message": "Opening Chatwoot…"}
    _login_task = asyncio.create_task(browser_sign_in(settings))
    return _login_state


@router.get("/chatwoot/login")
def login_status():
    return _login_state


@router.delete("/chatwoot/login")
async def cancel_login(request: Request):
    local_origin(request)
    if _login_task and not _login_task.done():
        _login_task.cancel()
    return {"status": "idle", "message": "Sign-in cancelled."}
