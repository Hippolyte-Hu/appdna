import asyncio
from pathlib import Path

import httpx

from app.providers.base import ProviderError


def extract_segments(payload: dict) -> list[dict]:
    transcription = _find_transcription(payload)
    utterances = transcription.get("utterances") if isinstance(transcription, dict) else None
    if not isinstance(utterances, list):
        return []
    segments = []
    for item in utterances:
        if not isinstance(item, dict) or not item.get("text"):
            continue
        speaker = item.get("speaker")
        segments.append(
            {
                "text": str(item["text"]).strip(),
                "start": float(item.get("start") or 0),
                "end": float(item.get("end") or 0),
                "speaker": speaker if isinstance(speaker, int) else None,
                "language": item.get("language"),
            }
        )
    return [segment for segment in segments if segment["text"]]


def _find_transcription(payload: dict) -> dict:
    result = payload.get("result")
    if isinstance(result, dict) and isinstance(result.get("transcription"), dict):
        return result["transcription"]
    if isinstance(payload.get("transcription"), dict):
        return payload["transcription"]
    return {}


class GladiaProvider:
    """Pre-recorded transcription via Gladia v2 upload and /v2/pre-recorded."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {"x-gladia-key": self.api_key}

    async def transcribe_url(self, audio_url: str) -> list[dict]:
        return await self._transcribe(audio_url)

    async def transcribe_file(self, path: Path) -> list[dict]:
        audio_url = await self._upload(path)
        return await self._transcribe(audio_url)

    async def _upload(self, path: Path) -> str:
        if not self.api_key:
            raise ProviderError("GLADIA_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=120) as client:
            with path.open("rb") as handle:
                response = await client.post(
                    f"{self.base_url}/v2/upload",
                    headers=self._headers(),
                    files={"audio": (path.name, handle, "application/octet-stream")},
                )
        if response.status_code >= 400:
            raise ProviderError(
                f"Gladia upload failed ({response.status_code})",
                status=response.status_code,
            )
        audio_url = response.json().get("audio_url")
        if not audio_url:
            raise ProviderError("Gladia upload did not return audio_url")
        return audio_url

    async def _transcribe(self, audio_url: str) -> list[dict]:
        if not self.api_key:
            raise ProviderError("GLADIA_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=60) as client:
            created = await client.post(
                f"{self.base_url}/v2/pre-recorded",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"audio_url": audio_url, "diarization": True},
            )
            if created.status_code >= 400:
                raise ProviderError(
                    f"Gladia transcription failed ({created.status_code})",
                    status=created.status_code,
                )
            job_id = created.json().get("id")
            if not job_id:
                raise ProviderError("Gladia did not return a transcription id")
            for _ in range(90):
                polled = await client.get(
                    f"{self.base_url}/v2/pre-recorded/{job_id}",
                    headers=self._headers(),
                )
                if polled.status_code >= 400:
                    raise ProviderError(
                        f"Gladia poll failed ({polled.status_code})",
                        status=polled.status_code,
                    )
                payload = polled.json()
                status = payload.get("status")
                if status == "done":
                    return extract_segments(payload)
                if status == "error":
                    raise ProviderError("Gladia transcription returned an error")
                await asyncio.sleep(2)
        raise ProviderError("Gladia transcription timed out")
