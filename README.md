# AppDNA

Teach an agent to acquire a software capability, then keep it only when an independent test passes.

## Current review snapshot — WIP

Branch: `feat/appdna-video-learning-agent`.

Start with [the teammate review guide](tasks/video-agent/TEAM-REVIEW.md) for the implemented flow, entry points, exact test status, and remaining safety work. This branch includes the application/UI work and the independently invocable Holo4 video-learning Agent; it is **not a completed end-to-end demo**.

**Do not run the tutorial GUI/save stage yet.** A real run saved to a previous scratch directory rather than the requested destination. The previous artifact was restored from a hash-matching backup, but filesystem write confinement is not implemented. Two new safety regression tests are intentionally still RED. Backend status at publication: **183 passed, 2 failed**, 3 deprecation warnings.

Keys, downloaded videos, raw source evidence, recordings, generated reports, and local execution state are deliberately excluded from GitHub. Provider credentials belong only in ignored `backend/.env`.

The sections below describe the original AppDNA flow; the review guide documents the newer video-learning workbench and its current limitations.

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

Copy `backend/.env.example` to `backend/.env` and fill in the provider keys. The `.env` file is gitignored. Do not commit it.

`HCOMPANY_BASE_URL`, `HCOMPANY_MODEL`, `LINKUP_BASE_URL`, and `GLADIA_BASE_URL` select the provider endpoints. The learning engines do not hardcode those values.

Blender must be on `PATH`. If it is missing, the run fails and says so. A screenshot is never treated as verification.

## Loop

Research uses Linkup and falls back to the official Blender manual only when Linkup returns nothing. An optional audio URL or file is transcribed with Gladia. H Company turns the corpus into claims and a Blender Python experiment. A second Blender process reopens the saved file and checks the object, mesh type, material, and that the file opens. The package is written under `backend/data/artifacts/`.
