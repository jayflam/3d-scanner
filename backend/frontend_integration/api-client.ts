/**
 * Car Damage Quote API — Frontend client
 *
 * Lightweight, zero-dependency client for the backend API.
 * Works in any framework (React, Vue, Svelte, vanilla JS).
 *
 * Usage:
 *   import { CarQuoteAPI } from "./api-client";
 *   const api = new CarQuoteAPI("http://localhost:8000");
 */

import type {
  UploadResponse,
  JobResponse,
  JobResult,
  ProgressUpdate,
} from "./api-types";

export class CarQuoteAPI {
  private baseUrl: string;

  constructor(baseUrl: string) {
    // Strip trailing slash
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  // ── REST endpoints ─────────────────────────────────────────────────────

  /** Upload a car damage photo. Returns a job_id to track progress. */
  async upload(file: File): Promise<UploadResponse> {
    const form = new FormData();
    form.append("file", file);

    const res = await fetch(`${this.baseUrl}/api/upload`, {
      method: "POST",
      body: form,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Upload failed: ${res.status}`);
    }
    return res.json();
  }

  /** Poll current job status. */
  async getJobStatus(jobId: string): Promise<JobResponse> {
    const res = await fetch(`${this.baseUrl}/api/jobs/${jobId}`);
    if (!res.ok) {
      throw new Error(`Job status failed: ${res.status}`);
    }
    return res.json();
  }

  /** Get the completed result (damage assessment + model URL). */
  async getJobResult(jobId: string): Promise<JobResult> {
    const res = await fetch(`${this.baseUrl}/api/jobs/${jobId}/result`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Result fetch failed: ${res.status}`);
    }
    return res.json();
  }

  /** Get the full URL to download the GLB 3D model file. */
  getModelUrl(jobId: string): string {
    return `${this.baseUrl}/api/jobs/${jobId}/model`;
  }

  /** Health check — returns true if the backend is reachable. */
  async isHealthy(): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/api/health`);
      return res.ok;
    } catch {
      return false;
    }
  }

  // ── WebSocket ──────────────────────────────────────────────────────────

  /**
   * Subscribe to real-time progress updates for a job.
   *
   * Returns a cleanup function to close the connection.
   *
   * Example:
   *   const unsub = api.onProgress(jobId, (update) => {
   *     console.log(update.progress_pct, update.message);
   *     if (update.status === "complete") { ... }
   *   });
   *   // later: unsub();
   */
  onProgress(
    jobId: string,
    callback: (update: ProgressUpdate) => void,
    onError?: (event: Event) => void
  ): () => void {
    const wsUrl = this.baseUrl
      .replace(/^http/, "ws")
      .concat(`/ws/${jobId}`);

    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      const update: ProgressUpdate = JSON.parse(event.data);
      callback(update);
      if (update.status === "complete" || update.status === "failed") {
        ws.close();
      }
    };

    ws.onerror = (event) => {
      if (onError) onError(event);
    };

    return () => {
      if (ws.readyState <= WebSocket.OPEN) {
        ws.close();
      }
    };
  }

  // ── Convenience: upload + track in one call ────────────────────────────

  /**
   * Upload an image and track the job to completion.
   *
   * Calls `onProgress` for every status update and resolves with the
   * final JobResult when complete.
   *
   * Example:
   *   const result = await api.uploadAndTrack(file, (update) => {
   *     setProgress(update.progress_pct);
   *     setMessage(update.message);
   *   });
   *   loadGLB(api.getModelUrl(result.job_id));
   *   showQuote(result.assessment);
   */
  async uploadAndTrack(
    file: File,
    onProgress?: (update: ProgressUpdate) => void
  ): Promise<JobResult> {
    const { job_id } = await this.upload(file);

    return new Promise((resolve, reject) => {
      const unsub = this.onProgress(
        job_id,
        (update) => {
          onProgress?.(update);

          if (update.status === "complete") {
            this.getJobResult(job_id).then(resolve).catch(reject);
          } else if (update.status === "failed") {
            reject(new Error(update.message));
          }
        },
        (err) => {
          unsub();
          reject(err);
        }
      );
    });
  }
}
