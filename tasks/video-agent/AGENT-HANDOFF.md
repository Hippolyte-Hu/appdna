# Video learning Agent — implementation handoff

> Historical learning-stage handoff. See [TEAM-REVIEW.md](TEAM-REVIEW.md) for the newer publication checkpoint: real GUI/save failure, restoration of the prior scratch artifact, source-derived checks, and the two pending safety tests. Do not interpret the older all-green/no-GUI statements below as the current branch status.

## Conclusion
The independently invocable source-learning Agent is implemented and called by the isolated AppDNA video workbench. The latest real Holo4-27B run produced six source-checked steps after autonomous reinspection and revision. This is one successful learning run, not a demonstrated reliability rate or an end-to-end video-to-Blender success.

## Implemented
- Holo4-only runtime policy for this workflow. Per-call controller reasoning and structured-output fallback preserve desktop grounding defaults. One malformed-JSON retry, aggregate citation feedback, request-only mixed-image padding, per-run exact-step audit caching, and bounded recovery of transient tool failures.
- A contradictory audit (supported=true plus nonempty issues) is re-asked once against the same evidence, never locally coerced to acceptance. Repeated contradiction fails closed.
- Per-run task context and bounded source-only tool loop: read transcript, request/crop exact video frames, propose steps, ask for clarification.
- Persisted source hash/URL, original frame evidence, timestamp citations, public tool trace and knowledge status. No GUI/shell tool is exposed to the learner.
- Each proposed step must cite inspected frames inside its source interval; unresolved uncertainty and unsupported source checks prevent acceptance.
- Original source images are checked in separate model requests. These checks are model observations, not independent artifact verification.
- Workbench caller integration, English status/tool trace, knowledge download, and `/api/video-sources` retrieval. Only source-checked runs appear in accepted-source search.
- Source-learning errors block GUI execution. New video-source artifacts cannot inherit the fixed legacy 0.22 m edge-Bevel check's overall `verified` status: they are `saved_unverified` until source-derived independent checks exist.

## Verified
- Backend regression: **167 passed**, 3 deprecation warnings.
- Python compilation and `git diff --check`: passed.
- Real Chromium browser against the accepted receipt: Holo4 model label and 10 tool decisions displayed; six clickable source-linked steps; actual JSON download; no page errors or horizontal overflow at 390 px. No execution button was clicked.
- Real API: downloaded knowledge matches the source receipt hash, and accepted-source search returns the latest six-step source with verification=not_executed. Video and transcript bytes match the declared reused inputs.

## Latest real source-learning run
- ID: `825b2bf417154c019c55f869fd9567cc`.
- Source: the existing authorized Blender tutorial video; reused video bytes and Gladia transcript only. No previous plan, model observations, manual review, or old Blender artifact was supplied.
- Outcome: `source_checked` / `ready_for_review` after 10 tool decisions and 19 inspected frame images. Model: `holo4-27b`; controller reasoning: `medium`. All six final source checks returned supported=true, issues=[].
- Reason: all final steps passed model source checks. The Agent handled an unresolved step by looking again, recovered a provider timeout, and revised rejected proposals before acceptance. Earlier failed runs remain on disk.
- Accepted `plan.json` and `knowledge.json` exist; no new GUI execution or `.blend` artifact. Learned final values differ from the old reference case: 0.24 m and Vertices, not the legacy 0.22 m / Edges recipe. Do not run the old checker and promote this source to verified.
- Earlier real attempts encountered provider rate limits, timeouts, and unresolved citation alignment. Unit tests prove guard behavior, not model-learning reliability.

## Remaining gates
1. Repeat real autonomous learning to establish reliability; one accepted run does not establish it. Keep citation/source gates intact. The accepted plan was not manually edited, and no historical plan was supplied.
2. Integrate the capability into the original AppDNA project/skills/graph workflow if that surface is required. The tested caller is the isolated video workbench; the original main orchestrator is not established as integrated.
3. Implement independent artifact checks derived from the accepted source, not a fixed historical recipe. The legacy reference check is preserved as reference evidence only for new source jobs.
4. A new source-Agent → GUI → independently checked artifact run has not been completed.

All changes remain local and uncommitted. No commit/push was made. Port 8000 and the original AppDNA services were not changed during this verification. The disposable 8788 browser-verification server is stopped after acceptance checks.

Machine-readable evidence: `deliverables/AppDNA-video-learning-agent-status.json`. Raw local receipts remain under ignored `tasks/video-agent/evidence/jobs/`.
