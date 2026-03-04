import type { PipelineStatus, PipelineStageStatus } from "../lib/api-types";

interface StatusTrackerProps {
  pipeline: PipelineStatus;
  progressPct?: number;
}

interface Stage {
  key: keyof PipelineStatus;
  label: string;
}

const STAGES: Stage[] = [
  { key: "exterior_video", label: "Upload" },
  { key: "frame_extraction", label: "Frames" },
  { key: "gaussian_splatting", label: "3D Splat" },
  { key: "damage_analysis", label: "Analysis" },
  { key: "report_generation", label: "Report" },
];

export default function StatusTracker({ pipeline, progressPct }: StatusTrackerProps) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-slate-300">Pipeline Progress</h3>
        {progressPct != null && (
          <span className="text-xs text-slate-400">{progressPct}%</span>
        )}
      </div>

      {/* Progress bar */}
      {progressPct != null && (
        <div className="w-full h-1.5 bg-slate-800 rounded-full mb-6 overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      )}

      {/* Stage indicators */}
      <div className="flex items-center">
        {STAGES.map((stage, i) => {
          const status = pipeline[stage.key];
          return (
            <div key={stage.key} className="flex items-center flex-1 last:flex-none">
              {/* Stage node */}
              <div className="flex flex-col items-center gap-2">
                <StageIcon status={status} />
                <span
                  className={`text-xs font-medium ${
                    status === "complete"
                      ? "text-emerald-400"
                      : status === "in_progress"
                      ? "text-blue-400"
                      : status === "failed"
                      ? "text-red-400"
                      : "text-slate-500"
                  }`}
                >
                  {stage.label}
                </span>
              </div>

              {/* Connector line */}
              {i < STAGES.length - 1 && (
                <div className="flex-1 mx-2 mt-[-1.25rem]">
                  <div
                    className={`h-0.5 ${
                      status === "complete" ? "bg-emerald-500/50" : "bg-slate-700"
                    }`}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StageIcon({ status }: { status: PipelineStageStatus }) {
  const baseClasses = "w-8 h-8 rounded-full flex items-center justify-center";

  switch (status) {
    case "complete":
      return (
        <div className={`${baseClasses} bg-emerald-900/50 border border-emerald-600`}>
          <CheckIcon className="w-4 h-4 text-emerald-400" />
        </div>
      );
    case "in_progress":
      return (
        <div className={`${baseClasses} bg-blue-900/50 border border-blue-500`}>
          <div className="w-4 h-4 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin" />
        </div>
      );
    case "failed":
      return (
        <div className={`${baseClasses} bg-red-900/50 border border-red-600`}>
          <XIcon className="w-4 h-4 text-red-400" />
        </div>
      );
    default:
      return (
        <div className={`${baseClasses} bg-slate-800 border border-slate-700`}>
          <div className="w-2 h-2 rounded-full bg-slate-600" />
        </div>
      );
  }
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}
