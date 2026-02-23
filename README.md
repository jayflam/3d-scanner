# Spaceframe

> Vehicle damage assessment app — TypeScript · React · Vite · React Three Fiber · Drei

---

## Setup

```bash
npm install
npm run dev
```

Open `http://localhost:5173` in your browser (or on your phone via the local network IP printed by Vite).

## Project Structure

```
src/
├── components/
│   ├── AppHeader.tsx       # Top navigation bar
│   ├── Navigation.tsx      # Bottom tab navigation
│   ├── HomeScreen.tsx      # Home / dashboard
│   ├── ScanScreen.tsx      # Camera capture + file upload
│   ├── ModelViewer.tsx     # react-three-fiber GLB viewer
│   ├── ModelScreen.tsx     # 3D viewer + damage assessment panel
│   └── ReportsScreen.tsx   # Reports listing (placeholder)
├── types/
│   └── index.ts            # Shared TypeScript types
├── App.tsx                 # Root component with screen routing
├── main.tsx                # Entry point
└── index.css               # Global CSS variables & resets
```

## Features

| # | Feature | Notes |
|---|---------|-------|
| 1 | **Camera Capture** | Photo and video via `MediaDevices.getUserMedia`. Multi-angle guided mode. iOS + Android compatible via browser. |
| 2 | **Upload & API** | `POST /api/assess` with multipart form data. Replace `API_ENDPOINT` in `ScanScreen.tsx` with your backend URL. |
| 3 | **GLB Viewer** | Full `OrbitControls` (rotate, zoom, pan). Auto-fits camera to model bounding box. Environment lighting via Drei. |
| 4 | **Damage Assessment** | Panel renders alongside the 3D viewer. Swap `MOCK_ASSESSMENT` in `ModelScreen.tsx` with real API response data. |
| 5 | **Mobile-first UI** | Bottom tab navigation, safe-area insets, large touch targets, white/ink high-contrast design system. |

## Backend Integration

Two integration points are stubbed:

### 1. Photo/Video Upload — `ScanScreen.tsx`
```ts
const API_ENDPOINT = '/api/assess'  // ← change to your backend
```
The `submitForAssessment` function POSTs a `FormData` object with all captured files.
Expected response shape:
```json
{ "assessmentId": "abc123", "status": "processing" }
```

### 2. Assessment Results — `ModelScreen.tsx`
Replace `MOCK_ASSESSMENT` with a fetch to your results endpoint:
```ts
const result = await fetch(`/api/assess/${id}`).then(r => r.json())
```
The `AssessmentResult` type in `src/types/index.ts` defines the expected shape.

## Tech Stack

- **Vite** — dev server + build tool
- **React 18** — UI framework
- **TypeScript** — type safety
- **react-three-fiber** — React renderer for Three.js
- **@react-three/drei** — Three.js helpers (OrbitControls, GLTFLoader, Environment, etc.)
- **CSS Modules** — scoped styles, no CSS-in-JS dependencies
