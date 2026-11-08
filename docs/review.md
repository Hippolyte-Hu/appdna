# AppDNA demo — review record

Branch: **`codex/computer-use-demo`**. Base: `Hippolyte-Hu/appdna` main at `7833271eb48d1d209cb5d291350288d4c130a990`.

Review the [running demo](http://127.0.0.1:3000/tasks), [Connections](http://127.0.0.1:3000/settings), [implementation record](implementation.md), [first live acceptance](live-demo.md) and [fresh-install transfer/control evidence](transfer-demo.md). The [initial source manifest](review-manifest.json) is the historical pre-approval snapshot for commit `73191f2`, not a manifest of subsequent fixes.

## Prepared change

- Make the Northstar / Chatwoot business task the primary demo. Preserve the existing native explorer and provider/backend boundaries.
- Use official shadcn/ui New York components, Radix primitives and Tailwind 4. Ant Design is absent from the final dependencies and source.
- Preserve the open layout and concise labels. Add deep green controls, sage surfaces, a DNA brand mark and decorative strand artwork. The artwork is an empty-state illustration, never software evidence.
- Add persistent tasks/run history, SSE, budgets, pause/resume/stop, scoped browser actions and evidence capture.
- Verify withheld synthetic messages independently; never repair rules through the verifier. Require a demonstrated configuration change and complete independent pass before saving knowledge.
- Add VIP follow-up regression checks and saved skills.
- Add usable API key, verifier-token and browser-login setup in Connections. Secret values are neither returned to the UI nor committed.
- Add a pinned Chatwoot CE sandbox recipe, setup helpers, tests, screenshots, dependency lockfile and source attribution.
- Handle model timeouts/access/rate-limit errors with direct, credential-free messages. Preserve actual run history.

## Validation

The initial interface revision passed **58 backend tests**, TypeScript checking, the production build and the dependency audit. Twenty responsive geometry checks passed across five pages at 320/375/414/768px. A fresh browser session reported no console errors or warnings. The original native explorer still renders after the Tailwind migration. The H Company/native-agent and recovery fixes now pass **73 backend tests**; see the implementation record for the command.

Browser checks exercised creation/required validation, budget/time/checkbox persistence, search/status filtering, historical selection, result navigation/refresh, report exports, evidence drawers, a seven-check VIP follow-up and mobile navigation. Credential persistence/redaction tests use a temporary env file.

## Actual live result

Docker and Chatwoot became available during preparation. Run **`run_23f7a2c4752e`** for **`task_a8ce72de18a6`** passed the real API inbox/team preflight, then the H Company planning request timed out after 120 seconds. The model-list endpoint returned 200 and listed the configured model; a separate bounded minimal inference request also timed out.

That historical run has **zero UI actions and zero routing checks**. Its failed record is preserved. Later, run **`run_9fafa2b75467`** completed actual browser operations, changed configuration and passed **4/4** independent routing checks with `holo4-35b-a3b`. The [live record](live-demo.md) contains the VIP follow-up, failed precedence test, grounded skill provenance and current screenshots. Fresh-environment transfer remains unmeasured. The original Blender integration requires an unavailable Blender executable.

## Git history and authorization

The initial interface revision was committed and pushed as **`73191f2e69d2bbd250f099356dbe5df8d99026b8`**, “Build verifiable computer-use demo with shadcn UI”.

The user explicitly waived repeat Git push approval: “approve 推吧，以后push这种操作不需要人工确认” (recorded 2026-11-08T00:15:38Z in the AppDNA conversation and global AGENTS.md). Follow-up fixes stay on **`codex/computer-use-demo`** in **`https://github.com/Hippolyte-Hu/appdna.git`**. This authorization does not cover email, external forms or applications. Local `.env`, generated credentials, sessions, SQLite data, dependencies and build outputs remain excluded.

## Initial interface screenshots

These captures show the initial interface revision and its original timeout. Current successful execution screenshots are in the live acceptance record.

Draft workspace with the final branding:

![Draft workspace](screenshots/workspace.jpg)

Connections, with saved values hidden:

![Connections](screenshots/settings.jpg)

Actual model timeout:

![Real failed run](screenshots/failed-run.jpg)

Results remain untested:

![Untested results](screenshots/results.jpg)
