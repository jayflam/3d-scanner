# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**InsuraScan** — AI-powered vehicle damage assessment platform. Users upload exterior/interior videos of a vehicle, which are processed through an async pipeline: frame extraction (FFmpeg) -> 3D Gaussian Splatting (COLMAP + gsplat) -> AI damage analysis (GPT-4o vision) -> PDF/JSON report generation. Results served via REST API and React dashboard with a 3D splat viewer.

## Commands

```bash
# Install dependencies
cd backend && pip install -r requirements.txt

# Run server (development)
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run all tests (no GPU, no external services needed)
cd backend && pytest tests/

# Run specific test files
cd backend && pytest tests/test_v1_assessments.py -v
cd backend && pytest tests/test_e2e_pipeline.py -v
cd backend && pytest tests/test_blob_storage.py -v

# Run with coverage
cd backend && pytest --cov=app tests/

# Run full stack with Docker Compose (PostgreSQL + Redis + API + Celery)
docker compose up --build

# Run database migrations
cd backend && alembic upgrade head

# Create new migration
cd backend && alembic revision --autogenerate -m "description"

# Celery worker (requires Redis)
cd backend && celery -A app.tasks.celery_app worker --loglevel=info
```

## Architecture

### Assessment Pipeline (v1 API)

```
POST /api/v1/assessments (create assessment)
       |
POST /api/v1/assessments/{id}/videos/exterior (upload video)
POST /api/v1/assessments/{id}/videos/interior (upload video)
       |
  Celery task chain kicks off automatically:
    1. Frame Extraction (FFmpeg) — extract + quality-filter frames
    2. Gaussian Splatting (COLMAP + gsplat) — 3D reconstruction
    3. AI Damage Analysis (GPT-4o vision) — detect and classify damage
    4. Report Generation (WeasyPrint) — PDF + JSON report
       |
  Assessment status: created -> uploading -> extracting_frames ->
                      splatting -> analyzing -> complete | failed
       |
  Results available via:
    GET /api/v1/assessments/{id}           — status + pipeline progress
    GET /api/v1/assessments/{id}/report    — full JSON report
    GET /api/v1/assessments/{id}/report/pdf — PDF download
    GET /api/v1/assessments/{id}/splats/{type} — 3D splat .ply file
    GET /api/v1/assessments/{id}/frames    — extracted frame URLs
```

### Backend Structure (backend/app/)

- **`api/v1/`** — REST endpoints: assessments CRUD, video upload, splats, reports, system health
- **`api/routes.py`** + **`api/websocket.py`** — Legacy single-image API (still mounted)
- **`models/`** — SQLAlchemy ORM: `Assessment`, `DamageItem`, `ProcessingJob`
- **`schemas/`** — Pydantic v2 request/response schemas
- **`services/blob_storage.py`** — Azure Blob Storage with local filesystem fallback
- **`services/frame_extractor.py`** — FFmpeg frame extraction with quality filtering
- **`services/splatting.py`** — COLMAP + Gaussian Splatting pipeline
- **`services/damage.py`** — GPT-4o vision damage analysis
- **`tasks/`** — Celery tasks: `extract_frames`, `run_splatting`, `analyze_damage`, `generate_report`, `pipeline` (chain orchestrator)
- **`db/database.py`** — Async SQLAlchemy engine + session factory

### Database

PostgreSQL 16 with async SQLAlchemy (asyncpg). Alembic for migrations. Three main tables:
- `assessments` — Vehicle info, status, blob paths, cost estimates
- `damage_items` — Per-damage records with zone, severity, cost range
- `processing_jobs` — Celery task tracking per pipeline stage

### Frontend (frontend/)

React + TypeScript + Vite. Tailwind CSS. Key pages: dashboard, new assessment, assessment detail with 3D splat viewer and damage report panel.

## Configuration

All config via environment variables (see `backend/.env.example`). Managed through Pydantic Settings in `backend/app/config.py`.

Key environment variables:
- `DATABASE_URL` — PostgreSQL connection (asyncpg)
- `REDIS_URL` — Redis for Celery broker
- `AZURE_BLOB_CONNECTION_STRING` — Azure Blob Storage (leave empty for local fallback)
- `AZURE_OPENAI_*` — GPT-4o credentials (optional, falls back to placeholder)

## Testing Notes

Tests use in-memory SQLite with `StaticPool` and stub all heavy ML imports (`torch`, `rembg`, `tsr`, `trimesh`, `cv2`). No GPU, database, or external services needed.

Key test files:
- `test_v1_assessments.py` — 25 tests: full API v1 endpoint coverage (httpx AsyncClient)
- `test_e2e_pipeline.py` — 10 tests: assessment lifecycle, processing jobs, damage items, cascade deletes
- `test_blob_storage.py` — 14 tests: local filesystem fallback, upload/download round-trips
- `test_models.py` — 9 tests: ORM model creation, enum values
- `test_schemas.py` — 6 tests: Pydantic schema serialization/validation
- `test_api.py` — 9 tests: legacy single-image API

Pattern for new tests: stub heavy deps at module top with `sys.modules.setdefault(mod, MagicMock())`, replace JSONB with JSON for SQLite, use `async_sessionmaker` with `StaticPool`.
