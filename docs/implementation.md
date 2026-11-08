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

Model transport timeouts, access failures and rate limits now create actionable blocked records without echoing credentials or upstream diagnostics. Historical records remain intact.

## Verification

- `python -m pytest tests/test_connections.py tests/test_tasks.py tests/test_core.py tests/test_visual.py tests/test_provider_connection.py -q`: **58 passed**. Covers persistence, independent HTTP contracts, hidden-test separation, control/cancellation, knowledge admission, secret handling and the observed model-timeout failure path.
- `npm run typecheck` and `npm run build`: passed on Next.js 15.5.29. Development output is isolated from production output. Node.js 22+ is required by the generated component stack.
- `npm audit`: **zero vulnerabilities** after updating PostCSS to 8.5.32 and applying its compatible override to Next.js.
- Five pages × 320/375/414/768px: **20 geometry checks passed**. Labeled Radix checkbox controls were checked through their associated labels. Long task names, mobile navigation and the model-error layout were inspected. See `browser-qa.json`.
- Real browser checks: task creation/required validation, saved run budgets/time/reuse checkbox, search/filtering, historical selection, results navigation and refresh, selected-run JSON exports, untested evidence drawer, seven-check VIP follow-up, saved-credential flags and reachable Chatwoot probe.
- A fresh browser tab traversed the final pages without console errors/warnings. Intermediate Tailwind migration errors were resolved by switching to the v4 PostCSS plugin and restarting the development server.
- The original explorer was visually checked after the Tailwind upgrade. Its custom legacy colors remain in the v4 theme.
- The pinned CE Compose recipe previously passed `docker compose config --quiet`; the seed passed Ruby syntax checking. Docker is now available, and the real Chatwoot account/inbox/team preflight passed.

## Live acceptance status

The live attempt **`run_23f7a2c4752e`** reached the real Chatwoot preflight, then failed during H Company task planning with a 120-second read timeout. `GET /v1/models` returned 200 and listed `holo4-27b`; a separate minimal 64-token inference request timed out at 30 seconds. This establishes API reachability/model listing, not working inference or model entitlement.

The attempt contains zero UI actions, zero verification results and no screenshot or saved skill. It did not alter the routing configuration. The timeout-handling improvement is covered by isolated regression tests; the historical record is not rewritten.

- [x] Repository integration audit and new branch.
- [x] Task/run/evidence/control/knowledge implementations.
- [x] Independent verifier contracts and local connection setup.
- [x] shadcn interface, brand styling and responsive/browser validation.
- [x] Live Chatwoot API preflight.
- [ ] M0 model-driven live UI action.
- [ ] M1–M4 complete routing, negative/VIP checks and fresh-session knowledge transfer.

The interface and implementation are reviewable. A live successful run and transfer claim still depend on completing model inference and the acceptance checks above. The original Blender integration test also requires Blender on PATH, absent on this machine.

## Primary references

- [Chatwoot automations](https://www.chatwoot.com/hc/user-guide/articles/1677689800-how-to-use-automation)
- [Conversation priority](https://www.chatwoot.com/hc/user-guide/articles/1682679737-how-to-assign-a-priority)
- [Create conversation API](https://developers.chatwoot.com/api-reference/conversations/create-new-conversation)
- [Chatwoot Docker deployment](https://developers.chatwoot.com/self-hosted/deployment/docker)
- [H Models API](https://hub.hcompany.ai/models-api/overview)
- [shadcn Next.js setup](https://ui.shadcn.com/docs/installation/next)
- [shadcn Tailwind 4](https://ui.shadcn.com/docs/tailwind-v4)
