# Learning Showcase — implementation contract

## User intent
Show the results of an already learned video inside the existing AppDNA application. Explain how results are saved. One explicit Run with Agent action reuses the saved workflow and opens the application for real GUI execution.

## Decisions
- English product interface; route `/learning`, linked from the existing workspace and home page.
- Preserve the current AppDNA palette, workspace panels and assessment flows. No replacement app or port.
- Read the real source catalog and receipts from the existing video-learning service. Next.js exposes an allowlisted same-origin `/api/learning/*` bridge; do not restart the active assessment backend.
- Only original `source_checked` knowledge appears as reusable workflows. Run receipts are not additional learned sources.
- Show saved instructions, expected outcomes, prerequisites, limitations, timestamped video/frame evidence, downloadable knowledge JSON and its real relative local path. File-backed knowledge is not claimed to be trained model memory or already published to the main skill graph.
- Initial executor supports Blender only. Label that scope explicitly.
- Run with Agent creates a fresh execution, then sends the existing reviewed/scratch approval, using the displayed steps as the review. Before clicking, disclose new scratch scene, desktop input, unlocked Mac and preserved original knowledge. Never execute on mount/reload.
- Keep all existing source checks, target binding, foreground and OS write-isolation gates. No tutorial-coordinate replay or fabricated execution results.
- Persist the selected execution in the page URL; poll its server receipt and restore on reload. Failed starts retain their run ID, clear error, and retry only by explicit action. Stop is cooperative and must not be described as immediate.
- Distinguish source checked, GUI observation, blocked/stopped, saved unverified and source-bound artifact verified. Never inherit the old source's or another run's verification.
- No arbitrary app automation, public hosting or modification to port 8000. Commit/push requires explicit user authorization; the user authorized publishing this update to the existing feature branch.

## Acceptance / plan
1. RED real browser check: existing home has a Learning Showcase link; module loads actual checked knowledge and its JSON. No GUI starts while browsing.
2. Add same-origin route bridge and typed frontend source/run contracts. Preserve upstream non-2xx and service-unavailable errors; restrict paths and cross-origin writes.
3. Add the responsive showcase with one workflow selection, steps, provenance, export, run/stop controls and honest execution state.
4. GREEN browser checks: navigation, persisted real knowledge, timestamp seek, export round-trip, reload, desktop/390px/320px, empty/failure/retry (clearly isolated injected failures), denied start without false success, no page errors.
5. Exercise an explicit real one-click run through AppDNA; read back its new receipt and real desktop action evidence. Report blocking model/desktop failures honestly; a working launch does not establish a verified artifact.
6. Run backend regressions, frontend type/build gates, diff/security self-review. Retain regression scripts; remove disposable artifacts and do not stop the user's existing AppDNA servers.

## Local acceptance receipt

- PASS: original AppDNA `/learning` route and navigation, source catalog, six saved steps, 19 timestamped frames, timestamp seeking, real knowledge JSON export and unchanged source package.
- PASS: real browser checks at 1440px, 390px and 320px, including the current LAN origin; no page errors or horizontal overflow.
- PASS: explicit loading/empty/read-failure/retry, denied-start and cooperative-stop UI states. Injected failure/running fixtures are isolated to the regression browser and are not real execution evidence.
- PASS: a real historical blocked execution renders its actual screenshot and step/action log without conferring verification.
- PASS: locked-desktop start returns actual HTTP 409; no GUI launch or inherited artifact.
- PASS: after unlocking, real showcase run `6ba6131ccc7146fc8003caa1de0d2d9b` returned HTTP 200, opened a new Blender scene, dispatched one click, and reached server/UI status `stopped` after the stop request. The captured post-click screen does not establish completion of the first workflow step. This is launch/action-dispatch/stop acceptance, not a completed reproduction or verified artifact.
- PASS: 208 backend tests (3 deprecation warnings), 13 frontend presentation-contract tests, TypeScript check, production build, compileall and diff whitespace checks. The Node test runner emits a module-format warning; the browser has no page errors.
- PASS: source-binding guard mutation is caught by the wrong-source regression assertion; simultaneous video-run approvals are limited to one executor after the yielding desktop check.
- PASS: 25 scoped changed/new files scanned with detect-secrets in no-network-verification mode, no findings.
- Scope limits: Blender-only execution; main skill-graph publication is not implemented; no newly verified source-bound `.blend`; no commit/push. Original 3000/8787 application remains available, with the 8788 learning service as its local backend dependency.

Reproduce read-only/denied-run browser checks from `backend` with `.venv/bin/python tests/verify_learning_showcase.py`. This regression never launches GUI input. The separate `.venv/bin/python tests/verify_showcase_launch.py` is opt-in REAL desktop execution and requests stop after observing the first recorded event. Neither test authorizes bypassing lock, foreground, source-binding or write-sandbox checks.
