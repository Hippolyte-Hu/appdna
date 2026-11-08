"""Bounded Holo function-calling conversation for the UI-only browser executor."""

import base64
import json

from app.providers.base import ProviderError

_DESCRIPTIONS = {
    "click": "Click a currently observed control, using its numeric target id.",
    "type": "Replace the value of a currently observed input/textarea with text.",
    "select": "Choose text as a visible option label in a native HTML select. For custom dropdowns use click, then observe the options.",
    "key": "Press one navigation/selection key in the focused control.",
    "scroll": "Scroll the current browser viewport up or down.",
    "navigate": "Open an account UI URL actually observed in the controls. External, API and login URLs are forbidden.",
    "wait": "Briefly wait for the visible interface to finish rendering.",
    "research": "Look up a new unanswered question in official documentation. Do not repeat an already covered query.",
}


def browser_tools(allow_research: bool) -> list[dict]:
    tools = []
    for name, description in _DESCRIPTIONS.items():
        if name == "research" and not allow_research:
            continue
        properties = {"summary": {"type": "string", "description": "Brief observable action description, without private reasoning."}}
        if name in {"click", "type", "select"}:
            properties["target"] = {"type": "integer", "minimum": 1, "description": "Control id from the current observation."}
        if name in {"type", "select", "key", "scroll", "navigate", "research"}:
            properties["text"] = {"type": "string"}
        if name == "key":
            properties["text"]["enum"] = ["Tab", "Enter", "Escape", "ArrowDown", "ArrowUp", "Space"]
        if name == "scroll":
            properties["text"]["enum"] = ["up", "down"]
        tools.append({"type": "function", "function": {"name": name, "description": description,
                      "parameters": {"type": "object", "properties": properties,
                                     "required": list(properties), "additionalProperties": False}}})
    tools.append({"type": "function", "function": {"name": "answer",
                  "description": "Finish only after the requested configuration is visibly saved. A separate verifier must still test it.",
                  "parameters": {"type": "object", "properties": {"content": {"type": "string"}},
                                 "required": ["content"], "additionalProperties": False}}})
    return tools


class BrowserAgent:
    def __init__(self, provider):
        self.provider = provider
        self.prefix: list[dict] = []
        self.turns: list[list[dict]] = []
        self.pending: dict | None = None

    async def decide(self, context: str, image: bytes, *, allow_research=True) -> dict:
        if self.pending:
            raise ProviderError("A browser tool result must be recorded before observing again.")
        policy, _, raw_state = context.partition("\n")
        state = json.loads(raw_state)
        if not self.prefix:
            static = {key: state[key] for key in ("business_request", "acceptance_criteria", "plan", "official_sources", "applicable_knowledge")}
            self.prefix = [{"role": "system", "content": policy + " Use exactly one tool call per turn. End with answer, never an empty action."},
                           {"role": "user", "content": json.dumps(static, ensure_ascii=False)}]
        # Durable observed actions live outside the rolling visual window, so
        # editing a long form cannot make the model forget earlier requirements.
        static = {key: state[key] for key in ("business_request", "acceptance_criteria", "plan", "official_sources", "applicable_knowledge")}
        static.update(previous_outcomes=state.get("previous_outcomes", []),
                      completed_actions=state.get("action_ledger", state["recent_actions"]))
        self.prefix[1]["content"] = json.dumps(static, ensure_ascii=False)
        dynamic = {key: state[key] for key in ("observation", "remaining_research_requests")}
        observation = {"role": "user", "content": [
            {"type": "text", "text": "<observation>\n" + json.dumps(dynamic, ensure_ascii=False)},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(image).decode()}},
            {"type": "text", "text": "\n</observation>"}]}
        self.turns = (self.turns + [[observation]])[-12:]
        seen = 0
        for turn in reversed(self.turns):
            for message in turn:
                if message["role"] != "user" or not isinstance(message["content"], list):
                    continue
                for chunk in message["content"]:
                    if chunk.get("type") == "image_url":
                        seen += 1
                        if seen > 3:
                            chunk.clear()
                            chunk.update(type="text", text="[screenshot evicted]")
        tools = browser_tools(allow_research)
        call = await self.provider.complete_browser_tool(self.prefix + [message for turn in self.turns for message in turn], tools)
        name = call["function"]["name"]
        if name not in {tool["function"]["name"] for tool in tools}:
            raise ProviderError("The model requested a browser tool outside the allowed set.")
        try:
            arguments = json.loads(call["function"]["arguments"])
            if not isinstance(arguments, dict):
                raise ValueError("Expected arguments object")
            summary = arguments["content"] if name == "answer" else arguments["summary"]
            if not isinstance(summary, str):
                raise ValueError("Expected observable summary")
            target = arguments.get("target", 0)
            text = arguments.get("text", "")
            if type(target) is not int or not isinstance(text, str):
                raise ValueError("Invalid control or text")
        except (ValueError, KeyError, TypeError):
            raise ProviderError("The model returned invalid browser tool arguments.") from None
        # Keep only the parsed tool call. API reasoning is never stored in this conversation or reports.
        self.turns[-1].append({"role": "assistant", "content": None, "tool_calls": [call]})
        self.pending = call
        return {"kind": "done" if name == "answer" else name, "target": target,
                "text": text, "summary": summary[:300]}

    def record_result(self, result: dict, *, sources: list[dict] | None = None):
        if not self.pending:
            raise ProviderError("No browser tool call is awaiting a result.")
        content = {"outcome": result["outcome"], "detail": result.get("detail"), "summary": result.get("summary")}
        if sources is not None:
            content["retrieved_sources"] = sources
        self.turns[-1].append({"role": "tool", "tool_call_id": self.pending["id"],
                               "content": json.dumps(content, ensure_ascii=False)})
        self.pending = None
