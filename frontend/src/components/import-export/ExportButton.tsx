"use client";

import { useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("dynaplan_token");
}

interface ExportButtonProps {
  moduleId: string;
  moduleName?: string;
}

/**
 * ExportButton — dropdown button that lets the user export a module
 * as CSV or Excel (.xlsx).
 *
 * Triggers a file download by fetching the export endpoint with the
 * user's auth token and creating a temporary anchor element.
 */
export default function ExportButton({ moduleId, moduleName = "module" }: ExportButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExport(format: "csv" | "xlsx") {
    setIsOpen(false);
    setIsDownloading(true);
    setError(null);

    try {
      const token = getAuthToken();
      const url = `${API_BASE_URL}/modules/${moduleId}/export?format=${format}`;
      const response = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const msg =
          (body as { detail?: string }).detail ??
          `Export failed: ${response.status}`;
        throw new Error(msg);
      }

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `${moduleName}.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <div className="relative inline-block text-left">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        disabled={isDownloading}
        className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 shadow-sm hover:bg-zinc-50 disabled:opacity-50 transition-colors"
      >
        <DownloadIcon className="h-4 w-4" />
        {isDownloading ? "Exporting..." : "Export"}
        <ChevronIcon className="h-4 w-4" />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          {/* Dropdown */}
          <div className="absolute right-0 z-20 mt-1 w-40 rounded-md border border-zinc-200 bg-white shadow-lg">
            <div className="py-1">
              <button
                type="button"
                onClick={() => handleExport("csv")}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50 transition-colors"
              >
                <CsvIcon className="h-4 w-4 text-zinc-400" />
                Export as CSV
              </button>
              <button
                type="button"
                onClick={() => handleExport("xlsx")}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50 transition-colors"
              >
                <ExcelIcon className="h-4 w-4 text-green-500" />
                Export as Excel
              </button>
            </div>
          </div>
        </>
      )}

      {error && (
        <p className="absolute left-0 top-full mt-1 w-64 rounded-md bg-red-50 px-3 py-2 text-xs text-red-600 shadow">
          {error}
        </p>
      )}
    </div>
  );
}

// ── Icons ──────────────────────────────────────────────────────────────────────

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4-4 4m0 0-4-4m4 4V4" />
    </svg>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m19 9-7 7-7-7" />
    </svg>
  );
}

function CsvIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

function ExcelIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 24 24">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm-1 1.5L18.5 9H13V3.5zM8.5 17l2-3-2-3h1.8l1.2 2 1.2-2h1.8l-2 3 2 3h-1.8L11.5 15l-1.2 2H8.5z" />
    </svg>
  );
}
