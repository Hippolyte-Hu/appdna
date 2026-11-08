"""User performs login; the agent never receives the password or saved session."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from playwright.async_api import async_playwright


async def main():
    settings = get_settings()
    if not settings.chatwoot_test_environment:
        raise SystemExit("Configure a synthetic Chatwoot sandbox and CHATWOOT_TEST_ENVIRONMENT=true first.")
    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(settings.chatwoot_base_url.rstrip('/') + '/auth/sign_in')
        print("Complete the local administrator login in the opened browser. No credentials are sent to a model.")
        await asyncio.to_thread(input, "After the account dashboard is visible, press Enter here to save the local session: ")
        expected = f"{settings.chatwoot_base_url.rstrip('/')}/app/accounts/{settings.chatwoot_account_id}"
        if not (page.url == expected or page.url.startswith(expected + '/')):
            await browser.close()
            raise SystemExit("The designated account dashboard is not open. Session was not saved.")
        path = settings.browser_state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(path))
        path.chmod(0o600)
        await browser.close()
        print("Saved the local browser session. Return to AppDNA Settings to check the connection.")


if __name__ == '__main__':
    asyncio.run(main())
