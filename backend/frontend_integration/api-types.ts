/**
 * Car Damage Quote API — TypeScript types
 *
 * These types mirror the backend Pydantic schemas exactly.
 * Drop this file into your frontend project and import from it.
 */

// ── Enums ────────────────────────────────────────────────────────────────

export type JobStatus =
  | "pending"
  | "preprocessing"
  | "generating_3d"
  | "assessing_damage"
  | "complete"
  | "failed";

export type Severity = "minor" | "moderate" | "severe";
export type RepairType = "repair" | "replace" | "repaint";

// ── Response types ───────────────────────────────────────────────────────

export interface UploadResponse {
  job_id: string;
  status: JobStatus;
  message: string;
}

export interface JobResponse {
  job_id: string;
  status: JobStatus;
  created_at: string; // ISO-8601 datetime
  progress_pct: number; // 0–100
  message: string;
}

export interface DamagePart {
  part_name: string; // e.g. "Front Bumper", "Hood", "Left Fender"
  severity: Severity;
  repair_type: RepairType;
  cost_low: number; // USD
  cost_high: number; // USD
  description: string;
}

export interface DamageAssessment {
  vehicle_description: string; // e.g. "White 2020 Toyota Camry"
  overall_severity: Severity;
  total_cost_low: number;
  total_cost_high: number;
  parts: DamagePart[];
  summary: string;
}

export interface JobResult {
  job_id: string;
  status: JobStatus;
  model_url: string; // relative URL: "/api/jobs/{id}/model"
  assessment: DamageAssessment | null;
}

/** Sent over the WebSocket connection at /ws/{job_id} */
export interface ProgressUpdate {
  job_id: string;
  status: JobStatus;
  progress_pct: number;
  message: string;
}
