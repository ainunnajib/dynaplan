"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { fetchApi } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

type ExportFormat = "pdf" | "xlsx" | "pptx";
type ExportStatus = "pending" | "generating" | "complete" | "failed";

interface ReportExport {
  id: string;
  report_id: string;
  exported_by: string;
  format: ExportFormat;
  file_path: string | null;
  status: ExportStatus;
  created_at: string;
}

interface Props {
  reportId: string;
  open: boolean;
  onClose: () => void;
}

// ── Format metadata ─────────────────────────────────────────────────────────

const FORMAT_META: Record<ExportFormat, { label: string; icon: string; description: string }> = {
  pdf: { label: "PDF", icon: "PDF", description: "Print-ready portable document" },
  xlsx: { label: "Excel", icon: "XLS", description: "Spreadsheet with data tables" },
  pptx: { label: "PowerPoint", icon: "PPT", description: "Presentation slides" },
};

const STATUS_BADGE: Record<ExportStatus, { color: string; label: string }> = {
  pending: { color: "bg-yellow-100 text-yellow-700", label: "Pending" },
  generating: { color: "bg-blue-100 text-blue-700", label: "Generating" },
  complete: { color: "bg-green-100 text-green-700", label: "Complete" },
  failed: { color: "bg-red-100 text-red-700", label: "Failed" },
};

// ── Component ────────────────────────────────────────────────────────────────

export default function ExportDialog({ reportId, open, onClose }: Props) {
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>("pdf");
  const [isExporting, setIsExporting] = useState(false);
  const [exports, setExports] = useState<ReportExport[]>([]);
  const [loading, setLoading] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  // Manage dialog open/close
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  // Load exports when opened
  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const data = await fetchApi<ReportExport[]>(
          `/reports/${reportId}/exports`
        );
        if (!cancelled) setExports(data);
      } catch {
        // silently fail
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [open, reportId]);

  const initiateExport = useCallback(async () => {
    setIsExporting(true);
    try {
      const exp = await fetchApi<ReportExport>(
        `/reports/${reportId}/export`,
        {
          method: "POST",
          body: JSON.stringify({ format: selectedFormat }),
        }
      );
      setExports((prev) => [exp, ...prev]);
    } catch {
      // silently fail
    } finally {
      setIsExporting(false);
    }
  }, [reportId, selectedFormat]);

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      className="fixed inset-0 z-50 m-auto h-auto max-h-[80vh] w-full max-w-lg rounded-xl bg-white p-0 shadow-2xl backdrop:bg-black/30"
      onClose={onClose}
    >
      <div className="flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-zinc-900">Export Report</h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-600"
            aria-label="Close"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Format selection */}
        <div className="border-b border-zinc-100 px-6 py-4">
          <p className="mb-3 text-sm font-medium text-zinc-700">Select format</p>
          <div className="grid grid-cols-3 gap-3">
            {(Object.keys(FORMAT_META) as ExportFormat[]).map((fmt) => {
              const meta = FORMAT_META[fmt];
              const isSelected = selectedFormat === fmt;
              return (
                <button
                  key={fmt}
                  onClick={() => setSelectedFormat(fmt)}
                  className={`flex flex-col items-center gap-1.5 rounded-lg border-2 p-3 transition ${
                    isSelected
                      ? "border-violet-500 bg-violet-50"
                      : "border-zinc-200 hover:border-zinc-300"
                  }`}
                >
                  <span
                    className={`text-xs font-bold ${isSelected ? "text-violet-600" : "text-zinc-400"}`}
                  >
                    {meta.icon}
                  </span>
                  <span className="text-xs font-medium text-zinc-700">{meta.label}</span>
                  <span className="text-[10px] text-zinc-400">{meta.description}</span>
                </button>
              );
            })}
          </div>

          <button
            onClick={initiateExport}
            disabled={isExporting}
            className="mt-4 w-full rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-violet-700 disabled:opacity-50"
          >
            {isExporting ? "Starting export..." : `Export as ${FORMAT_META[selectedFormat].label}`}
          </button>
        </div>

        {/* Recent exports */}
        <div className="max-h-60 overflow-y-auto px-6 py-4">
          <p className="mb-2 text-sm font-medium text-zinc-700">Recent exports</p>
          {loading && (
            <p className="text-xs text-zinc-400">Loading...</p>
          )}
          {!loading && exports.length === 0 && (
            <p className="text-xs text-zinc-400">No exports yet</p>
          )}
          {exports.map((exp) => {
            const badge = STATUS_BADGE[exp.status];
            return (
              <div
                key={exp.id}
                className="flex items-center justify-between border-b border-zinc-100 py-2 last:border-0"
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-zinc-400">
                    {FORMAT_META[exp.format]?.icon ?? exp.format.toUpperCase()}
                  </span>
                  <span className="text-xs text-zinc-500">
                    {new Date(exp.created_at).toLocaleString()}
                  </span>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${badge.color}`}
                >
                  {badge.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </dialog>
  );
}
