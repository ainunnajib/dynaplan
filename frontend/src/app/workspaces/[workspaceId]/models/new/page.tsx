"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { fetchApi } from "@/lib/api";
import type { PlanningModel } from "@/lib/api";

export default function NewModelPage() {
  const router = useRouter();
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!workspaceId) {
      setError("Workspace ID is missing");
      return;
    }
    if (!name.trim()) {
      setError("Model name is required");
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      const created = await fetchApi<PlanningModel>("/models", {
        method: "POST",
        body: JSON.stringify({
          workspace_id: workspaceId,
          name: name.trim(),
          description: description.trim() || null,
        }),
      });
      router.push(`/models/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create model");
    } finally {
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
          <Link href={`/workspaces/${workspaceId}`} className="hover:text-zinc-800">
            Workspace
          </Link>
          <span>/</span>
          <span className="text-zinc-800">New Model</span>
        </nav>
        <h1 className="text-2xl font-semibold text-zinc-900">Create Model</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Create a planning model inside this workspace.
        </p>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <div>
            <label htmlFor="name" className="mb-1 block text-sm font-medium text-zinc-700">
              Name
            </label>
            <input
              id="name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="Sales Plan FY27"
              disabled={isSubmitting}
            />
          </div>

          <div>
            <label
              htmlFor="description"
              className="mb-1 block text-sm font-medium text-zinc-700"
            >
              Description (optional)
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-24 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="Describe this planning model..."
              disabled={isSubmitting}
            />
          </div>

          <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:items-center sm:gap-3">
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
            >
              {isSubmitting ? "Creating..." : "Create Model"}
            </button>
            <Link
              href={`/workspaces/${workspaceId}`}
              className="w-full rounded-md border border-zinc-300 px-4 py-2 text-center text-sm font-medium text-zinc-700 hover:bg-zinc-50 sm:w-auto"
            >
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
