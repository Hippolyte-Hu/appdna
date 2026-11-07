import ctypes
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

ALLOWED_ACTIONS = {"click", "double_click", "type", "key", "scroll", "wait", "done"}
ALLOWED_KEYS = {"return", "escape", "tab", "space", "up", "down", "left", "right"}
BLOCKED_TEXT = ("delete", "remove all", "format disk", "sudo", "password", "quit", "send", "pay", "purchase")
KEY_CODES = {
    "return": 36,
    "escape": 53,
    "tab": 48,
    "space": 49,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
}


class VisualExploreError(Exception):
    pass


class UnsafeAction(Exception):
    pass


@dataclass
class WindowBounds:
    x: int
    y: int
    width: int
    height: int


def assert_safe(action: dict) -> None:
    name = str(action.get("action") or "")
    if name not in ALLOWED_ACTIONS:
        raise UnsafeAction(f"action not allowed: {name}")
    text = str(action.get("text") or "")
    lowered = text.lower()
    if any(token in lowered for token in BLOCKED_TEXT):
        raise UnsafeAction("that action can change or destroy data, so it was not executed")
    if name == "key" and lowered not in ALLOWED_KEYS:
        raise UnsafeAction("only navigation keys are allowed")
    if name == "type" and len(text) > 120:
        raise UnsafeAction("typed text is too long")


def map_click(image_x: int, image_y: int, image_width: int, image_height: int, bounds: WindowBounds) -> tuple[int, int]:
    if image_width <= 0 or image_height <= 0:
        raise UnsafeAction("screenshot has no size")
    if not (0 <= image_x < image_width and 0 <= image_y < image_height):
        raise UnsafeAction("click is outside the application window")
    screen_x = bounds.x + image_x * bounds.width / image_width
    screen_y = bounds.y + image_y * bounds.height / image_height
    return int(screen_x), int(screen_y)


class MacOSDriver:
    """Sees one application window and clicks only inside it."""

    def focus(self, app_name: str) -> WindowBounds:
        _reject_unsafe_name(app_name)
        ensure_accessibility()
        launched = _launch(app_name)
        time.sleep(1.4)
        bounds = self.bounds(launched)
        if bounds is None:
            bounds = self.bounds(app_name)
        if bounds is None:
            raise VisualExploreError(f"Opened {launched}, but no window appeared to click.")
        return bounds

    def bounds(self, app_name: str) -> WindowBounds | None:
        _reject_unsafe_name(app_name)
        script = f'''
        tell application "System Events"
          if not (exists process "{app_name}") then return "missing"
          tell process "{app_name}"
            set frontmost to true
            if (count of windows) is 0 then return "nowindow"
            set p to position of window 1
            set s to size of window 1
            return (item 1 of p as text) & "," & (item 2 of p as text) & "," & (item 1 of s as text) & "," & (item 2 of s as text)
          end tell
        end tell
        '''
        result = _osascript(script)
        if result in {"missing", "nowindow", ""} or result.startswith("error"):
            return None
        parts = [int(float(item)) for item in result.split(",")]
        if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
            return None
        return WindowBounds(*parts)

    def capture(self, bounds: WindowBounds, path: Path) -> tuple[Path, int, int]:
        path.parent.mkdir(parents=True, exist_ok=True)
        region = f"{bounds.x},{bounds.y},{bounds.width},{bounds.height}"
        completed = subprocess.run(
            ["screencapture", "-x", "-R", region, str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 or not path.exists():
            raise VisualExploreError(completed.stderr.strip() or "screen capture failed")
        _limit_image_size(path, 1440)
        return path, *_image_size(path)

    def click(self, x: int, y: int, *, double: bool = False) -> None:
        ensure_accessibility()
        _post_click(int(x), int(y), double=double)

    def type_text(self, text: str) -> None:
        escaped = _apple_string(text)
        _osascript(f'tell application "System Events" to keystroke "{escaped}"')

    def key(self, name: str) -> None:
        code = KEY_CODES[name.lower()]
        _osascript(f"tell application \"System Events\" to key code {code}")

    def scroll(self, bounds: WindowBounds, direction: str) -> None:
        ensure_accessibility()
        anchor_x = bounds.x + bounds.width // 2
        anchor_y = bounds.y + bounds.height // 2
        # Positive line deltas reveal what is above; negative deltas reveal what is below.
        lines = 6 if direction.lower() == "up" else -6
        _post_scroll(anchor_x, anchor_y, lines)


def ensure_accessibility() -> None:
    app_services = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
    app_services.AXIsProcessTrusted.restype = ctypes.c_bool
    if app_services.AXIsProcessTrusted():
        return
    _prompt_accessibility()
    raise VisualExploreError(
        "macOS has not allowed this API process to control the mouse. "
        "In Privacy & Security → Accessibility, enable the Python or Cursor process that runs AppDNA, then start the learning run again."
    )


def _prompt_accessibility() -> None:
    try:
        core = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        app_services = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        core.CFStringCreateWithCString.restype = ctypes.c_void_p
        core.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        core.CFDictionaryCreate.restype = ctypes.c_void_p
        core.CFDictionaryCreate.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        app_services.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        app_services.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        key = core.CFStringCreateWithCString(None, b"AXTrustedCheckOptionPrompt", 0x08000100)
        value = ctypes.c_void_p.in_dll(core, "kCFBooleanTrue")
        keys = (ctypes.c_void_p * 1)(key)
        values = (ctypes.c_void_p * 1)(value)
        options = core.CFDictionaryCreate(None, keys, values, 1, None, None)
        app_services.AXIsProcessTrustedWithOptions(options)
    except (AttributeError, OSError):
        return


def _launch(app_name: str) -> str:
    direct = subprocess.run(["open", "-a", app_name], check=False, capture_output=True, text=True)
    if direct.returncode == 0:
        return app_name
    bundle = _find_app_bundle(app_name)
    if bundle is None:
        raise VisualExploreError(
            f"No Mac application named {app_name} is installed. Use the name shown in the menu bar, for example VoiceCue."
        )
    opened = subprocess.run(["open", bundle], check=False, capture_output=True, text=True)
    if opened.returncode != 0:
        raise VisualExploreError(f"Could not open {bundle}.")
    return Path(bundle).stem


def _find_app_bundle(app_name: str) -> str | None:
    safe = app_name.replace('"', "")
    query = f'kMDItemContentType == "com.apple.application-bundle" && kMDItemDisplayName == "{safe}"c'
    found = subprocess.run(["mdfind", query], check=False, capture_output=True, text=True)
    paths = [line.strip() for line in found.stdout.splitlines() if line.strip().endswith(".app")]
    paths.sort(key=lambda path: ("backup" in path.lower(), "application support" in path.lower(), len(path)))
    return paths[0] if paths else None


def _post_click(x: int, y: int, *, double: bool) -> None:
    graphics = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")

    class CGPoint(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

    graphics.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    graphics.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
    graphics.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    graphics.CFRelease.argtypes = [ctypes.c_void_p]

    def post(kind: int, point: CGPoint) -> None:
        event = graphics.CGEventCreateMouseEvent(None, kind, point, 0)
        if not event:
            raise VisualExploreError("macOS did not create a mouse event")
        graphics.CGEventPost(0, event)
        graphics.CFRelease(event)

    target = CGPoint(float(x), float(y))
    post(5, target)
    time.sleep(0.08)
    repeats = 2 if double else 1
    for _ in range(repeats):
        post(1, target)
        time.sleep(0.04)
        post(2, target)
        time.sleep(0.08)


def _post_scroll(x: int, y: int, lines: int) -> None:
    graphics = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")

    class CGPoint(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

    graphics.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    graphics.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
    graphics.CGEventCreateScrollWheelEvent.restype = ctypes.c_void_p
    graphics.CGEventCreateScrollWheelEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int32]
    graphics.CGEventSetLocation.argtypes = [ctypes.c_void_p, CGPoint]
    graphics.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    graphics.CFRelease.argtypes = [ctypes.c_void_p]

    point = CGPoint(float(x), float(y))
    moved = graphics.CGEventCreateMouseEvent(None, 5, point, 0)
    if not moved:
        raise VisualExploreError("macOS did not create a mouse event")
    graphics.CGEventPost(0, moved)
    graphics.CFRelease(moved)
    time.sleep(0.08)
    for _ in range(2):
        event = graphics.CGEventCreateScrollWheelEvent(None, 1, 1, int(lines))
        if not event:
            raise VisualExploreError("macOS did not create a scroll event")
        graphics.CGEventSetLocation(event, point)
        graphics.CGEventPost(0, event)
        graphics.CFRelease(event)
        time.sleep(0.12)


def _reject_unsafe_name(app_name: str) -> None:
    if not app_name or re.search(r'["\\\n]', app_name):
        raise VisualExploreError("application name contains unsupported characters")


def _osascript(script: str) -> str:
    completed = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "osascript failed").strip()
        if "not allowed assistive" in message or "1002" in message:
            raise VisualExploreError(
                "macOS blocked AppDNA from seeing or clicking the app. "
                "Open System Settings, Privacy & Security, Accessibility, and allow Cursor or the terminal running the API."
            )
        return "error"
    return completed.stdout.strip()


def _apple_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _image_size(path: Path) -> tuple[int, int]:
    completed = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    width = _sips_value(completed.stdout, "pixelWidth")
    height = _sips_value(completed.stdout, "pixelHeight")
    if width <= 0 or height <= 0:
        raise VisualExploreError("could not read the screenshot size")
    return width, height


def _sips_value(output: str, key: str) -> int:
    for line in output.splitlines():
        if key in line and ":" in line:
            return int(line.split(":")[-1].strip())
    return 0


def _limit_image_size(path: Path, longest: int) -> None:
    width, height = _image_size(path)
    if max(width, height) <= longest:
        return
    subprocess.run(["sips", "-Z", str(longest), str(path)], check=False, capture_output=True)
