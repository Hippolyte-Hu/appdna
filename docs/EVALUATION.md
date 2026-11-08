# Evaluation & evidence

[← Project overview](../README.md) · [Workflow & architecture guide](WORKFLOWS.md)

**Documentation review: 8 November 2026.** This page separates retained live execution evidence, checks rerun during this review, and capabilities that remain unproven. It supersedes older checkpoint-level readiness statements; historical handoffs are retained for context.

## 1. Concrete result: learned Bevel workflow → saved Blender scene

A retained source-bound execution has all three evidence layers:

- **Source learning:** original job `825b2bf417154c019c55f869fd9567cc` contains six steps accepted by separate model source checks.
- **GUI execution:** execution job `bb98cc914ecf4be385ea4eda0bc01e6c`, using **Holo4-27B**, reused checked knowledge/media and recorded 17 tutorial-loop events. The GUI loop reached `observed_complete`; saving had its own receipt.
- **Artifact verification:** its saved `replica.blend` passed **11** independent, source-bound structural/parameter checks under `blender_bevel_v1`.

During this documentation review, a **new background Blender inspection process** reopened that exact saved artifact, validated the target binding, recomputed the checks and confirmed its bytes were unchanged. The process exited **0**; all **11 checks passed**. This was a fresh inspection of an existing result, **not a new GUI run or a new learning trial**.

[Machine-readable, sanitized verification summary](evidence/blender-verification.json)

### What the saved file contains

Expected values were derived from source evidence before execution, not chosen after inspecting the result:

- Shape: cube — measured **cube**.
- Bevel affect: `VERTICES` — measured **`VERTICES`**.
- Width type: `OFFSET` — measured **`OFFSET`**.
- Width: **0.24** — measured **0.23999999463558197**.
- Segments: **4** — measured **4**.
- Limit method: `ANGLE` — measured **`ANGLE`**.
- Angle limit: **30°** — measured **30.000000834826057°**.
- Smooth shading: **true** — measured **true**.
- Smooth by Angle: **true** — measured **true**.
- One visible Bevel modifier: **passed**.
- Evaluated geometry rounded beyond the base cube: **passed**.

Floating-point comparisons use the repository's verifier tolerances; these are not exact decimal equality claims.

Artifact SHA-256:

```text
9f28901c3c4f49c325dc52e2a8b5f458715be547ab4f7cd94a4396704024b9ce
```

Target binding SHA-256:

```text
84ed18f5b15f641b2270e533a095c6d000b0f9ce5c9c4924c658a5d260cfb652
```

The inspection reports Blender **5.2.0 LTS**. The learned source title refers to Blender 4.4; this result demonstrates this particular workflow transfer, not general cross-version compatibility.

### What this result does and does not prove

It establishes that one retained execution produced a saved file matching the bounded source-derived target and that a separate process can verify that file again. It does **not** establish correctness of every interpretation in the video, arbitrary Blender task completion, or repeated-run reliability. Source audits and target extraction still depend on model perception. The executor reused an accepted plan rather than relearning from raw media.

The repository includes the sanitized summary, code and tests—not the raw source video, screenshots, local database or `.blend`. Hashes identify the local evidence; they do not make omitted bytes independently downloadable or reproducible from the summary alone.

## 2. Failures are part of the evidence

Earlier local runs include provider blocks, unresolved source-learning requests, stopped executions and failed saves. In particular, the original accepted source job reached GUI-observed completion but failed to save at the requested location; it ended **`artifact_failed`**, not verified. A later, separate execution succeeded. It must not be presented as though the original failed receipt passed.

The scratch driver now enforces OS-level per-run write confinement, kernel scope attestation and directory-first saving. These mechanisms and their regressions are distinct from a prompt asking the model to save safely. The successful receipt does not justify bypassing those gates in subsequent runs.

No aggregate live success rate is claimed: the retained jobs mix debugging, source reuse, explicit stops and different failure conditions rather than a controlled benchmark.

## 3. Checks rerun during this documentation review

### Backend

From `backend/`:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests -q
.venv/bin/python -m compileall -q app
```

Result: **208 passed**, **3 deprecation warnings**. The warnings concern FastAPI `on_event` lifecycle registration and Starlette's AnyIO portal alias. Compilation passed.

These tests cover source-tool constraints and citations, provider contracts/errors, target provenance, wrong-artifact rejection, write confinement/resume attestation, save policy, source reuse, API approvals and assessment behavior. Most provider-dependent tests use synthetic fixtures. They test contracts and guards—not live model intelligence or a measured safety guarantee.

### Frontend

From `frontend/`:

```bash
node --test tests/learning.test.mjs
npx tsc --noEmit
```

Result: **13 passed**, **0 failed**; TypeScript check passed. Node emitted a module-format warning when importing the TypeScript helper. The contracts reject false verification from source checks alone, GUI observation alone, missing/changed artifacts, wrong source/target bindings and legacy checker results.

### Documentation and repository checks

Local Markdown links, section anchors, fenced shell syntax and Mermaid diagram parsing were checked. The included JSON summary was parsed and compared to the retained local receipt. `git diff --check` passed. Installed backend dependencies passed `uv pip check`.

This is a documentation-only change; no application behavior was modified here. No provider calls, new GUI execution or new browser acceptance run were performed for this review. A new production build was not run: the documentation does not change bundled frontend code. The earlier Learning Showcase implementation records its build and browser acceptance in [its historical acceptance receipt](../tasks/video-agent/LEARNING-SHOWCASE.md).

## 4. Reproduce without mistaking a test for a live demo

### Fresh clone

Follow the [README setup](../README.md#quick-start), then run the backend and frontend checks above. Provider keys and private local receipts are not required for the regression suites. A fresh clone does not contain the retained execution cited on this page.

### Read-only product inspection

Start the three services, then visit `/` and `/learning`. If the catalog is empty, that is expected on a clean checkout. Use the workbench at port 8788 to learn your own authorized source; real learning uses provider credits and may block.

### Live execution — explicit opt-in

Review the learned steps and prerequisites, unlock the Mac, ensure no other assessment/desktop execution is active, and choose **Run with Agent**. This creates a fresh run and can send real mouse/keyboard input to Blender. Do not start it on a shared desktop or while editing another document.

Success requires a new saved artifact and matching source-bound verification, not just a running badge, visible clicks or `observed_complete`. Use the actual receipt if the run stops or fails. Never copy an older verification result into the new run.

Browser scripts under `backend/tests/verify_*.py` have different effects. For example, `verify_learning_showcase.py` exercises read-only/denied-run states; `verify_showcase_launch.py` performs **real desktop execution** and then requests stop. They are not interchangeable with the unit suite and must not be launched blindly.

## 5. Current limits and next steps

- **Bounded executor/verifier:** tutorial execution is Blender-only; independent source-bound inspection is limited to `blender_bevel_v1`.
- **Model uncertainty:** unreadable controls, ambiguous branches, provider timeouts and rate limits can block learning or actions. Separate model checks are not independent ground truth.
- **Incomplete unified skill publishing:** accepted video knowledge is retrievable/reusable in the showcase; automatic publication into the main assessment graph is not implemented.
- **No controlled reliability benchmark:** repeated fresh learning and repeated fresh execution need a defined test set and protocol before reporting a success rate.
- **macOS dependency:** native input, Swift guard and Seatbelt write confinement are not Windows/Linux implementations.
- **Local authorized use:** services lack public multi-user authentication. The generic assessment driver is not the dedicated Blender sandbox. Source content and model action policies are not a guarantee against all side effects.
- **Cloud data boundary:** audio, selected images/screenshots and text can leave the Mac for configured providers. Keep credentials and sensitive source material out of Git and review exports before sharing.
- **Human decision support:** a software assessment is not formal procurement approval, security certification or complete UAT sign-off.

Near-term priorities are repeatable learning/execution evaluation, additional typed artifact verifiers and an explicit bridge from accepted video knowledge into assessment skills—without weakening the evidence gates.
