"""A scoped browser surface. The model gets screenshots/visible controls, never an API client."""

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit



class BrowserBlocked(Exception):
    pass


def prohibited_routing_action(label: str) -> bool:
    return bool(re.search(r"\b(delete|send\s+(?:(?:a|an)\s+)?(?:email|message|attachment)|webhook|sign\s*out)\b",
                          " ".join(label.casefold().split())))


def safe_ui_url(url: str, base_url: str, account_id: int) -> str:
    target, base = urlsplit(url), urlsplit(base_url)
    if target.scheme not in {"http", "https"} or (target.scheme, target.netloc) != (base.scheme, base.netloc):
        raise BrowserBlocked("Navigation is restricted to the designated Chatwoot test environment.")
    if target.username or target.password or target.query or target.fragment:
        raise BrowserBlocked("Use a Chatwoot UI URL without credentials, query parameters or fragments.")
    decoded = unquote(target.path)
    if "\\" in decoded or any(part in {".", ".."} for part in decoded.split("/")):
        raise BrowserBlocked("Navigation cannot escape the designated account path.")
    account_path = f"/app/accounts/{account_id}"
    if not (target.path == account_path or target.path.startswith(account_path + "/")):
        raise BrowserBlocked("Only the designated account's UI may be navigated. API and login URLs are unavailable to the agent.")
    return url


class BrowserDriver:
    def __init__(self, base_url: str, account_id: int, storage_state: Path, folder: Path, headless: bool = True,
                 *, start_url: str | None = None, protect_conversations: bool = False):
        self.base_url = base_url.rstrip("/")
        self.account_id = account_id
        self.storage_state = storage_state
        self.folder = folder
        self.headless = headless
        self.start_url = start_url or f"{self.base_url}/app/accounts/{account_id}/dashboard"
        self.protect_conversations = protect_conversations
        self.page = None
        self.context = None
        self.browser = None
        self.runtime = None
        self.controls: dict[int, dict] = {}

    async def __aenter__(self):
        from playwright.async_api import async_playwright

        self.runtime = await async_playwright().start()
        try:
            self.browser = await self.runtime.chromium.launch(headless=self.headless)
            self.context = await self.browser.new_context(storage_state=str(self.storage_state), viewport={"width": 1280, "height": 800})
            origin = urlsplit(self.base_url).netloc

            async def scope(route):
                # Chatwoot's own frontend is allowed to use its APIs. The agent cannot call them directly.
                if urlsplit(route.request.url).netloc != origin:
                    await route.abort()
                else:
                    await route.continue_()

            await self.context.route("**/*", scope)
            self.page = await self.context.new_page()
            self.page.set_default_timeout(8000)
            self.validate_observation_url(self.start_url)
            await self.page.goto(self.start_url, wait_until="domcontentloaded")
            return self
        except Exception:
            await self.__aexit__(None, None, None)
            raise

    async def __aexit__(self, *_):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.runtime:
            await self.runtime.stop()

    def validate_observation_url(self, url: str):
        safe_ui_url(url, self.base_url, self.account_id)
        settings_path = f"/app/accounts/{self.account_id}/settings"
        path = urlsplit(url).path
        if self.protect_conversations and not (path == settings_path or path.startswith(settings_path + "/")):
            raise BrowserBlocked("Verification inputs are protected. Resume from an actually observed account settings page.")

    async def observe(self, step: int) -> dict:
        self.validate_observation_url(self.page.url)
        if await self.page.locator('input[type="password"]').count():
            raise BrowserBlocked("The browser session needs a fresh administrator login. Run the login helper.")
        controls = await self.page.evaluate("""() => {
          document.querySelectorAll('[data-appdna-target]').forEach(el => el.removeAttribute('data-appdna-target'));
          const items = [...document.querySelectorAll('button,a,input,textarea,select,[role="button"],[role="combobox"],[role="option"],[role="tab"],[role="checkbox"]')];
          return items.filter(el => {
            const r = el.getBoundingClientRect();
            const x = Math.max(0, Math.min(innerWidth - 1, r.x + r.width / 2));
            const y = Math.max(0, Math.min(innerHeight - 1, r.y + r.height / 2));
            const hit = document.elementFromPoint(x, y);
            return r.width > 0 && r.height > 0 && r.top < innerHeight && r.bottom > 0 && r.left < innerWidth && r.right > 0 &&
              getComputedStyle(el).visibility !== 'hidden' && !el.disabled && el.type !== 'password' && el.type !== 'hidden' &&
              hit && (el === hit || el.contains(hit));
          }).slice(0, 100).map((el, i) => {
            el.setAttribute('data-appdna-target', String(i + 1));
            const r = el.getBoundingClientRect();
            const visibleText = el.tagName === 'SELECT' ? el.selectedOptions?.[0]?.textContent : el.innerText;
            const label = el.getAttribute('aria-label') || el.labels?.[0]?.innerText || visibleText || el.getAttribute('placeholder') || el.getAttribute('title') || el.name || el.tagName;
            let href = null;
            if (el.tagName === 'A') { const url = new URL(el.href, location.origin); if (url.origin === location.origin && !url.search && !url.hash) href = url.href; }
            return {id: i + 1, tag: el.tagName.toLowerCase(), role: el.getAttribute('role'), label: label.trim().slice(0, 240), href,
              bounds: {x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height)},
              options: el.tagName === 'SELECT' ? [...el.options].map(o => ({label: o.text, value: o.value})) : []};
          });
        }""")
        self.controls = {item["id"]: item for item in controls}
        self.folder.mkdir(parents=True, exist_ok=True)
        name = f"step_{step:03d}.png"
        image = await self.page.screenshot(path=str(self.folder / name), animations="disabled")
        return {"step": step, "image": name, "checksum": hashlib.sha256(image).hexdigest(),
                "image_width": 1280, "image_height": 800, "url": self.page.url,
                "title": await self.page.title(), "controls": controls}

    async def execute(self, action: dict) -> str:
        safe_ui_url(self.page.url, self.base_url, self.account_id)
        kind, text = action.get("kind"), str(action.get("text") or "")
        if kind == "navigate":
            await self.page.goto(safe_ui_url(text, self.base_url, self.account_id), wait_until="domcontentloaded")
        elif kind in {"click", "type", "select"}:
            target = action.get("target")
            if target not in self.controls:
                raise ValueError("The requested control was not in the current observation. Observe again.")
            control = self.controls[target]
            # Opening a select does not choose every option in its menu. Validate
            # the requested option on selection, and actionable labels on clicks.
            if (kind == "select" and prohibited_routing_action(text)) or (
                kind == "click" and control["tag"] != "select" and prohibited_routing_action(control["label"])
            ):
                raise BrowserBlocked("The requested control is outside routing configuration permissions.")
            locator = self.page.locator(f'[data-appdna-target="{target}"]')
            if kind == "click":
                await locator.click()
            elif kind == "type":
                if len(text) > 1200 or control["tag"] not in {"input", "textarea"}:
                    raise BrowserBlocked("Typing is limited to observed input fields and 1200 characters.")
                await locator.fill(text)
            else:
                await locator.select_option(label=text)
        elif kind == "key":
            if text not in {"Tab", "Enter", "Escape", "ArrowDown", "ArrowUp", "Space"}:
                raise BrowserBlocked("Only navigation and selection keys are available.")
            await self.page.keyboard.press(text)
        elif kind == "scroll":
            await self.page.mouse.wheel(0, -600 if text == "up" else 600)
        elif kind == "wait":
            await self.page.wait_for_timeout(600)
        else:
            raise BrowserBlocked("Unsupported browser action.")
        await self.page.wait_for_timeout(350)
        return "UI action executed; outcome requires the next observation and independent verification."
