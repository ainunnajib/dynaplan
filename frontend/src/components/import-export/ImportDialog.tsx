"use client";

import { useRef, useState } from "react";
import ColumnMapper from "./ColumnMapper";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("dynaplan_token");
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface ImportPreview {
  column_names: string[];
  sample_rows: Record<string, unknown>[];
  suggested_mapping: Record<string, string | null>;
}

interface ImportResult {
  rows_imported: number;
  rows_skipped: number;
  errors: string[];
}

interface ImportDialogProps {
  /** Module ID to import into */
  moduleId: string;
  /** Available line item names for column mapping */
  lineItemNames: string[];
  /** Called after a successful import */
  onSuccess?: (result: ImportResult) => void;
  /** Button label override */
  label?: string;
}

type Step = "idle" | "selecting" | "preview" | "importing" | "done";

// ── Component ─────────────────────────────────────────────────────────────────

/**
 * ImportDialog — multi-step file upload dialog for importing CSV/Excel data
 * into a module.
 *
 * Steps:
 *  1. User clicks "Import" button → dialog opens
 *  2. User selects a CSV or Excel file
 *  3. File is sent to /modules/{id}/import/preview → columns are shown
 *  4. User maps columns to line items via ColumnMapper
 *  5. User clicks "Import" → file is sent to /modules/{id}/import
 *  6. Result is displayed
 */
export default function ImportDialog({
  moduleId,
  lineItemNames,
  onSuccess,
  label = "Import",
}: ImportDialogProps) {
  const [step, setStep] = useState<Step>("idle");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  function openDialog() {
    setStep("selecting");
    setPreview(null);
    setMapping({});
    setResult(null);
    setError(null);
    setSelectedFile(null);
  }

  function closeDialog() {
    if (step === "importing") return;
    setStep("idle");
  }

  async function handleFileSelected(file: File) {
    setSelectedFile(file);
    setError(null);

    const token = getAuthToken();
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(
        `${API_BASE_URL}/modules/${moduleId}/import/preview`,
        {
          method: "POST",
          body: formData,
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      );

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(
          (body as { detail?: string }).detail ?? `Preview failed: ${response.status}`
        );
      }

      const data: ImportPreview = await response.json();
      setPreview(data);
      setMapping(data.suggested_mapping);
      setStep("preview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to preview file");
    }
  }

  async function handleImport() {
    if (!selectedFile || !preview) return;

    setStep("importing");
    setError(null);

    const token = getAuthToken();
    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch(
        `${API_BASE_URL}/modules/${moduleId}/import`,
        {
          method: "POST",
          body: formData,
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      );

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(
          (body as { detail?: string }).detail ?? `Import failed: ${response.status}`
        );
      }

      const data: ImportResult = await response.json();
      setResult(data);
      setStep("done");
      onSuccess?.(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
      setStep("preview");
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={openDialog}
        className="inline-flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 shadow-sm hover:bg-zinc-50 transition-colors"
      >
        <UploadIcon className="h-4 w-4" />
        {label}
      </button>

      {step !== "idle" && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeDialog();
          }}
        >
          <div className="w-full max-w-2xl rounded-xl bg-white shadow-xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
              <h2 className="text-base font-semibold text-zinc-900">
                {step === "done" ? "Import complete" : "Import data"}
              </h2>
              <button
                type="button"
                onClick={closeDialog}
                disabled={step === "importing"}
                className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 disabled:opacity-50 transition-colors"
              >
                <CloseIcon className="h-5 w-5" />
              </button>
            </div>

            {/* Body */}
            <div className="px-6 py-5 space-y-4">
              {/* Step: selecting a file */}
              {step === "selecting" && (
                <FileDropZone
                  onFileSelected={handleFileSelected}
                  fileInputRef={fileInputRef}
                />
              )}

              {/* Step: preview & column mapping */}
              {(step === "preview" || step === "importing") && preview && (
                <>
                  <div>
                    <p className="text-sm text-zinc-600 mb-3">
                      <strong>{preview.column_names.length}</strong> columns detected.
                      Map each column to a line item (or skip it).
                    </p>
                    <ColumnMapper
                      columnNames={preview.column_names}
                      mapping={mapping}
                      targetFields={lineItemNames}
                      targetLabel="Line item"
                      onChange={setMapping}
                    />
                  </div>

                  {/* Sample rows */}
                  {preview.sample_rows.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-zinc-500 mb-1 uppercase tracking-wide">
                        Sample data
                      </p>
                      <div className="overflow-x-auto rounded-lg border border-zinc-200">
                        <table className="text-xs w-full">
                          <thead className="bg-zinc-50">
                            <tr>
                              {preview.column_names.map((col) => (
                                <th
                                  key={col}
                                  className="px-3 py-1.5 text-left font-medium text-zinc-500"
                                >
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-zinc-100">
                            {preview.sample_rows.map((row, i) => (
                              <tr key={i} className="bg-white">
                                {preview.column_names.map((col) => (
                                  <td key={col} className="px-3 py-1.5 text-zinc-700">
                                    {String(row[col] ?? "")}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Step: done */}
              {step === "done" && result && (
                <ImportResultView result={result} />
              )}

              {/* Error message */}
              {error && (
                <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
                  {error}
                </p>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 border-t border-zinc-200 px-6 py-4">
              {step === "done" ? (
                <button
                  type="button"
                  onClick={closeDialog}
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
                >
                  Close
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={closeDialog}
                    disabled={step === "importing"}
                    className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
                  >
                    Cancel
                  </button>
                  {step === "preview" && (
                    <button
                      type="button"
                      onClick={handleImport}
                      className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
                    >
                      Import
                    </button>
                  )}
                  {step === "importing" && (
                    <button
                      type="button"
                      disabled
                      className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white opacity-60 cursor-not-allowed"
                    >
                      Importing...
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

interface FileDropZoneProps {
  onFileSelected: (file: File) => void;
  fileInputRef: React.MutableRefObject<HTMLInputElement | null>;
}

function FileDropZone({ onFileSelected, fileInputRef }: FileDropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onFileSelected(file);
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onFileSelected(file);
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      onClick={() => fileInputRef.current?.click()}
      className={[
        "flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 cursor-pointer transition-colors",
        isDragOver
          ? "border-blue-400 bg-blue-50"
          : "border-zinc-300 hover:border-blue-400 hover:bg-zinc-50",
      ].join(" ")}
    >
      <UploadIcon className="h-10 w-10 text-zinc-300 mb-3" />
      <p className="text-sm font-medium text-zinc-700">
        Drop a file here, or click to browse
      </p>
      <p className="text-xs text-zinc-400 mt-1">
        Supports CSV and Excel (.xlsx)
      </p>
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        className="hidden"
        onChange={handleInputChange}
      />
    </div>
  );
}

function ImportResultView({ result }: { result: ImportResult }) {
  return (
    <div className="space-y-3">
      <div className="flex gap-6">
        <div className="rounded-lg bg-green-50 px-4 py-3 text-center">
          <p className="text-2xl font-bold text-green-700">{result.rows_imported}</p>
          <p className="text-xs text-green-600">Rows imported</p>
        </div>
        <div className="rounded-lg bg-zinc-50 px-4 py-3 text-center">
          <p className="text-2xl font-bold text-zinc-500">{result.rows_skipped}</p>
          <p className="text-xs text-zinc-400">Rows skipped</p>
        </div>
      </div>
      {result.errors.length > 0 && (
        <div>
          <p className="text-xs font-medium text-zinc-500 mb-1 uppercase tracking-wide">
            Warnings / errors
          </p>
          <ul className="max-h-40 overflow-y-auto rounded-lg border border-zinc-200 divide-y divide-zinc-100 text-xs text-zinc-600">
            {result.errors.map((err, i) => (
              <li key={i} className="px-3 py-2">
                {err}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Icons ──────────────────────────────────────────────────────────────────────

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8-4-4m0 0L8 8m4-4v12" />
    </svg>
  );
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}
