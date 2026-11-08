"""Bounded local FFmpeg preparation of authorized uploaded recordings."""
import hashlib
import json
import math
import subprocess
from pathlib import Path

MAX_DURATION = 600
MAX_FRAMES = 20


def _run(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=90, check=True).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Could not process the uploaded recording with FFmpeg") from exc


def prepare_media(source: Path, folder: Path) -> dict:
    if not source.is_file():
        raise ValueError("Uploaded recording is missing")
    folder.mkdir(parents=True, exist_ok=True)
    raw = _run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams", "-of", "json", str(source)])
    try:
        probe = json.loads(raw)
        duration = float(probe["format"]["duration"])
        if not math.isfinite(duration) or not 0 < duration <= MAX_DURATION:
            raise ValueError("Recording must be between 0 and 600 seconds")
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Recording has no valid duration") from exc
    streams = probe.get("streams", [])
    has_video = any(s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic") for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if not has_video and not has_audio:
        raise ValueError("Recording has no audio or video stream")
    manifest = {"duration": duration, "has_video": has_video, "has_audio": has_audio,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "audio_path": None, "frames": []}
    base = ["ffmpeg", "-v", "error", "-y", "-protocol_whitelist", "file,pipe"]
    if has_audio:
        audio = folder / "audio.wav"
        _run([*base, "-i", str(source), "-vn", "-ar", "16000", "-ac", "1", str(audio)])
        manifest["audio_path"] = str(audio)
    if has_video:
        count = min(MAX_FRAMES, max(1, math.ceil(duration / 8)))
        for index in range(count):
            timestamp = round(index * duration / count, 3)
            name = f"frame_{index:03d}.jpg"
            _run([*base, "-ss", str(timestamp), "-i", str(source), "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "3", str(folder / name)])
            if not (folder / name).is_file():
                raise ValueError("FFmpeg did not produce an expected video frame")
            manifest["frames"].append({"timestamp": timestamp, "image": name})
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
