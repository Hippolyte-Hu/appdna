import json
from pathlib import Path

GENERIC_TOOLS = {"click", "double_click", "type", "key", "scroll", "wait", "done"}


def combined_source_relevance(root: Path) -> dict | None:
    written = load_source_relevance(root / "explore" / "source_relevance.json")
    recording = load_source_relevance(root / "media" / "relevance.json")
    if not recording or not recording.get("sources"):
        return written
    rows = list((written or {}).get("sources", []))
    ids = {row.get("id") for row in rows}
    rows += [row for row in recording["sources"] if row.get("id") not in ids]
    return {"checked": True, "sources": rows}


def load_source_relevance(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("checked"):
        return None
    return data


def build_outcome(
    *,
    software_name: str,
    objective: str,
    capabilities: list[dict],
    claims: list[dict],
    frames: list[dict],
    source_count: int,
    source_relevance: dict | None = None,
    run_status: str | None = None,
    run_error: str | None = None,
) -> dict:
    """Turn learned capabilities into tool skills, an app evaluation, and a knowledge graph."""
    capabilities, claims, notes, source_count, unrelated = _admit(capabilities, claims, source_count, source_relevance)
    skills = [_skill(item, frames) for item in capabilities if str(item.get("name") or "").strip()]
    evaluation = _evaluation(software_name, objective, skills, frames, source_count, unrelated)
    if run_status == "failed":
        evaluation["verdict"] = "Incomplete"
        if run_error and run_error not in evaluation["gaps"]:
            evaluation["gaps"].insert(0, run_error)
    return {
        "evaluation": evaluation,
        "skills": skills,
        "graph": _graph(
            software_name,
            skills,
            claims,
            notes,
            include_written=bool(source_relevance and source_relevance.get("checked")),
        ),
    }


def _admit(
    capabilities: list[dict],
    claims: list[dict],
    source_count: int,
    source_relevance: dict | None,
) -> tuple[list[dict], list[dict], list[dict], int, bool]:
    """Keep written knowledge only after the open app confirms the source is the same product."""
    if not source_relevance or not source_relevance.get("checked"):
        return capabilities, claims, [], source_count, False
    notes = [
        item
        for item in source_relevance.get("sources") or []
        if isinstance(item, dict) and item.get("relevant") and str(item.get("id") or "").strip()
    ]
    relevant_ids = {str(item["id"]) for item in notes}
    kept_claims = [
        claim
        for claim in claims
        if any(str(item) in relevant_ids for item in claim.get("evidence_ids") or [])
    ]
    kept_claim_ids = {str(claim.get("id")) for claim in kept_claims}
    kept_capabilities = []
    for capability in capabilities:
        related = [str(item) for item in capability.get("related_claims") or [] if str(item) in kept_claim_ids]
        status = str(capability.get("verification_status") or "")
        if status in {"experimented", "verified"} or related:
            kept_capabilities.append({**capability, "related_claims": related})
    return kept_capabilities, kept_claims, notes, len(relevant_ids), len(relevant_ids) == 0


def _skill(capability: dict, frames: list[dict]) -> dict:
    name = str(capability.get("name") or "").strip()
    description = str(capability.get("description") or "").strip()
    preconditions = _strings(capability.get("preconditions"))
    outputs = _strings(capability.get("expected_outputs"))
    tools = _tools(name, capability, frames)
    steps = [f"Confirm {item}." for item in preconditions]
    matched = _matching_frames(name, tools, frames)
    if matched:
        for frame in matched[:3]:
            learned = str(frame.get("learned") or frame.get("thought") or "").strip()
            control = str(frame.get("text") or name).strip()
            steps.append(f"Use {control}. {learned}".strip())
    elif description:
        steps.append(description if description.endswith(".") else f"{description}.")
    else:
        steps.append(f"Use {name}.")
    for item in outputs:
        steps.append(f"Expect {item}.")
    return {
        "id": str(capability.get("id") or name),
        "name": name,
        "use_when": description or f"When you need {name}.",
        "steps": steps[:6],
        "tools": tools,
        "status": str(capability.get("verification_status") or "discovered"),
        "claim_ids": _strings(capability.get("related_claims")),
    }


def _tools(name: str, capability: dict, frames: list[dict]) -> list[str]:
    found: list[str] = []
    for item in _strings(capability.get("inputs")):
        if item.lower() not in GENERIC_TOOLS and item not in found:
            found.append(item)
    for frame in _matching_frames(name, found, frames):
        control = str(frame.get("text") or "").strip()
        if control and control.lower() not in GENERIC_TOOLS and control not in found:
            found.append(control)
    if not found:
        found.append(name)
    return found[:4]


def _matching_frames(name: str, tools: list[str], frames: list[dict]) -> list[dict]:
    needles = {name.casefold(), *(tool.casefold() for tool in tools)}
    matched = []
    for frame in frames:
        if frame.get("action") != "click" or not frame.get("executed"):
            continue
        text = f"{frame.get('text') or ''} {frame.get('learned') or ''}".casefold()
        if any(needle and needle in text for needle in needles):
            matched.append(frame)
    return matched


def _evaluation(
    software_name: str,
    objective: str,
    skills: list[dict],
    frames: list[dict],
    source_count: int,
    unrelated_sources: bool = False,
) -> dict:
    verified = [item for item in skills if item["status"] == "verified"]
    observed = [item for item in skills if item["status"] == "experimented"]
    clicked = [frame for frame in frames if frame.get("action") == "click" and frame.get("executed")]
    strengths = [item["name"] for item in verified + observed][:5]
    gaps: list[str] = []
    last_resume = max((index for index, frame in enumerate(frames) if frame.get("action") == "resume"), default=-1)
    # Only replace old gap reports when this continuation actually reached a coverage checkpoint.
    current_frames = frames[last_resume:] if last_resume >= 0 and any(
        frame.get("action") == "coverage" for frame in frames[last_resume:]
    ) else frames
    for frame in current_frames:
        note = str(frame.get("thought") or "")
        if note.startswith(("Coverage incomplete:", "Stopped asking", "Stopped after")):
            gaps.append(note)
    if unrelated_sources:
        gaps.append("No online source was confirmed as this product; unconfirmed sources were left out of the skills and the graph.")
    elif source_count == 0:
        gaps.append("No public document described this application.")
    if not clicked:
        gaps.append("Usage steps were not confirmed by clicking the live interface.")
    if not verified:
        gaps.append("No skill has passed an independent test.")
    if not skills:
        gaps.append("No tool skill was extracted.")
    if any(gap.startswith(("Coverage incomplete:", "Stopped asking", "Stopped after")) for gap in gaps):
        verdict = "Incomplete"
    elif verified:
        verdict = "Ready"
    elif observed or clicked:
        verdict = "Observed"
    elif skills:
        verdict = "Documented"
    else:
        verdict = "Incomplete"
    summary = (
        f"{software_name} has {len(skills)} tool skill{'s' if len(skills) != 1 else ''}"
        f" for “{objective}”. "
        f"{len(verified)} verified, {len(observed)} observed on the live app, "
        f"from {source_count} written source{'s' if source_count != 1 else ''}."
    )
    return {
        "summary": summary,
        "verdict": verdict,
        "strengths": strengths,
        "gaps": gaps,
    }


def _graph(
    software_name: str,
    skills: list[dict],
    claims: list[dict],
    notes: list[dict] | None = None,
    include_written: bool = False,
) -> dict:
    nodes = [{"id": "app", "label": software_name or "App", "kind": "app"}]
    edges = []
    seen = {"app"}
    claim_by_id = {str(item.get("id")): item for item in claims}
    for skill in skills:
        skill_id = f"skill:{skill['id']}"
        nodes.append({"id": skill_id, "label": skill["name"], "kind": "skill"})
        edges.append({"source": "app", "target": skill_id, "label": "offers"})
        seen.add(skill_id)
        for tool in skill["tools"]:
            tool_id = f"tool:{_slug(tool)}"
            if tool_id not in seen:
                nodes.append({"id": tool_id, "label": tool, "kind": "tool"})
                seen.add(tool_id)
            edges.append({"source": skill_id, "target": tool_id, "label": "uses"})
        for claim_id in skill.get("claim_ids") or []:
            claim = claim_by_id.get(str(claim_id))
            if claim is None:
                continue
            node_id = f"claim:{claim_id}"
            if node_id not in seen:
                nodes.append({"id": node_id, "label": str(claim.get("claim") or "Note")[:180], "kind": "concept"})
                seen.add(node_id)
            edges.append({"source": skill_id, "target": node_id, "label": "based on"})
    if not include_written:
        return {"nodes": nodes, "edges": edges}
    for note in notes or []:
        summary = str(note.get("summary") or "").strip()
        if not summary:
            continue
        node_id = f"source:{note['id']}"
        if node_id in seen:
            continue
        nodes.append({"id": node_id, "label": summary[:180], "kind": "concept"})
        edges.append({"source": "app", "target": node_id, "label": "from sources"})
        seen.add(node_id)
    for claim in claims:
        claim_id = str(claim.get("id") or "")
        node_id = f"claim:{claim_id}"
        if not claim_id or node_id in seen:
            continue
        nodes.append({"id": node_id, "label": str(claim.get("claim") or "Note")[:180], "kind": "concept"})
        edges.append({"source": "app", "target": node_id, "label": "from sources"})
        seen.add(node_id)
    return {"nodes": nodes, "edges": edges}


def _strings(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _slug(name: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in name).strip("-")
    return cleaned or "tool"
