"""Distill only operations that exist in a successfully verified UI trace."""

import json

from app.drivers.browser import prohibited_routing_action
from app.providers.base import ProviderError

_UI_KINDS = {"click", "type", "select", "key", "scroll"}


def describe_action(action: dict) -> str:
    kind, text = action["kind"], action.get("text", "")
    label = action.get("target_label", "")
    control = next((item for item in action.get("observation", {}).get("controls", [])
                    if item["id"] == action.get("target")), {})
    if kind == "type":
        return f'Enter {json.dumps(text, ensure_ascii=False)} in the observed “{label[:100]}” input.'
    if kind == "select":
        return f'Select {json.dumps(text, ensure_ascii=False)} in the observed dropdown.'
    if kind == "key":
        return f'Press {text} in the focused control.'
    if kind == "scroll":
        return f'Scroll {text}, then observe the interface again.'
    if kind == "click":
        if control.get("tag") == "select":
            return 'Open the observed dropdown.'
        if label and label != "BUTTON" and len(label) < 120 and not prohibited_routing_action(label):
            return f'Click “{label}”.'
        summary = action.get("summary", "Click the observed control").strip().rstrip(".")
        if prohibited_routing_action(summary):
            return 'Click the observed routing control shown in the referenced screenshot.'
        return summary + '.'
    raise ProviderError("Knowledge can reference only executed UI operations.")


def grounded_knowledge(task: dict, run: dict) -> dict:
    """Build a local, auditable replay record without another model request."""
    candidates = {index: action for index, action in enumerate(run["actions"])
                  if action.get("outcome") == "executed" and action.get("kind") in _UI_KINDS}
    if not candidates:
        raise ProviderError("No demonstrated UI operations are available for knowledge extraction.")
    indices = list(candidates)
    # A useful configuration skill must include the observed mutation and commit.
    has_mutation = any(candidates[index]["kind"] in {"type", "select"} for index in indices)
    commits = [index for index, action in candidates.items()
               if action["kind"] == "click" and action.get("target_label", "").strip().casefold() in {"save", "create", "update"}]
    if not has_mutation or (commits and not any(index in commits for index in indices)):
        raise ProviderError("The extracted skill omitted its observed configuration or save operation.")
    return {
        "grounding_version": 2,
        "extraction": "Local reconstruction of executed UI actions; includes observed exploration.",
        "preconditions": [f'Chatwoot {task["software_version"]} with account-administrator access.',
                          'Re-observe the current automation rules and controls before reusing this recorded workflow.'],
        "procedure": [describe_action(candidates[index]) for index in indices],
        "completion_check": [f'Independent “{item["requirement"]}” check returns team {item["team"] or "Unassigned"} and priority {item["priority"]}.'
                             for item in task["criteria"]],
        "unresolved": ['Fresh-environment transfer has not been measured.'],
        "permissions": ['Chatwoot account administrator'],
        "source_refs": list(dict.fromkeys(source["url"] for source in run["sources"])),
        "action_references": indices,
        "evidence_steps": [candidates[index]["observation"]["step"] for index in indices],
        "related_runs": [run["id"]],
        "applicability": 'Exact software version and observed UI landmarks; adapt to the current rules after observing them.',
    }
