# Car Damage Quote

Upload a photo of your damaged car and receive an instant 3D model of the
vehicle alongside an AI-generated insurance quote with per-part cost breakdowns.

## How it works

1. User snaps a photo of their damaged car from their phone
2. Backend generates a 3D model of the car via [TripoSR](https://github.com/VAST-AI-Research/TripoSR)
3. Azure OpenAI GPT-4o with vision assesses the damage and produces a quote
4. Frontend displays an interactive 3D viewer with the quote breakdown
5. Clicking on parts of the 3D model shows the repair cost for that area

## Project structure

```
├── backend/               ← FastAPI + TripoSR + Azure OpenAI (Python)
│   ├── app/               ← Application code
│   ├── frontend_integration/  ← TypeScript types & API client for frontend
│   ├── tests/             ← Integration tests
│   ├── Dockerfile         ← GPU-ready container
│   └── README.md          ← Full API docs, setup, and frontend contract
│
├── frontend/              ← (coming soon) React + Three.js
└── README.md              ← You are here
```

## Getting started

### Backend

See [`backend/README.md`](backend/README.md) for full setup instructions,
API reference, and deployment guide.

Quick test (no GPU or Azure credentials needed):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install scipy
python run_demo.py
```

### Frontend

See [`backend/frontend_integration/`](backend/frontend_integration/) for
TypeScript types, an API client, and a React usage example. Full frontend
setup instructions are in [`backend/README.md`](backend/README.md) under
"What the Frontend Team Needs to Build".

## Tech stack

| Component | Technology |
|-----------|-----------|
| Backend API | FastAPI (Python) |
| 3D generation | TripoSR (MIT license) |
| Damage assessment | Azure OpenAI GPT-4o with vision |
| 3D model format | GLB (glTF binary) |
| Frontend (planned) | React + Three.js + Tailwind |
| Hosting | Azure Container Apps (serverless GPU) |

## License

MIT
