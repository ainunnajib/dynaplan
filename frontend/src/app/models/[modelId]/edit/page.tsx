"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { fetchApi, getModel, getModelStatus } from "@/lib/api";
import type { PlanningModel } from "@/lib/api";

export default function EditModelPage() {
  const router = useRouter();
  const params = useParams<{ modelId: string }>();
  const modelId = params.modelId;

  const [model, setModel] = useState<PlanningModel | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isArchived, setIsArchived] = useState(false);
  const [originalArchived, setOriginalArchived] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function load() {
      if (!modelId) return;
      setIsLoading(true);
      setError(null);
      try {
        const data = await getModel(modelId);
        if (!isMounted) return;
        const archived = getModelStatus(data) === "archived";
        setModel(data);
        setName(data.name);
        setDescription(data.description ?? "");
        setIsArchived(archived);
        setOriginalArchived(archived);
      } catch (err) {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Failed to load model");
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }
    void load();
    return () => {
      isMounted = false;
    };
  }, [modelId]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!modelId || !name.trim()) {
      setError("Model name is required");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await fetchApi<PlanningModel>(`/models/${modelId}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
        }),
      });

      if (isArchived !== originalArchived) {
        const action = isArchived ? "archive" : "unarchive";
        await fetchApi<PlanningModel>(`/models/${modelId}/${action}`, {
          method: "POST",
        });
      }

      router.push(`/models/${modelId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update model");
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl p-4 sm:p-6">
      <div className="mb-6">
        <nav className="mb-2 flex flex-wrap items-center gap-x-1 text-xs text-zinc-500">
          <Link href="/workspaces" className="hover:text-zinc-800">
            Workspaces
          </Link>
          <span>/</span>
          <Link
            href={model ? `/workspaces/${model.workspace_id}` : "/workspaces"}
            className="hover:text-zinc-800"
          >
            Workspace
          </Link>
          <span>/</span>
          <Link href={`/models/${modelId}`} className="hover:text-zinc-800">
            Model
          </Link>
          <span>/</span>
          <span className="text-zinc-800">Edit</span>
        </nav>
        <h1 className="text-2xl font-semibold text-zinc-900">Edit Model</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Update model details and lifecycle state.
        </p>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        {isLoading ? (
          <p className="text-sm text-zinc-500">Loading model...</p>
        ) : (
          <>
            {error && (
              <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
              <div>
                <label
                  htmlFor="name"
                  className="mb-1 block text-sm font-medium text-zinc-700"
                >
                  Name
                </label>
                <input
                  id="name"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  disabled={isSubmitting}
                />
              </div>

              <div>
                <label
                  htmlFor="description"
                  className="mb-1 block text-sm font-medium text-zinc-700"
                >
                  Description
                </label>
                <textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="min-h-24 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  disabled={isSubmitting}
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-zinc-700">
                <input
                  type="checkbox"
                  checked={isArchived}
                  onChange={(e) => setIsArchived(e.target.checked)}
                  disabled={isSubmitting}
                />
                Archive model
              </label>

              <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:items-center sm:gap-3">
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                >
                  {isSubmitting ? "Saving..." : "Save Changes"}
                </button>
                <Link
                  href={`/models/${modelId}`}
                  className="w-full rounded-md border border-zinc-300 px-4 py-2 text-center text-sm font-medium text-zinc-700 hover:bg-zinc-50 sm:w-auto"
                >
                  Cancel
                </Link>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
