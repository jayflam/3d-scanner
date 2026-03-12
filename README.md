## InsuraScan — 3D Vehicle Damage Assessment (Web + Mobile AR)

InsuraScan lets adjusters and drivers upload **exterior/interior vehicle videos**, automatically reconstruct a **3D model**, run **AI damage analysis**, and review results in a **web dashboard** – including a **web‑only AR view on mobile** to walk around the reconstructed car.

### How it works (end to end)

- **Capture & upload**
  - User records short exterior and/or interior videos on their phone.
  - Videos are uploaded to the API: `POST /api/v1/assessments/{id}/videos/{exterior|interior}`.

- **Processing pipeline (backend)**
  - Frame extraction (FFmpeg) → `frames/{assessment_id}/{type}/frame_XXXX.jpg`.
  - Structure‑from‑Motion (COLMAP) → camera poses + sparse reconstruction.
  - 3D Gaussian splatting (Nerfstudio `splatfacto`) → `.ply` splat in blob storage.
  - GLB export for AR/web (via `trimesh`) → `models/{assessment_id}/{type}.glb`.
  - AI damage analysis (GPT‑4o vision) → per‑damage items + narrative summary.
  - Report generation (WeasyPrint) → JSON + PDF.

- **Serving results**
  - `GET /api/v1/assessments/{id}` → pipeline status, frame counts, `splat_ready`, `model_ready`, and cost estimates.
  - `GET /api/v1/assessments/{id}/splat/{exterior|interior}` → JSON with direct `.ply` URL for the Gaussian splat.
  - `GET /api/v1/assessments/{id}/model/{exterior|interior}` → JSON with direct **GLB** URL for AR/web viewers.
  - `GET /api/v1/assessments/{id}/report` + `/report/pdf` → damage report (JSON + PDF).

- **Frontend viewing (desktop + mobile web)**
  - React + Vite + Tailwind dashboard.
  - 3D splat viewer using `@mkkellogg/gaussian-splats-3d`.
  - **Web‑only AR** card on the assessment detail page:
    - Uses `<model-viewer>` (via CDN) with the GLB URL from `/model/{type}`.
    - On mobile browsers, launches Scene Viewer (Android) or Quick Look (iOS) when available, or falls back to in‑browser 3D.

---

## Project structure

```text
.
├── backend/                 ← FastAPI API, Celery pipeline, COLMAP + splats + GLB + reports
│   ├── app/
│   │   ├── api/v1/          ← v1 video pipeline endpoints (assessments, videos, splats, models, reports)
│   │   ├── models/          ← SQLAlchemy models (Assessment, DamageItem, ProcessingJob)
│   │   ├── schemas/         ← Pydantic v2 schemas for /api/v1
│   │   └── services/        ← blob storage, frame extraction, splatting, damage analysis
│   ├── tests/               ← pytest suite (no GPU / external services needed)
│   ├── alembic/             ← database migrations
│   └── README.md            ← backend docs (legacy single‑image API; see CLAUDE.md for v1 pipeline)
│
├── src/                     ← React + Vite frontend
│   ├── pages/               ← assessment list/detail pages
│   ├── components/          ← 3D splat viewer, AR viewer, video player, report UI
│   └── lib/                 ← API client + TypeScript API types
│
└── CLAUDE.md                ← authoritative architecture + testing notes
```

---

## Running the stack locally

### Backend API

From `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# Set up local DB schema
alembic upgrade head

# Start API (no GPU / external services required for tests)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Configuration is driven by `.env` (see `backend/.env.example` and `backend/app/config.py`), and high‑level behavior is described in `CLAUDE.md`.

### Frontend (dashboard + 3D + AR)

From the repo root:

```bash
npm install
npm run dev
```

Configure the API URL (Vite):

```bash
# .env.local
VITE_API_URL=http://localhost:8000
```

Then open the Vite dev URL (typically `http://localhost:5173`).

---

## Key flows to test

- **Create and process an assessment**
  - Create a new assessment in the React app.
  - Upload an exterior video; watch pipeline status advance from `uploading` → `extracting_frames` → `splatting` → `analyzing` → `complete`.

- **Inspect 3D reconstruction**
  - Use the splat viewer to rotate/zoom the reconstructed vehicle on desktop and mobile.

- **View in AR (web‑only)**
  - Open the same assessment on a phone browser.
  - Look for the **“AR ready”** pill in the header once `model_ready.exterior` is true.
  - Scroll to the **“View in AR (beta)”** card and tap the AR control to launch the native AR viewer or in‑browser 3D fallback.

---

## Verification commands

Backend (from `backend/`):

```bash
pytest tests/
```

Frontend (from repo root):

```bash
npm run lint
npm run build
```

For deeper backend API reference and pipeline diagrams, prefer `CLAUDE.md` and the code under `backend/app/api/v1/`.
