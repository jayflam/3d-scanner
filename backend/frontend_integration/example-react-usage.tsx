/**
 * EXAMPLE ONLY — not a runnable component.
 *
 * Shows the frontend team exactly how to integrate with the backend:
 *   1. Upload an image
 *   2. Track progress via WebSocket
 *   3. Load the GLB 3D model in Three.js
 *   4. Display the damage assessment with per-part breakdown
 *
 * Required npm packages:
 *   npm install @react-three/fiber @react-three/drei three
 *   npm install @types/three  (dev)
 */

import React, { useState, useCallback, Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, useGLTF } from "@react-three/drei";
import { CarQuoteAPI } from "./api-client";
import type { JobResult, ProgressUpdate, DamagePart } from "./api-types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api = new CarQuoteAPI(API_BASE);

// ── 3D Model Viewer ──────────────────────────────────────────────────────

function CarModel({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} />;
}

// ── Damage Quote Card ────────────────────────────────────────────────────

function QuoteCard({ part }: { part: DamagePart }) {
  return (
    <div className="border rounded-lg p-4 mb-2">
      <div className="flex justify-between">
        <h3 className="font-semibold">{part.part_name}</h3>
        <span className={`badge badge-${part.severity}`}>{part.severity}</span>
      </div>
      <p className="text-sm text-gray-600">{part.description}</p>
      <div className="flex justify-between mt-2">
        <span>
          ${part.cost_low.toLocaleString()} – ${part.cost_high.toLocaleString()}
        </span>
        <span className="text-xs uppercase text-gray-500">
          {part.repair_type}
        </span>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────

export default function DamageQuotePage() {
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<JobResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setIsProcessing(true);
      setError(null);
      setResult(null);

      try {
        const jobResult = await api.uploadAndTrack(
          file,
          (update: ProgressUpdate) => {
            setProgress(update.progress_pct);
            setMessage(update.message);
          }
        );
        setResult(jobResult);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setIsProcessing(false);
      }
    },
    []
  );

  const assessment = result?.assessment;

  return (
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Car Damage Quote</h1>

      {/* ── Upload ──────────────────────────────────────────────── */}
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={handleUpload}
        disabled={isProcessing}
      />

      {/* ── Progress bar ───────────────────────────────────────── */}
      {isProcessing && (
        <div className="mt-4">
          <div className="w-full bg-gray-200 rounded h-3">
            <div
              className="bg-blue-600 h-3 rounded transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-sm mt-1 text-gray-600">{message}</p>
        </div>
      )}

      {error && <p className="text-red-600 mt-4">{error}</p>}

      {/* ── Results: 3D model + quote ──────────────────────────── */}
      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          {/* 3D viewer */}
          <div className="h-[500px] bg-gray-100 rounded-lg overflow-hidden">
            <Canvas camera={{ position: [3, 2, 3], fov: 45 }}>
              <ambientLight intensity={0.5} />
              <directionalLight position={[5, 5, 5]} />
              <Suspense fallback={null}>
                <CarModel url={api.getModelUrl(result.job_id)} />
              </Suspense>
              <OrbitControls />
            </Canvas>
          </div>

          {/* Quote breakdown */}
          {assessment && (
            <div>
              <h2 className="text-xl font-semibold mb-2">
                {assessment.vehicle_description}
              </h2>
              <p className="text-gray-600 mb-4">{assessment.summary}</p>

              <div className="bg-blue-50 p-4 rounded-lg mb-4">
                <p className="text-sm text-blue-800">Total Estimated Cost</p>
                <p className="text-2xl font-bold text-blue-900">
                  ${assessment.total_cost_low.toLocaleString()} – $
                  {assessment.total_cost_high.toLocaleString()}
                </p>
              </div>

              {assessment.parts.map((part) => (
                <QuoteCard key={part.part_name} part={part} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
