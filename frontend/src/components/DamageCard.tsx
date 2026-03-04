import { useState } from "react";
import type { DamageItem, Severity } from "../lib/api-types";

interface DamageCardProps {
  item: DamageItem;
  id?: string;
}

const SEVERITY_CLASSES: Record<Severity, string> = {
  minor: "bg-emerald-900/50 text-emerald-400",
  moderate: "bg-yellow-900/50 text-yellow-400",
  severe: "bg-red-900/50 text-red-400",
};

const REPAIR_LABELS: Record<string, string> = {
  repair: "Repair",
  replace: "Replace",
  repaint: "Repaint",
};

export default function DamageCard({ item, id }: DamageCardProps) {
  const [showFrames, setShowFrames] = useState(false);

  return (
    <div
      id={id}
      className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 transition-colors hover:border-slate-600"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div>
          <h4 className="text-sm font-semibold text-slate-200">{item.location}</h4>
          <p className="text-xs text-slate-400">{item.damage_type}</p>
        </div>
        <span
          className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium uppercase tracking-wide ${
            SEVERITY_CLASSES[item.severity] ?? SEVERITY_CLASSES.minor
          }`}
        >
          {item.severity}
        </span>
      </div>

      {/* Description */}
      <p className="text-sm text-slate-400 mb-3">{item.description}</p>

      {/* Details grid */}
      <div className="grid grid-cols-2 gap-2 text-xs mb-3">
        <div>
          <span className="text-slate-500">Repair Method</span>
          <p className="text-slate-300 font-medium">
            {REPAIR_LABELS[item.repair_method] ?? item.repair_method}
          </p>
        </div>
        <div>
          <span className="text-slate-500">Cost Estimate</span>
          <p className="text-slate-300 font-medium">
            ${item.estimated_cost_low.toLocaleString()} &ndash; $
            {item.estimated_cost_high.toLocaleString()}
          </p>
        </div>
        <div>
          <span className="text-slate-500">Confidence</span>
          <p className="text-slate-300 font-medium">{Math.round(item.confidence_score * 100)}%</p>
        </div>
        <div>
          <span className="text-slate-500">Zone</span>
          <p className="text-slate-300 font-medium">
            {item.vehicle_zone.replace(/_/g, " ")}
          </p>
        </div>
      </div>

      {/* Affected parts */}
      {item.affected_parts.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {item.affected_parts.map((part) => (
            <span
              key={part}
              className="px-2 py-0.5 bg-slate-700 rounded text-xs text-slate-300"
            >
              {part}
            </span>
          ))}
        </div>
      )}

      {/* Reference frames toggle */}
      {item.reference_frame_paths.length > 0 && (
        <div>
          <button
            onClick={() => setShowFrames(!showFrames)}
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            {showFrames ? "Hide" : "View"} reference frames (
            {item.reference_frame_paths.length})
          </button>
          {showFrames && (
            <div className="grid grid-cols-3 gap-2 mt-2">
              {item.reference_frame_paths.map((path, i) => (
                <img
                  key={i}
                  src={path}
                  alt={`Reference frame ${i + 1}`}
                  className="w-full aspect-video object-cover rounded border border-slate-700"
                  loading="lazy"
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
