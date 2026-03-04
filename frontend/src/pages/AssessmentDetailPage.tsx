import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getAssessment, getDamageReport, getSplatUrl } from "../lib/api-client";
import StatusTracker from "../components/StatusTracker";
import SplatViewer from "../components/SplatViewer";
import DamageReportPanel from "../components/DamageReport";
import VideoPlayer from "../components/VideoPlayer";
import StatusBadge from "../components/StatusBadge";
import ZoneDiagram from "../components/ZoneDiagram";
import useJobProgress from "../hooks/useJobProgress";

export default function AssessmentDetailPage() {
  const { id } = useParams<{ id: string }>();

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
        <div className="text-right text-sm text-slate-400">
          <p>Created {new Date(assessment.created_at).toLocaleString()}</p>
          {assessment.agent_id && <p className="text-slate-500">Agent: {assessment.agent_id}</p>}
        </div>
      </div>

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
          {damageReport && damageReport.items.length > 0 && (
            <ZoneDiagram damages={damageReport.items} />
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
