# AppDNA

Learn a software workflow from video, keep its source evidence, and reproduce it through computer use. Native execution currently targets Blender on macOS. Independent artifact inspection supports a default cube with a Bevel modifier and smoothing.

The main application opens the video workbench. Projects, skill graphs and packages are available through `/assessments` and `/projects/{id}`. See [the validation record](docs/video-learning-validation.md) for exact test results and live-execution evidence.

## Requirements

- Python 3.11+, Node.js 22+, FFmpeg and FFprobe on `PATH`.
- Blender in `/Applications/Blender.app`, on `PATH`, or selected through `BLENDER_BIN`.
- An H Company API key. Gladia transcribes videos when YouTube or supplied captions are unavailable.
- macOS device control and screen recording permissions for the application running the controller. This machine calls device control **System Settings → Privacy & Security → Device Control and Data Access**; earlier macOS versions call it **Accessibility**. The workbench checks the actual permission state before execution.

## Start locally

```sh
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp -n .env.example .env
```

Fill in the keys in `backend/.env`, then start one controller worker:

```sh
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open [AppDNA](http://127.0.0.1:3000). Browser requests use the frontend origin. Set `APPDNA_API_URL` when the API uses a different address. Development and production builds use separate output directories.

`APPDNA_LEARNING_MODEL` and `APPDNA_ACTION_MODEL` select learning and execution models independently, including in `.env`. Both fall back to `HCOMPANY_MODEL`; the example selects `holo4-27b`. Restart the API after editing configuration. Keys and generated local evidence are ignored by Git.

## Video → capability

1. Choose **Use Blender example**, paste an authorized YouTube link, or upload MP4, MOV, WebM or MKV. Videos are limited to 10 minutes and 100 MB.
2. Learn from narration and inspected frames. The source agent can revisit and crop frames, propose semantic steps and revise rejected source checks. Each accepted step cites real inspected images inside its source interval.
3. Review the source trace, steps, limitations and downloadable knowledge. Missing dependencies, ambiguous evidence and provider errors remain visible.
4. Approve a new scratch scene. A dedicated Blender PID runs inside an OS write sandbox confined to that run's directory. Actions use fresh screenshots; lock, permission, foreground and repeated-action checks guard input. Transient provider failures and foreground changes pause the owned scene. **Resume same scratch scene** continues unfinished steps with a new capture, preserving completed steps and the cumulative action budget. **Stop** closes the paused scratch process.
5. After observed completion, save `replica.blend` through the GUI. Source-derived targets are bound to the video, knowledge and plan before execution. A separate Blender process reopens the exact saved file and compares measured state with those targets. Artifact hashes confirm inspection left the file unchanged.
6. **Reuse in a new scratch run** transfers checked knowledge to a new directory, process and scene. Execution receipts belong to each individual run.
7. **Save to projects & skill graph** imports the procedure and evidence into the main console. Download its ZIP package with skills, graph and source receipts. Imported video steps retain their observed status; independent artifact results are reviewed in the video workbench.

Optional transcript uploads accept YouTube JSON3 or JSON arrays of timestamped `start`, `end` and `text` segments. Captions are validated against video duration. Steps still require model source checks against original video frames.

Controller restarts preserve evidence and mark interrupted jobs blocked. An arbitrary PID or an old PID file cannot resume desktop control: only a still-live process launched and attested by the current controller can resume. Use one API worker for this local desktop application.

## API entry points

- `/video/api/tutorials`: create/list tutorials; `/{id}` exposes source and run receipts.
- `/video/api/tutorials/{id}/run`, `/resume` and `/stop`: reviewed scratch execution, attested resume and stop.
- `/video/api/video-sources`: search accepted knowledge; `/{id}` downloads JSON.
- `/video/api/video-sources/{id}/reuse`: prepare a fresh execution using checked knowledge.
- `/video/api/tutorials/{id}/project`: idempotent project, skill graph and package import.
- `/video/api/runtime` and `/desktop`: dependencies, models and permission status.

The standalone workbench remains available through `app.tutorial_app:app` on a separate port. The original assessment flow is under `/assessments`.

## Verification

```sh
cd backend
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest tests -q
.venv/bin/python -m compileall -q app
cd ../frontend
npm run typecheck
npm run build
```

Real browser acceptance against an existing accepted learning receipt:

```sh
cd backend
.venv/bin/python tests/verify_video_learning_browser.py JOB_ID \
  --base http://127.0.0.1:3000/video --check-project
```

Unit fixtures and OS regression probes are separate from real video/model receipts. Unsupported artifact types remain unverified. This is a bounded Blender implementation; it does not claim arbitrary application support or a general reliability rate.
