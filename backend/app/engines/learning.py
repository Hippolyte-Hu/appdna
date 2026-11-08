import json
from pathlib import Path

from app.models import Capability, KnowledgeClaim, KnowledgeSource, Project
from app.providers.base import ProviderError
from app.providers.hcompany import HCompanyProvider
from app.store import Store
from app.util import loads, new_id

KNOWLEDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "claim": {"type": "string"},
                    "claim_type": {"type": "string"},
                    "confidence": {"type": "number"},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["claim", "claim_type", "confidence", "source_refs"],
            },
        },
        "capabilities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "preconditions": {"type": "array", "items": {"type": "string"}},
                    "inputs": {"type": "array", "items": {"type": "string"}},
                    "expected_outputs": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "claim_indexes": {"type": "array", "items": {"type": "integer"}},
                },
                "required": [
                    "name",
                    "description",
                    "preconditions",
                    "inputs",
                    "expected_outputs",
                    "confidence",
                    "source_refs",
                    "claim_indexes",
                ],
            },
        },
        "objective_answered": {"type": "boolean"},
    },
    "required": ["claims", "capabilities", "objective_answered"],
}

EXPERIMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "object_name": {"type": "string"},
        "material_name": {"type": "string"},
        "objective": {"type": "string"},
        "expected_result": {"type": "string"},
        "script": {"type": "string"},
    },
    "required": ["object_name", "material_name", "objective", "expected_result", "script"],
}


class LearningError(Exception):
    pass


def text_covers_objective(source_count: int, objective_answered: bool) -> bool:
    """Online text is enough only when sources exist and they answer this objective."""
    return source_count > 0 and objective_answered


def needs_click(matches: bool, complete: bool) -> bool:
    """Click when the live app differs from the documents or the documents leave something out."""
    return not (matches and complete)


def _catalog(sources: list[KnowledgeSource], transcripts: list[dict]) -> tuple[str, dict[str, str]]:
    lines = []
    refs: dict[str, str] = {}
    for index, source in enumerate(sources, start=1):
        ref = f"S{index}"
        refs[ref] = source.id
        excerpt = ""
        path = Path(source.content_reference)
        if path.exists():
            excerpt = path.read_text(encoding="utf-8")[:1800]
        lines.append(
            f"[{ref}] type={source.source_type} reliability={source.reliability} url={source.url}\n{excerpt}"
        )
    for index, segment in enumerate(transcripts, start=1):
        ref = f"T{index}"
        refs[ref] = segment["evidence_id"]
        speaker = segment.get("speaker")
        speaker_label = f"speaker {speaker}" if speaker is not None else "speaker unknown"
        lines.append(
            f"[{ref}] type=audio {speaker_label} {segment['start']:.2f}-{segment['end']:.2f}s "
            f"origin={segment['origin']}\n{segment['text'][:800]}"
        )
    return "\n\n".join(lines), refs


def _clamp(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.4
    return max(0.0, min(1.0, number))


def _refs(raw, known: dict[str, str]) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [known[item] for item in raw if isinstance(item, str) and item in known]


async def understand(
    store: Store,
    project: Project,
    reasoner: HCompanyProvider,
    transcripts: list[dict],
    artifact_dir: Path,
) -> tuple[Capability, bool]:
    sources = store.sources(project.id)
    catalog, ref_map = _catalog(sources, transcripts)
    if not catalog.strip():
        raise LearningError("There is no research corpus to understand")
    prompt = (
        f"Software: {project.software_name} {project.software_version or ''}\n"
        f"Learning objective: {project.learning_objective}\n\n"
        "Extract claims and capabilities that the sources support. "
        "Cite source_refs from the catalog only. "
        "Do not invent a license, version, or operation that the excerpts do not support. "
        + (
            "Include a capability for creating a mesh cube and assigning a material when the sources support it. "
            if project.software_name.lower() == "blender"
            else "Focus on capabilities that serve the learning objective. "
        )
        + "Use claim_type values such as capability, concept, interface, or limitation. "
        "Set objective_answered to true only when these excerpts explain how to accomplish the learning objective "
        "for this exact application. A page that only mentions the name, or describes a different product, is false.\n\n"
        f"Sources:\n{catalog}"
    )
    parsed = await reasoner.complete_json(prompt, KNOWLEDGE_SCHEMA, "capability_graph")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    raw_path = artifact_dir / "understanding.json"
    raw_path.write_text(json.dumps(parsed), encoding="utf-8")
    store.add_evidence(
        project.id,
        origin="hcompany",
        kind="model_output",
        summary="Structured reading of the research corpus",
        payload={"schema": "capability_graph"},
        artifact_path=str(raw_path),
    )

    claim_rows: list[KnowledgeClaim] = []
    for item in parsed.get("claims") or []:
        if not isinstance(item, dict) or not str(item.get("claim") or "").strip():
            continue
        evidence_ids = _refs(item.get("source_refs"), ref_map)
        confidence = _clamp(item.get("confidence"))
        if not evidence_ids:
            confidence = min(confidence, 0.4)
        row = KnowledgeClaim(
            id=new_id("claim"),
            project_id=project.id,
            claim=str(item["claim"]).strip()[:1000],
            claim_type=str(item.get("claim_type") or "capability")[:40],
            software_version=project.software_version,
            evidence_ids_json=json.dumps(evidence_ids),
            confidence=confidence,
            verification_status="discovered",
        )
        store.db.add(row)
        claim_rows.append(row)

    created: list[Capability] = []
    for item in parsed.get("capabilities") or []:
        if not isinstance(item, dict) or not str(item.get("name") or "").strip():
            continue
        evidence_ids = _refs(item.get("source_refs"), ref_map)
        if not evidence_ids:
            continue
        indexes = item.get("claim_indexes") if isinstance(item.get("claim_indexes"), list) else []
        related = []
        for index in indexes:
            if isinstance(index, int) and 0 <= index < len(claim_rows):
                related.append(claim_rows[index].id)
        row = Capability(
            id=new_id("capability"),
            project_id=project.id,
            name=str(item["name"]).strip()[:200],
            description=str(item.get("description") or "").strip()[:2000],
            preconditions_json=json.dumps([str(value) for value in item.get("preconditions") or []]),
            inputs_json=json.dumps([str(value) for value in item.get("inputs") or []]),
            expected_outputs_json=json.dumps([str(value) for value in item.get("expected_outputs") or []]),
            related_claims_json=json.dumps(related),
            verification_status="discovered",
            confidence=_clamp(item.get("confidence")),
        )
        store.db.add(row)
        created.append(row)
    store.db.commit()
    selected = _select_target(created, project)
    if selected is None:
        if project.software_name.lower() == "blender":
            raise LearningError("The sources did not support a capability for creating a mesh and assigning a material")
        raise LearningError(f"The sources did not support a capability for {project.software_name}.")
    answered = text_covers_objective(len(store.sources(project.id)), bool(parsed.get("objective_answered")))
    coverage = (
        "The written sources appear to cover the objective. The agent will open the app and compare them."
        if answered
        else "The written sources do not cover the objective, so the agent will click the app."
    )
    store.log(
        project.id,
        "understanding",
        f"Extracted {len(claim_rows)} claims and {len(created)} capabilities. {coverage}",
    )
    return selected, answered


def blender_objective_capability(store: Store, project: Project) -> Capability:
    """Keep the cube-and-material check available when the document reading does not finish."""
    row = Capability(
        id=new_id("capability"),
        project_id=project.id,
        name="Create a mesh cube and assign a material",
        description="Create one mesh cube and assign one material. The written reading did not finish.",
        preconditions_json="[]",
        inputs_json="[]",
        expected_outputs_json='["A mesh cube exists.", "A material is assigned."]',
        related_claims_json="[]",
        verification_status="discovered",
        confidence=0.4,
    )
    store.db.add(row)
    store.db.commit()
    store.log(project.id, "understanding", "The document reading did not finish. Blender will still open, and the cube and material check stays available.")
    return row


def _select_target(capabilities: list[Capability], project: Project) -> Capability | None:
    if project.software_name.lower() != "blender":
        return capabilities[0] if capabilities else None
    for capability in capabilities:
        text = f"{capability.name} {capability.description}".lower()
        if any(token in text for token in ("cube", "material", "mesh", "primitive")):
            return capability
    return None


async def propose_experiment(
    reasoner: HCompanyProvider,
    project: Project,
    capability: Capability,
    sources: list[KnowledgeSource],
    feedback: str | None = None,
) -> dict:
    excerpts = []
    for source in sources[:6]:
        path = Path(source.content_reference)
        body = path.read_text(encoding="utf-8")[:1200] if path.exists() else ""
        excerpts.append(f"{source.url}\n{body}")
    prompt = (
        f"Write a Blender Python experiment for this capability.\n"
        f"Capability: {capability.name}\n{capability.description}\n"
        f"Objective: {project.learning_objective}\n"
        "The script must import only bpy, math, mathutils, or bmesh. "
        "Create one mesh object and assign one material with materials.append. "
        "Use object_name AppDNACube and material_name AppDNAMaterial unless the excerpts require different identifiers. "
        "Do not open, save, or quit Blender, and do not import os, sys, subprocess, or shutil.\n\n"
        "Source excerpts:\n"
        + "\n\n".join(excerpts)
    )
    if feedback:
        prompt += f"\n\nThe previous attempt failed. Fix the script.\n{feedback[:2000]}"
    proposal = await reasoner.complete_json(prompt, EXPERIMENT_SCHEMA, "blender_experiment")
    if not proposal.get("script"):
        raise ProviderError("The model did not propose an experiment script")
    return proposal


def claim_payload(claim: KnowledgeClaim) -> dict:
    return {
        "id": claim.id,
        "claim": claim.claim,
        "claim_type": claim.claim_type,
        "software_version": claim.software_version,
        "evidence_ids": loads(claim.evidence_ids_json, []),
        "confidence": claim.confidence,
        "verification_status": claim.verification_status,
    }
