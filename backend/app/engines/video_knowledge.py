"""Observe actual video frames; never promote narration to verified evidence."""
import json
from pathlib import Path
from app.models import Capability, KnowledgeClaim, KnowledgeSource
from app.providers.base import ProviderError
from app.util import new_id, utcnow


async def ingest_video(store, project, reasoner, media: dict, transcripts: list[dict], folder: Path) -> dict:
    accepted = []
    source_id = new_id("source")
    notes = []
    for frame in media.get("frames", []):
        timestamp = frame["timestamp"]
        nearby = "\n".join(segment["text"] for segment in transcripts
                           if float(segment["start"]) <= timestamp + 8 and float(segment["end"]) >= timestamp - 8)
        try:
            parsed = await reasoner.analyze_recording_frame(
                software=project.software_name, objective=project.learning_objective,
                timestamp=timestamp, image_bytes=(folder / frame["image"]).read_bytes(), transcript=nearby)
        except ProviderError as exc:
            store.log(project.id, "understanding", f"Video frame {timestamp:.3f}s could not be analyzed: {exc}")
            notes.append({"timestamp": timestamp, "image": frame["image"], "error": str(exc)})
            continue
        (folder / f"analysis_{len(notes):03d}.json").write_text(json.dumps(parsed, indent=2))
        same = parsed.get("same_product") is True
        evidence = store.add_evidence(project.id, origin="uploaded_recording", kind="video_frame",
            summary=f"Recording at {timestamp:.3f}s — identity {'confirmed' if same else 'not confirmed'}",
            payload={"timestamp": timestamp, "image": frame["image"], "model": reasoner.model,
                     "status": "observed", "analysis": parsed}, artifact_path=str(folder / frame["image"]))
        notes.append({"timestamp": timestamp, "image": frame["image"], "evidence_id": evidence.id,
                      "same_product": same, "analysis": parsed})
        if not same:
            continue
        for item in parsed.get("observations", []):
            if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip() for k in ("capability", "control", "observation")):
                continue
            accepted.append({**item, "timestamp": timestamp, "evidence_id": evidence.id})
    relevance = {"checked": True, "sources": []}
    if accepted:
        text = [f"# Authorized {project.software_name} recording observations", "Status: observed in recording, NOT independently verified."]
        for item in accepted:
            text.append(f"\n## {item['timestamp']:.3f}s — {item['capability']}\nControl: {item['control']}\n{item['observation']}\nEvidence: {item['evidence_id']}")
        text.append("\n## Narration / transcript (claims, not proof)")
        text.extend(f"{segment['start']:.3f}–{segment['end']:.3f}s: {segment['text']}" for segment in transcripts)
        content = folder / "observations.md"
        content.write_text("\n".join(text), encoding="utf-8")
        source = KnowledgeSource(id=source_id, project_id=project.id,
            title=f"{project.software_name} — recorded demonstration", url=f"/api/projects/{project.id}/media/original",
            source_type="video", software_version=project.software_version, retrieved_at=utcnow(),
            license=None, content_reference=str(content), reliability="medium")
        store.db.add(source)
        store.db.commit()
        seen = set()
        for item in accepted:
            key = (item["capability"].casefold(), item["control"].casefold())
            if key in seen:
                continue
            seen.add(key)
            claim_id = new_id("claim")
            store.db.add(KnowledgeClaim(id=claim_id, project_id=project.id,
                claim=f"At {item['timestamp']:.3f}s in the recording: {item['observation']}", claim_type="video_observation",
                evidence_ids_json=json.dumps([source_id, item["evidence_id"]]), confidence=0.5, verification_status="observed"))
            store.db.add(Capability(id=new_id("capability"), project_id=project.id, name=item["capability"][:200],
                description=f"Recorded demonstration at {item['timestamp']:.3f}s: {item['observation']}",
                inputs_json=json.dumps([item["control"]]), related_claims_json=json.dumps([claim_id]),
                confidence=0.5, verification_status="observed"))
        store.db.commit()
        relevance["sources"].append({"id": source_id, "relevant": True,
            "summary": "Product identity confirmed from actual recording frames; observations are not independent tests."})
    (folder / "analysis.json").write_text(json.dumps({"frames": notes, "observations": accepted}, indent=2))
    (folder / "relevance.json").write_text(json.dumps(relevance, indent=2))
    store.log(project.id, "understanding", f"Analyzed {len(notes)} sampled video frames; {len(accepted)} product-matched observations. Video is not independent verification.")
    return relevance
