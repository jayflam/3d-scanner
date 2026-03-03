import type { AssessmentStatus } from "../lib/api-types";

const STATUS_CONFIG: Record<AssessmentStatus, { label: string; classes: string }> = {
  created: { label: "Created", classes: "bg-slate-700 text-slate-300" },
  uploading: { label: "Uploading", classes: "bg-blue-900/50 text-blue-400" },
  extracting_frames: { label: "Extracting", classes: "bg-yellow-900/50 text-yellow-400" },
  splatting: { label: "Splatting", classes: "bg-purple-900/50 text-purple-400" },
  analyzing: { label: "Analyzing", classes: "bg-orange-900/50 text-orange-400" },
  complete: { label: "Complete", classes: "bg-emerald-900/50 text-emerald-400" },
  failed: { label: "Failed", classes: "bg-red-900/50 text-red-400" },
};

interface StatusBadgeProps {
  status: AssessmentStatus;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.created;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.classes}`}
    >
      {isProcessing(status) && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      )}
      {config.label}
    </span>
  );
}

function isProcessing(status: AssessmentStatus): boolean {
  return ["uploading", "extracting_frames", "splatting", "analyzing"].includes(status);
}
