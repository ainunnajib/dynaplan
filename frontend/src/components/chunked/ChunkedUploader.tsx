"use client";

import { useCallback, useRef, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("dynaplan_token");
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface ChunkedUploaderProps {
  modelId: string;
  chunkSizeBytes?: number;
  onUploadComplete?: (uploadId: string) => void;
}

interface UploadSession {
  id: string;
  filename: string;
  total_chunks: number;
  received_chunks: number;
  status: string;
}

type UploadState = "idle" | "creating" | "uploading" | "completing" | "done" | "error";

// ── Helpers ───────────────────────────────────────────────────────────────────

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

async function apiPost(path: string, body: Record<string, unknown>) {
  const token = getAuthToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ChunkedUploader({
  modelId,
  chunkSizeBytes = 1024 * 1024, // 1 MB default
  onUploadComplete,
}: ChunkedUploaderProps) {
  const [state, setState] = useState<UploadState>("idle");
  const [session, setSession] = useState<UploadSession | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = useCallback(() => {
    setState("idle");
    setSession(null);
    setProgress(0);
    setError(null);
    setFileName(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  const handleUpload = useCallback(
    async (file: File) => {
      setError(null);
      setFileName(file.name);

      const totalChunks = Math.ceil(file.size / chunkSizeBytes);

      try {
        // 1. Create upload session
        setState("creating");
        const sessionData: UploadSession = await apiPost(
          `/models/${modelId}/uploads`,
          {
            filename: file.name,
            content_type: file.type || "application/octet-stream",
            total_chunks: totalChunks,
            total_size_bytes: file.size,
          }
        );
        setSession(sessionData);

        // 2. Upload chunks
        setState("uploading");
        for (let i = 0; i < totalChunks; i++) {
          const start = i * chunkSizeBytes;
          const end = Math.min(start + chunkSizeBytes, file.size);
          const blob = file.slice(start, end);
          const buffer = await blob.arrayBuffer();
          const base64Data = arrayBufferToBase64(buffer);

          await apiPost(`/uploads/${sessionData.id}/chunks`, {
            chunk_index: i,
            data: base64Data,
            size_bytes: end - start,
          });

          setProgress(Math.round(((i + 1) / totalChunks) * 100));
        }

        // 3. Complete
        setState("completing");
        await apiPost(`/uploads/${sessionData.id}/complete`, {});

        setState("done");
        onUploadComplete?.(sessionData.id);
      } catch (err) {
        setState("error");
        setError(err instanceof Error ? err.message : "Upload failed");
      }
    },
    [modelId, chunkSizeBytes, onUploadComplete]
  );

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleUpload(file);
      }
    },
    [handleUpload]
  );

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <h3 className="mb-4 text-lg font-semibold text-gray-900">
        Chunked File Upload
      </h3>

      {state === "idle" && (
        <div className="flex flex-col items-center gap-4">
          <div className="flex w-full items-center justify-center">
            <label
              htmlFor="chunked-file-input"
              className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 hover:bg-gray-100"
            >
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <svg
                  className="mb-2 h-8 w-8 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                <p className="text-sm text-gray-500">
                  Click to select a file for chunked upload
                </p>
                <p className="text-xs text-gray-400">
                  Chunk size: {Math.round(chunkSizeBytes / 1024)} KB
                </p>
              </div>
              <input
                id="chunked-file-input"
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={onFileChange}
              />
            </label>
          </div>
        </div>
      )}

      {(state === "creating" || state === "uploading" || state === "completing") && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm text-gray-600">
            <span>{fileName}</span>
            <span>
              {state === "creating"
                ? "Creating session..."
                : state === "completing"
                ? "Finalizing..."
                : `${progress}%`}
            </span>
          </div>
          <div className="h-3 w-full rounded-full bg-gray-200">
            <div
              className="h-3 rounded-full bg-blue-600 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          {session && (
            <p className="text-xs text-gray-400">
              Chunks: {Math.round((progress / 100) * session.total_chunks)} /{" "}
              {session.total_chunks}
            </p>
          )}
        </div>
      )}

      {state === "done" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-green-700">
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <span className="font-medium">Upload complete</span>
          </div>
          <p className="text-sm text-gray-500">{fileName}</p>
          <button
            onClick={reset}
            className="rounded bg-gray-100 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-200"
          >
            Upload another file
          </button>
        </div>
      )}

      {state === "error" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-red-700">
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <span className="font-medium">Upload failed</span>
          </div>
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={reset}
            className="rounded bg-gray-100 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-200"
          >
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
