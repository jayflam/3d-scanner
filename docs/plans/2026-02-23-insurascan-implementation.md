# InsuraScan Full Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Evolve the existing single-image MVP into the full InsuraScan platform with video capture, Gaussian Splatting 3D reconstruction, PostgreSQL persistence, Celery task queue, and a React dashboard.

**Architecture:** Three parallel workstreams — backend infrastructure (DB + Celery + Blob + API v1), processing pipeline (FFmpeg + COLMAP + 3DGS + enhanced AI + PDF), and frontend (React dashboard with Gaussian Splat viewer). The existing MVP code in `backend/app/` is preserved and extended. The existing frontend prototype in `src/` (Vite + React + Three.js GLB viewer) is extended into the full dashboard.

**Tech Stack:** FastAPI, SQLAlchemy (async), Alembic, Celery + Redis, Azure Blob Storage, FFmpeg, COLMAP, 3D Gaussian Splatting (gsplat/nerfstudio), Azure OpenAI GPT-4o, React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Three.js, @mkkellogg/gaussian-splats-3d, TanStack Query, React Router v6, WeasyPrint (PDF).

---

## Workstream 1: Backend Infrastructure

Owner: **backend-infra** teammate

### Task 1: Add infrastructure dependencies to requirements.txt

**Files:**
- Modify: `backend/requirements.txt`

**Steps:**

1. Add these packages to `backend/requirements.txt`:
```
# Database
sqlalchemy[asyncio]>=2.0.25
asyncpg>=0.29.0
alembic>=1.13.0

# Task queue
celery[redis]>=5.3.6
redis>=5.0.0

# Azure Blob Storage
azure-storage-blob>=12.19.0
azure-identity>=1.15.0

# Video processing
ffmpeg-python>=0.2.0

# PDF generation
weasyprint>=61.0

# Gaussian Splatting dependencies
# gsplat and nerfstudio installed separately (GPU machine)
```

2. Commit: `feat: add infrastructure dependencies`

### Task 2: Database models with SQLAlchemy

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/database.py` — async engine, session factory
- Modify: `backend/app/models/assessment.py` — SQLAlchemy Assessment ORM model
- Create: `backend/app/models/damage_item.py` — SQLAlchemy DamageItem ORM model
- Create: `backend/app/models/processing_job.py` — SQLAlchemy ProcessingJob ORM model
- Test: `backend/tests/test_models.py`

**Details:**

`backend/app/db/database.py`:
- Create async engine from `DATABASE_URL` config setting (default: `postgresql+asyncpg://...`)
- Create `async_sessionmaker` bound to engine
- Provide `get_db()` async generator dependency for FastAPI
- `Base = declarative_base()` for all ORM models

`backend/app/models/assessment.py` — SQLAlchemy model matching Section 6.1 of project plan:
- Fields: id (UUID PK), claim_number, agent_id, vin, vehicle_year/make/model, status (Enum), exterior/interior_video_blob_path, exterior/interior_splat_blob_path, frame counts, total_estimate_low/high, gps coords, error_message, timestamps
- Status enum: `created, uploading, extracting_frames, splatting, analyzing, complete, failed`

`backend/app/models/damage_item.py` — Section 6.2:
- Fields: id (UUID PK), assessment_id (FK), damage_id, location, vehicle_zone (Enum), damage_type, severity (Enum), description, affected_parts (JSONB), repair_method, cost estimates, confidence_score, reference_frame_paths (JSONB), created_at

`backend/app/models/processing_job.py` — Section 6.3:
- Fields: id (UUID PK), assessment_id (FK), stage (Enum), status (Enum), celery_task_id, timestamps, duration_seconds, error_message

**Tests:** Test model creation, relationships, enum values.

**Step-by-step:**
1. Write failing test that imports Assessment model and creates an instance
2. Implement database.py with engine setup
3. Implement assessment.py ORM model
4. Run test — verify pass
5. Repeat for DamageItem and ProcessingJob
6. Commit: `feat: add SQLAlchemy database models`

### Task 3: Alembic migrations setup

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/` (initial migration)

**Steps:**
1. Run: `cd backend && alembic init alembic`
2. Configure `alembic/env.py` to use async engine from `app.db.database`
3. Import all models in env.py so autogenerate finds them
4. Generate initial migration: `alembic revision --autogenerate -m "initial tables"`
5. Test: `alembic upgrade head` against a test PostgreSQL (or SQLite for CI)
6. Commit: `feat: add Alembic migrations`

### Task 4: Pydantic v2 request/response schemas for API v1

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/assessment.py` — CreateAssessment, AssessmentResponse, AssessmentListResponse
- Create: `backend/app/schemas/damage.py` — DamageItemResponse, DamageAssessmentResponse
- Create: `backend/app/schemas/report.py` — ReportResponse
- Keep: `backend/app/models/schemas.py` — existing schemas for backwards-compat with old /api/ endpoints

**Details:**

`schemas/assessment.py`:
```python
class CreateAssessment(BaseModel):
    claim_number: str
    agent_id: str
    vehicle_year: int
    vehicle_make: str
    vehicle_model: str
    vin: str = ""
    gps_latitude: float | None = None
    gps_longitude: float | None = None

class PipelineStatus(BaseModel):
    exterior_video: str  # "pending" | "complete" | "failed"
    interior_video: str
    frame_extraction: str
    gaussian_splatting: str
    damage_analysis: str
    report_generation: str

class AssessmentResponse(BaseModel):
    id: UUID
    status: str
    claim_number: str
    vehicle: dict  # {year, make, model}
    pipeline: PipelineStatus
    frame_count: dict  # {exterior: int, interior: int}
    splat_ready: dict  # {exterior: bool, interior: bool}
    created_at: datetime
```

Test: Validate serialization roundtrip.

Commit: `feat: add API v1 Pydantic schemas`

### Task 5: Azure Blob Storage service

**Files:**
- Create: `backend/app/services/blob_storage.py`
- Modify: `backend/app/config.py` — add blob storage settings
- Test: `backend/tests/test_blob_storage.py`

**Details:**

Add to `config.py`:
```python
azure_blob_connection_string: str = ""
azure_blob_container_name: str = "insurascan-storage"
```

`blob_storage.py`:
- Class `BlobStorageService` with methods:
  - `upload_video(assessment_id, video_type, file_stream) -> str` (returns blob path)
  - `upload_frame(assessment_id, video_type, frame_number, image_bytes) -> str`
  - `upload_splat(assessment_id, splat_type, file_path) -> str`
  - `upload_report(assessment_id, report_bytes, format) -> str`
  - `get_blob_url(blob_path) -> str` (generates SAS URL)
  - `download_blob(blob_path) -> bytes`
- Follow the blob structure: `videos/{id}/exterior.mp4`, `frames/{id}/exterior/frame_NNNN.jpg`, etc.
- Graceful fallback to local filesystem when no connection string configured

Tests: Mock the Azure SDK, test upload/download paths.

Commit: `feat: add Azure Blob Storage service`

### Task 6: Celery setup with Redis broker

**Files:**
- Create: `backend/app/tasks/__init__.py`
- Create: `backend/app/tasks/celery_app.py`
- Modify: `backend/app/config.py` — add Redis/Celery settings

**Details:**

Add to `config.py`:
```python
redis_url: str = "redis://localhost:6379/0"
celery_broker_url: str = ""  # defaults to redis_url
celery_result_backend: str = ""  # defaults to redis_url
```

`celery_app.py`:
```python
from celery import Celery
from app.config import settings

celery = Celery(
    "insurascan",
    broker=settings.celery_broker_url or settings.redis_url,
    backend=settings.celery_result_backend or settings.redis_url,
)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_hijack_root_logger=False,
)
```

Commit: `feat: add Celery configuration`

### Task 7: API v1 — Assessment CRUD endpoints

**Files:**
- Create: `backend/app/api/v1/__init__.py`
- Create: `backend/app/api/v1/router.py` — aggregate all v1 routes
- Create: `backend/app/api/v1/assessments.py` — CRUD endpoints
- Create: `backend/app/api/deps.py` — dependency injection (db session)
- Modify: `backend/app/main.py` — include v1 router
- Test: `backend/tests/test_v1_assessments.py`

**Endpoints (from project plan Section 5.1):**
- `POST /api/v1/assessments` — create assessment with metadata
- `GET /api/v1/assessments` — list assessments (paginated, filterable by status/claim_number)
- `GET /api/v1/assessments/{id}` — get detail with pipeline status
- `DELETE /api/v1/assessments/{id}` — soft-delete

**Tests:** Test each endpoint with TestClient, mock DB session.

Commit: `feat: add assessment CRUD API v1 endpoints`

### Task 8: API v1 — Video upload endpoints

**Files:**
- Create: `backend/app/api/v1/videos.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_v1_videos.py`

**Endpoints:**
- `POST /api/v1/assessments/{id}/videos/exterior` — upload exterior video (multipart, max 500MB)
- `POST /api/v1/assessments/{id}/videos/interior` — upload interior video
- `GET /api/v1/assessments/{id}/videos/{type}/status` — check processing status

On upload: store to Blob Storage, update assessment record, trigger Celery frame extraction task.

Commit: `feat: add video upload endpoints`

### Task 9: API v1 — Splat and report endpoints

**Files:**
- Create: `backend/app/api/v1/splats.py`
- Create: `backend/app/api/v1/reports.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_v1_splats.py`, `backend/tests/test_v1_reports.py`

**Endpoints:**
- `GET /api/v1/assessments/{id}/splat/exterior` — get .ply URL
- `GET /api/v1/assessments/{id}/splat/interior` — get .ply URL
- `GET /api/v1/assessments/{id}/report` — full damage report JSON
- `GET /api/v1/assessments/{id}/report/pdf` — download PDF
- `GET /api/v1/assessments/{id}/damages` — list damage items
- `GET /api/v1/assessments/{id}/frames` — list extracted frames

Commit: `feat: add splat and report API endpoints`

### Task 10: Health and system endpoints

**Files:**
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_v1_health.py`

**Endpoints:**
- `GET /api/v1/health` — health check (DB + Redis connectivity)
- `GET /api/v1/health/gpu` — GPU availability status
- `GET /api/v1/config` — app configuration (limits, supported formats)

Commit: `feat: add health and system endpoints`

### Task 11: Update main.py lifespan for new services

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`

**Details:**
- Add database initialization in lifespan (create engine, run migrations check)
- Initialize Blob Storage service
- Keep existing TripoSR + damage service initialization as fallback
- Include v1 router alongside existing router
- Add `DATABASE_URL` and other new config vars with sensible defaults

Commit: `feat: integrate new services into app lifespan`

### Task 12: Docker Compose for full stack

**Files:**
- Create: `docker-compose.yml` (project root)
- Modify: `backend/Dockerfile`

**Details:**

`docker-compose.yml`:
```yaml
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    env_file: ./backend/.env
    depends_on: [redis]
    # Note: PostgreSQL and Redis are Azure-hosted, but include local fallback

  celery-worker:
    build: ./backend
    command: celery -A app.tasks.celery_app worker --loglevel=info
    env_file: ./backend/.env
    depends_on: [redis]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    # Local Redis for development; production uses Azure Redis
```

Update Dockerfile to install FFmpeg and other system deps.

Commit: `feat: add docker-compose for full stack`

---

## Workstream 2: Processing Pipeline

Owner: **pipeline** teammate

Depends on: Tasks 2, 5, 6 from Workstream 1 (DB models, Blob Storage, Celery)

### Task 13: FFmpeg frame extraction service

**Files:**
- Create: `backend/app/services/frame_extractor.py`
- Test: `backend/tests/test_frame_extractor.py`

**Details:**

`frame_extractor.py`:
- Class `FrameExtractorService` with methods:
  - `extract_frames(video_path, output_dir, fps=2) -> list[Path]`
  - `filter_quality(frame_path) -> bool` — blur detection (Laplacian variance > threshold) + brightness check
- Uses `ffmpeg-python` or subprocess call to FFmpeg
- FFmpeg command: `ffmpeg -i input.mp4 -vf "fps=2" -q:v 2 frames/frame_%04d.jpg`
- Returns list of paths to frames that pass quality filtering

**Tests:**
- Create a small test video (or mock FFmpeg subprocess)
- Test frame extraction count
- Test quality filtering (provide a blurry image, verify rejection)

Commit: `feat: add FFmpeg frame extraction service`

### Task 14: Celery task — extract_frames

**Files:**
- Create: `backend/app/tasks/extract_frames.py`
- Test: `backend/tests/test_task_extract_frames.py`

**Details:**

```python
@celery.task(bind=True)
def extract_frames_task(self, assessment_id: str, video_type: str):
    """Download video from Blob → extract frames → upload frames to Blob → update DB."""
    # 1. Download video from blob
    # 2. Extract frames with FFmpeg
    # 3. Filter quality
    # 4. Upload passing frames to blob
    # 5. Update assessment.{type}_frame_count in DB
    # 6. Update processing_job status
    # 7. Chain to next task (run_colmap) if both exterior+interior done
```

Commit: `feat: add frame extraction Celery task`

### Task 15: COLMAP SfM integration

**Files:**
- Create: `backend/app/services/colmap_service.py`
- Test: `backend/tests/test_colmap_service.py`

**Details:**

`colmap_service.py`:
- Class `COLMAPService` with methods:
  - `run_sfm(frames_dir, output_dir) -> Path` — runs COLMAP pipeline
  - Steps: feature_extractor → exhaustive_matcher → mapper
  - Input: directory of frames
  - Output: sparse reconstruction (cameras.bin, images.bin, points3D.bin)
- Wraps COLMAP as subprocess calls
- Timeout + error handling for GPU-bound operations

**Tests:** Mock subprocess calls, verify command construction.

Commit: `feat: add COLMAP SfM service`

### Task 16: Gaussian Splatting integration

**Files:**
- Create: `backend/app/services/gaussian_splat.py`
- Test: `backend/tests/test_gaussian_splat.py`

**Details:**

`gaussian_splat.py`:
- Class `GaussianSplatService` with methods:
  - `train(frames_dir, colmap_output_dir, output_dir, iterations=7000) -> Path`
  - `export_ply(model_dir) -> Path` — export trained model to .ply
- Uses gsplat or nerfstudio Python API (or subprocess to `ns-train`)
- Configurable iterations (7k for hackathon speed, 15k for quality)
- Returns path to exported .ply file

**Tests:** Mock the training subprocess, verify .ply output path construction.

Commit: `feat: add Gaussian Splatting service`

### Task 17: Celery task — run_splatting (COLMAP + 3DGS)

**Files:**
- Create: `backend/app/tasks/run_splatting.py`
- Test: `backend/tests/test_task_splatting.py`

**Details:**

```python
@celery.task(bind=True)
def run_splatting_task(self, assessment_id: str, video_type: str):
    """Download frames from Blob → COLMAP SfM → Gaussian Splatting → upload .ply to Blob."""
    # 1. Download frames from blob to local temp dir
    # 2. Run COLMAP SfM → get camera poses
    # 3. Run Gaussian Splatting training → get .ply
    # 4. Upload .ply to blob
    # 5. Update assessment splat_blob_path in DB
    # 6. Update processing_job status
```

Commit: `feat: add Gaussian Splatting Celery task`

### Task 18: Enhanced AI damage analysis

**Files:**
- Create: `backend/app/services/damage_analyzer.py` (new, enhanced version)
- Test: `backend/tests/test_damage_analyzer.py`

**Details:**

Enhanced version of existing `damage.py`:
- Zone-based frame batching: organize frames by estimated vehicle zone
- Send 4-8 frames per API call (batched by zone)
- Use the enhanced prompt from project plan Section 9 (includes vehicle info, zone categories, confidence scores)
- Parse the richer damage schema (damage_id, vehicle_zone enum, affected_parts, confidence_score, reference_frames)
- Store individual DamageItem records in PostgreSQL

Commit: `feat: add enhanced zone-based damage analyzer`

### Task 19: Celery task — analyze_damage

**Files:**
- Create: `backend/app/tasks/analyze_damage.py`
- Test: `backend/tests/test_task_analyze.py`

**Details:**

```python
@celery.task(bind=True)
def analyze_damage_task(self, assessment_id: str):
    """Download sampled frames → batch by zone → send to GPT-4o → store damage items in DB."""
    # 1. Download frames from blob (sample every Nth)
    # 2. Organize by estimated vehicle zone
    # 3. For each zone batch, call GPT-4o
    # 4. Parse structured JSON response
    # 5. Create DamageItem records in DB
    # 6. Calculate aggregate totals on Assessment
    # 7. Update processing_job status
```

**Note:** This task can run in parallel with splatting since it only needs frames (available after extraction).

Commit: `feat: add damage analysis Celery task`

### Task 20: Report generation service + task

**Files:**
- Create: `backend/app/services/report_generator.py`
- Create: `backend/app/tasks/generate_report.py`
- Test: `backend/tests/test_report_generator.py`

**Details:**

`report_generator.py`:
- `generate_json_report(assessment_id) -> dict` — aggregate all damage items into full report JSON
- `generate_pdf_report(assessment_id) -> bytes` — render HTML template, convert to PDF via WeasyPrint
- HTML template includes: vehicle info header, damage items table with severity colors, cost breakdown, totals, summary narrative
- Upload both to Blob Storage

Commit: `feat: add report generation service and task`

### Task 21: Pipeline orchestration — Celery task chain

**Files:**
- Create: `backend/app/tasks/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

**Details:**

```python
def start_pipeline(assessment_id: str, video_type: str):
    """Orchestrate the full processing chain."""
    chain = (
        extract_frames_task.s(assessment_id, video_type)
        | run_splatting_task.s(assessment_id, video_type)
    )
    # analyze_damage runs after frames are extracted (parallel with splatting)
    chord = group(
        chain,
        extract_frames_task.s(assessment_id, video_type)
        | analyze_damage_task.s(assessment_id)
    ) | generate_report_task.s(assessment_id)
    chord.apply_async()
```

Actually: use Celery chord — splatting and analysis run in parallel after frame extraction, report generates after both complete.

Commit: `feat: add pipeline orchestration`

### Task 22: WebSocket enhancement — Redis pub/sub

**Files:**
- Modify: `backend/app/api/websocket.py`
- Test: `backend/tests/test_websocket_v1.py`

**Details:**

Celery tasks publish progress updates to a Redis channel: `insurascan:progress:{assessment_id}`.
WebSocket handler subscribes to this channel and forwards to connected clients.
This replaces the in-memory subscriber pattern from the MVP, enabling multi-process support.

Commit: `feat: enhance WebSocket with Redis pub/sub`

---

## Workstream 3: Frontend

Owner: **frontend** teammate

Depends on: Task 7 API endpoints being available (can mock initially)

### Task 23: Frontend project restructure + dependencies

**Files:**
- Modify: `package.json` — add new dependencies
- Create: `src/lib/api-client.ts` — API client (adapt from `backend/frontend_integration/api-client.ts`)
- Create: `src/lib/api-types.ts` — types (adapt from `backend/frontend_integration/api-types.ts`)
- Create: `tailwind.config.js`
- Create: `postcss.config.js`

**Dependencies to add:**
```
npm install tailwindcss @tailwindcss/vite react-router-dom @tanstack/react-query
npm install @mkkellogg/gaussian-splats-3d
```

**Steps:**
1. Install Tailwind CSS + configure with Vite plugin
2. Install React Router v6
3. Install TanStack Query
4. Copy and adapt API client/types from `backend/frontend_integration/`
5. Set up API base URL from env var `VITE_API_URL`
6. Commit: `feat: add frontend dependencies and API client`

### Task 24: App shell — routing + layout

**Files:**
- Modify: `src/App.tsx` — add Router + layout shell
- Create: `src/layouts/DashboardLayout.tsx` — sidebar + header + main content
- Create: `src/pages/AssessmentListPage.tsx` (placeholder)
- Create: `src/pages/NewAssessmentPage.tsx` (placeholder)
- Create: `src/pages/AssessmentDetailPage.tsx` (placeholder)
- Modify: `src/main.tsx` — wrap with QueryClientProvider + RouterProvider

**Routes:**
```
/                    → redirect to /assessments
/assessments         → AssessmentListPage
/assessments/new     → NewAssessmentPage
/assessments/:id     → AssessmentDetailPage
```

**Layout:**
- Sidebar with InsuraScan logo + nav links
- Header with breadcrumbs
- Main content area

Commit: `feat: add app shell with routing and layout`

### Task 25: Assessment list page

**Files:**
- Modify: `src/pages/AssessmentListPage.tsx`
- Create: `src/components/StatusBadge.tsx`

**Details:**
- Table with columns: claim number, vehicle, status, date, total estimate
- Status badges with color coding: Processing (yellow), Complete (green), Failed (red)
- Search input (filter by claim number)
- Filter dropdown (by status)
- "New Assessment" button → navigates to /assessments/new
- Uses TanStack Query to fetch `GET /api/v1/assessments`

Commit: `feat: add assessment list page`

### Task 26: New assessment page

**Files:**
- Modify: `src/pages/NewAssessmentPage.tsx`
- Create: `src/components/UploadZone.tsx` — drag-and-drop video upload with progress

**Details:**
- Form fields: claim number, agent ID, vehicle year/make/model, VIN
- Two upload zones: "Exterior Video" and "Interior Video"
- Each zone: drag-and-drop + click-to-browse, shows upload progress bar
- Submit button: POST /api/v1/assessments, then POST videos, then redirect to detail page
- Form validation: required fields, file size check (max 500MB)

Commit: `feat: add new assessment page with upload`

### Task 27: Assessment detail page — status tracker

**Files:**
- Modify: `src/pages/AssessmentDetailPage.tsx`
- Create: `src/components/StatusTracker.tsx` — visual pipeline progress

**Details:**

StatusTracker shows the pipeline stages with visual progress:
```
Upload → Frames → Splat → Analysis → Complete
  ✓        ✓       ●        ○          ○
```
- Each stage shows: done (checkmark), in-progress (spinner), pending (circle)
- Connects to WebSocket for real-time updates
- Falls back to polling `GET /api/v1/assessments/{id}` every 5s

Commit: `feat: add assessment detail page with status tracker`

### Task 28: Gaussian Splat viewer component

**Files:**
- Create: `src/components/SplatViewer.tsx` — Three.js Gaussian Splat .ply renderer

**Details:**

Use `@mkkellogg/gaussian-splats-3d` library to render .ply files:
- Load .ply from URL (Blob Storage SAS URL)
- Orbit controls (rotate, zoom, pan)
- Toggle between exterior/interior splat
- Full-screen mode button
- Loading state with progress indicator
- Touch-responsive for mobile

**Integration:**
```tsx
import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';

// In a useEffect:
const viewer = new GaussianSplats3D.Viewer({
  cameraUp: [0, -1, 0],
  initialCameraPosition: [0, 0, 5],
  initialCameraLookAt: [0, 0, 0],
});
viewer.addSplatScene(plyUrl).then(() => viewer.start());
```

Commit: `feat: add Gaussian Splat 3D viewer component`

### Task 29: Damage report panel

**Files:**
- Create: `src/components/DamageReport.tsx` — damage items + cost breakdown
- Create: `src/components/DamageCard.tsx` — individual damage item card

**Details:**

DamageReport panel shows:
- List of damage items as cards
- Each card: part name, severity badge (color-coded), damage type, description, repair method, cost range
- Severity colors: minor (green), moderate (yellow), severe (red)
- Cost breakdown table at bottom (per item + totals)
- Expandable reference frames section per damage item
- "Download PDF Report" button

DamageCard:
```
┌──────────────────────────────────────┐
│ Front Bumper          [SEVERE] 🔴    │
│ Dent with paint transfer             │
│ Repair: Replace + repaint            │
│ Cost: $800 – $1,200                  │
│ Confidence: 85%                      │
│ [View reference frames ▼]            │
└──────────────────────────────────────┘
```

Commit: `feat: add damage report panel`

### Task 30: Assessment detail page — full integration

**Files:**
- Modify: `src/pages/AssessmentDetailPage.tsx`
- Create: `src/components/VideoPlayer.tsx`

**Details:**

Wire together all components on the detail page:
- **Top:** Status tracker (full-width)
- **Left column:** 3D Splat viewer (or GLB viewer for TripoSR fallback)
  - Tabs: Exterior | Interior
  - Below: Video playback for both captures
- **Right column:** Damage report panel
  - Damage cards
  - Cost breakdown
  - Download PDF button

VideoPlayer: simple HTML5 `<video>` element with Blob Storage URL, play/pause/scrub.

Commit: `feat: integrate detail page with all components`

### Task 31: Real-time WebSocket integration in frontend

**Files:**
- Create: `src/hooks/useJobProgress.ts` — WebSocket hook for real-time updates
- Modify: `src/pages/AssessmentDetailPage.tsx` — connect hook

**Details:**

`useJobProgress(assessmentId)`:
- Connect to `ws://{API_URL}/ws/{assessmentId}`
- Parse ProgressUpdate messages
- Return: `{ status, progressPct, message, isConnected }`
- Auto-reconnect on disconnect
- Close on component unmount
- Invalidate TanStack Query cache when status reaches "complete"

Commit: `feat: add real-time WebSocket progress hook`

### Task 32: Vehicle zone diagram (P1)

**Files:**
- Create: `src/components/ZoneDiagram.tsx` — SVG vehicle outline with damage pins

**Details:**

SVG top-down vehicle outline with clickable zones:
- Zones: front_left, front_right, front_center, rear_left, rear_right, rear_center, side_left, side_right, roof
- Each zone highlights with severity color if damage detected
- Click zone → scrolls to corresponding damage card in report panel
- Responsive sizing

Commit: `feat: add vehicle zone damage diagram`

---

## Integration & Finalization

### Task 33: Update CLAUDE.md and .env.example

**Files:**
- Modify: `CLAUDE.md` — add new commands, updated architecture
- Modify: `backend/.env.example` — add all new env vars

Commit: `docs: update project docs for full platform`

### Task 34: End-to-end integration test

**Files:**
- Create: `backend/tests/test_e2e_pipeline.py`

**Details:**
- Test full flow: create assessment → upload video (mock) → frame extraction → splatting (mock) → analysis (mock) → report generation
- Verify all DB records created correctly
- Verify status transitions
- Verify WebSocket updates

Commit: `test: add end-to-end pipeline integration test`

---

## Task Dependency Graph

```
Workstream 1 (Backend Infra):
  T1 → T2 → T3 → T4 → T7 → T8 → T9 → T10 → T11 → T12
       T2 → T5 (Blob)
       T2 → T6 (Celery)

Workstream 2 (Pipeline):
  Needs T2,T5,T6 first, then:
  T13 → T14 → T15 → T16 → T17 → T18 → T19 → T20 → T21 → T22

Workstream 3 (Frontend):
  Can start immediately (mock API):
  T23 → T24 → T25 → T26 → T27 → T28 → T29 → T30 → T31 → T32

Final:
  T33, T34 (after all workstreams complete)
```
