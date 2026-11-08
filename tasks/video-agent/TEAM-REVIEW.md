# Teammate review guide — WIP snapshot

Branch: `feat/appdna-video-learning-agent`. This is a review checkpoint, not a release. Source code, tests, design contracts, and the English workbench are included. Credentials, raw evidence, downloaded tutorial media, generated deliverables, caches, and local execution state are not included.

## What changed

- AppDNA interface, interactive knowledge graph, recording evidence, source matching/control exploration, and timeout/resume improvements.
- A separately invocable video-learning Agent, callable as an AppDNA sub-agent. It has a private source-learning context and bounded tools for transcript reading, frame extraction/cropping, plan proposals, and source checks. It has no desktop or arbitrary shell tool.
- YouTube/upload source ingestion using FFmpeg, Gladia transcription, and H Company vision. Holo4-27B is the current learning/action model choice; learning and desktop configurations remain separated.
- English video workbench with learning trace, timestamped source-linked steps, accepted knowledge download/search, source-derived artifact targets, and measured-versus-expected artifact results.
- A bounded `blender_bevel_v1` artifact-target schema. Holo4 derives final-state expectations from the latest inspected frame cited by the final step. A separate source-check request must accept those expectations. Video, knowledge, plan, and target hashes bind the check to this source, not a historical recipe.
- A separate read-only Blender inspection process measures saved scene state. Source acceptance, GUI completion, and artifact verification remain different gates.

## Start reading here

- `backend/app/agents/video_learning.py`: source-only agent loop and acceptance gates.
- `backend/app/providers/video_learning.py`: structured source requests, audit behavior, bounded retries, and image normalization.
- `backend/app/tutorial_app.py`: isolated workbench API and execution orchestration.
- `backend/app/engines/tutorial_expectations.py`: bounded source-derived targets, provenance binding, and measured-value comparison.
- `backend/app/engines/tutorial_artifact.py` and `backend/app/adapters/inspect_tutorial_artifact.py`: GUI-save stage and independent read-only inspection.
- `backend/app/drivers/blender_tutorial.py` and `tasks/video-agent/blender_guard.swift`: dedicated scratch PID, foreground/lock checks, real input events.
- `tasks/video-agent/index.html`: English workbench.
- `frontend/`: original AppDNA application surface; full video-source integration into its project/skills/graph workflow is still incomplete.

## What was actually exercised locally

- Accepted learning receipt: `825b2bf417154c019c55f869fd9567cc`, Holo4-27B, 10 decisions, 19 inspected images, 6 source-checked steps. This reused video and Gladia transcript bytes only, not an old plan or manual parameter edits. It is one successful run, not a reliability estimate.
- Final artifact targets passed a Holo4 source check against final cited `frame-11`: cube; Vertices; Offset; Amount 0.24; Segments 4; Angle limit 30 degrees; smooth-shading/Smooth-by-Angle targets. This is model source checking, not independent truth certification.
- A fresh dedicated Blender process executed the six steps through actual GUI input. The save model then used the previous scratch directory. The requested file was absent, and the job correctly ended `artifact_failed`, not `verified`.
- That save overwrote the earlier scratch reference artifact. Its original bytes were restored from the automatic `.blend1` backup and checked against both the historical verification hash and the previously delivered copy. The wrongly located new artifact and an incident receipt were preserved locally. Do not use this recovery as a successful correctly located GUI save.
- Real Chromium workbench checks: source/model/trace/targets exposed, no page errors, no horizontal overflow at 390 px. These are UI checks, not artifact success.

Raw receipts and media are deliberately not part of this branch. The statements above report local execution, not bundled reproducible fixtures. Unit tests use explicitly synthetic fixtures and are not substitutes for those runs.

## Safety blocker — do not execute the GUI/save stage

The current validator limits typed destinations but does not independently confirm the active file-browser directory. A model can skip editing that directory and click an existing file's Overwrite button. PID/foreground/lock checks do not prevent this filesystem mistake.

Before another live GUI run, implement and test OS-enforced per-run write confinement plus an appropriate save-state gate. The current driver does **not** implement the proposed sandbox or attested-resume APIs. Merely changing the prompt, copying the wrongly located artifact to the desired name, or passing the old 0.22/Edges checker is not a fix.

## Exact test checkpoint

From `backend/`, the actual full regression result was:

```text
2 failed, 183 passed, 3 warnings
```

The two failing RED tests in `tests/test_blender_write_sandbox.py` are:

- `test_sandbox_denies_writes_outside_own_scratch`: required `sandbox_command` is not implemented.
- `test_resume_refuses_unattested_process`: required `resume` attestation API is not implemented. The older CLI currently attaches to a PID directly; this test describes a proposed safer replacement, not an existing method regression.

Python application compilation and `git diff --check` passed. The three warnings are existing FastAPI lifespan/Starlette AnyIO deprecations. A new frontend production build was not run for this publication checkpoint.

## Reproduce tests / inspect UI without GUI execution

Use Python 3.11 and Node dependencies from the repository lockfile. No provider keys are needed for unit tests.

```bash
cd backend
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
PYTHONPATH=. .venv/bin/python -m pytest tests -q
```

For the isolated workbench (opening this UI does not itself start Blender):

```bash
cd backend
APPDNA_LEARNING_MODEL=holo4-27b APPDNA_ACTION_MODEL=holo4-27b \
  PYTHONPATH=. .venv/bin/uvicorn app.tutorial_app:app --host 127.0.0.1 --port 8788
```

Open `http://127.0.0.1:8788`. The historical receipt will not appear in a fresh clone because local evidence is excluded. Do not press **Run on a new Blender scratch scene**, and do not call `/run` or the Blender execution CLI until the safety blocker is fixed. Real source-learning requests require your own provider configuration in ignored `backend/.env`, authorized source media, and provider credits. Stop the disposable server after inspection.

## Remaining acceptance gates

1. Implement and verify write confinement and safe save handling; keep the new tests RED until the real mechanisms exist.
2. Execute a new source-bound scratch run, save to the exact authorized destination, independently reopen and check its real `.blend` file.
3. Repeat real source learning to measure reliability rather than extrapolating from one accepted run.
4. Finish original AppDNA project/skills/graph caller integration; the isolated workbench is the currently exercised caller.

Earlier handoffs and specifications are historical snapshots. This guide describes the publication checkpoint and supersedes older claims that no GUI execution has occurred or that the entire current test suite is green.
