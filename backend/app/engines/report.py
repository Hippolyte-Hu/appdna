"""Deterministic, printable assessment from saved evidence, not a sales score."""
from collections import Counter
from html import escape
from urllib.parse import urlsplit

LEVEL = {"discovered": "Documented claim", "observed": "Recorded observation", "experimented": "Live control exercised", "verified": "Independent check passed"}


def e(value):
    return escape(str(value if value is not None else ""), quote=True)


def render_report(detail: dict) -> str:
    evaluation = detail["outcome"]["evaluation"]
    capabilities = detail.get("capabilities", [])
    counts = Counter(item["verification_status"] for item in capabilities)
    gaps = list(evaluation.get("gaps", []))
    if detail.get("error_message"):
        gaps.insert(0, detail["error_message"])
    ready = detail["status"] == "completed" and evaluation["verdict"] == "Proven" and not gaps
    decision = "Scoped pilot candidate — human sign-off required" if ready else "Not ready for approval"
    summary = "Use the evidence below to prepare a scoped pilot. Do not treat one workflow as complete product acceptance." if ready else "Hold final rollout approval. Close the coverage gaps and independently test the workflows that matter to your team."
    rows = []
    for cap in capabilities:
        refs = ", ".join(cap.get("related_claims") or []) or "No claim reference"
        rows.append(f"<tr><td><strong>{e(cap['name'])}</strong><small>{e(cap.get('id'))}</small></td><td>{e(LEVEL.get(cap['verification_status'], cap['verification_status']))}</td><td>{e(cap.get('control'))}<small>{e(cap.get('summary') or cap.get('description'))}</small></td><td>{e(refs)}</td></tr>")
    sources = []
    for source in detail.get("sources", []):
        relevance = source.get("relevant", source.get("is_relevant"))
        status = "Matched product" if relevance is True else "Different product — excluded" if relevance is False else "Identity not confirmed — excluded"
        url = source.get("url", "")
        title = e(source.get("title", "Untitled source"))
        if urlsplit(url).scheme in {"http", "https"}:
            title = f'<a href="{e(url)}" rel="noreferrer">{title}</a>'
        sources.append(f"<li>{title}<small>{e(status)} · {e(source.get('id'))}</small></li>")
    transcript = " ".join(segment["text"] for segment in detail.get("transcripts", []))
    media = detail.get("media") or {}
    media_text = f"{media.get('duration', 0):.1f} seconds; {len(media.get('frames', []))} timestamped frames. Source SHA-256: {media.get('source_sha256', 'Not available')}." if media else "No recording ingested for this run."
    checklist = ["Confirm target requirements and acceptance thresholds with the buying or product team.",
        "Replay priority workflows under the intended device, language and accessibility conditions.",
        "Run failure, recovery, permission, cancellation and destructive-action checks in a safe test account.",
        "Security, legal and commercial due diligence: Not assessed by this technical run.",
        "Performance, accessibility conformance, privacy compliance and total cost: Not assessed unless explicitly supported by a separate check."]
    list_html = lambda items: "<ul>" + "".join(f"<li>{e(item)}</li>" for item in items) + "</ul>"
    evidence = "".join(f"<tr><td>{e(item.get('id'))}</td><td>{e(item.get('origin'))} / {e(item.get('kind'))}</td><td>{e(item.get('summary'))}</td></tr>" for item in detail.get("evidence", []))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AppDNA assessment — {e(detail['software_name'])}</title>
<style>body{{background:#f5f4ef;color:#182522;font:15px/1.65 system-ui,sans-serif;margin:0}}main{{max-width:1100px;margin:0 auto;padding:48px 32px}}header{{border-top:5px solid #19644d;padding-top:20px}}h1{{font:48px/1.1 Georgia,serif;letter-spacing:-1.3px}}h2{{font:29px/1.2 Georgia,serif;margin-top:0}}h3{{font-size:16px}}p{{max-width:850px}}small{{display:block;color:#5f706b;font-size:12px;overflow-wrap:anywhere}}.eyebrow{{font:12px monospace;text-transform:uppercase;letter-spacing:2px;color:#19644d}}.decision{{background:#143e32;color:#fff;padding:24px 28px;border-radius:16px}}.decision small{{color:#c7dfd6}}section{{margin-top:26px;padding:26px;background:#fff;border:1px solid #dbe1dc;border-radius:14px}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}}.metrics div{{border-top:2px solid #19644d;padding-top:10px}}.metrics strong{{display:block;font:34px Georgia,serif}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{padding:12px 10px;text-align:left;vertical-align:top;border-bottom:1px solid #e0e6e2;overflow-wrap:anywhere}}th{{background:#edf3ef}}li{{margin:9px 0}}a{{color:#19644d}}.table{{overflow:auto}}button{{background:#19644d;color:#fff;border:0;padding:10px 18px;border-radius:30px;cursor:pointer}}footer{{margin:24px 0;color:#5f706b;font-size:12px}}@media(max-width:600px){{main{{padding:24px 16px}}h1{{font-size:34px}}.metrics{{grid-template-columns:repeat(2,1fr)}}section{{padding:18px}}}}@media print{{body{{background:white}}main{{padding:0}}button{{display:none}}section{{break-inside:auto}}tr{{break-inside:avoid}}}}</style></head><body><main>
<header><p class="eyebrow">AppDNA / Evidence-led software assessment</p><h1>{e(detail['software_name'])}<br>From product claims to a reviewable decision.</h1><p>Assessment scope: {e(detail.get('learning_objective'))}</p><small>Run {e(detail['id'])} · State: {e(detail['status'])} · Version: {e(detail.get('software_version') or 'Not supplied')} · Updated: {e(detail.get('updated_at'))}</small></header>
<section class="decision"><p class="eyebrow" style="color:#b6edcf">Decision brief</p><h2>{decision}</h2><p>{summary}</p><small>Evidence verdict: {e(evaluation["verdict"])}</small><small>Technical evidence only. AppDNA does not approve a supplier, certify compliance, or replace UAT sign-off.</small></section>
<div class="metrics">{''.join(f'<div><strong>{counts[status]}</strong><small>{e(label)}</small></div>' for status,label in LEVEL.items())}</div>
<section><h2>1. What this run establishes</h2><p>{e(evaluation.get('summary'))}</p><h3>Saved strengths</h3>{list_html(evaluation.get('strengths', []))}<h3>Open gaps and blockers</h3>{list_html(gaps or ['No saved gap is not proof of complete coverage. Confirm the acceptance scope.'])}</section>
<section><h2>2. Functional assessment</h2><p>Statuses are not interchangeable. Documentation is a claim; a recording is an observation; a live click exercises a control; an independent check verifies only its stated predicate. Blender scene checks never verify GUI coverage.</p><div class="table"><table><thead><tr><th>Capability / ID</th><th>Evidence level</th><th>Control and saved finding</th><th>Claim references</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="4">No admitted capabilities yet.</td></tr>'}</tbody></table></div></section>
<section><h2>3. Procurement and pre-UAT follow-up</h2><p>For Procurement: use this technical shortlist review before committing to a supplier. For an internal product team: turn the same gaps into a focused pre-UAT test plan. These are two views of the same evidence, not two independent certifications.</p>{list_html(checklist)}</section>
<section><h2>4. Recording and narration provenance</h2><p>{e(media_text)}</p><p>Sampling does not establish continuous coverage. Narration is a description, not proof that the described action succeeded. Product-matched frame observations remain unverified until separately tested.</p><details><summary>Saved transcript</summary><p>{e(transcript or 'No transcript available.')}</p></details></section>
<section><h2>5. Source identity and references</h2><ul>{''.join(sources) or '<li>No saved sources.</li>'}</ul></section>
<section><h2>Appendix — Evidence index</h2><div class="table"><table><thead><tr><th>Evidence ID</th><th>Origin / type</th><th>Saved observation</th></tr></thead><tbody>{evidence}</tbody></table></div></section>
<footer>Generated from saved AppDNA run data. Counts are evidence classifications, not a completion score. Retain the original recording, frame timestamps, transcript and run package for audit.</footer></main></body></html>"""
