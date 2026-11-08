"""Isolated, ephemeral browser driven by real CDP mouse/keyboard events.

The synchronous worker lives outside the API's asyncio loop. No user Chrome
profile, cookies, or authenticated browser state is accessed.
"""
import json
import select
import subprocess
import sys
from pathlib import Path

from app.drivers.macos import VisualExploreError, WindowBounds
from app.targets import validate_web_target


class BrowserDriver:
    def __init__(self, url: str):
        self.url = validate_web_target(url)
        self.process = None

    def _call(self, action, **kwargs):
        if self.process is None:
            self.process = subprocess.Popen(
                [sys.executable, "-m", "app.drivers.browser_worker"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1,
            )
        assert self.process.stdin is not None and self.process.stdout is not None
        try:
            self.process.stdin.write(json.dumps({"action": action, **kwargs}) + "\n")
            self.process.stdin.flush()
            if not select.select([self.process.stdout], [], [], 60)[0]:
                raise VisualExploreError("Website browser did not respond within 60 seconds")
            line = self.process.stdout.readline()
            if not line:
                raise VisualExploreError("Website browser stopped unexpectedly")
            result = json.loads(line)
            if "error" in result:
                raise VisualExploreError(result["error"])
            return result
        except (OSError, ValueError) as exc:
            raise VisualExploreError("Website browser communication failed") from exc

    def focus(self, _name):
        try:
            self._call("open", url=self.url)
            return self.bounds(_name)
        except Exception:
            self.close()
            raise

    def bounds(self, _name):
        return WindowBounds(0, 0, 1440, 900)

    def capture(self, _bounds, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._call("capture", path=str(path.resolve()))
        return path, 1440, 900

    def page_info(self):
        return self._call("info")

    def click(self, x, y, *, double=False):
        if not (0 <= x < 1440 and 0 <= y < 900):
            raise VisualExploreError("Click is outside the website viewport")
        self._call("click", x=x, y=y, double=double)

    def key(self, name):
        self._call("key", name=name)

    def type_text(self, text):
        self._call("type", text=text)

    def scroll(self, _bounds, direction):
        self._call("scroll", direction=direction)

    def close(self):
        if self.process is not None and self.process.poll() is None:
            if self.process.stdin is not None:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)
