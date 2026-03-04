import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { listAssessments } from "../lib/api-client";
import type { AssessmentStatus } from "../lib/api-types";
import StatusBadge from "../components/StatusBadge";

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All Statuses" },
  { value: "created", label: "Created" },
  { value: "uploading", label: "Uploading" },
  { value: "extracting_frames", label: "Extracting Frames" },
  { value: "splatting", label: "Splatting" },
  { value: "analyzing", label: "Analyzing" },
  { value: "complete", label: "Complete" },
  { value: "failed", label: "Failed" },
];

export default function AssessmentListPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, error } = useQuery({
    queryKey: ["assessments", { page, search, status: statusFilter }],
    queryFn: () =>
      listAssessments({
        page,
        page_size: 20,
        status: statusFilter || undefined,
        search: search || undefined,
      }),
  });

  const assessments = data?.items ?? [];
  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  return (
    <div>
      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Assessments</h1>
          <p className="text-slate-400 text-sm mt-1">
            Manage vehicle damage assessments
          </p>
        </div>
        <button
          onClick={() => navigate("/assessments/new")}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <PlusIcon className="w-4 h-4" />
          New Assessment
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search by claim number..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-800">
              <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider">
                Claim #
              </th>
              <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider">
                Vehicle
              </th>
              <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider">
                Status
              </th>
              <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider">
                Date
              </th>
              <th className="text-right px-6 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider">
                Estimate
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-slate-500">
                  <LoadingSpinner />
                </td>
              </tr>
            )}
            {error && (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-red-400">
                  Failed to load assessments. Is the backend running?
                </td>
              </tr>
            )}
            {!isLoading && !error && assessments.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-slate-500">
                  No assessments found. Create your first one!
                </td>
              </tr>
            )}
            {assessments.map((a) => (
              <tr
                key={a.id}
                className="hover:bg-slate-800/50 cursor-pointer transition-colors"
                onClick={() => navigate(`/assessments/${a.id}`)}
              >
                <td className="px-6 py-4">
                  <Link
                    to={`/assessments/${a.id}`}
                    className="text-sm font-medium text-blue-400 hover:text-blue-300"
                  >
                    {a.claim_number}
                  </Link>
                </td>
                <td className="px-6 py-4 text-sm text-slate-300">
                  {a.vehicle.year} {a.vehicle.make} {a.vehicle.model}
                </td>
                <td className="px-6 py-4">
                  <StatusBadge status={a.status} />
                </td>
                <td className="px-6 py-4 text-sm text-slate-400">
                  {new Date(a.created_at).toLocaleDateString()}
                </td>
                <td className="px-6 py-4 text-sm text-right text-slate-300">
                  {a.total_estimate_low != null && a.total_estimate_high != null
                    ? `$${a.total_estimate_low.toLocaleString()} - $${a.total_estimate_high.toLocaleString()}`
                    : "--"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-slate-400">
            Page {page} of {totalPages} ({data?.total ?? 0} total)
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-sm bg-slate-800 border border-slate-700 rounded-lg disabled:opacity-40 hover:bg-slate-700 transition-colors"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1.5 text-sm bg-slate-800 border border-slate-700 rounded-lg disabled:opacity-40 hover:bg-slate-700 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// -- Inline icons & spinner --------------------------------------------------

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
    </svg>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center gap-2">
      <div className="w-5 h-5 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin" />
      <span>Loading assessments...</span>
    </div>
  );
}
