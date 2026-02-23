# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**InsuraScan** — AI-powered car damage assessment backend. Accepts a car photo, generates a 3D GLB model via TripoSR, and produces an AI damage assessment via Azure OpenAI GPT-4o vision. Results delivered via REST polling or WebSocket real-time updates.

## Commands

```bash
# Install dependencies
cd backend && pip install -r requirements.txt

# Run server
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run tests (no GPU or Azure credentials needed — uses stubs)
cd backend && pytest tests/

# Run single test
cd backend && pytest tests/test_api.py::TestHealthEndpoint

# Run with coverage
cd backend && pytest --cov=app tests/

# Automated demo (outputs to demo_output/)
cd backend && python run_demo.py

# Docker build (GPU-enabled, NVIDIA CUDA base)
cd backend && docker build -t car-quote-backend .
```

## Architecture

```
POST /api/upload (car photo)
       ↓
  JobManager creates async job
       ↓
  asyncio.gather() runs in parallel:
    ├─ TripoSRService: image → background removal → 3D mesh → GLB file
    └─ DamageAssessmentService: image → GPT-4o vision → structured JSON quote
       ↓
  Results stored in-memory, delivered via:
    - REST polling: GET /api/jobs/{id}, GET /api/jobs/{id}/result
    - WebSocket: WS /ws/{id} (real-time progress 0-100%)
    - Model download: GET /api/jobs/{id}/model
```

### Key Services (backend/app/services/)

- **`job_manager.py`** — In-memory async job queue, orchestrates pipeline, broadcasts progress to WebSocket subscribers
- **`triposr.py`** — Wraps TripoSR model (Hugging Face). Loads on GPU (falls back to CPU). Pipeline: rembg background removal → foreground crop → inference → marching cubes mesh extraction → texture baking → GLB export
- **`damage.py`** — Wraps Azure OpenAI async client. Sends image to GPT-4o with expert auto-insurance prompt. Falls back to realistic placeholder JSON when no Azure credentials are configured

### API Layer (backend/app/api/)

- **`routes.py`** — REST endpoints (upload, job status, result, model download, health)
- **`websocket.py`** — WebSocket endpoint with auto-close after job completion

### Data Models (backend/app/models/schemas.py)

Job lifecycle: `pending → preprocessing → generating_3d → assessing_damage → complete | failed`

Key types: `DamagePart` (per-part severity/cost), `DamageAssessment` (vehicle-level summary), `JobResponse` (polling), `ProgressUpdate` (WebSocket)

## Configuration

All config via environment variables (see `backend/.env.example`). Managed through Pydantic Settings in `backend/app/config.py`.

Azure OpenAI credentials are optional — services degrade gracefully with placeholder responses when missing. TripoSR falls back from CUDA to CPU automatically.

## Frontend Integration

TypeScript types and a zero-dependency API client are provided in `backend/frontend_integration/`. These mirror the backend Pydantic schemas and are ready to copy into any frontend project. 3D viewer expects GLB format (Three.js / @react-three/fiber compatible).

## Testing Notes

Tests in `backend/tests/test_api.py` mock all heavy ML imports (`tsr`, `rembg`, `torch`) so they run without GPU or model weights. When adding tests, follow this pattern — stub services, test endpoint behavior.
