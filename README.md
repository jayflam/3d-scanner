# InsuraScan

**AI-powered vehicle damage assessment platform.** Users upload exterior and interior videos of a vehicle, which are processed through an async pipeline: frame extraction → 3D Gaussian Splatting → AI damage analysis → PDF/JSON report generation. Results are served via a REST API and a React dashboard with an interactive 3D splat viewer.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture Overview](#architecture-overview)
- [Pipeline Flow](#pipeline-flow)
- [Assessment Lifecycle](#assessment-lifecycle)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Option 1: Docker Compose (Recommended)](#option-1-docker-compose-recommended)
  - [Option 2: Manual Setup](#option-2-manual-setup)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [WebSocket Real-Time Updates](#websocket-real-time-updates)
- [Database Schema](#database-schema)
- [Frontend Guide](#frontend-guide)
- [Testing](#testing)
- [Tech Stack](#tech-stack)
- [License](#license)

---

## How It Works

```
 ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐
 │  User films  │────▶│  Upload to  │────▶│    Async Celery Pipeline    │
 │  vehicle     │     │  REST API   │     │                             │
 └─────────────┘     └─────────────┘     │  1. FFmpeg frame extraction │
                                          │  2. COLMAP + Gaussian Splat │
                                          │  3. GPT-4o damage analysis  │
                                          │  4. PDF / JSON report gen   │
                                          └──────────────┬──────────────┘
                                                         │
                      ┌─────────────┐                    │
                      │  React App  │◀───────────────────┘
                      │  Dashboard  │   REST API + WebSocket
                      │             │   progress updates
                      │  • 3D Splat │
                      │    Viewer   │
                      │  • Damage   │
                      │    Report   │
                      │  • Zone     │
                      │    Diagram  │
                      └─────────────┘
```

1. **Capture** — User records an exterior walkaround and interior scan of the vehicle
2. **Upload** — Videos are uploaded via the REST API and stored in blob storage (Azure or local)
3. **Extract Frames** — FFmpeg extracts frames at 2 FPS, filters for blur and brightness
4. **3D Reconstruction** — COLMAP estimates camera poses, then Gaussian Splatting builds a 3D model
5. **AI Analysis** — GPT-4o Vision analyzes frames in batches, detecting damage with zone/severity/cost
6. **Report** — A structured JSON report and styled PDF are generated with cost breakdowns
7. **View** — The React dashboard displays real-time progress, an interactive 3D splat viewer, a clickable vehicle zone diagram, and the full damage report

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                    │
│  React 19 · TypeScript · Vite · Tailwind CSS · React Query              │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────────┐    │
│  │ Assessment   │  │    New       │  │   Assessment Detail         │    │
│  │ List Page    │  │  Assessment  │  │                             │    │
│  │              │  │  Page        │  │  ┌─────────┐ ┌───────────┐ │    │
│  │ • Search     │  │              │  │  │ 3D Splat│ │  Damage   │ │    │
│  │ • Filter     │  │ • Form      │  │  │ Viewer  │ │  Report   │ │    │
│  │ • Paginate   │  │ • Video     │  │  └─────────┘ │  + Cards  │ │    │
│  │              │  │   Upload    │  │  ┌─────────┐ │  + Costs  │ │    │
│  │              │  │ • Validate  │  │  │  Zone   │ │  + PDF    │ │    │
│  │              │  │             │  │  │ Diagram │ └───────────┘ │    │
│  └──────────────┘  └──────────────┘  │  └─────────┘              │    │
│                                       └─────────────────────────────┘    │
│                                                                          │
│  Vite Dev Server Proxy:  /api/* → :8000   /ws/* → ws://:8000            │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │  HTTP + WebSocket
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                     │
│  FastAPI · SQLAlchemy (async) · Celery · Redis · PostgreSQL              │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                         REST API (:8000)                          │   │
│  │  POST /api/v1/assessments              Create assessment          │   │
│  │  POST /api/v1/assessments/{id}/videos  Upload video               │   │
│  │  GET  /api/v1/assessments/{id}         Status + progress          │   │
│  │  GET  /api/v1/assessments/{id}/report  JSON damage report         │   │
│  │  GET  /api/v1/assessments/{id}/report/pdf   PDF download          │   │
│  │  GET  /api/v1/assessments/{id}/splat/{type}  3D .ply file         │   │
│  │  WS   /ws/{id}                         Real-time progress         │   │
│  └───────────────────────┬───────────────────────────────────────────┘   │
│                          │                                               │
│  ┌───────────────────────▼───────────────────────────────────────────┐   │
│  │                     Celery Workers                                │   │
│  │                                                                   │   │
│  │  ┌──────────────┐  ┌───────────┐  ┌────────────┐  ┌───────────┐ │   │
│  │  │   Extract    │  │ Gaussian  │  │  GPT-4o    │  │  Report   │ │   │
│  │  │   Frames     │  │ Splatting │  │  Damage    │  │  Generate │ │   │
│  │  │   (FFmpeg)   │  │ (COLMAP   │  │  Analysis  │  │ (PDF+JSON)│ │   │
│  │  │              │  │  + gsplat)│  │            │  │           │ │   │
│  │  └──────────────┘  └───────────┘  └────────────┘  └───────────┘ │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                          │                                               │
│  ┌───────────────────────▼───────────────────────────────────────────┐   │
│  │                      Data Layer                                   │   │
│  │                                                                   │   │
│  │  ┌────────────┐   ┌──────────┐   ┌─────────────────────────────┐ │   │
│  │  │ PostgreSQL │   │  Redis   │   │  Blob Storage               │ │   │
│  │  │ 16         │   │  7       │   │  (Azure Blob or local fs)   │ │   │
│  │  │            │   │          │   │                             │ │   │
│  │  │ assessments│   │ • Celery │   │  videos/{id}/{type}.mp4    │ │   │
│  │  │ damage_items   │   broker │   │  frames/{id}/{type}/*.jpg  │ │   │
│  │  │ processing_│   │ • Pub/Sub│   │  splats/{id}/{type}.ply    │ │   │
│  │  │   jobs     │   │   progress   │  reports/{id}/report.*     │ │   │
│  │  └────────────┘   └──────────┘   └─────────────────────────────┘ │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Flow

The Celery pipeline processes videos through four stages. Exterior and interior videos are processed in parallel where possible.

```
                         start_pipeline(assessment_id)
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
          ┌─────────────────┐             ┌─────────────────┐
          │ Extract Frames  │             │ Extract Frames  │
          │ (exterior)      │             │ (interior)      │
          │                 │             │                 │
          │ • FFmpeg @ 2fps │             │ • FFmpeg @ 2fps │
          │ • Blur filter   │             │ • Blur filter   │
          │ • Brightness    │             │ • Brightness    │
          │   filter        │             │   filter        │
          └────────┬────────┘             └────────┬────────┘
                   │                               │
                   └───────────────┬───────────────┘
                                   │
                   ┌───────────────┼───────────────┐
                   ▼               ▼               ▼
         ┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐
         │ Gaussian Splat  │ │ Gaussian     │ │ Damage Analysis │
         │ (exterior)      │ │ Splat        │ │                 │
         │                 │ │ (interior)   │ │ • Sample frames │
         │ • COLMAP SfM    │ │              │ │ • Batch to      │
         │   - SIFT feat.  │ │ • COLMAP SfM │ │   GPT-4o Vision │
         │   - Matching    │ │ • gsplat     │ │ • Zone mapping  │
         │   - Mapping     │ │   training   │ │ • Severity +    │
         │ • gsplat train  │ │ • Export .ply │ │   cost estimate │
         │   (7k iters)    │ │              │ │ • Store damage  │
         │ • Export .ply   │ │              │ │   items in DB   │
         └────────┬────────┘ └──────┬───────┘ └────────┬────────┘
                  │                 │                   │
                  └─────────────────┼───────────────────┘
                                    ▼
                          ┌─────────────────┐
                          │ Report          │
                          │ Generation      │
                          │                 │
                          │ • Build JSON    │
                          │   report        │
                          │ • Render HTML   │
                          │   → PDF via     │
                          │   WeasyPrint    │
                          │ • Upload to     │
                          │   blob storage  │
                          │ • Mark COMPLETE │
                          └─────────────────┘
```

Each stage publishes progress updates to Redis pub/sub, which are forwarded to the frontend via WebSocket.

---

## Assessment Lifecycle

```
   ┌──────────┐
   │ CREATED  │  POST /api/v1/assessments
   └────┬─────┘
        │  Upload video(s)
        ▼
  ┌───────────┐
  │ UPLOADING │  POST /api/v1/assessments/{id}/videos/{type}
  └─────┬─────┘
        │  Pipeline starts automatically
        ▼
┌─────────────────┐
│EXTRACTING_FRAMES│  FFmpeg + quality filtering
└────────┬────────┘
         ▼
   ┌───────────┐
   │ SPLATTING │  COLMAP + Gaussian Splatting
   └─────┬─────┘
         ▼
   ┌───────────┐
   │ ANALYZING │  GPT-4o Vision damage detection
   └─────┬─────┘
         ▼
   ┌──────────┐
   │ COMPLETE │  Reports generated, results available
   └──────────┘

   Any stage can transition to:
   ┌──────────┐
   │  FAILED  │  error_message populated
   └──────────┘
```

---

## Project Structure

```
3d-scanner/
│
├── backend/                          # Python backend
│   ├── app/
│   │   ├── main.py                   # FastAPI app entry point
│   │   ├── config.py                 # Pydantic Settings (env vars)
│   │   ├── api/
│   │   │   ├── v1/                   # V1 REST API
│   │   │   │   ├── router.py         # V1 route aggregator
│   │   │   │   ├── assessments.py    # CRUD endpoints
│   │   │   │   ├── videos.py         # Video upload endpoints
│   │   │   │   ├── reports.py        # Report + damage endpoints
│   │   │   │   ├── splats.py         # 3D splat download
│   │   │   │   └── health.py         # Health + config endpoints
│   │   │   ├── routes.py             # Legacy single-image API
│   │   │   └── websocket.py          # WebSocket progress (v1 + legacy)
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── assessment.py         # Assessment table
│   │   │   ├── damage_item.py        # DamageItem table
│   │   │   └── processing_job.py     # ProcessingJob table
│   │   ├── schemas/                  # Pydantic v2 request/response
│   │   │   ├── assessment.py
│   │   │   ├── damage.py
│   │   │   └── report.py
│   │   ├── services/                 # Business logic
│   │   │   ├── blob_storage.py       # Azure Blob / local filesystem
│   │   │   ├── frame_extractor.py    # FFmpeg frame extraction
│   │   │   ├── colmap_service.py     # COLMAP Structure-from-Motion
│   │   │   ├── gaussian_splat.py     # Gaussian Splatting training
│   │   │   ├── damage_analyzer.py    # GPT-4o damage analysis (async)
│   │   │   └── report_generator.py   # PDF + JSON report generation
│   │   ├── tasks/                    # Celery async tasks
│   │   │   ├── celery_app.py         # Celery config
│   │   │   ├── pipeline.py           # Pipeline orchestration (chord/chain)
│   │   │   ├── extract_frames.py     # Frame extraction task
│   │   │   ├── run_splatting.py      # Splatting task
│   │   │   ├── analyze_damage.py     # Damage analysis task
│   │   │   └── generate_report.py    # Report generation task
│   │   └── db/
│   │       └── database.py           # Async SQLAlchemy engine + sessions
│   ├── alembic/                      # Database migrations
│   ├── tests/                        # Pytest test suite
│   ├── Dockerfile                    # CUDA 11.8 GPU-ready container
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                         # React frontend
│   ├── src/
│   │   ├── main.tsx                  # Entry point (React Query provider)
│   │   ├── App.tsx                   # Router configuration
│   │   ├── lib/
│   │   │   ├── api-client.ts         # HTTP + XHR client functions
│   │   │   └── api-types.ts          # TypeScript interfaces
│   │   ├── hooks/
│   │   │   └── useJobProgress.ts     # WebSocket hook for pipeline progress
│   │   ├── layouts/
│   │   │   └── DashboardLayout.tsx   # App shell (sidebar + header)
│   │   ├── pages/
│   │   │   ├── AssessmentListPage.tsx    # Search, filter, paginate
│   │   │   ├── NewAssessmentPage.tsx     # Create + upload videos
│   │   │   └── AssessmentDetailPage.tsx  # 3D viewer + report + zones
│   │   └── components/
│   │       ├── SplatViewer.tsx        # 3D Gaussian Splat viewer
│   │       ├── ZoneDiagram.tsx        # Clickable SVG vehicle diagram
│   │       ├── DamageReport.tsx       # Report panel + cost breakdown
│   │       ├── DamageCard.tsx         # Individual damage item card
│   │       ├── StatusTracker.tsx      # Pipeline stage progress bar
│   │       ├── StatusBadge.tsx        # Color-coded status indicator
│   │       ├── UploadZone.tsx         # Drag-and-drop video upload
│   │       └── VideoPlayer.tsx        # HTML5 video player
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── docker-compose.yml                # Full stack orchestration
├── InsuraScan_Project_Plan.md        # Detailed project specification
├── CLAUDE.md                         # AI assistant context
└── LICENSE                           # MIT
```

---

## Getting Started

### Prerequisites

| Tool | Version | Required For |
|------|---------|-------------|
| **Docker** + **Docker Compose** | 20+ / v2+ | Full stack (recommended) |
| **Python** | 3.11+ | Backend (manual setup) |
| **Node.js** | 18+ | Frontend |
| **PostgreSQL** | 16 | Database |
| **Redis** | 7 | Celery broker + pub/sub |
| **FFmpeg** | 6+ | Frame extraction |
| **COLMAP** | 3.8+ | Structure-from-Motion (GPU) |
| **CUDA** | 11.8+ | GPU acceleration (splatting) |

### Option 1: Docker Compose (Recommended)

Spins up PostgreSQL, Redis, the FastAPI server, and a Celery worker in one command.

```bash
# 1. Clone the repository
git clone https://github.com/jayflam/3d-scanner.git
cd 3d-scanner

# 2. Create environment file
cp backend/.env.example backend/.env
# Edit backend/.env with your credentials (see Environment Variables below)

# 3. Start the full stack
docker compose up --build
```

Services will be available at:

| Service | URL |
|---------|-----|
| **FastAPI** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |
| **PostgreSQL** | localhost:5432 |
| **Redis** | localhost:6379 |

Then start the frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server starts at **http://localhost:5173** and proxies API/WebSocket requests to the backend automatically.

### Option 2: Manual Setup

#### Backend

```bash
# 1. Set up Python environment
cd backend
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start PostgreSQL and Redis
#    (Use your preferred method: brew, apt, docker, etc.)
#    PostgreSQL should be running on port 5432
#    Redis should be running on port 6379

# 4. Create the database
createdb insurascan

# 5. Configure environment
cp .env.example .env
# Edit .env — at minimum set:
#   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/insurascan
#   REDIS_URL=redis://localhost:6379/0

# 6. Run database migrations
alembic upgrade head

# 7. Start the API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 8. Start a Celery worker (in a separate terminal)
celery -A app.tasks.celery_app worker --loglevel=info
```

#### Frontend

```bash
# 1. Install dependencies
cd frontend
npm install

# 2. (Optional) Set API URL if not using default proxy
#    Create .env.local with:
#    VITE_API_URL=http://localhost:8000

# 3. Start dev server
npm run dev
```

The Vite dev server (port 5173) proxies `/api/*` and `/ws/*` requests to `localhost:8000`, so no CORS configuration is needed in development.

#### Full Development Stack (All Terminals)

```
Terminal 1 (Database):     PostgreSQL running on :5432
Terminal 2 (Cache):        Redis running on :6379
Terminal 3 (API):          cd backend && uvicorn app.main:app --reload
Terminal 4 (Worker):       cd backend && celery -A app.tasks.celery_app worker -l info
Terminal 5 (Frontend):     cd frontend && npm run dev
```

---

## Environment Variables

Create `backend/.env` from `backend/.env.example`. All config is managed through Pydantic Settings in `backend/app/config.py`.

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection (asyncpg) | `postgresql+asyncpg://postgres:postgres@localhost:5432/insurascan` |
| `REDIS_URL` | Redis for Celery + pub/sub | `redis://localhost:6379/0` |

### Azure OpenAI (for damage analysis)

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource URL | `https://<resource>.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | API key | `sk-...` |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name | `gpt-4o` |
| `AZURE_OPENAI_API_VERSION` | API version | `2024-12-01-preview` |

### Azure Blob Storage (optional — falls back to local filesystem)

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_BLOB_CONNECTION_STRING` | Connection string (leave empty for local) | `DefaultEndpointsProtocol=https;...` |
| `AZURE_BLOB_CONTAINER_NAME` | Container name | `insurascan-storage` |

### Other

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | `REDIS_URL` | Override Celery broker |
| `CELERY_RESULT_BACKEND` | `REDIS_URL` | Override Celery result store |
| `MAX_UPLOAD_SIZE_MB` | `500` | Maximum video upload size |
| `CORS_ORIGINS` | `["http://localhost:3000", "http://localhost:5173"]` | Allowed CORS origins |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | (empty — uses Vite proxy) | Backend API base URL |

---

## API Reference

Base URL: `http://localhost:8000`

### Assessments

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/assessments` | Create a new assessment |
| `GET` | `/api/v1/assessments` | List assessments (paginated, filterable) |
| `GET` | `/api/v1/assessments/{id}` | Get assessment details + pipeline status |
| `DELETE` | `/api/v1/assessments/{id}` | Delete assessment (cascades) |

#### Create Assessment

```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{
    "claim_number": "CLM-2026-001",
    "agent_id": "AGT-100",
    "vehicle_year": 2023,
    "vehicle_make": "BMW",
    "vehicle_model": "M4 Competition",
    "vin": "WBS43AZ09P1234567"
  }'
```

#### List Assessments

```bash
# With pagination and filtering
curl "http://localhost:8000/api/v1/assessments?page=1&page_size=20&status=complete&search=CLM-2026"
```

### Videos

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/assessments/{id}/videos/{type}` | Upload video (`exterior` or `interior`) |
| `GET` | `/api/v1/assessments/{id}/videos/{type}/status` | Check upload status |

#### Upload Video

```bash
curl -X POST http://localhost:8000/api/v1/assessments/{id}/videos/exterior \
  -F "file=@exterior_walkaround.mp4"
```

### Reports & Damage

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/assessments/{id}/report` | Full JSON damage report |
| `GET` | `/api/v1/assessments/{id}/report/pdf` | Download PDF report |
| `GET` | `/api/v1/assessments/{id}/damages` | List all detected damage items |
| `GET` | `/api/v1/assessments/{id}/frames` | Get extracted frame metadata |

### 3D Splats

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/assessments/{id}/splat/{type}` | Download `.ply` splat file (`exterior` or `interior`) |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | API + database + Redis health |
| `GET` | `/api/v1/health/gpu` | GPU availability and device info |
| `GET` | `/api/v1/config` | Upload limits, allowed extensions, storage type |

### Interactive API Docs

FastAPI auto-generates interactive documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## WebSocket Real-Time Updates

The frontend receives pipeline progress in real-time via WebSocket.

### Connection

```
ws://localhost:8000/ws/v1/assessments/{assessment_id}/status
```

### Message Format

```json
{
  "assessment_id": "550e8400-e29b-41d4-a716-446655440000",
  "stage": "frame_extraction",
  "progress_pct": 45,
  "message": "Extracting exterior frames: 90/200",
  "timestamp": "2026-03-04T10:30:00Z"
}
```

### Pipeline Stages

| Stage | Description |
|-------|-------------|
| `frame_extraction` | FFmpeg frame extraction + quality filtering |
| `gaussian_splatting` | COLMAP SfM + Gaussian Splat training |
| `damage_analysis` | GPT-4o Vision batch analysis |
| `report_generation` | JSON + PDF report creation |

The connection automatically closes when the assessment reaches `complete` or `failed` status.

---

## Database Schema

Three main tables managed by SQLAlchemy ORM with Alembic migrations.

```
┌──────────────────────────────┐
│         assessments          │
├──────────────────────────────┤
│ id (UUID, PK)                │
│ claim_number (indexed)       │
│ agent_id                     │
│ vin                          │
│ vehicle_year / make / model  │
│ status (enum)                │
│ exterior_video_blob_path     │
│ interior_video_blob_path     │
│ exterior_splat_blob_path     │
│ interior_splat_blob_path     │
│ exterior_frame_count         │
│ interior_frame_count         │
│ total_estimate_low (decimal) │
│ total_estimate_high (decimal)│
│ gps_latitude / longitude     │
│ error_message                │
│ created_at / updated_at      │
│ completed_at                 │
├──────────────────────────────┤
│ 1 ──── * damage_items        │
│ 1 ──── * processing_jobs     │
└──────────────────────────────┘

┌──────────────────────────────┐       ┌──────────────────────────────┐
│        damage_items          │       │      processing_jobs         │
├──────────────────────────────┤       ├──────────────────────────────┤
│ id (UUID, PK)                │       │ id (UUID, PK)                │
│ assessment_id (FK)           │       │ assessment_id (FK)           │
│ damage_id ("DMG-001")        │       │ stage (enum)                 │
│ location                     │       │   FRAME_EXTRACTION           │
│ vehicle_zone (enum)          │       │   SPLATTING                  │
│   FRONT_LEFT/RIGHT/CENTER    │       │   ANALYSIS                   │
│   REAR_LEFT/RIGHT/CENTER     │       │   REPORT_GENERATION          │
│   SIDE_LEFT/RIGHT            │       │ status (enum)                │
│   ROOF                       │       │   QUEUED / RUNNING           │
│   INTERIOR_FRONT/REAR        │       │   COMPLETE / FAILED          │
│ damage_type                  │       │ celery_task_id               │
│ severity (MINOR/MOD/SEVERE)  │       │ started_at / completed_at    │
│ description                  │       │ duration_seconds             │
│ affected_parts (JSONB)       │       │ error_message                │
│ repair_method                │       └──────────────────────────────┘
│ estimated_cost_low (decimal) │
│ estimated_cost_high (decimal)│
│ confidence_score (0.0–1.0)   │
│ reference_frame_paths (JSONB)│
│ created_at                   │
└──────────────────────────────┘
```

### Migration Commands

```bash
cd backend

# Apply all migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "add new field"

# View migration history
alembic history
```

---

## Frontend Guide

### Pages

| Page | Route | Description |
|------|-------|-------------|
| **Assessment List** | `/assessments` | Searchable, filterable table of all assessments |
| **New Assessment** | `/assessments/new` | Multi-step form: claim info → vehicle details → video upload |
| **Assessment Detail** | `/assessments/:id` | 3D splat viewer, damage report, zone diagram, progress tracker |

### Key Components

| Component | Description |
|-----------|-------------|
| `SplatViewer` | Interactive 3D Gaussian Splat viewer with exterior/interior toggle and fullscreen |
| `ZoneDiagram` | SVG top-down vehicle diagram with clickable zones colored by damage severity |
| `DamageReport` | Full report panel with cost breakdown table and PDF download |
| `DamageCard` | Individual damage item with severity badge, cost, confidence, reference frames |
| `StatusTracker` | 5-stage pipeline progress visualization with animated indicators |
| `UploadZone` | Drag-and-drop file upload with progress bar and size validation |

### Data Flow

```
React Query                              WebSocket (useJobProgress)
    │                                           │
    ├─ GET /assessments        ──▶ List page    │
    ├─ POST /assessments       ──▶ Create       │
    ├─ POST /videos/{type}     ──▶ Upload       │
    ├─ GET /assessments/{id}   ──▶ Detail ◀─────┤ Real-time status updates
    ├─ GET /report             ──▶ Report       │ invalidate queries on
    └─ GET /damages            ──▶ Cards        │ terminal state
```

### Build for Production

```bash
cd frontend
npm run build     # Output in frontend/dist/
npm run preview   # Preview production build locally
```

---

## Testing

Tests run without GPU, database, or external services. Heavy ML dependencies are stubbed.

```bash
cd backend

# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run a specific test file
pytest tests/test_v1_assessments.py -v

# Run with coverage
pytest --cov=app tests/
```

### Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `test_v1_assessments.py` | 25 | Full v1 API endpoint coverage |
| `test_e2e_pipeline.py` | 10 | Assessment lifecycle, cascading deletes |
| `test_blob_storage.py` | 14 | Local filesystem fallback, upload/download |
| `test_models.py` | 9 | ORM model creation, enum validation |
| `test_schemas.py` | 6 | Pydantic schema serialization |
| `test_api.py` | 9 | Legacy single-image API |
| `test_task_*.py` | — | Celery task unit tests |

### Test Architecture

- **Database**: In-memory SQLite with `StaticPool` (no PostgreSQL needed)
- **ML Dependencies**: Stubbed via `sys.modules.setdefault(mod, MagicMock())`
- **Async**: `pytest-asyncio` with `async_sessionmaker`
- **HTTP Client**: `httpx.AsyncClient` with FastAPI `TestClient`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, TypeScript 5.9, Vite 7, Tailwind CSS 4 |
| **3D Viewer** | Gaussian Splats 3D (`@mkkellogg/gaussian-splats-3d`) |
| **State/Data** | React Query (TanStack Query v5) |
| **Routing** | React Router v7 |
| **Backend API** | FastAPI, Uvicorn, Pydantic v2 |
| **Database** | PostgreSQL 16, SQLAlchemy 2 (async), Alembic |
| **Task Queue** | Celery 5 with Redis broker |
| **Real-Time** | WebSocket + Redis pub/sub |
| **Frame Extraction** | FFmpeg |
| **3D Reconstruction** | COLMAP (SfM) + Gaussian Splatting (gsplat/nerfstudio) |
| **AI Analysis** | Azure OpenAI GPT-4o Vision |
| **PDF Reports** | WeasyPrint |
| **Blob Storage** | Azure Blob Storage (with local filesystem fallback) |
| **Container** | Docker + Docker Compose, CUDA 11.8 base image |
| **Testing** | Pytest, pytest-asyncio, httpx |

---

## License

MIT
