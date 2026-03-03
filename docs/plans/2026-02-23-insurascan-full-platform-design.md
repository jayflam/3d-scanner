# InsuraScan Full Platform Design

## Scope

Full P0 + P1 implementation from the InsuraScan Project Plan. Evolve the existing MVP backend into a production-grade platform with video-based capture, Gaussian Splatting 3D reconstruction, and a React dashboard.

## Architecture

### Backend (FastAPI + Celery)

Evolve the existing `backend/app/` structure. Replace in-memory job queue with Celery + Azure Redis. Add PostgreSQL via SQLAlchemy + Alembic.

**New directory structure:**

```
backend/app/
  models/
    assessment.py      # SQLAlchemy ORM model
    damage_item.py     # SQLAlchemy ORM model
    processing_job.py  # SQLAlchemy ORM model
  schemas/
    assessment.py      # Pydantic request/response schemas
    damage.py          # Pydantic damage schemas
    report.py          # Report schemas
  api/v1/
    assessments.py     # Assessment CRUD endpoints
    videos.py          # Video upload endpoints
    splats.py          # 3D splat endpoints
    reports.py         # Damage report endpoints
    router.py          # Aggregated API router
  services/
    blob_storage.py    # Azure Blob Storage operations
    frame_extractor.py # FFmpeg wrapper with quality filtering
    gaussian_splat.py  # COLMAP + 3DGS orchestration
    damage_analyzer.py # Enhanced GPT-4o analysis (zone-based batching)
    report_generator.py # PDF + JSON report builder
  tasks/
    celery_app.py      # Celery configuration
    extract_frames.py  # Frame extraction task
    run_splatting.py   # COLMAP + Gaussian Splatting task
    analyze_damage.py  # AI analysis task
    generate_report.py # Report generation task
  db/
    database.py        # SQLAlchemy engine + session
    migrations/        # Alembic
```

**API versioned under `/api/v1/`** per project plan spec. Keep existing `/api/` endpoints temporarily for backwards compatibility during migration.

### Processing Pipeline

5-stage Celery task chain:

1. **extract_frames** — FFmpeg at 2fps, blur detection (Laplacian variance), brightness filtering
2. **run_colmap** — COLMAP SfM: feature extraction, matching, sparse reconstruction → camera poses
3. **run_splatting** — 3DGS training (7k-15k iterations) → export .ply
4. **analyze_damage** — GPT-4o with zone-based frame batching (4-8 frames per call)
5. **generate_report** — Aggregate damage items, generate JSON + PDF report

Tasks 1-3 run sequentially (each depends on prior output). Task 4 can run in parallel with task 3 (frames are available after task 1).

### Storage (Azure Blob)

```
insurascan-storage/
  videos/{assessment_id}/exterior.mp4, interior.mp4
  frames/{assessment_id}/exterior/frame_NNNN.jpg, interior/...
  splats/{assessment_id}/exterior.ply, interior.ply
  reports/{assessment_id}/report.json, report.pdf
```

### Frontend (React + TypeScript)

- **Framework:** React 18 + TypeScript + Vite
- **Styling:** Tailwind CSS + shadcn/ui
- **3D Viewer:** Three.js via `@mkkellogg/gaussian-splats-3d` for .ply rendering
- **Data:** TanStack Query for API state + polling
- **Routing:** React Router v6

**Pages:**
- Assessment list (table with search/filter/status badges)
- New assessment (form + dual video upload zones with progress)
- Assessment detail (status tracker + video playback + 3D splat viewer + damage report panel)

### Database Models

Three tables per project plan: `assessments`, `damage_items`, `processing_jobs`. Use Alembic for migrations. See Section 6 of InsuraScan_Project_Plan.md for full schema.

### WebSocket

Enhance existing `/ws/{id}` to support assessment-level progress streaming. Celery tasks publish progress to Redis pub/sub, WebSocket handler subscribes and forwards to clients.

### PDF Report

Use WeasyPrint or ReportLab to generate downloadable PDF reports from the damage assessment data.

## Infrastructure

- **Database:** Azure Database for PostgreSQL (Flexible Server, Burstable B1ms)
- **Cache/Queue:** Azure Cache for Redis (Basic C0) as Celery broker
- **GPU:** Azure NC-series VM or Container Apps GPU for COLMAP + 3DGS
- **Storage:** Azure Blob Storage (Standard LRS)
- **AI:** Azure AI Foundry (GPT-4o deployment)

## Workstreams

1. **Backend Infrastructure** — DB models, Alembic migrations, Celery setup, Blob Storage service, API v1 endpoints
2. **Processing Pipeline** — FFmpeg frame extraction, COLMAP integration, Gaussian Splatting, enhanced AI analysis, report generation
3. **Frontend** — React scaffold, all pages, Gaussian Splat viewer, upload flow, real-time status

## Decisions

- Keep TripoSR as fallback for single-image quick mode alongside the full Gaussian Splatting pipeline
- API versioned at `/api/v1/` from the start
- SQLAlchemy async for database access
- Celery with Redis broker for task queue (Azure-hosted Redis)
