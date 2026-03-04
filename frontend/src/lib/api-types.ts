/**
 * InsuraScan API v1 — TypeScript types
 *
 * These types mirror the backend Pydantic v2 schemas for the /api/v1/ endpoints.
 */

// -- Enums ------------------------------------------------------------------

export type AssessmentStatus =
  | "created"
  | "uploading"
  | "extracting_frames"
  | "splatting"
  | "analyzing"
  | "complete"
  | "failed";

export type Severity = "minor" | "moderate" | "severe";
export type RepairType = "repair" | "replace" | "repaint";

export type VehicleZone =
  | "front_left"
  | "front_right"
  | "front_center"
  | "rear_left"
  | "rear_right"
  | "rear_center"
  | "side_left"
  | "side_right"
  | "roof";

export type PipelineStageStatus = "pending" | "in_progress" | "complete" | "failed";

// -- Request types -----------------------------------------------------------

export interface CreateAssessmentRequest {
  claim_number: string;
  agent_id: string;
  vehicle_year: number;
  vehicle_make: string;
  vehicle_model: string;
  vin?: string;
  gps_latitude?: number | null;
  gps_longitude?: number | null;
}

// -- Response types ----------------------------------------------------------

export interface PipelineStatus {
  exterior_video: PipelineStageStatus;
  interior_video: PipelineStageStatus;
  frame_extraction: PipelineStageStatus;
  gaussian_splatting: PipelineStageStatus;
  damage_analysis: PipelineStageStatus;
  report_generation: PipelineStageStatus;
}

export interface AssessmentResponse {
  id: string;
  status: AssessmentStatus;
  claim_number: string;
  agent_id: string;
  vehicle: {
    year: number;
    make: string;
    model: string;
  };
  vin: string;
  pipeline: PipelineStatus;
  frame_count: {
    exterior: number;
    interior: number;
  };
  splat_ready: {
    exterior: boolean;
    interior: boolean;
  };
  total_estimate_low: number | null;
  total_estimate_high: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface AssessmentCreateResponse {
  id: string;
  status: AssessmentStatus;
  claim_number: string;
  created_at: string;
  upload_urls: Record<string, string>;
}

export interface AssessmentListResponse {
  items: AssessmentResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface DamageItem {
  id: string;
  assessment_id: string;
  damage_id: string;
  location: string;
  vehicle_zone: VehicleZone;
  damage_type: string;
  severity: Severity;
  description: string;
  affected_parts: string[];
  repair_method: RepairType;
  estimated_cost_low: number;
  estimated_cost_high: number;
  confidence_score: number;
  reference_frame_paths: string[];
  created_at: string;
}

export interface ReportSummary {
  total_damage_count: number;
  total_estimate_low: number;
  total_estimate_high: number;
  recommendation: string;
  narrative: string;
}

export interface DamageReport {
  assessment_id: string;
  vehicle: {
    year: number;
    make: string;
    model: string;
    vin: string;
  };
  damages: DamageItem[];
  summary: ReportSummary;
  generated_at: string;
}

export interface DamageListResponse {
  items: DamageItem[];
  total: number;
}

export interface FrameInfo {
  path: string;
  url: string;
  video_type: "exterior" | "interior";
  frame_number: number;
}

/** Sent over the WebSocket connection at /ws/{assessmentId} */
export interface ProgressUpdate {
  assessment_id: string;
  status: AssessmentStatus;
  stage: string;
  progress_pct: number;
  message: string;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "error";
  database: boolean;
  redis: boolean;
  gpu_available: boolean;
}
