import type { DamageItem, DamageReport as DamageReportType } from "../lib/api-types";
import { getReportPdfUrl } from "../lib/api-client";
import DamageCard from "./DamageCard";

interface DamageReportProps {
  report: DamageReportType | null;
  assessmentId: string;
  isLoading: boolean;
}

export default function DamageReport({
  report,
  assessmentId,
  isLoading,
}: DamageReportProps) {
  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-2 text-slate-400">
          <div className="w-4 h-4 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin" />
          <span className="text-sm">Loading damage report...</span>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center">
        <DocumentIcon className="w-10 h-10 text-slate-600 mx-auto mb-3" />
        <p className="text-sm text-slate-400">Damage report not yet available</p>
        <p className="text-xs text-slate-500 mt-1">
          Report will appear after analysis completes
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-200">Damage Report</h3>
            <p className="text-sm text-slate-400">
              {report.vehicle.year} {report.vehicle.make} {report.vehicle.model}
            </p>
          </div>
          <a
            href={getReportPdfUrl(assessmentId)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <DownloadIcon className="w-4 h-4" />
            PDF Report
          </a>
        </div>

        {/* Summary */}
        <p className="text-sm text-slate-300 mb-4">{report.summary.narrative}</p>

        {/* Cost totals */}
        <div className="bg-slate-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-400">Total Estimated Cost</span>
            <span className="text-xl font-bold text-slate-100">
              ${report.summary.total_estimate_low.toLocaleString()} &ndash; $
              {report.summary.total_estimate_high.toLocaleString()}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-2">{report.summary.recommendation}</p>
        </div>
      </div>

      {/* Damage items */}
      <div className="space-y-3">
        {report.damages.map((item) => (
          <DamageCard
            key={item.id}
            item={item}
            id={`damage-${item.vehicle_zone}`}
          />
        ))}
      </div>

      {/* Cost breakdown table */}
      {report.damages.length > 0 && (
        <CostBreakdownTable items={report.damages} report={report} />
      )}
    </div>
  );
}

function CostBreakdownTable({
  items,
  report,
}: {
  items: DamageItem[];
  report: { summary: { total_estimate_low: number; total_estimate_high: number } };
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-800">
        <h4 className="text-sm font-medium text-slate-300">Cost Breakdown</h4>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800">
            <th className="text-left px-4 py-2 text-xs font-medium text-slate-500 uppercase">
              Item
            </th>
            <th className="text-left px-4 py-2 text-xs font-medium text-slate-500 uppercase">
              Severity
            </th>
            <th className="text-left px-4 py-2 text-xs font-medium text-slate-500 uppercase">
              Method
            </th>
            <th className="text-right px-4 py-2 text-xs font-medium text-slate-500 uppercase">
              Low
            </th>
            <th className="text-right px-4 py-2 text-xs font-medium text-slate-500 uppercase">
              High
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {items.map((item) => (
            <tr key={item.id} className="hover:bg-slate-800/50">
              <td className="px-4 py-2 text-slate-300">{item.location}</td>
              <td className="px-4 py-2">
                <span
                  className={`text-xs font-medium ${
                    item.severity === "severe"
                      ? "text-red-400"
                      : item.severity === "moderate"
                      ? "text-yellow-400"
                      : "text-emerald-400"
                  }`}
                >
                  {item.severity}
                </span>
              </td>
              <td className="px-4 py-2 text-slate-400 capitalize">
                {item.repair_method}
              </td>
              <td className="px-4 py-2 text-right text-slate-300">
                ${item.estimated_cost_low.toLocaleString()}
              </td>
              <td className="px-4 py-2 text-right text-slate-300">
                ${item.estimated_cost_high.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-slate-700 bg-slate-800/30 font-semibold">
            <td colSpan={3} className="px-4 py-2 text-slate-300">
              Total
            </td>
            <td className="px-4 py-2 text-right text-slate-200">
              ${report.summary.total_estimate_low.toLocaleString()}
            </td>
            <td className="px-4 py-2 text-right text-slate-200">
              ${report.summary.total_estimate_high.toLocaleString()}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

// -- Inline icons ------------------------------------------------------------

function DocumentIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
    </svg>
  );
}
