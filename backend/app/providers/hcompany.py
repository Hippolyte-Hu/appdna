import base64
import json

import httpx

from app.providers.base import ProviderError

_CONTROL_LIST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "controls": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string"},
                    "cell": {"type": "integer"},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["label", "cell", "x", "y"],
            },
        },
        "more": {"type": "string", "enum": ["down", "up", "none"]},
    },
    "required": ["controls", "more"],
}

_ONE_CONTROL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "cell": {"type": "integer"},
        "x": {"type": "integer"},
        "y": {"type": "integer"},
    },
    "required": ["cell", "x", "y"],
}

_CLICK_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"learned": {"type": "string"}},
    "required": ["learned"],
}

_COMPARE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "matches": {"type": "boolean"},
        "complete": {"type": "boolean"},
        "note": {"type": "string"},
    },
    "required": ["matches", "complete", "note"],
}

COMPUTER_ACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["name", "arguments"],
            },
        }
    },
    "required": ["actions"],
}


class HCompanyProvider:
    """OpenAI-compatible H Models API. Model, base URL, and request shape stay here."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def build_chat_request(self, messages: list[dict], schema: dict | None, schema_name: str) -> dict:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "reasoning_effort": "none",
            "max_tokens": 4096,
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            }
        return body

    async def complete_json(self, instructions: str, schema: dict, schema_name: str) -> dict:
        if not self.api_key:
            raise ProviderError("HCOMPANY_API_KEY is not configured")
        messages = [
            {
                "role": "system",
                "content": "You extract structured software knowledge. Return only the JSON object.",
            },
            {"role": "user", "content": instructions},
        ]
        try:
            content = await self._post(self.build_chat_request(messages, schema, schema_name))
        except ProviderError as exc:
            if exc.status != 400:
                raise
            reminder = (
                instructions
                + "\n\nReturn one JSON object matching this schema:\n"
                + json.dumps(schema)
            )
            content = await self._post(
                self.build_chat_request(
                    [
                        messages[0],
                        {"role": "user", "content": reminder},
                    ],
                    None,
                    schema_name,
                )
            )
        return _parse_json(content)

    async def list_controls(
        self, *, software: str, objective: str, image_bytes: bytes, already: list[str]
    ) -> tuple[list[dict], str]:
        tried = ", ".join(already) or "nothing"
        instructions = (
            f"The image is the live Mac app {software}. A green number marks every cell.\n"
            f"Learning objective: {objective}\n"
            "List every visible button, tab, menu item, or icon control in this window. "
            "Do not list captions, paragraphs, status text, or the window close/minimize/zoom buttons. "
            "Do not invent a control that is not drawn. "
            "cell is the green number closest to that control. "
            "x and y are a 0 to 1000 grid, not pixels: x=0 is the left edge, x=1000 the right edge, y=0 the top, y=1000 the bottom. "
            "A control near the right side has a large x. Put the point on the control itself. "
            f"Already clicked: {tried}. Include a control again only if it is still visible.\n"
            "If a list, form, or scrollbar continues past the bottom, set more to down. "
            "If content is cut off at the top, set more to up. "
            "If this view already shows the whole page, set more to none.\n"
            "Return at most 12 controls."
        )
        parsed = await self._look(instructions, [image_bytes], _CONTROL_LIST_SCHEMA, "visible_controls")
        more = str(parsed.get("more") or "none").strip().lower()
        if more not in {"down", "up", "none"}:
            more = "none"
        controls = parsed.get("controls")
        if not isinstance(controls, list):
            return [], more
        clean = []
        for item in controls:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            clean.append(
                {
                    "label": label[:80],
                    "cell": int(item.get("cell") or 1),
                    "x": int(item.get("x") or 0),
                    "y": int(item.get("y") or 0),
                }
            )
        return clean[:12], more

    async def compare_with_documents(
        self,
        *,
        software: str,
        objective: str,
        image_bytes: bytes,
        documents: str,
    ) -> dict:
        instructions = (
            f"The image is the live local Mac application {software}.\n"
            f"Learning objective: {objective}\n"
            "Compare this window with the documents below.\n"
            "matches is true only when this window is the same product the documents describe. "
            "A different product that merely shares the name is false.\n"
            "complete is true only when the documents explain the controls on this screen and fully cover the learning objective. "
            "If the screen shows a control, panel, or behavior the documents do not explain, complete is false.\n"
            "note is one sentence.\n\n"
            f"Documents:\n{documents[:6000]}"
        )
        parsed = await self._look(instructions, [image_bytes], _COMPARE_SCHEMA, "document_check")
        return {
            "matches": bool(parsed.get("matches")),
            "complete": bool(parsed.get("complete")),
            "note": str(parsed.get("note") or "").strip()[:300],
        }

    async def describe_click(self, *, software: str, label: str, before: bytes, after: bytes) -> str:
        instructions = (
            f"Image 1 is {software} before the control “{label}” was pressed. Image 2 is immediately after.\n"
            "Write one sentence on what that control did. "
            "If the interface did not respond, start with “没点中”."
        )
        parsed = await self._look(instructions, [before, after], _CLICK_RESULT_SCHEMA, "click_result")
        return str(parsed.get("learned") or "").strip()[:240]

    async def correct_point(self, *, software: str, label: str, image_bytes: bytes) -> dict:
        instructions = (
            f"The last click missed “{label}” in {software}. The green numbers are cell ids.\n"
            "Return the cell number on that control, and x,y from 0 to 1000 at its center."
        )
        parsed = await self._look(instructions, [image_bytes], _ONE_CONTROL_SCHEMA, "corrected_control")
        return {
            "label": label,
            "cell": int(parsed.get("cell") or 1),
            "x": int(parsed.get("x") or 0),
            "y": int(parsed.get("y") or 0),
        }

    async def _look(self, instructions: str, images: list[bytes], schema: dict, schema_name: str) -> dict:
        if not self.api_key:
            raise ProviderError("HCOMPANY_API_KEY is not configured")
        content: list[dict] = [{"type": "text", "text": instructions}]
        for blob in images:
            encoded = base64.standard_b64encode(blob).decode("ascii")
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}})
        messages = [
            {
                "role": "system",
                "content": "You learn software by looking at it. Return only the JSON object.",
            },
            {"role": "user", "content": content},
        ]
        try:
            raw = await self._post(self.build_chat_request(messages, schema, schema_name))
        except ProviderError as exc:
            if exc.status != 400:
                raise
            raw = await self._post(self.build_chat_request(messages, None, schema_name))
        return _parse_json(raw)

    async def propose_computer_actions(self, observation: str) -> dict:
        """Computer-use request shape. The MVP executor does not call this."""
        instructions = (
            "Given the software observation, propose the next low-risk computer-use actions. "
            f"Observation:\n{observation}"
        )
        return await self.complete_json(instructions, COMPUTER_ACTION_SCHEMA, "computer_actions")

    async def _post(self, body: dict) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        if response.status_code >= 400:
            detail = response.text[:300].replace(self.api_key, "[redacted]")
            raise ProviderError(
                f"H Company request failed ({response.status_code}): {detail}",
                status=response.status_code,
            )
        payload = response.json()
        try:
            content = payload["choices"][0]["message"].get("content")
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("H Company response did not include message content") from exc
        if not content:
            raise ProviderError("H Company returned an empty message")
        return content


def _parse_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError("H Company did not return valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ProviderError("H Company JSON response was not an object")
    return parsed
