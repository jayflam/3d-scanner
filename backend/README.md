# Car Damage Quote — Backend Service

FastAPI backend that accepts a photo of a damaged car, generates a 3D model via
[TripoSR](https://github.com/VAST-AI-Research/TripoSR), and produces an
insurance quote using Azure OpenAI GPT-4o with vision.

## Architecture

```
                          ┌──────────────────────────────┐
  Phone / Browser         │         FastAPI Backend       │
  ─────────────────       │                              │
  POST /api/upload ──────►│  ┌─────────────┐             │
       (car photo)        │  │ Job Manager │             │
                          │  └──────┬──────┘             │
                          │         │  (parallel)        │
                          │    ┌────┴────┐               │
                          │    ▼         ▼               │
                          │ TripoSR   GPT-4o Vision      │
                          │ (3D mesh)  (damage JSON)     │
                          │    │         │               │
                          │    └────┬────┘               │
                          │         ▼                    │
  GET  /api/jobs/{id} ◄───│   Job complete               │
  WS   /ws/{id}       ◄───│   (progress stream)          │
  GET  /api/jobs/{id}/    │                              │
       result          ◄───│   → GLB URL + assessment    │
  GET  /api/jobs/{id}/    │                              │
       model           ◄───│   → .glb binary download    │
                          └──────────────────────────────┘
```

---

## Prerequisites & Dependencies

Everything required to run this app in production, broken down by category.

### 1. GPU (required for 3D model generation)

TripoSR runs a neural network that requires an NVIDIA GPU with CUDA support.

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **GPU** | NVIDIA with 6 GB VRAM | NVIDIA T4 (16 GB) or better |
| **CUDA Toolkit** | 11.8 | 11.8 or 12.x |
| **NVIDIA Driver** | 520+ | 535+ |
| **RAM** | 8 GB | 16 GB |
| **Disk** | 5 GB (model weights + deps) | 10 GB |

**Azure GPU options (cheapest first):**

| Azure Service | GPU | VRAM | Cost | Notes |
|---------------|-----|------|------|-------|
| Container Apps Serverless GPU (T4) | T4 | 16 GB | $0.000090/sec (~$0.32/hr) | Scales to zero, per-second billing. Requires GPU quota request. |
| NC4as_T4_v3 VM | T4 | 16 GB | $0.526/hr ($0.27/hr Spot) | Fastest to get running, no quota needed in most regions. |
| NC6s_v3 VM | V100 | 16 GB | ~$0.90/hr | More powerful, overkill for TripoSR. |

**Without a GPU:** The backend still starts and runs, but TripoSR will fall
back to CPU (very slow, ~2–5 min per image). Use `TRIPOSR_DEVICE=cpu` in `.env`.
For local dev/testing, use `run_demo.py` which stubs the model entirely.

**Free GPU for testing:** Google Colab (free T4), Kaggle Notebooks (free T4/P100,
30 hrs/week), or Lightning.ai (free A10G, 22 hrs/month).

### 2. Azure OpenAI (required for damage assessment)

The damage assessment service calls GPT-4o with vision via the Azure OpenAI API.

**What you need:**

1. An **Azure subscription** (free tier $200 credit works)
2. An **Azure OpenAI resource** created in the Azure Portal
3. A **GPT-4o deployment** within that resource (deploy the `gpt-4o` model)
4. The **endpoint URL** and **API key** from the resource's "Keys and Endpoint" page

**Setup steps:**

```
Azure Portal → Create a resource → "Azure OpenAI" → Create
  → Region: pick one where GPT-4o is available (e.g. East US, Sweden Central)
  → Pricing tier: Standard S0
  → Deploy a model: gpt-4o
```

Then set these in your `.env`:

```
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-key>
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

**Cost:** ~$0.01–0.03 per image (depends on image size and response length).
GPT-4o vision pricing: $2.50/1M input tokens, $10.00/1M output tokens.
A single car photo assessment typically uses ~1,500 input tokens + ~500 output tokens.

**Without Azure OpenAI:** The backend still starts and returns realistic
placeholder damage assessments (3 sample parts, $1,500–$4,500 range). This
lets you develop and demo the 3D pipeline independently.

### 3. Python & system packages

| Requirement | Version |
|-------------|---------|
| **Python** | 3.9+ (3.11 recommended) |
| **pip** | 21+ |
| **OS** | Linux (production), macOS/Linux (development) |
| **Docker** (optional) | 20+ with NVIDIA Container Toolkit for GPU passthrough |

### 4. TripoSR model (auto-downloaded)

The TripoSR model weights are hosted on Hugging Face and downloaded
automatically on first run. No manual download required.

| Item | Details |
|------|---------|
| **Model** | `stabilityai/TripoSR` |
| **Size** | ~1.5 GB download |
| **License** | MIT |
| **Source** | [github.com/VAST-AI-Research/TripoSR](https://github.com/VAST-AI-Research/TripoSR) |

The `tsr` Python package from the TripoSR repo must be on your `PYTHONPATH`.
The Dockerfile handles this automatically. For local dev, clone the repo
and export the path (see Quick Start below).

### 5. Python dependencies

Installed via `pip install -r requirements.txt`:

| Package | Purpose | License |
|---------|---------|---------|
| `fastapi` | Web framework | MIT |
| `uvicorn` | ASGI server | BSD-3 |
| `pydantic-settings` | Configuration from `.env` | MIT |
| `python-multipart` | File upload parsing | Apache 2.0 |
| `openai` | Azure OpenAI SDK | Apache 2.0 |
| `torch` | PyTorch (TripoSR runtime) | BSD-3 |
| `transformers` | Hugging Face model loading | Apache 2.0 |
| `trimesh` | 3D mesh handling and GLB export | MIT |
| `rembg` | Background removal from car photos | MIT |
| `Pillow` | Image processing | HPND |
| `xatlas` | UV atlas generation for texture baking | MIT |
| `moderngl` | OpenGL for texture rasterization | MIT |
| `omegaconf` | Config loading for TripoSR | BSD-3 |
| `einops` | Tensor operations | MIT |
| `huggingface-hub` | Model weight downloads | Apache 2.0 |
| `imageio` | Image/video I/O | BSD-2 |
| `numpy` | Numerical computing | BSD-3 |
| `scipy` | Sparse matrix ops (trimesh GLB export) | BSD-3 |

Additionally, `torchmcubes` must be installed from git:

```bash
pip install git+https://github.com/tatsy/torchmcubes.git
```

### 6. Environment variables

All configuration is done via a `.env` file. Copy `.env.example` to get started:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_OPENAI_ENDPOINT` | For real assessment | `""` | Your Azure OpenAI resource endpoint |
| `AZURE_OPENAI_API_KEY` | For real assessment | `""` | API key for the resource |
| `AZURE_OPENAI_DEPLOYMENT` | For real assessment | `gpt-4o` | Name of your GPT-4o deployment |
| `AZURE_OPENAI_API_VERSION` | No | `2024-12-01-preview` | API version |
| `TRIPOSR_MODEL_ID` | No | `stabilityai/TripoSR` | Hugging Face model ID |
| `TRIPOSR_DEVICE` | No | `cuda:0` | `cuda:0` for GPU, `cpu` for CPU |
| `TRIPOSR_CHUNK_SIZE` | No | `8192` | Inference chunk size (lower = less VRAM) |
| `TRIPOSR_MC_RESOLUTION` | No | `256` | Marching cubes resolution (mesh detail) |
| `TRIPOSR_TEXTURE_RESOLUTION` | No | `2048` | Texture atlas resolution |
| `TRIPOSR_FOREGROUND_RATIO` | No | `0.85` | Foreground crop ratio |
| `CORS_ORIGINS` | No | `["*"]` | Allowed CORS origins (JSON array) |

### 7. Estimated costs (hackathon budget)

For a hackathon demo with ~50 image uploads:

| Service | Cost |
|---------|------|
| Azure Container Apps GPU T4 (50 runs × ~10s each) | ~$0.05 |
| Azure OpenAI GPT-4o Vision (50 images) | ~$1.00 |
| Azure Blob Storage (optional) | ~$0.01 |
| **Total** | **~$1.06** |

With the Azure free account ($200 credits) or Azure for Students ($100 credits),
the hackathon costs are fully covered.

---

## Quick Start (local testing, no GPU)

The backend runs in stub mode when no GPU or Azure credentials are available.
It produces a real GLB file (simple 3D shape) and placeholder damage assessment.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install scipy  # needed by trimesh for GLB export

# Run the automated demo
python run_demo.py

# Or start the server and test manually via the browser test page
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Then open test_local.html in your browser
```

### Browser test page

Open `test_local.html` directly in your browser (just double-click it or
`open test_local.html`). It lets you:

1. Point at your running backend URL (default `http://localhost:8000`)
2. Upload any car image
3. Watch real-time WebSocket progress
4. View the 3D model in an embedded viewer
5. See the full damage quote breakdown
6. Download the `.glb` file

### Automated demo script

```bash
python run_demo.py
```

Produces `demo_output/model.glb` and `demo_output/result.json`.

---

## Quick Start (with GPU)

```bash
# 1. Clone TripoSR so its `tsr` package is importable
git clone https://github.com/VAST-AI-Research/TripoSR.git ../TripoSR

# 2. Install deps
pip install -r requirements.txt
pip install git+https://github.com/tatsy/torchmcubes.git

# 3. Put TripoSR on the Python path
export PYTHONPATH="$(realpath ../TripoSR):$PYTHONPATH"

# 4. Configure environment
cp .env.example .env
# Edit .env with your Azure OpenAI credentials

# 5. Run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The first request downloads TripoSR model weights from Hugging Face (~1.5 GB).

---

## Docker

```bash
docker build -t car-quote-backend .
docker run --gpus all -p 8000:8000 --env-file .env car-quote-backend
```

---

## API Reference

Base URL: `http://localhost:8000` (local) or your deployed URL.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload a car damage photo. Returns `job_id`. |
| `GET`  | `/api/jobs/{id}` | Poll job status and progress percentage. |
| `GET`  | `/api/jobs/{id}/result` | Get the GLB model URL and damage assessment JSON. |
| `GET`  | `/api/jobs/{id}/model` | Download the generated `.glb` file. |
| `WS`   | `/ws/{id}` | Real-time progress stream via WebSocket. |
| `GET`  | `/api/health` | Health check. |
| `GET`  | `/api/openapi.json` | OpenAPI 3.1 schema (for frontend codegen). |

### `POST /api/upload`

Upload a car damage photo to start processing.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | binary | yes | JPEG, PNG, or WebP image. Max 20 MB. |

**Response** `200`:
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "pending",
  "message": "Image uploaded — processing started"
}
```

**Errors:**

| Status | Condition |
|--------|-----------|
| `400` | File is not an image or has unsupported extension |

---

### `GET /api/jobs/{id}`

Poll the current status of a processing job.

**Response** `200`:
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "generating_3d",
  "created_at": "2026-02-20T23:22:33.432Z",
  "progress_pct": 40,
  "message": "Generating 3D model…"
}
```

**`status` values** (in order):

| Status | Progress | Meaning |
|--------|----------|---------|
| `pending` | 0% | Queued, not started |
| `preprocessing` | 10% | Reading and preparing the image |
| `generating_3d` | 20% | TripoSR is building the 3D mesh |
| `assessing_damage` | 40% | GPT-4o is analyzing the damage |
| `complete` | 100% | Done — results ready |
| `failed` | varies | Something went wrong — check `message` |

**Errors:**

| Status | Condition |
|--------|-----------|
| `404` | Job ID not found |

---

### `GET /api/jobs/{id}/result`

Retrieve the completed result. Only succeeds when `status === "complete"`.

**Response** `200`:
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "complete",
  "model_url": "/api/jobs/a1b2c3d4e5f6/model",
  "assessment": {
    "vehicle_description": "White 2020 Toyota Camry",
    "overall_severity": "moderate",
    "total_cost_low": 2500,
    "total_cost_high": 6000,
    "parts": [
      {
        "part_name": "Front Bumper",
        "severity": "severe",
        "repair_type": "replace",
        "cost_low": 1200,
        "cost_high": 2500,
        "description": "Large crack across bumper with paint loss"
      },
      {
        "part_name": "Hood",
        "severity": "minor",
        "repair_type": "repaint",
        "cost_low": 400,
        "cost_high": 1200,
        "description": "Surface scratches on driver side"
      },
      {
        "part_name": "Left Headlight",
        "severity": "moderate",
        "repair_type": "replace",
        "cost_low": 300,
        "cost_high": 1300,
        "description": "Lens cracked, housing intact"
      }
    ],
    "summary": "Moderate front-end collision damage requiring bumper replacement and headlight replacement."
  }
}
```

**Errors:**

| Status | Condition |
|--------|-----------|
| `404` | Job ID not found |
| `409` | Job not complete yet |
| `500` | Job failed |

---

### `GET /api/jobs/{id}/model`

Download the generated `.glb` 3D model file.

**Response:** Binary GLB data with `Content-Type: model/gltf-binary`.

**Errors:**

| Status | Condition |
|--------|-----------|
| `404` | Job ID not found |
| `409` | Model not ready yet |

---

### `WS /ws/{id}`

WebSocket endpoint that streams progress updates in real time.

**Connection:** `ws://localhost:8000/ws/{job_id}`

**Messages** (server → client): JSON `ProgressUpdate` objects:
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "generating_3d",
  "progress_pct": 20,
  "message": "Generating 3D model…"
}
```

**Behavior:**
- Sends the current state immediately on connection (so no updates are missed)
- Sends a message on every status transition
- Automatically closes after `complete` or `failed`
- If the job is already complete when you connect, sends the final state and closes

**Fallback:** If WebSocket is unavailable, poll `GET /api/jobs/{id}` every 500ms.

---

## Frontend Integration

### Files provided for the frontend team

```
frontend_integration/
├── api-types.ts           ← TypeScript types matching all API responses
├── api-client.ts          ← Ready-to-use API client class (zero dependencies)
└── example-react-usage.tsx ← Example React component showing full integration
```

### How to use

1. Copy `api-types.ts` and `api-client.ts` into your frontend project
2. Import and instantiate the client:

```typescript
import { CarQuoteAPI } from "./api-client";

const api = new CarQuoteAPI("http://localhost:8000");
```

3. Upload and track a job:

```typescript
const result = await api.uploadAndTrack(file, (update) => {
  console.log(`${update.progress_pct}% — ${update.message}`);
});

// result.assessment  → DamageAssessment object
// api.getModelUrl(result.job_id)  → URL to load GLB in Three.js
```

### Auto-generate types from OpenAPI

The backend exposes its schema at `GET /api/openapi.json`. You can use this
to auto-generate frontend types:

```bash
npx openapi-typescript http://localhost:8000/api/openapi.json -o src/api-types.generated.ts
```

---

## What the Frontend Team Needs to Build

### Required pages/views

1. **Upload page** — file picker or camera capture (`<input type="file" accept="image/*" capture="environment">`) that calls `api.upload(file)`.

2. **Processing screen** — connect to `WS /ws/{job_id}` (or use `api.onProgress()`) to show a progress bar. Status transitions: `pending → preprocessing → generating_3d → assessing_damage → complete`.

3. **Results page** with two panels:
   - **3D model viewer** — load the `.glb` from `api.getModelUrl(jobId)` using Three.js (`@react-three/fiber` + `useGLTF`). Enable `OrbitControls` so the user can rotate/zoom the car.
   - **Damage quote** — render `assessment.parts[]` as cards showing part name, severity badge, repair type, and cost range. Show `assessment.total_cost_low`/`total_cost_high` as the headline number.

4. **Interactive click-on-part** (stretch goal) — when the user clicks a region of the 3D model, highlight the corresponding `DamagePart` in the quote breakdown. Approach: map `part_name` values to approximate 3D bounding regions on the mesh and use Three.js raycasting.

### Required npm packages

```
@react-three/fiber    — React renderer for Three.js
@react-three/drei     — Helpers (OrbitControls, useGLTF, etc.)
three                 — 3D engine
```

### CORS

The backend allows all origins by default (`CORS_ORIGINS=["*"]`). For
production, set `CORS_ORIGINS` in `.env` to your frontend domain.

### Environment variable for frontend

Set the backend URL in your frontend environment:

```
NEXT_PUBLIC_API_URL=http://localhost:8000    # local
NEXT_PUBLIC_API_URL=https://your-app.azurecontainerapps.io  # production
```

---

## Data Shapes Reference (for frontend team)

### `DamagePart`

| Field | Type | Example |
|-------|------|---------|
| `part_name` | string | `"Front Bumper"` |
| `severity` | `"minor"` \| `"moderate"` \| `"severe"` | `"severe"` |
| `repair_type` | `"repair"` \| `"replace"` \| `"repaint"` | `"replace"` |
| `cost_low` | number (USD) | `1200` |
| `cost_high` | number (USD) | `2500` |
| `description` | string | `"Large crack across bumper"` |

### `DamageAssessment`

| Field | Type | Example |
|-------|------|---------|
| `vehicle_description` | string | `"White 2020 Toyota Camry"` |
| `overall_severity` | `"minor"` \| `"moderate"` \| `"severe"` | `"moderate"` |
| `total_cost_low` | number | `2500` |
| `total_cost_high` | number | `6000` |
| `parts` | `DamagePart[]` | see above |
| `summary` | string | `"Moderate front-end collision damage…"` |

### `ProgressUpdate` (WebSocket)

| Field | Type | Example |
|-------|------|---------|
| `job_id` | string | `"a1b2c3d4e5f6"` |
| `status` | JobStatus | `"generating_3d"` |
| `progress_pct` | number (0–100) | `40` |
| `message` | string | `"Generating 3D model…"` |

---

## Azure Deployment

Deploy to **Azure Container Apps** with a serverless GPU (T4) for the cheapest
per-second billing.

```bash
# Build & push to Azure Container Registry
az acr build --registry <acr-name> --image car-quote-backend:latest .

# Deploy to Container Apps with GPU
az containerapp create \
  --name car-quote-backend \
  --resource-group <rg> \
  --environment <env> \
  --image <acr-name>.azurecr.io/car-quote-backend:latest \
  --workload-profile-name gpu \
  --cpu 4 --memory 16Gi \
  --min-replicas 0 --max-replicas 1 \
  --target-port 8000 \
  --ingress external
```

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                 ← FastAPI app entry point
│   ├── config.py               ← Settings (reads from .env)
│   ├── models/
│   │   └── schemas.py          ← Pydantic request/response models
│   ├── api/
│   │   ├── routes.py           ← REST endpoints
│   │   └── websocket.py        ← WebSocket progress endpoint
│   └── services/
│       ├── triposr.py          ← TripoSR 3D generation service
│       ├── damage.py           ← Azure OpenAI damage assessment
│       └── job_manager.py      ← Async job queue + progress broadcast
├── frontend_integration/
│   ├── api-types.ts            ← TypeScript types for frontend
│   ├── api-client.ts           ← API client class for frontend
│   └── example-react-usage.tsx ← Example React integration
├── tests/
│   └── test_api.py             ← Integration tests (9 tests)
├── test_local.html             ← Browser-based test page
├── run_demo.py                 ← Automated demo script
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```
