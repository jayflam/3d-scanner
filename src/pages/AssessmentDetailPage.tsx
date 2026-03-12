import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getAssessment, getDamageReport, getSplatUrl, deleteAssessment } from "../lib/api-client";
import StatusTracker from "../components/StatusTracker";
import SplatViewer from "../components/SplatViewer";
import DamageReportPanel from "../components/DamageReport";
import VideoPlayer from "../components/VideoPlayer";
import StatusBadge from "../components/StatusBadge";
import ZoneDiagram from "../components/ZoneDiagram";
import useJobProgress from "../hooks/useJobProgress";

export default function AssessmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const wsProgress = useJobProgress(id);

  const {
    data: assessment,
    isLoading: assessmentLoading,
    error: assessmentError,
  } = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => getAssessment(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "complete" || status === "failed") return false;
      return 5000;
    },
  });

  const { data: damageReport, isLoading: reportLoading } = useQuery({
    queryKey: ["damageReport", id],
    queryFn: () => getDamageReport(id!),
    enabled: !!id && assessment?.status === "complete",
  });

  if (assessmentLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-400">Loading assessment...</p>
        </div>
      </div>
    );
  }

  if (assessmentError || !assessment) {
    return (
      <div className="max-w-md mx-auto text-center py-16">
        <p className="text-red-400 mb-4">Failed to load assessment</p>
        <Link
          to="/assessments"
          className="text-sm text-blue-400 hover:text-blue-300"
        >
          Back to assessments
        </Link>
      </div>
    );
  }

  const exteriorSplatUrl =
    assessment.splat_ready.exterior ? getSplatUrl(assessment.id, "exterior") : null;
  const interiorSplatUrl =
    assessment.splat_ready.interior ? getSplatUrl(assessment.id, "interior") : null;

  // Build video URLs (convention: /api/v1/assessments/{id}/videos/{type})
  const exteriorVideoUrl =
    assessment.pipeline.exterior_video !== "pending"
      ? `/api/v1/assessments/${assessment.id}/videos/exterior/stream`
      : null;
  const interiorVideoUrl =
    assessment.pipeline.interior_video !== "pending"
      ? `/api/v1/assessments/${assessment.id}/videos/interior/stream`
      : null;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold">{assessment.claim_number}</h1>
            <StatusBadge status={assessment.status} />
          </div>
          <p className="text-slate-400 text-sm">
            {assessment.vehicle.year} {assessment.vehicle.make}{" "}
            {assessment.vehicle.model}
            {assessment.vin && (
              <span className="text-slate-500"> &middot; VIN: {assessment.vin}</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right text-sm text-slate-400">
            <p>Created {new Date(assessment.created_at).toLocaleString()}</p>
            {assessment.agent_id && <p className="text-slate-500">Agent: {assessment.agent_id}</p>}
          </div>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-400 border border-red-800/60 rounded-lg hover:bg-red-900/30 transition-colors"
          >
            <TrashIcon className="w-4 h-4" />
            Delete
          </button>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 max-w-sm w-full mx-4 shadow-xl">
            <h3 className="text-base font-semibold text-slate-100 mb-2">Delete Assessment</h3>
            <p className="text-sm text-slate-400 mb-1">
              This will permanently delete <span className="text-slate-200 font-medium">{assessment.claim_number}</span> and all associated data:
            </p>
            <ul className="text-xs text-slate-500 list-disc list-inside mb-4 space-y-0.5">
              <li>Uploaded videos</li>
              <li>Extracted frames</li>
              <li>3D splat files</li>
              <li>Damage items &amp; report</li>
            </ul>
            {deleteError && <p className="text-sm text-red-400 mb-3">{deleteError}</p>}
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => { setShowDeleteConfirm(false); setDeleteError(null); }}
                disabled={isDeleting}
                className="px-4 py-2 text-sm text-slate-300 hover:text-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  setIsDeleting(true);
                  setDeleteError(null);
                  try {
                    await deleteAssessment(id!);
                    queryClient.removeQueries({ queryKey: ["assessment", id] });
                    queryClient.invalidateQueries({ queryKey: ["assessments"] });
                    navigate("/assessments");
                  } catch (e) {
                    setDeleteError(e instanceof Error ? e.message : "Delete failed");
                    setIsDeleting(false);
                  }
                }}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium bg-red-700 hover:bg-red-600 text-white rounded-lg disabled:opacity-50 transition-colors"
              >
                {isDeleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Status tracker (full width) */}
      <StatusTracker
        pipeline={assessment.pipeline}
        progressPct={wsProgress.progressPct || undefined}
      />

      {/* WebSocket status message */}
      {wsProgress.message && wsProgress.status !== "complete" && wsProgress.status !== "failed" && (
        <div className="bg-blue-900/20 border border-blue-800/50 rounded-lg px-4 py-2">
          <p className="text-sm text-blue-300">{wsProgress.message}</p>
        </div>
      )}

      {/* Error message */}
      {assessment.error_message && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-lg px-4 py-3">
          <p className="text-sm text-red-400 font-medium">Processing Error</p>
          <p className="text-sm text-red-300 mt-1">{assessment.error_message}</p>
        </div>
      )}

      {/* Two-column layout: viewer + report */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left column: 3D viewer + video */}
        <div className="space-y-4">
          <SplatViewer
            exteriorUrl={exteriorSplatUrl}
            interiorUrl={interiorSplatUrl}
          />
          <VideoPlayer
            exteriorUrl={exteriorVideoUrl}
            interiorUrl={interiorVideoUrl}
          />

          {/* Zone diagram */}
          {damageReport && damageReport.damages.length > 0 && (
            <ZoneDiagram damages={damageReport.damages} />
          )}

          {/* Frame counts */}
          {(assessment.frame_count.exterior > 0 || assessment.frame_count.interior > 0) && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <h3 className="text-sm font-medium text-slate-300 mb-2">
                Extracted Frames
              </h3>
              <div className="flex gap-6 text-sm">
                <div>
                  <span className="text-slate-500">Exterior: </span>
                  <span className="text-slate-200 font-medium">
                    {assessment.frame_count.exterior}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">Interior: </span>
                  <span className="text-slate-200 font-medium">
                    {assessment.frame_count.interior}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right column: damage report */}
        <div>
          <DamageReportPanel
            report={damageReport ?? null}
            assessmentId={assessment.id}
            isLoading={reportLoading}
          />
        </div>
      </div>
    </div>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
    </svg>
  );
}
