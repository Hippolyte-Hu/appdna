# AppDNA

Give an agent a software task, observe its computer use, then keep the procedure only when an independent outcome test passes.

This branch adds a Northstar Goods / Chatwoot demo with tasks, a workspace, independent routing checks, evidence, VIP follow-up requirements and saved skills. The original native-app explorer remains available.

The interface uses official **shadcn/ui New York components**, **Radix UI**, Tailwind CSS 4 and bundled Geist fonts. The light sage surfaces, deep green controls and DNA artwork share one theme. No successful run, screenshot or learned skill is fabricated.

## Run locally

Use Node.js 22 or newer for the frontend.

```sh
cd backend
uv venv --python 3.11 .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8787
```

```sh
cd frontend
npm ci
npm run dev
```

Open [AppDNA](http://127.0.0.1:3000/tasks). The task UI proxies API calls to `http://127.0.0.1:8787`; set `APPDNA_API_URL` if the API runs elsewhere. The optional `NEXT_PUBLIC_API_BASE` overrides the browser API origin. Development and production outputs use separate directories.

## API key and Chatwoot setup

Open **[Connections](http://127.0.0.1:3000/settings) → AI model → API key**, paste your **H Company** key, and click **Save API key**. Saving takes effect immediately. The local API writes the ignored `backend/.env` with file mode `0600` and returns only whether a key is saved. The form clears after saving; it does not retrieve the saved value.

For actual execution, follow the [local Chatwoot setup](infra/chatwoot/README.md). Save the Chatwoot address, account/inbox IDs and API token in Connections, select the dedicated test account, then use **Sign in to Chatwoot**. Complete the login yourself in the browser window. Only the resulting local session is saved. Changing the target account invalidates the previous session and token.

Linkup is optional under **Web search**. Without its key, research retrieves official Chatwoot documentation. Advanced provider endpoints/model names are in `backend/.env.example`; copy it only when starting without an existing `.env`. Secrets, browser sessions and generated sandbox credentials stay out of Git and the executor's structured prompt.

## Demo flow

1. Create the prefilled routing task.
2. Run it, or open Run settings to adjust the action/time budget and saved-skill reuse.
3. Observe actual browser captures, activity and pause/resume/stop controls.
4. Inspect Results, including expected/actual routing, evidence and the selected run's JSON report.
5. Add the VIP requirement. The follow-up retains the four original checks and adds three VIP checks.
6. A completely passing run with an observed UI configuration change can save a skill. A fresh environment is required to demonstrate transfer.
7. Open **Knowledge → 3D graph** to explore the app, saved skills, source/reuse runs, independent checks and documentation. Rotate or zoom the graph, search for a node, then open its actual skill or result. The **Skills** tab retains the table view.

Routes: `/tasks`, `/tasks/[id]`, `/tasks/[id]/results`, `/knowledge`, `/settings`. The original experience is at `/explore` and `/projects/[id]`.

The executor operates only the designated account's visible UI. The independent verifier creates withheld synthetic conversations and reads assignments/priorities; it never repairs automation rules. Missing dependencies and model failures remain explicit, with untested results kept untested.

## Validation and current limits

```sh
cd backend
python -m pytest tests/test_connections.py tests/test_tasks.py tests/test_core.py tests/test_visual.py tests/test_provider_connection.py tests/test_browser_agent.py tests/test_grounded_knowledge.py tests/test_sandbox_setup.py tests/test_knowledge_graph.py -q
cd ../frontend
npm run typecheck
npm run build
npm audit
```

The current backend passed **92 tests**, and the frontend passed type checking and a production build. The interface revision also passed 20 responsive geometry checks. The [3D knowledge graph](docs/knowledge-graph.md) was checked with real WebGL rendering, node selection, evidence navigation and 320/375/1440px layouts. See the [implementation record](docs/implementation.md), [browser QA](docs/browser-qa.json) and [review](docs/review.md).

The live Chatwoot demo passes **4/4 base checks** and **7/7 VIP follow-up checks** using `holo4-35b-a3b`. A later [fresh-install transfer experiment](docs/transfer-demo.md) began with zero rules, contacts and conversations: two frozen saved skills reached **7/7 after one correction**; the independent no-skill control remained **6/7 across three observed attempts**. All attempts are recorded; no one-shot or general speedup claim is made.

The original model timeout remains in history. Holo's native function-calling conversation, bounded retries, durable action/research history and request timings support actual browser execution. Skills are reconstructed locally from executed UI actions after verification. See the [first live acceptance record](docs/live-demo.md) and [transfer evidence](docs/transfer-demo.json). The original Blender integration additionally requires Blender on `PATH`.

PostCSS is pinned through a compatible override so Next.js 15 and the styling pipeline use the patched 8.5.32 release. The dependency audit reported zero vulnerabilities at preparation time. Official shadcn component sources and their MIT license are in `frontend/components/ui/`.
