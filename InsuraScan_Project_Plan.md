# 🚗 InsuraScan — AR/XR Vehicle Damage Assessment Platform

## Hackathon Project Plan & Technical Specification

---

## 1. Project Overview

**InsuraScan** is an AR/XR-powered vehicle damage assessment platform that enables insurance agents to capture walkround videos of damaged vehicles, reconstruct them as 3D Gaussian Splats, and leverage multimodal AI to automatically identify, classify, and estimate repair costs.

**Hackathon Objective:** Demonstrate AR/VR/XR capability through 3D Gaussian Splat reconstruction of damaged vehicles combined with AI-powered damage analysis.

**Core Workflow:**

```
Agent captures video (exterior + interior)
        ↓
Video uploaded → Azure Blob Storage
        ↓
Backend extracts frames → saved to Blob
        ↓
Frames processed → Gaussian Splatting → .ply file saved to Blob
        ↓
Frames sent → Azure AI Foundry (GPT-4o multimodal) → Damage Analysis
        ↓
Structured damage report generated
        ↓
Web dashboard + Mobile app display results with interactive 3D viewer
```

---

## 2. High-Level Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│   Mobile App        │     │   Web Frontend       │
│   (Video Capture)   │     │   (React Dashboard)  │
└────────┬────────────┘     └────────┬────────────┘
         │                           │
         └──────────┬────────────────┘
                    ▼
         ┌─────────────────────┐
         │   FastAPI Backend   │
         │   (REST API)        │
         └────────┬────────────┘
                  │
     ┌────────────┼────────────────┐
     ▼            ▼                ▼
┌─────────┐ ┌──────────┐  ┌──────────────┐
│ Azure   │ │ Celery + │  │ PostgreSQL   │
│ Blob    │ │ Redis    │  │ (Metadata &  │
│ Storage │ │ (Async   │  │  Job State)  │
│         │ │  Queue)  │  │              │
└─────────┘ └────┬─────┘  └──────────────┘
                 │
    ┌────────────┼──────────────┐
    ▼            ▼              ▼
┌────────┐ ┌──────────┐ ┌────────────────┐
│ FFmpeg │ │ Gaussian │ │ Azure AI       │
│ Frame  │ │ Splatting│ │ Foundry        │
│ Extract│ │ (GPU)    │ │ (GPT-4o Vision)│
└────────┘ └──────────┘ └────────────────┘
```

---

## 3. Technology Stack

### 3.1 Backend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Framework | **FastAPI** (Python 3.11+) | REST API — serves both web frontend and mobile app |
| Task Queue | **Celery** + **Redis** | Async processing pipeline (frame extraction, splatting, AI analysis) |
| Video Processing | **FFmpeg** | Frame extraction from uploaded videos |
| 3D Reconstruction | **3D Gaussian Splatting** (gsplat / nerfstudio) | Generate .ply splat files from video frames |
| SfM (Structure from Motion) | **COLMAP** | Camera pose estimation from frames (prerequisite for splatting) |
| Storage | **Azure Blob Storage** | Videos, frames, .ply files, reports |
| Database | **PostgreSQL** | Assessment metadata, job tracking, damage reports |
| AI / LLM | **Azure AI Foundry** (GPT-4o multimodal) | Vision-based damage detection and cost estimation |

### 3.2 Frontend (Web Dashboard)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | **React 18** + **TypeScript** | SPA dashboard |
| 3D Viewer | **Three.js** + Gaussian Splat viewer | Interactive .ply splat rendering in browser |
| Styling | **Tailwind CSS** + **shadcn/ui** | UI components |
| Data Fetching | **TanStack Query** (React Query) | API state management, polling |
| Routing | **React Router v6** | Page navigation |

### 3.3 Mobile App (Phase 2 — consumes same FastAPI)

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | React Native **or** Swift (iOS) / Kotlin (Android) | Cross-platform or native |
| Camera | Native video capture APIs | Exterior walkaround + interior scan |
| AR Guidance | **ARKit** (iOS) / **ARCore** (Android) | Guided capture overlay showing path + coverage |

### 3.4 Azure Infrastructure

| Resource | Service | SKU / Notes |
|----------|---------|-------------|
| Compute (API) | Azure Container Apps **or** App Service | B2+ for API server |
| Compute (GPU) | Azure VM (NC-series) **or** Azure ML Compute | NVIDIA T4/A10 for Gaussian Splatting |
| Object Storage | Azure Blob Storage | Standard LRS — containers: `videos`, `frames`, `splats`, `reports` |
| Database | Azure Database for PostgreSQL — Flexible Server | Burstable B1ms for hackathon |
| Cache / Queue | Azure Cache for Redis | Basic C0 for Celery broker |
| AI | Azure AI Foundry | GPT-4o deployment for multimodal analysis |
| DNS / Gateway | Azure API Management **or** direct Container App ingress | HTTPS endpoint |

---

## 4. Core Features — Detailed Specification

### 4.1 Feature: Video Capture & Upload

**Description:** Insurance agent captures two separate videos of the damaged vehicle and uploads them to the backend.

**Two Separate Capture Processes:**

| Capture | Description | Guidance |
|---------|------------|----------|
| **Exterior Walkaround** | 360° slow walk around the full vehicle — all panels, bumpers, wheels, roof | Walk in a steady circle, keep vehicle centered, cover all 4 sides + front + rear |
| **Interior Scan** | Dashboard, seats, headliner, door panels, center console, steering wheel, floor | Systematic sweep: driver door → dash → passenger → rear seats → trunk/cargo |

**Technical Requirements:**
- Minimum resolution: 1080p at 30fps
- Recommended duration: 30–90 seconds per capture
- Format: MP4 (H.264)
- Max file size: 500MB per video
- Upload method: Chunked/multipart upload with resume capability
- Metadata captured on upload: claim number, agent ID, vehicle info (year/make/model), VIN (manual or OCR), GPS coordinates, timestamp

**Acceptance Criteria:**
- [ ] Agent can upload exterior video
- [ ] Agent can upload interior video
- [ ] Upload progress is displayed
- [ ] Failed uploads can be retried
- [ ] Metadata is stored with the assessment record

---

### 4.2 Feature: Video Ingestion & Frame Extraction

**Description:** Backend receives the video, persists to Blob Storage, then extracts individual frames for downstream processing.

**Pipeline Steps:**

1. **Receive video** via FastAPI upload endpoint
2. **Store raw video** in Azure Blob: `videos/{assessment_id}/exterior.mp4`
3. **Trigger Celery task** for frame extraction
4. **FFmpeg extracts frames** at configurable rate (default: 2 fps for splatting quality)
5. **Quality filter** each frame:
   - Blur detection (Laplacian variance threshold)
   - Brightness check (reject over/underexposed)
   - Discard frames that fail quality checks
6. **Save passing frames** to Blob: `frames/{assessment_id}/exterior/frame_0001.jpg`
7. **Update job status** in PostgreSQL → triggers next pipeline stage

**FFmpeg Command (reference):**

```bash
ffmpeg -i input.mp4 -vf "fps=2" -q:v 2 frames/frame_%04d.jpg
```

**Acceptance Criteria:**
- [ ] Video is stored in Blob Storage immediately on upload
- [ ] Frames are extracted at 2fps
- [ ] Blurry / bad frames are filtered out
- [ ] Frame count and paths are recorded in DB
- [ ] Job status transitions: `uploading → extracting_frames`

---

### 4.3 Feature: Gaussian Splatting (3D Reconstruction)

**Description:** Extracted frames are processed through a Gaussian Splatting pipeline to produce a 3D reconstructed splat (.ply file) of the vehicle.

**Pipeline Steps:**

1. **COLMAP — Structure from Motion**
   - Input: extracted frames
   - Process: feature extraction → feature matching → sparse reconstruction
   - Output: camera poses + sparse point cloud
   - Estimated time: 2–5 minutes

2. **Gaussian Splatting Training**
   - Input: frames + camera poses from COLMAP
   - Process: Train 3D Gaussian Splatting model
   - Iterations: 7,000–15,000 (reduced for hackathon speed)
   - Output: Trained Gaussian Splat model
   - Estimated time: 5–15 minutes on GPU

3. **Export .ply File**
   - Export trained model to `.ply` (Gaussian Splat format)
   - Save to Blob: `splats/{assessment_id}/exterior.ply`
   - Generate turntable preview render (optional: short video or thumbnail)

**GPU Requirements:**
- NVIDIA GPU with CUDA support
- Minimum: T4 (16GB VRAM) — works for hackathon-scale scenes
- Recommended: A10 (24GB VRAM) for better quality
- Azure NC-series VMs or Azure ML Compute clusters

**XR/AR Demonstration Value:**
- `.ply` Gaussian Splat can be viewed interactively in a web-based 3D viewer (core XR demo)
- Future: load into AR headset (Meta Quest 3, Apple Vision Pro) for immersive review
- Adjuster can rotate, zoom, and inspect damage from any angle without being on-site

**Fallback Plan (if GPU is unavailable):**
- Pre-compute 1–2 sample splats ahead of the hackathon demo
- Show the live pipeline triggering but display pre-computed results
- Alternative: Use photogrammetry (Meshroom / OpenMVS) for mesh-based 3D reconstruction

**Acceptance Criteria:**
- [ ] COLMAP successfully estimates camera poses from frames
- [ ] Gaussian Splatting produces a viewable .ply file
- [ ] .ply is stored in Azure Blob Storage
- [ ] Processing status is tracked and visible to the user
- [ ] Job status transitions: `extracting_frames → splatting`

---

### 4.4 Feature: AI Multimodal Damage Analysis

**Description:** Selected frames are sent to Azure AI Foundry's GPT-4o (multimodal) to perform automated damage detection, classification, and repair cost estimation.

**Pipeline Steps:**

1. **Frame Selection Strategy**
   - Sample every Nth frame from the full set (e.g., every 5th frame)
   - Organize frames by estimated vehicle zone (front, rear, left, right, roof, interior)
   - Optionally: pre-filter using a lightweight damage detection model to prioritize damaged areas

2. **Prompt Construction**
   - System prompt establishes role as an expert vehicle damage assessor
   - Include vehicle context (year/make/model) for accurate part pricing
   - Send 4–8 frames per API call (batched by zone)
   - Request structured JSON output

3. **Azure AI Foundry Call**
   - Model: GPT-4o (multimodal deployment on Azure AI Foundry)
   - Input: system prompt + batch of base64-encoded frame images
   - Output: structured JSON damage assessment

4. **Parse & Store Results**
   - Validate JSON schema
   - Store individual damage items in PostgreSQL
   - Calculate aggregate totals

**AI Output Schema — Per Damage Instance:**

```json
{
  "damage_id": "DMG-001",
  "location": "Front bumper, driver side",
  "vehicle_zone": "front_left",
  "damage_type": "Dent with paint transfer",
  "severity": "moderate",
  "description": "Approximately 8-inch dent on front bumper cover with white paint transfer consistent with low-speed frontal collision. Bumper cover is deformed but not cracked.",
  "affected_parts": [
    "Front bumper cover",
    "Bumper reinforcement bar (inspect)"
  ],
  "repair_method": "Replace bumper cover + repaint. PDR not viable due to paint damage.",
  "estimated_cost_low": 800,
  "estimated_cost_high": 1200,
  "confidence_score": 0.85,
  "reference_frames": ["frame_0042.jpg", "frame_0043.jpg"]
}
```

**Full Report Output:**

```json
{
  "assessment_id": "uuid",
  "vehicle": { "year": 2022, "make": "Toyota", "model": "Camry" },
  "damages": [ ... ],
  "summary": {
    "total_damage_count": 4,
    "total_estimate_low": 3200,
    "total_estimate_high": 4800,
    "recommendation": "Repair — estimate below total loss threshold",
    "pre_existing_damage_flags": ["Minor scratch on rear bumper appears weathered / pre-existing"],
    "narrative": "Vehicle sustained moderate frontal damage consistent with a low-speed collision..."
  }
}
```

**Acceptance Criteria:**
- [ ] Frames are batched and sent to Azure AI Foundry
- [ ] GPT-4o returns structured damage JSON
- [ ] Each damage item is stored with location, type, severity, cost range
- [ ] Aggregate report with totals is generated
- [ ] Job status transitions: `splatting → analyzing → complete`

---

### 4.5 Feature: Web Dashboard

**Description:** React-based frontend for agents and adjusters to manage assessments, view 3D splats, and review AI damage reports.

**Pages / Views:**

#### Assessment List Page
- Table of all assessments with: claim number, vehicle, status, date, total estimate
- Status badges: `Processing`, `Complete`, `Failed`
- Search/filter by claim number, date range, status
- "New Assessment" button

#### New Assessment Page
- Form: claim number, agent ID, vehicle year/make/model, VIN
- Two upload zones: Exterior Video, Interior Video
- Upload progress bars
- Submit → begins processing pipeline

#### Assessment Detail Page
- **Status Tracker** — visual pipeline progress (Upload → Frames → Splat → Analysis → Complete)
- **Video Playback** — side-by-side exterior/interior video players
- **3D Splat Viewer** — interactive Three.js Gaussian Splat renderer
  - Rotate, zoom, pan
  - Toggle exterior / interior splat
  - Full-screen mode
- **Damage Report Panel**
  - List of damage items with severity color coding
  - Click damage item → highlights reference frames
  - Cost breakdown table (per item + total low/high)
  - Repair vs. replace recommendations
- **Export** — Download PDF report button

#### 3D Viewer Component (Key XR Element)
- Powered by Three.js + Gaussian Splat renderer (e.g., `antimatter15/splat` or `@mkkellogg/gaussian-splats-3d`)
- Loads .ply from Blob Storage URL
- Touch/mouse orbit controls
- Mobile-responsive for viewing on phone

**Acceptance Criteria:**
- [ ] Dashboard lists assessments with real-time status
- [ ] Video playback works for both exterior and interior
- [ ] Gaussian Splat .ply renders interactively in browser
- [ ] Damage report displays all items with cost estimates
- [ ] Assessment can be created and uploaded from the web UI

---

## 5. API Design (FastAPI)

### 5.1 Endpoint Inventory

**Base URL:** `https://{host}/api/v1`

#### Assessments

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/assessments` | Create new assessment | Yes |
| `GET` | `/assessments` | List all assessments (paginated, filterable) | Yes |
| `GET` | `/assessments/{id}` | Get assessment detail + current status | Yes |
| `DELETE` | `/assessments/{id}` | Cancel / soft-delete assessment | Yes |

#### Video Upload

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/assessments/{id}/videos/exterior` | Upload exterior walkaround video |
| `POST` | `/assessments/{id}/videos/interior` | Upload interior scan video |
| `GET` | `/assessments/{id}/videos/{type}/status` | Check video processing status |

#### 3D Splat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/assessments/{id}/splat/exterior` | Get exterior .ply file URL |
| `GET` | `/assessments/{id}/splat/interior` | Get interior .ply file URL |
| `GET` | `/assessments/{id}/splat/{type}/preview` | Get preview thumbnail |

#### Damage Report

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/assessments/{id}/report` | Full damage report (JSON) |
| `GET` | `/assessments/{id}/report/pdf` | Download PDF version |
| `GET` | `/assessments/{id}/damages` | List individual damage items |
| `GET` | `/assessments/{id}/frames` | List extracted frames with metadata |
| `GET` | `/assessments/{id}/frames/{frame_id}` | Get single frame (annotated) |

#### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/health/gpu` | GPU availability status |
| `GET` | `/config` | App configuration (limits, supported formats) |

### 5.2 Key Request/Response Examples

**Create Assessment:**
```json
// POST /api/v1/assessments
// Request
{
  "claim_number": "CLM-2026-00142",
  "agent_id": "agent_jsmith",
  "vehicle_year": 2022,
  "vehicle_make": "Toyota",
  "vehicle_model": "Camry",
  "vin": "4T1BF1FK5CU512345",
  "gps_latitude": 33.7490,
  "gps_longitude": -84.3880
}

// Response (201)
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "created",
  "claim_number": "CLM-2026-00142",
  "created_at": "2026-02-23T14:30:00Z",
  "upload_urls": {
    "exterior": "/api/v1/assessments/a1b2c3.../videos/exterior",
    "interior": "/api/v1/assessments/a1b2c3.../videos/interior"
  }
}
```

**Assessment Status Response:**
```json
// GET /api/v1/assessments/{id}
{
  "id": "a1b2c3d4-...",
  "status": "analyzing",
  "claim_number": "CLM-2026-00142",
  "vehicle": { "year": 2022, "make": "Toyota", "model": "Camry" },
  "pipeline": {
    "exterior_video": "complete",
    "interior_video": "complete",
    "frame_extraction": "complete",
    "gaussian_splatting": "complete",
    "damage_analysis": "in_progress",
    "report_generation": "pending"
  },
  "frame_count": { "exterior": 124, "interior": 87 },
  "splat_ready": { "exterior": true, "interior": false },
  "created_at": "2026-02-23T14:30:00Z"
}
```

---

## 6. Data Models

### 6.1 Assessment

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `claim_number` | VARCHAR(50) | Insurance claim reference |
| `agent_id` | VARCHAR(100) | Agent identifier |
| `vin` | VARCHAR(17) | Vehicle Identification Number |
| `vehicle_year` | INTEGER | Model year |
| `vehicle_make` | VARCHAR(50) | Manufacturer |
| `vehicle_model` | VARCHAR(50) | Model name |
| `status` | ENUM | `created`, `uploading`, `extracting_frames`, `splatting`, `analyzing`, `complete`, `failed` |
| `exterior_video_blob_path` | TEXT | Blob path to exterior video |
| `interior_video_blob_path` | TEXT | Blob path to interior video |
| `exterior_splat_blob_path` | TEXT | Blob path to exterior .ply |
| `interior_splat_blob_path` | TEXT | Blob path to interior .ply |
| `exterior_frame_count` | INTEGER | Number of extracted exterior frames |
| `interior_frame_count` | INTEGER | Number of extracted interior frames |
| `total_estimate_low` | DECIMAL | Aggregate low repair estimate |
| `total_estimate_high` | DECIMAL | Aggregate high repair estimate |
| `gps_latitude` | DECIMAL | Capture location lat |
| `gps_longitude` | DECIMAL | Capture location lng |
| `error_message` | TEXT | Error details if status=failed |
| `created_at` | TIMESTAMP | Record creation |
| `updated_at` | TIMESTAMP | Last status update |
| `completed_at` | TIMESTAMP | When analysis finished |

### 6.2 DamageItem

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `assessment_id` | UUID (FK) | Parent assessment |
| `damage_id` | VARCHAR(20) | Human-readable ID (DMG-001) |
| `location` | TEXT | Description of damage location |
| `vehicle_zone` | ENUM | `front_left`, `front_right`, `front_center`, `rear_left`, `rear_right`, `rear_center`, `side_left`, `side_right`, `roof`, `interior_front`, `interior_rear` |
| `damage_type` | VARCHAR(100) | E.g., dent, scratch, crack, shatter |
| `severity` | ENUM | `minor`, `moderate`, `severe` |
| `description` | TEXT | Detailed AI-generated description |
| `affected_parts` | JSONB | Array of part names |
| `repair_method` | TEXT | Recommended repair approach |
| `estimated_cost_low` | DECIMAL | Low-end estimate |
| `estimated_cost_high` | DECIMAL | High-end estimate |
| `confidence_score` | DECIMAL | AI confidence (0.0–1.0) |
| `reference_frame_paths` | JSONB | Array of blob paths to relevant frames |
| `created_at` | TIMESTAMP | When damage was detected |

### 6.3 ProcessingJob

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `assessment_id` | UUID (FK) | Parent assessment |
| `stage` | ENUM | `frame_extraction`, `splatting`, `analysis`, `report_generation` |
| `status` | ENUM | `queued`, `running`, `complete`, `failed` |
| `celery_task_id` | VARCHAR(255) | Celery task reference |
| `started_at` | TIMESTAMP | Processing start |
| `completed_at` | TIMESTAMP | Processing end |
| `duration_seconds` | INTEGER | Total processing time |
| `error_message` | TEXT | Error details if failed |

---

## 7. Async Processing Pipeline Detail

```
┌──────────────────────────────────────────────────────────┐
│                    CELERY TASK CHAIN                      │
│                                                          │
│  ┌─────────────────┐                                     │
│  │ Task 1:         │  FFmpeg frame extraction             │
│  │ extract_frames  │  Input:  blob video path             │
│  │                 │  Output: blob frame paths             │
│  │ ~30-60 sec      │  Filters: blur + brightness check    │
│  └───────┬─────────┘                                     │
│          ▼                                               │
│  ┌─────────────────┐                                     │
│  │ Task 2:         │  COLMAP SfM → camera poses           │
│  │ run_colmap      │  Input:  frames from blob             │
│  │                 │  Output: cameras.bin, points3D.bin    │
│  │ ~2-5 min        │                                      │
│  └───────┬─────────┘                                     │
│          ▼                                               │
│  ┌─────────────────┐                                     │
│  │ Task 3:         │  3D Gaussian Splatting training       │
│  │ run_splatting   │  Input:  frames + COLMAP output       │
│  │                 │  Output: .ply file → blob             │
│  │ ~5-15 min (GPU) │  Iterations: 7k-15k                  │
│  └───────┬─────────┘                                     │
│          ▼                                               │
│  ┌─────────────────┐                                     │
│  │ Task 4:         │  Send frames to Azure AI Foundry      │
│  │ analyze_damage  │  Input:  sampled frames (base64)      │
│  │                 │  Output: structured damage JSON        │
│  │ ~1-3 min        │  Model:  GPT-4o multimodal            │
│  └───────┬─────────┘                                     │
│          ▼                                               │
│  ┌─────────────────┐                                     │
│  │ Task 5:         │  Aggregate results + generate PDF     │
│  │ generate_report │  Input:  damage items from DB          │
│  │                 │  Output: report JSON + PDF → blob      │
│  │ ~10-30 sec      │                                      │
│  └─────────────────┘                                     │
│                                                          │
│  Total estimated pipeline time: 10-25 minutes            │
└──────────────────────────────────────────────────────────┘
```

**Status Polling:** Frontend/mobile polls `GET /assessments/{id}` every 5 seconds, or optionally subscribe via **WebSocket** at `ws://{host}/ws/assessments/{id}/status` for real-time updates.

---

## 8. Azure Blob Storage Structure

```
insurascan-storage/
├── videos/
│   └── {assessment_id}/
│       ├── exterior.mp4
│       └── interior.mp4
├── frames/
│   └── {assessment_id}/
│       ├── exterior/
│       │   ├── frame_0001.jpg
│       │   ├── frame_0002.jpg
│       │   └── ...
│       └── interior/
│           ├── frame_0001.jpg
│           └── ...
├── splats/
│   └── {assessment_id}/
│       ├── exterior.ply
│       ├── interior.ply
│       ├── exterior_preview.png
│       └── interior_preview.png
└── reports/
    └── {assessment_id}/
        ├── report.json
        └── report.pdf
```

---

## 9. AI Prompt Engineering (Azure AI Foundry)

### System Prompt (GPT-4o)

```
You are an expert automotive damage assessor with 20 years of experience 
in vehicle collision repair estimation. You are analyzing images of a 
damaged vehicle captured by an insurance field agent.

Vehicle Information:
- Year: {vehicle_year}
- Make: {vehicle_make}
- Model: {vehicle_model}
- VIN: {vin}

Analyze the provided images and identify ALL visible damage. For each 
damage instance, provide:

1. Location — specific panel/area of vehicle
2. Vehicle Zone — categorize into: front_left, front_right, front_center, 
   rear_left, rear_right, rear_center, side_left, side_right, roof, 
   interior_front, interior_rear
3. Damage Type — dent, scratch, crack, shatter, deformation, paint damage, 
   missing part, etc.
4. Severity — minor, moderate, or severe
5. Description — detailed description of the damage
6. Affected Parts — list of OEM parts affected
7. Repair Method — recommended repair approach (PDR, repaint, replace, etc.)
8. Cost Estimate — low and high range in USD based on current labor and 
   parts pricing for this vehicle
9. Confidence Score — your confidence in this assessment (0.0 to 1.0)
10. Reference — which image(s) show this damage

Also flag any damage that appears to be pre-existing (weathered, oxidized, 
inconsistent with reported incident).

Respond ONLY with valid JSON matching the provided schema.
```

---

## 10. Hackathon Scope & Prioritization

### 🔴 P0 — Must Have (MVP Demo)

| # | Feature | Notes |
|---|---------|-------|
| 1 | FastAPI backend with assessment CRUD + video upload endpoints | Core API surface |
| 2 | Azure Blob Storage integration | Store videos, frames, splats |
| 3 | FFmpeg frame extraction pipeline | Celery task |
| 4 | Gaussian Splatting on at least one sample | Pre-computed is OK for demo |
| 5 | 3D Gaussian Splat viewer in web frontend | Three.js — **this is the XR demo** |
| 6 | GPT-4o multimodal damage analysis via Azure AI Foundry | Send frames, get JSON |
| 7 | Structured damage report in UI | Display damage items + cost |
| 8 | Basic React dashboard (list + detail views) | Functional, not polished |

### 🟡 P1 — Nice to Have

| # | Feature | Notes |
|---|---------|-------|
| 9 | Real-time Gaussian Splatting pipeline (not pre-computed) | Depends on GPU availability |
| 10 | Mobile app with video capture + upload | React Native or native |
| 11 | AR guided capture overlay on mobile | ARKit/ARCore path guidance |
| 12 | PDF report export | ReportLab or WeasyPrint |
| 13 | WebSocket real-time status updates | Replace polling |
| 14 | Vehicle zone diagram with damage pins | 2D SVG overlay |

### 🟢 P2 — Stretch Goals

| # | Feature | Notes |
|---|---------|-------|
| 15 | VIN OCR auto-detection from video frames | Azure Computer Vision |
| 16 | Damage heatmap overlay on 3D splat | Color-coded severity regions |
| 17 | AR headset viewing (Quest 3 / Vision Pro) | Load .ply in XR headset |
| 18 | Voice-to-text agent notes during capture | Whisper or Azure Speech |
| 19 | Before/after comparison view | If baseline vehicle images exist |
| 20 | Mock claims system integration | REST callback to fake claims API |

---

## 11. Project Directory Structure

```
insurascan/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app entry point
│   │   ├── config.py                # Settings (Azure keys, blob config)
│   │   ├── models/
│   │   │   ├── assessment.py        # SQLAlchemy models
│   │   │   ├── damage_item.py
│   │   │   └── processing_job.py
│   │   ├── schemas/
│   │   │   ├── assessment.py        # Pydantic request/response schemas
│   │   │   ├── damage.py
│   │   │   └── report.py
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── assessments.py   # Assessment endpoints
│   │   │   │   ├── videos.py        # Video upload endpoints
│   │   │   │   ├── splats.py        # 3D splat endpoints
│   │   │   │   ├── reports.py       # Damage report endpoints
│   │   │   │   └── router.py        # API router aggregation
│   │   │   └── deps.py              # Dependencies (DB session, auth)
│   │   ├── services/
│   │   │   ├── blob_storage.py      # Azure Blob operations
│   │   │   ├── frame_extractor.py   # FFmpeg wrapper
│   │   │   ├── gaussian_splat.py    # COLMAP + splatting orchestration
│   │   │   ├── damage_analyzer.py   # Azure AI Foundry client
│   │   │   └── report_generator.py  # PDF + JSON report builder
│   │   ├── tasks/
│   │   │   ├── celery_app.py        # Celery configuration
│   │   │   ├── extract_frames.py    # Frame extraction task
│   │   │   ├── run_splatting.py     # Gaussian splatting task
│   │   │   ├── analyze_damage.py    # AI analysis task
│   │   │   └── generate_report.py   # Report generation task
│   │   └── db/
│   │       ├── database.py          # DB engine + session
│   │       └── migrations/          # Alembic migrations
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml           # API + Redis + Celery + PostgreSQL
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── AssessmentList.tsx
│   │   │   ├── AssessmentDetail.tsx
│   │   │   └── NewAssessment.tsx
│   │   ├── components/
│   │   │   ├── SplatViewer.tsx       # Three.js Gaussian Splat renderer
│   │   │   ├── DamageReport.tsx
│   │   │   ├── VideoPlayer.tsx
│   │   │   ├── StatusTracker.tsx
│   │   │   └── UploadZone.tsx
│   │   ├── api/
│   │   │   └── client.ts            # API client (axios/fetch wrapper)
│   │   └── types/
│   │       └── index.ts             # TypeScript interfaces
│   ├── package.json
│   └── Dockerfile
├── mobile/                           # Phase 2
│   └── ...
├── scripts/
│   ├── setup_azure.sh               # Azure resource provisioning
│   └── seed_sample_data.py          # Load sample assessment for demo
├── sample_data/
│   ├── sample_exterior.mp4          # Pre-recorded sample video
│   ├── sample_interior.mp4
│   └── sample_exterior.ply          # Pre-computed splat for demo fallback
├── .env.example
├── docker-compose.yml               # Full stack compose
└── README.md
```

---

## 12. Development Plan & Task Breakdown

### Day 1 — Foundation

| Task | Owner | Duration |
|------|-------|----------|
| Set up Azure resources (Blob, PostgreSQL, Redis, AI Foundry) | DevOps | 2h |
| FastAPI project scaffolding + Docker Compose | Backend | 2h |
| Database models + Alembic migrations | Backend | 1h |
| Assessment CRUD endpoints | Backend | 2h |
| React project scaffolding + routing | Frontend | 2h |
| Basic assessment list + create form UI | Frontend | 2h |

### Day 2 — Core Pipeline

| Task | Owner | Duration |
|------|-------|----------|
| Video upload endpoint + Azure Blob integration | Backend | 3h |
| Celery setup + frame extraction task (FFmpeg) | Backend | 3h |
| Gaussian Splatting integration (COLMAP + 3DGS) | Backend/ML | 4h |
| Upload UI with progress + status tracking | Frontend | 2h |
| Three.js Gaussian Splat viewer component | Frontend | 4h |

### Day 3 — AI Analysis & Polish

| Task | Owner | Duration |
|------|-------|----------|
| Azure AI Foundry integration + prompt engineering | Backend | 3h |
| Damage analysis task + structured output parsing | Backend | 2h |
| Assessment detail page (video + splat + report) | Frontend | 4h |
| Damage report display component | Frontend | 2h |
| End-to-end testing + demo prep | All | 3h |
| Pre-compute sample splats as demo fallback | ML | 2h |

---

## 13. Key Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| GPU not available on Azure during hackathon | Cannot run Gaussian Splatting live | Medium | Pre-compute sample .ply files. Show pipeline code + pre-computed result. |
| Gaussian Splatting takes too long per video | Demo feels slow | Medium | Reduce iterations (7k), use smaller frame sets, show cached results |
| COLMAP fails on video frames (bad camera poses) | Splatting pipeline breaks | Medium | Use steady, well-lit sample videos. Have backup COLMAP outputs ready. |
| Azure AI Foundry rate limits or latency | AI analysis slow/fails | Low | Cache sample AI responses. Batch efficiently. Have mock responses ready. |
| Large video uploads timeout | Agent can't upload | Low | Implement chunked upload. Set generous timeouts. Test with real file sizes. |
| Blob Storage costs with many large files | Budget concerns | Low | Use LRS tier. Clean up test data. Set lifecycle policies. |

---

## 14. Demo Script Outline

1. **Open web dashboard** — show empty assessment list
2. **Create new assessment** — enter claim number, vehicle info (2022 Toyota Camry)
3. **Upload videos** — upload pre-recorded exterior and interior videos
4. **Show processing pipeline** — status tracker moves through: Uploading → Extracting Frames → Splatting → Analyzing
5. **Interactive 3D viewer** — once splat is ready, rotate and zoom the 3D Gaussian Splat of the vehicle (**XR highlight moment**)
6. **Damage report** — show AI-generated damage items with locations, severity, descriptions, and cost estimates
7. **Total estimate** — show aggregate repair cost range
8. **Explain mobile story** — "This same API powers a mobile app where the agent captures video on-site with AR guidance"
9. **(Stretch)** Show .ply loaded in a VR headset viewer

---

## 15. Success Criteria

- [ ] End-to-end flow works: upload video → frames → splat → AI analysis → report
- [ ] Gaussian Splat .ply is viewable and interactive in the web browser (XR demo)
- [ ] AI produces structured, plausible damage assessment with cost estimates
- [ ] FastAPI serves both the web frontend and is ready for mobile consumption
- [ ] Pipeline status is tracked and visible to the user
- [ ] Demo completes within 5 minutes and tells a compelling story

---

*Last Updated: February 23, 2026*
