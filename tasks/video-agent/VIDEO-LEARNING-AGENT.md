# Video learning Agent — approved role and implementation contract

## Product definition
A separately invocable, bounded video-learning Agent runs as an AppDNA sub-agent. It learns from a video source, requests transcript excerpts and additional frames, reconciles branches/parameters, and returns source-grounded reusable knowledge. It cannot control Blender. AppDNA remains the caller and the existing GUI executor remains separate.

User-approved role: independent video learner, used as a sub-agent, with video as a learning source. Implementation uses an async task with private per-run context, not a new OS process or a new product. This is not a coding-agent delegation.

## Scope and acceptance
- Accept the existing authorized YouTube/upload pipeline; no new provider or dependency.
- Model chooses read_transcript / inspect_frames / submit_plan / needs_input in a bounded observation-action loop. No GUI, arbitrary path, shell, network or Python tool is exposed to this Agent.
- Read requested timestamps from the actual local video, optionally crop a normalized region, persist citations and observations. Limits: 20 decisions, 48 requested frames, 4 per request, 600-second media.
- Every step must cite actually inspected frame evidence. Before accepting a plan, re-check its steps against cited source images and nearby narration in separate model requests. Reject out-of-range, missing, invented or over-wide timestamps/citations. No hard-coded 0.22 / 0.24 decision and no reuse of an old plan.
- Unresolved conflicts yield needs_input; timeouts/errors yield blocked, never a fabricated success. Model source checks remain model observations, NOT independent artifact verification.
- Persist agent.json (public action trace), knowledge.json (video provenance, steps, limitations, status), and compatible plan.json ONLY after source checks pass. Expose learned sources to the caller via API. Execution still requires existing scratch authorization and safety gates.
- Show source, status, trace, audit and downloadable knowledge in the English workbench. Old jobs remain viewable.
- Exercise real H Company learning on the original local tutorial (fresh learning, existing extracted media/ASR may be reused and disclosed), and the real browser/API. No GUI run needed to prove the learner's role; do not claim new artifact execution without one.

## Files and plan
1. app/agents/video_learning.py: private context, bounded tools, persisted trace, source checks and knowledge result. Add focused RED tests before implementation.
2. app/providers/video_learning.py plus HCompanyProvider.video_learning_turn / inspect_video_frames / check_video_step: model contracts and source-only prompts.
3. app/tutorial_app.py: invoke learner as sub-agent; expose knowledge/status and reusable source lookup. Add API tests.
4. tasks/video-agent/index.html: English source and action-trace panel with safe text rendering; browser regression.
5. tests/run_video_learning_agent.py and browser verifier: reproducible real runs, no stubs in evidence.

## Runtime policy
- Use Holo4 for learning and source auditing. The tested source model is selected with `APPDNA_LEARNING_MODEL=holo4-27b`; desktop execution remains separately selected with `APPDNA_ACTION_MODEL=holo4-27b`.
- Enable `reasoning_effort=medium` for the multi-turn learning controller, with an 8192-token completion budget. Keep single-shot frame reading and GUI grounding at their existing no-thinking default. Never store or replay hidden reasoning.
- On invalid JSON, regenerate once from the same evidence with an explicit schema. Do not repair parameter values or fabricate a response. Authentication errors are not retried; rate limits retain one bounded cooldown retry.
- Report all step-citation validation failures in one tool result; do not lower the interval/citation/uncertainty gates to obtain acceptance.
- Normalize mixed full/cropped images to an aspect-preserving padded canvas only in the source-check request. Keep original files, hashes, timestamps and crop coordinates unchanged.
- A legacy fixed reference check cannot verify a newly learned workflow. New source artifacts remain `saved_unverified` until source-derived independent checks are implemented.

## Verification commands (from backend)
- PYTHONPATH=. .venv/bin/python -m pytest tests/test_video_learning_agent.py tests/test_tutorial_app.py -q
- PYTHONPATH=. .venv/bin/python -m pytest tests -q
- .venv/bin/python -m compileall -q app
- git diff --check

Baseline: main, dirty pre-existing workspace retained; 132 tests passed, 3 deprecation warnings. No automatic commit/push, no changes to port 8000, no coding-agent CLIs. Service replacement only after idle check; disposable browser previews stopped after validation. Correctness/security/design/performance self-review required.
