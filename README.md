# AppDNA

Teach an agent to acquire a software capability, then keep it only when an independent test passes.

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
