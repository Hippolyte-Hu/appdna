"""Generated media below is a labeled test fixture, never demo evidence."""
import json
import subprocess
import pytest
from app.engines.media import prepare_media


def test_ffmpeg_splits_real_streams_and_keeps_timestamps(tmp_path):
    video = tmp_path / "fixture.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=10", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000", "-t", "2", "-c:v", "libx264", "-c:a", "aac", str(video)], check=True)
    media = prepare_media(video, tmp_path / "out")
    assert media["duration"] == pytest.approx(2, abs=0.1)
    assert media["has_video"] is True
    assert media["audio_path"] and media["frames"]
    assert media["frames"][0]["timestamp"] == 0
    assert all(0 <= frame["timestamp"] < media["duration"] for frame in media["frames"])
    assert (tmp_path / "out" / media["frames"][0]["image"]).is_file()
    assert json.loads((tmp_path / "out" / "manifest.json").read_text())["source_sha256"]


def test_invalid_media_is_rejected_without_reading_arbitrary_urls(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_text("not video")
    with pytest.raises(ValueError):
        prepare_media(bad, tmp_path / "out")
