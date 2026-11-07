import json
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def loads(raw: str, fallback):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self.parts.append(text)


def html_to_text(html: str, limit: int = 12000) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    return text[:limit]


def strip_code_fence(script: str) -> str:
    text = script.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


_VERSION_RE = re.compile(r"\b(\d+\.\d+(?:\.\d+)?|latest|current)\b", re.I)


def infer_version(*chunks: str | None) -> str | None:
    for chunk in chunks:
        if not chunk:
            continue
        match = _VERSION_RE.search(chunk)
        if match:
            return match.group(1)
    return None


def classify_url(url: str) -> tuple[str, str]:
    host = url.lower()
    if "docs.blender.org" in host or "developer.blender.org" in host:
        return "official_documentation", "high"
    if "github.com" in host or "gitlab.com" in host:
        return "github_repository", "medium"
    if any(token in host for token in ("youtube.com", "youtu.be", "vimeo.com")):
        return "video", "low"
    if any(token in host for token in ("forum", "stackexchange", "reddit.com")):
        return "forum", "low"
    if any(token in host for token in ("tutorial", "blog", "medium.com")):
        return "tutorial", "medium"
    return "article", "medium"


RELIABILITY_RANK = {"high": 0, "medium": 1, "low": 2}
