/**
 * InsuraScan API v1 — Frontend client
 *
 * Adapted from backend/frontend_integration/api-client.ts for the v1 API.
 */

import type {
  CreateAssessmentRequest,
  AssessmentCreateResponse,
  AssessmentResponse,
  AssessmentListResponse,
  DamageReport,
  DamageItem,
  DamageListResponse,
  FrameInfo,
  HealthResponse,
} from "./api-types";

const API_BASE = import.meta.env.VITE_API_URL || "";

function url(path: string): string {
  return `${API_BASE}${path}`;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// -- Assessments -------------------------------------------------------------

export async function createAssessment(
  data: CreateAssessmentRequest
): Promise<AssessmentCreateResponse> {
  const res = await fetch(url("/api/v1/assessments"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<AssessmentCreateResponse>(res);
}

export async function listAssessments(params?: {
  page?: number;
  page_size?: number;
  status?: string;
  search?: string;
}): Promise<AssessmentListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  if (params?.status) searchParams.set("status", params.status);
  if (params?.search) searchParams.set("claim_number", params.search);

  const qs = searchParams.toString();
  const res = await fetch(url(`/api/v1/assessments${qs ? `?${qs}` : ""}`));
  return handleResponse<AssessmentListResponse>(res);
}

export async function getAssessment(id: string): Promise<AssessmentResponse> {
  const res = await fetch(url(`/api/v1/assessments/${id}`));
  return handleResponse<AssessmentResponse>(res);
}

export async function deleteAssessment(id: string): Promise<void> {
  const res = await fetch(url(`/api/v1/assessments/${id}`), {
    method: "DELETE",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Delete failed: ${res.status}`);
  }
}

// -- Video uploads -----------------------------------------------------------

export async function uploadVideo(
  assessmentId: string,
  videoType: "exterior" | "interior",
  file: File,
  onProgress?: (pct: number) => void
): Promise<{ assessment_id: string; video_type: string; blob_path: string; status: string; message: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url(`/api/v1/assessments/${assessmentId}/videos/${videoType}`));

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject(new Error(body.detail || `Upload failed: ${xhr.status}`));
        } catch {
          reject(new Error(`Upload failed: ${xhr.status}`));
        }
      }
    };

    xhr.onerror = () => reject(new Error("Upload network error"));

    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

// -- Splats ------------------------------------------------------------------

export function getSplatUrl(assessmentId: string, type: "exterior" | "interior"): string {
  return url(`/api/v1/assessments/${assessmentId}/splat/${type}`);
}

// -- Damage report -----------------------------------------------------------

export async function getDamageReport(assessmentId: string): Promise<DamageReport> {
  const res = await fetch(url(`/api/v1/assessments/${assessmentId}/report`));
  return handleResponse<DamageReport>(res);
}

export async function getDamageItems(assessmentId: string): Promise<DamageItem[]> {
  const res = await fetch(url(`/api/v1/assessments/${assessmentId}/damages`));
  const data = await handleResponse<DamageListResponse>(res);
  return data.items;
}

export function getReportPdfUrl(assessmentId: string): string {
  return url(`/api/v1/assessments/${assessmentId}/report/pdf`);
}

// -- Frames ------------------------------------------------------------------

export async function getFrames(assessmentId: string): Promise<FrameInfo[]> {
  const res = await fetch(url(`/api/v1/assessments/${assessmentId}/frames`));
  return handleResponse<FrameInfo[]>(res);
}

// -- Health ------------------------------------------------------------------

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(url("/api/v1/health"));
  return handleResponse<HealthResponse>(res);
}

// -- WebSocket URL -----------------------------------------------------------

export function getWebSocketUrl(assessmentId: string): string {
  const base = API_BASE || window.location.origin;
  const wsBase = base.replace(/^http/, "ws");
  return `${wsBase}/ws/v1/assessments/${assessmentId}/status`;
}
