import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { listAssessments, deleteAssessment } from "../lib/api-client";
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
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

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
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                  <LoadingSpinner />
                </td>
              </tr>
            )}
            {error && (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-red-400">
                  Failed to load assessments. Is the backend running?
                </td>
              </tr>
            )}
            {!isLoading && !error && assessments.length === 0 && (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
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
                <td className="px-4 py-4">
                  <button
                    onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(a.id); }}
                    className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-900/20 rounded transition-colors"
                    title="Delete assessment"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
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
      {/* Delete confirmation dialog */}
      {confirmDeleteId && (() => {
        const target = assessments.find((a) => a.id === confirmDeleteId);
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
            <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 max-w-sm w-full mx-4 shadow-xl">
              <h3 className="text-base font-semibold text-slate-100 mb-2">Delete Assessment</h3>
              <p className="text-sm text-slate-400 mb-4">
                Permanently delete{" "}
                <span className="text-slate-200 font-medium">{target?.claim_number}</span>
                {" "}and all associated videos, frames, splats, and damage data? This cannot be undone.
              </p>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setConfirmDeleteId(null)}
                  disabled={isDeleting}
                  className="px-4 py-2 text-sm text-slate-300 hover:text-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={async () => {
                    setIsDeleting(true);
                    try {
                      await deleteAssessment(confirmDeleteId);
                      queryClient.invalidateQueries({ queryKey: ["assessments"] });
                      setConfirmDeleteId(null);
                    } finally {
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
        );
      })()}
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

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
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
