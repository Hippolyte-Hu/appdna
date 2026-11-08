# AppDNA computer-use demo

Local branch: `codex/computer-use-demo`, based on main on 2026-11-07. Final interface revision prepared on 2026-11-08 (Europe/Paris).

## Integration audit and product choice

The original project combines Next.js 15 / React 19 with FastAPI, SQLAlchemy and SQLite. The H Company adapter already supports multimodal structured requests; Linkup provides research. The native visual loop offers bounded observation/action traces, and the Blender verifier checks a saved artifact in a separate process. Those parts remain available at `/explore` and `/projects/[id]`.

The original engine lacked browser navigation, business-task acceptance criteria, recoverable controls, per-action persistence, applicable cross-run knowledge and a Chatwoot verifier. These were added rather than replacing the original project schema.

The supplied Northstar / Chatwoot routing task best exposes the computer-use theme: a business goal, UI-only configuration, and independent observation of the resulting conversation assignment. Generic chat, a software catalog, audio upload and generated Blender scripts are secondary to this proof. No event-specific scoring rules were supplied, so this is a product judgment.

## Final interface

The primary interface uses official shadcn/ui New York sources generated with CLI 4.23.0, Radix UI 1.8.1, Tailwind CSS 4.3.5, Lucide icons and locally bundled Geist fonts. Ant Design was removed. Component source attribution is included in `frontend/components/ui/LICENSE`.

The design keeps white space and direct controls. Primary actions use deep green; sage surfaces, the DNA mark and strand illustration establish a consistent identity. The same artwork appears only as branding/empty-state decoration. It cannot be mistaken for captured Chatwoot evidence.

The six internal stages appear as three public steps: Learn the app, Make changes, Check results. Raw records and setup commands are available on demand. The UI does not add explanatory banners, fictional metrics, seeded successes or fake screenshots.

Connections saves H Company and optional Linkup keys to the ignored local `.env`, with atomic replacement, unrelated settings preserved, `0600` permissions and immediate settings reload. It only returns saved flags. Chatwoot setup includes account/inbox IDs, token, a test-account guard and a manual browser login. Changing the target invalidates old account credentials. Invalid input and external-origin writes receive secret-free errors.

## Execution and evidence

Tasks and run history persist in SQLite. SSE reports actual state; controls and bounded budgets remain recoverable. The browser executor receives screenshots and observed controls and is restricted to the configured account. It cannot navigate API/login endpoints or use the verifier token.

The verifier's test messages are withheld from the executor. It writes only synthetic contacts/conversations and reads results; it never repairs assignments, priority or automation rules. VIP follow-ups retain the original four assertions and add three more. Reusable knowledge needs every required check, an executed UI action and a real before/after configuration change. Merely retesting already-correct rules does not establish transfer.

The browser agent uses Holo's native function-calling protocol, matching tool-result IDs and screenshot observations. It retains three recent images, a rolling visual conversation and a durable action ledger. Research results are recorded as actions, official documentation excludes site navigation, and exhausted research is removed from the allowed tool set. Retry feedback includes only previous expected/actual outcomes, never the withheld message fixtures.

Inference has a 45-second request timeout and one retry for transient transport/status failures. Authentication failures are not retried. The runner's independent wall-clock and cancellation guards stay responsive, and model/version/latency metadata is recorded without credentials or private reasoning. A stale executor exits when another API process has recovered its run.

Opening an action dropdown is allowed even when its menu also lists email/webhook actions; choosing those forbidden actions remains blocked. Skills are reconstructed locally from executed UI steps with action/screenshot references. Documentation examples cannot add unexecuted skill operations. Superseded artifacts and all original run evidence are retained.

## Verification

- `python -m pytest tests/test_connections.py tests/test_tasks.py tests/test_core.py tests/test_visual.py tests/test_provider_connection.py tests/test_browser_agent.py tests/test_grounded_knowledge.py -q`: **73 passed**. Covers persistence, independent HTTP contracts, hidden-test separation, control/cancellation, restart recovery, grounded knowledge admission, native tool conversation, bounded retries and secret handling.
- `npm run typecheck` and `npm run build`: passed on Next.js 15.5.29. Development output is isolated from production output. Node.js 22+ is required by the generated component stack.
- `npm audit`: **zero vulnerabilities** after updating PostCSS to 8.5.32 and applying its compatible override to Next.js.
- Five pages × 320/375/414/768px: **20 geometry checks passed**. Labeled Radix checkbox controls were checked through their associated labels. Long task names, mobile navigation and the model-error layout were inspected. See `browser-qa.json`.
- Real browser checks: task creation/required validation, saved run budgets/time/reuse checkbox, search/filtering, historical selection, results navigation and refresh, selected-run JSON exports, untested evidence drawer, seven-check VIP follow-up, saved-credential flags and reachable Chatwoot probe.
- A fresh browser tab traversed the final pages without console errors/warnings. Intermediate Tailwind migration errors were resolved by switching to the v4 PostCSS plugin and restarting the development server.
- The original explorer was visually checked after the Tailwind upgrade. Its custom legacy colors remain in the v4 theme.
- The pinned CE Compose recipe previously passed `docker compose config --quiet`; the seed passed Ruby syntax checking. Docker is now available, and the real Chatwoot account/inbox/team preflight passed.

## Live acceptance status

The original attempt **`run_23f7a2c4752e`** failed during H Company planning with a 120-second read timeout and performed no UI actions. That failed record is preserved. On 2026-11-08, actual planning and multimodal inference returned successfully. Later execution exposed harness problems: repeated research without useful history, an unsuitable stateless agent contract, a dropdown permission false positive, and incorrect message-field selection. These were fixed without supplying a scripted navigation path.

Base routing subsequently passed **4/4** independent checks in **`run_9fafa2b75467`** using **`holo4-35b-a3b`** and actual UI configuration changes. It recorded 29 actions, including wait/research, and saved verified knowledge. See [live-demo.md](live-demo.md) for the current follow-up results, request timing, evidence checksums and limits. This does not establish the cause of the earlier upstream transport stall or guarantee future provider availability.

- [x] Repository integration audit and new branch.
- [x] Task/run/evidence/control/knowledge implementations.
- [x] Independent verifier contracts and local connection setup.
- [x] shadcn interface, brand styling and responsive/browser validation.
- [x] Live Chatwoot API preflight.
- [x] M0 model-driven live UI action.
- [x] M1–M2 actual routing creation, independent positive/negative checks and observed failed configurations.
- [x] M3 separate fresh installations, frozen-source reuse and a recorded no-skill control; reuse passed after correction, control remained failed in three observed attempts.
- [x] M4 VIP follow-up, skill reuse and seven independent checks, including complaint precedence.
- [x] M5 complete browser-driven demo, actual screenshots, evidence inspection and report export.

The [fresh-install transfer record](transfer-demo.md) now covers M3: independent empty databases, explicit source skill IDs, all attempts, safe retry entry points and complete successful transfer verification. The new API can freeze a source skill set; the profile harness uses the production orchestrator without changing shared live connections. Workspace links use the recorded environment. Current checks passed **86 backend tests**, frontend type checking and the production build. The single observed comparison does not establish a general performance gain; the cold arm never reached a complete pass. The original Blender integration still requires a Blender executable on PATH.

## Primary references

- [Chatwoot automations](https://www.chatwoot.com/hc/user-guide/articles/1677689800-how-to-use-automation)
- [Conversation priority](https://www.chatwoot.com/hc/user-guide/articles/1682679737-how-to-assign-a-priority)
- [Create conversation API](https://developers.chatwoot.com/api-reference/conversations/create-new-conversation)
- [Chatwoot Docker deployment](https://developers.chatwoot.com/self-hosted/deployment/docker)
- [H Models API](https://hub.hcompany.ai/models-api/overview)
- [Holo agent core concepts](https://hub.hcompany.ai/models-api/build-an-agent/core-concepts)
- [Holo function calling](https://hub.hcompany.ai/models-api/build-an-agent/function-calling)
- [shadcn Next.js setup](https://ui.shadcn.com/docs/installation/next)
- [shadcn Tailwind 4](https://ui.shadcn.com/docs/tailwind-v4)
