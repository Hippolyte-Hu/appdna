"""Independent test inputs and assertions. Never imported into the executor's prompt builder.

The only writes here create synthetic contacts/conversations. There is deliberately no
automation, assignment or priority mutation method on this client.
"""

import asyncio
import time
from uuid import uuid4

import httpx

from app.tasks.catalog import criteria
from app.util import utcnow

# Kept server-side, outside planner/executor context; only reports reveal them after execution.
_INPUTS = {
    "refund": ("I need a refund for the duplicate charge on my order.", False),
    "delivery": ("Can you check the delivery date for my parcel?", False),
    "complaint": ("This is a serious complaint. My order is unsafe and I need an urgent response.", False),
    "unrelated": ("Do you offer your products in a different colour?", False),
    "vip_refund": ("Please arrange a refund for my returned purchase.", True),
    "vip_delivery": ("Where is the delivery of my latest purchase?", True),
    "vip_complaint": ("I have a serious complaint about an unsafe delivery and need a refund. This is urgent.", True),
}


def actual_result(record: dict, teams: dict[int, str]) -> dict | None:
    if "priority" not in record:
        return None
    meta = record.get("meta") or {}
    team = meta.get("team", record.get("team"))
    if isinstance(team, dict):
        name = team.get("name") or teams.get(team.get("id")) or f"Unknown team #{team.get('id')}"
    elif "team_id" in record:
        name = teams.get(record["team_id"], f"Unknown team #{record['team_id']}") if record["team_id"] else None
    elif "team" in meta or "team" in record:
        name = None
    elif (meta.get("channel") == "Channel::Api"
          and all(isinstance(record.get(key), int) and record[key] > 0 for key in ("id", "account_id", "inbox_id"))
          and record.get("status") in {"open", "resolved", "pending", "snoozed"}):
        # The pinned conversation serializer omits meta.team when no team is assigned.
        # Require the complete API conversation identity; an arbitrary partial response stays unknown.
        name = None
    else:
        return None
    priority = record["priority"]
    if priority is None or priority == "":
        priority = "default"
    elif isinstance(priority, int):
        priority = {0: "low", 1: "medium", 2: "high", 3: "urgent"}.get(priority, f"unknown ({priority})")
    return {"team": name, "priority": str(priority).lower()}


def compare(expected: dict, actual: dict | None) -> str:
    if actual is None:
        return "unverified"
    # Chatwoot normalizes team names to lowercase before saving them.
    expected_team = expected["team"].strip().casefold() if expected["team"] else None
    actual_team = actual["team"].strip().casefold() if actual["team"] else None
    return "passed" if actual_team == expected_team and actual["priority"] == expected["priority"] else "failed"


class ChatwootVerifier:
    def __init__(self, base_url: str, account_id: int, inbox_id: int, token: str,
                 *, transport=None, settle_seconds: float = 4.0, timeout_seconds: float = 18.0):
        self.base_url = base_url.rstrip("/")
        self.account_id, self.inbox_id = account_id, inbox_id
        self.client = httpx.AsyncClient(base_url=f"{self.base_url}/api/v1/accounts/{account_id}/",
                                        headers={"api_access_token": token}, timeout=15,
                                        transport=transport)
        self.settle_seconds = settle_seconds
        self.timeout_seconds = timeout_seconds

    async def close(self):
        await self.client.aclose()

    async def configuration_snapshot(self) -> list[dict]:
        response = await self.client.get("automation_rules")
        response.raise_for_status()
        rows = response.json()
        if isinstance(rows, dict):
            rows = rows.get("payload", [])
        return [{key: row.get(key) for key in ("id", "name", "event_name", "active", "conditions", "actions")}
                for row in rows]

    async def preflight(self) -> dict[int, str]:
        response = await self.client.get("teams")
        response.raise_for_status()
        teams = response.json()
        if isinstance(teams, dict):
            teams = teams.get("payload", [])
        result = {item["id"]: item["name"] for item in teams}
        if not {"billing", "logistics", "customer care"}.issubset(name.strip().casefold() for name in result.values()):
            raise ValueError("The sandbox must have Billing, Logistics and Customer Care teams before the agent runs.")
        response = await self.client.get(f"inboxes/{self.inbox_id}")
        response.raise_for_status()
        inbox = response.json()
        if inbox.get("channel_type") != "Channel::Api":
            raise ValueError("Verification requires an API inbox containing only synthetic contacts.")
        if inbox.get("enable_auto_assignment"):
            raise ValueError("Disable automatic inbox assignment so unrelated-message tests remain independent.")
        return result

    async def _create_input(self, message: str, vip: bool) -> int:
        identifier = uuid4().hex[:16]
        response = await self.client.post("contacts", json={
            "inbox_id": self.inbox_id, "name": f"AppDNA synthetic {identifier}",
            "email": f"appdna-{identifier}@northstar.invalid",
            "custom_attributes": {"customer_tier": "vip" if vip else "standard"},
        })
        response.raise_for_status()
        payload = response.json().get("payload", response.json())
        contact = payload.get("contact", payload)
        links = contact.get("contact_inboxes", payload.get("contact_inboxes", []))
        link = next((item for item in links if item.get("inbox", {}).get("id") == self.inbox_id), None)
        if not link or not link.get("source_id"):
            raise ValueError("Chatwoot did not return a contact-inbox source_id.")
        response = await self.client.post("conversations", json={
            "source_id": link["source_id"], "inbox_id": self.inbox_id, "contact_id": contact["id"],
            "status": "open", "message": {"content": message, "message_type": "incoming"},
        })
        response.raise_for_status()
        return response.json()["id"]

    async def verify(self, scenario: str, teams: dict[int, str], on_result, checkpoint) -> list[dict]:
        results = []
        for requirement in criteria(scenario):
            await checkpoint()
            case_id = requirement["id"]
            message, vip = _INPUTS[case_id]
            result = {"id": case_id, "requirement": requirement["requirement"],
                      "expected": {"team": requirement["team"], "priority": requirement["priority"]},
                      "actual": None, "status": "unverified", "checked_at": utcnow(),
                      "input": {"message": message, "customer_tier": "vip" if vip else "standard"},
                      "method": "Independent Chatwoot API read; synthetic input only"}
            try:
                conversation_id = await self._create_input(message, vip)
                result["conversation_id"] = conversation_id
                result["url"] = f"{self.base_url}/app/accounts/{self.account_id}/conversations/{conversation_id}"
                started, unchanged_since = time.monotonic(), time.monotonic()
                previous = object()
                while True:
                    await checkpoint()
                    response = await self.client.get(f"conversations/{conversation_id}")
                    response.raise_for_status()
                    record = response.json()
                    actual = actual_result(record, teams)
                    if actual != previous:
                        unchanged_since, previous = time.monotonic(), actual
                    elapsed = time.monotonic() - started
                    stable = time.monotonic() - unchanged_since >= self.settle_seconds
                    matched = compare(requirement, actual) == "passed"
                    # Negative cases must also settle, so an initial unassigned response is never an instant pass.
                    if (stable and matched) or elapsed >= self.timeout_seconds:
                        result.update(actual=actual, status=compare(requirement, actual),
                                      record={"id": record.get("id"), "team": actual["team"] if actual else None,
                                              "priority": record.get("priority")}, checked_at=utcnow())
                        break
                    await asyncio.sleep(0.5)
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                result.update(status="blocked", detail=f"The verifier could not read a complete result ({type(exc).__name__}).")
            results.append(result)
            on_result(results.copy())
        return results
