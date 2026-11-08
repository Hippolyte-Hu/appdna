# Isolated Northstar Chatwoot sandbox

This is a reproducible setup recipe, not a claim that a live Chatwoot run has passed. Docker must be running. The image is pinned to Chatwoot Community Edition `v4.8.0-ce`; its official registry tag supports amd64 and arm64. PostgreSQL and Redis are private to this Compose project. Only Chatwoot port `127.0.0.1:3001` is exposed.

## Prepare

From the repository root:

```sh
python3 infra/chatwoot/setup.py
cd infra/chatwoot
docker compose run --rm rails bundle exec rails db:chatwoot_prepare
docker compose run --rm rails bundle exec rails runner /app/appdna/seed.rb
docker compose up -d rails sidekiq
```

The seed creates an administrator, a synthetic API inbox with automatic assignment disabled, Billing / Logistics / Customer Care teams, and the contact custom attribute `customer_tier`. It does not create or repair automation rules. The first run must start with no configured routing automations. Re-running the seed preserves existing rules; use a separate fresh Compose project/volume for a cold-environment comparison rather than silently clearing an earlier run.

Generated credentials are in ignored `local/admin.txt`. Connection identifiers and a verifier token are in ignored `local/connection.json`; neither belongs in the knowledge library or a commit.

## Connect AppDNA

Activate the backend virtual environment, then:

```sh
cd ../../backend
python -m playwright install chromium
python scripts/import_chatwoot_connection.py
```

Open [Connections](http://127.0.0.1:3000/settings), click Refresh after importing the sandbox identifiers, then use Sign in to Chatwoot. Complete the administrator login in the browser window yourself. The local API saves the session only after the designated account dashboard is visible. It does not send your password to a model. The equivalent CLI helper remains available as `python scripts/chatwoot_login.py`.

In Connections → AI model, paste the H Company API key and click Save API key; it takes effect without restarting the API. The ignored `backend/.env` remains available for advanced settings. Linkup is optional. Select the test-account checkbox only for this dedicated synthetic sandbox. Setup preserves existing files.

Connections shows whether keys and the browser sign-in are saved; these flags do not mean inference or a verifier passed. Check connection probes HTTP reachability. A run preflight also reads the teams and API-inbox type before the agent acts.

## Demo

1. Create the prefilled support-routing task.
2. Start a run with a bounded action/time budget. The model plans outcomes, retrieves documentation and observes the browser. No successful navigation sequence is injected.
3. Observe real captures and activity. The browser executor may only navigate the designated account and uses observed controls for click/type/select.
4. Inspect Results: four server-side withheld synthetic messages test refunds, delivery, complaints and incorrect routing of unrelated messages. The independent verifier writes only contacts/conversations; it cannot mutate rules, priority or assignments.
5. Add the VIP follow-up. A new session may load version-matched, previously validated knowledge, and must re-observe the interface. Seven checks cover the original four plus VIP refund, delivery and serious complaint. VIP complaints must remain urgent.
6. For a knowledge-transfer claim, repeat in a genuinely clean environment with the same software version and compare raw reports for cold/reuse sessions. A retry against already-configured rules is not evidence of transfer. No speedup is assumed.

## Fresh-install transfer and cold control

Create two independent Compose projects with new Postgres/Redis/storage volumes and different loopback ports. The helper refuses to overwrite an existing profile. It copies no database, conversations or automation rules.

```sh
python3 infra/chatwoot/fresh_sandbox.py --name transfer-reuse --port 3004
python3 infra/chatwoot/fresh_sandbox.py --name transfer-cold --port 3003
cd infra/chatwoot
docker compose --env-file local/transfer-reuse/.env run --rm rails bundle exec rails db:chatwoot_prepare
docker compose --env-file local/transfer-reuse/.env run --rm rails bundle exec rails runner /app/appdna/seed.rb
docker compose --env-file local/transfer-reuse/.env up -d rails sidekiq
```

Repeat the three Compose commands with `local/transfer-cold/.env`. The existing default sandbox on port 3001 keeps its original volumes. Profile environment files and generated credentials are under ignored `local/` paths.

Use a different saved browser session for each installation. From `backend`, with its virtual environment active:

```sh
python scripts/run_transfer.py login --profile ../infra/chatwoot/local/transfer-reuse
python scripts/run_transfer.py login --profile ../infra/chatwoot/local/transfer-cold
```

Complete each normal synthetic administrator login and press Enter when its dashboard is visible. This helper saves only that installation's browser state. It does not alter the shared backend `.env`, use the verifier token to log in, or configure business rules.

Run the reuse trial with explicit IDs from previously verified skills, then the matched cold trial:

```sh
python scripts/run_transfer.py run --profile ../infra/chatwoot/local/transfer-reuse --knowledge-ids knowledge_BASE knowledge_VIP
python scripts/run_transfer.py run --profile ../infra/chatwoot/local/transfer-cold --no-reuse
```

The harness calls the production `execute_run`, with the same goal, model, seven fixed assertions and default 150-action/1200-second budget for both trials. It requires zero rules for a new trial, records the frozen source skill IDs, uses an independent model/browser session and respects the shared single-run lock. Its tasks, activity, screenshots, results and controls appear in the ordinary AppDNA UI. No successful navigation path is provided. Source skills must already be verified for the matching Chatwoot version.

If a trial fails, preserve it. An explicit `--retry-task task_ID` repeats that task against its real partial configuration with outcome feedback; it does not reset the installation. Report all attempts when comparing time/actions. A passing repair is not a second clean start.

The API also accepts optional `knowledge_ids` alongside `reuse_knowledge: true` when starting a run. Omit them for the usual latest compatible skills. Unknown, duplicate or incompatible selections are rejected. This lets an experiment freeze its source set even if another task saves newer skills.

To make a completed installation the UI's current connection, wait for active runs to finish and run:

```sh
python scripts/import_chatwoot_connection.py --connection ../infra/chatwoot/local/transfer-reuse/connection.json --url http://127.0.0.1:3004 --session-path data/sessions/transfer-reuse.json
```

Refresh Connections to reload the address and token. The import preserves model keys, uses atomic private-file writes, refuses target changes during an active run and requires a separate session path when changing origins. Each recorded workspace's Open Chatwoot link uses its own captured environment, even after the current connection changes.

## Known limits

- The live model/browser/Chatwoot path requires an actual sandbox, valid browser session, model key and API token. Contract tests do not substitute for live integration evidence.
- The task verifier supports the Northstar routing and VIP scenarios. Free-text changes outside these acceptance criteria need their own verifier before success can be asserted.
- One active run owns the sandbox. Use a single backend worker for this local MVP. Run recovery preserves history and marks interrupted work blocked; it does not resume arbitrary browser actions after a process restart.
- Actions are paused between UI operations; in-flight UI requests can finish. Provider requests remain cancellable. Cancellation preserves the target's actual partial configuration.
- Screenshot observation is bounded to the current viewport; scrolling is explicit. No full-local inference claim is made.
- The pinned image, seed and incoming-message API contract must be smoke-tested in your Docker environment before a live presentation.

## Source references

The deployment follows [Chatwoot's official Docker guide](https://developers.chatwoot.com/self-hosted/deployment/docker), with the [official CE image tag](https://hub.docker.com/v2/repositories/chatwoot/chatwoot/tags/v4.8.0-ce/). The verifier's nested incoming message follows the pinned version's [conversation controller](https://github.com/chatwoot/chatwoot/blob/v4.8.0/app/controllers/api/v1/accounts/conversations_controller.rb) and [message builder](https://github.com/chatwoot/chatwoot/blob/v4.8.0/app/builders/messages/message_builder.rb). All test contacts use `northstar.invalid` addresses.
