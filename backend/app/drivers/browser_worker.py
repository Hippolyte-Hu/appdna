"""JSON-lines worker; stdout is reserved for protocol messages."""
import ipaddress
import json
import socket
import sys
from functools import lru_cache
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from app.targets import validate_web_target


@lru_cache(maxsize=512)
def public_host(host, port):
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(row[4][0]).is_global for row in addresses)
    except (OSError, ValueError):
        return False


def main():
    with sync_playwright() as engine:
        browser = engine.chromium.launch(headless=True, args=["--disable-quic"])
        context = browser.new_context(viewport={"width": 1440, "height": 900},
                                      accept_downloads=False, service_workers="block")
        page = context.new_page()
        page.set_default_timeout(10000)
        target_origin = None

        def guard(route):
            url = route.request.url
            parsed = urlsplit(url)
            host = parsed.hostname or ""
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            valid = parsed.scheme in {"http", "https"} and not parsed.username and not parsed.password
            valid = valid and public_host(host, port)
            if route.request.is_navigation_request() and route.request.frame == page.main_frame:
                # Stop cross-origin navigation; procurement exploration is not
                # permission to visit identity/payment providers or other apps.
                valid = valid and (parsed.scheme, parsed.netloc) == target_origin
            route.continue_() if valid else route.abort()

        context.route("**/*", guard)
        context.on("page", lambda popup: popup.close())
        keys = {"escape": "Escape", "return": "Enter", "tab": "Tab", "space": "Space",
                "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight"}
        for line in sys.stdin:
            try:
                request = json.loads(line)
                action = request["action"]
                result = {}
                if action == "open":
                    url = validate_web_target(request["url"])
                    parsed = urlsplit(url)
                    target_origin = (parsed.scheme, parsed.netloc)
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(500)
                elif action == "capture":
                    page.screenshot(path=request["path"], animations="disabled")
                elif action == "info":
                    result = {"title": page.title(), "url": page.url}
                elif action in {"click", "type"}:
                    if page.locator('input[type="password"]:visible').count():
                        raise ValueError("Authentication required. Use an authorized signed-in test session; AppDNA will not enter credentials.")
                    if action == "click":
                        page.mouse.click(request["x"], request["y"], click_count=2 if request.get("double") else 1)
                    else:
                        page.keyboard.insert_text(request["text"])
                    page.wait_for_timeout(250)
                elif action == "key":
                    page.keyboard.press(keys[request["name"]])
                elif action == "scroll":
                    page.mouse.wheel(0, -540 if request["direction"] == "up" else 540)
                    page.wait_for_timeout(200)
                else:
                    raise ValueError("Unsupported browser operation")
                print(json.dumps(result), flush=True)
            except Exception as exc:
                # No URLs/credentials or arbitrary browser content in errors.
                message = str(exc) if isinstance(exc, ValueError) else f"Website operation failed ({type(exc).__name__}). Check public reachability or an authentication gate."
                print(json.dumps({"error": message}), flush=True)
        browser.close()


if __name__ == "__main__":
    main()
