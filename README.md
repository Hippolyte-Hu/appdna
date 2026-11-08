# AppDNA

Teach an agent to acquire a software capability, then keep it only when an independent test passes.

## Current review snapshot — WIP

Branch: `feat/appdna-video-learning-agent`.

Historical published checkpoint: `4aa58ed`. [The teammate review guide](tasks/video-agent/TEAM-REVIEW.md) describes that checkpoint; the current Learning Showcase implementation is documented below. This is still **not a completed end-to-end Blender demo**.

The current local implementation adds **Learning Showcase** at `/learning` inside the existing AppDNA frontend. It displays real source-checked video knowledge, timestamped evidence and a downloadable JSON package, then provides **Run with Agent** to create a fresh execution. See [the module contract and acceptance checks](tasks/video-agent/LEARNING-SHOWCASE.md).

OS-enforced per-run write confinement and directory-first saving are implemented and regression-tested. Source checking, GUI observation and independent artifact verification remain separate. Real GUI runs may still block on model actions. The showcase has exercised both locked-desktop denial and an unlocked real launch: Blender opened, the first mouse click was dispatched and recorded, and cooperative stop reached `stopped`. The post-click screenshot does not establish that the first workflow step completed. This proves launch/action dispatch/stop, not full workflow completion. A new source-bound verified `.blend` has not been demonstrated.

Keys, downloaded videos, raw source evidence, recordings, generated reports, and local execution state are deliberately excluded from GitHub. Provider credentials belong only in ignored `backend/.env`.

The sections below describe the original AppDNA assessment flow. The newer showcase also needs the local video-learning service documented below.

The first learning target is Blender: create a cube and assign a material.

## Layout

- `backend/` FastAPI, SQLite, provider adapters, Blender sandbox
- `frontend/` Next.js project console

## Run

```bash
cd backend
uv venv --python 3.11 .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8787
```

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:3000. The frontend calls the API at `NEXT_PUBLIC_API_BASE` (default `http://127.0.0.1:8787`).

### Learning Showcase

Keep the assessment backend on 8787 and run the video-learning service separately:

```bash
cd backend
APPDNA_LEARNING_MODEL=holo4-27b APPDNA_ACTION_MODEL=holo4-27b PYTHONPATH=. .venv/bin/uvicorn app.tutorial_app:app --host 127.0.0.1 --port 8788 --no-access-log
```

Open http://127.0.0.1:3000/learning or choose **Learning Showcase** in the workspace. The frontend's allowlisted same-origin `/api/learning/*` routes bridge to the loopback service; no direct browser access to port 8788 is required. Generic assessment API routes remain a fallback to 8787.

Review the saved steps, then use **Run with Agent** to approve a fresh scratch scene and real desktop input. Keep this Mac unlocked and idle. Do not start another assessment during execution. Stop is cooperative, not an immediate interruption of an in-flight model request. Execution currently supports Blender only. This is a local authorized-use demo, not an authenticated public multi-user control service.

Knowledge stays in local `tasks/video-agent/evidence/jobs/<source-id>/knowledge.json` and `plan.json`, with frames in `agent_frames/`. Every execution has a new sibling job ID; its `run/` folder contains action evidence and any artifact verification. Browsing, exporting or reloading does not start the Agent. These knowledge files are not model training or automatically published graph skills.

Copy `backend/.env.example` to `backend/.env` and fill in the provider keys. The `.env` file is gitignored. Do not commit it.

`HCOMPANY_BASE_URL`, `HCOMPANY_MODEL`, `LINKUP_BASE_URL`, and `GLADIA_BASE_URL` select the provider endpoints. The learning engines do not hardcode those values.

Blender must be on `PATH`. If it is missing, the run fails and says so. A screenshot is never treated as verification.

## Loop

Research uses Linkup and falls back to the official Blender manual only when Linkup returns nothing. An optional audio URL or file is transcribed with Gladia. H Company turns the corpus into claims and a Blender Python experiment. A second Blender process reopens the saved file and checks the object, mesh type, material, and that the file opens. The package is written under `backend/data/artifacts/`.
