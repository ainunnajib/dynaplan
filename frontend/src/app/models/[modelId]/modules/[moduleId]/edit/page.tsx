"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { fetchApi, getModule } from "@/lib/api";
import type { Module } from "@/lib/api";

export default function EditModulePage() {
  const router = useRouter();
  const params = useParams<{ modelId: string; moduleId: string }>();
  const modelId = params.modelId;
  const moduleId = params.moduleId;

  const [moduleData, setModuleData] = useState<Module | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      if (!moduleId) return;
      setIsLoading(true);
      setError(null);
      try {
        const mod = await getModule(moduleId);
        if (!isMounted) return;
        setModuleData(mod);
        setName(mod.name);
        setDescription(mod.description ?? "");
      } catch (err) {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Failed to load module");
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
  }, [moduleId]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!moduleId || !name.trim()) {
      setError("Module name is required");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await fetchApi<Module>(`/modules/${moduleId}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
        }),
      });
      router.push(`/models/${modelId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update module");
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
          <Link href={`/models/${modelId}`} className="hover:text-zinc-800">
            Model
          </Link>
          <span>/</span>
          <span className="text-zinc-800">Edit Module</span>
        </nav>
        <h1 className="text-2xl font-semibold text-zinc-900">Edit Module</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Update module details for {moduleData?.name ?? "this module"}.
        </p>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        {isLoading ? (
          <p className="text-sm text-zinc-500">Loading module...</p>
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
                  htmlFor="module-name-edit"
                  className="mb-1 block text-sm font-medium text-zinc-700"
                >
                  Name
                </label>
                <input
                  id="module-name-edit"
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
                  htmlFor="module-description-edit"
                  className="mb-1 block text-sm font-medium text-zinc-700"
                >
                  Description
                </label>
                <textarea
                  id="module-description-edit"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="min-h-24 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  disabled={isSubmitting}
                />
              </div>

              <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:items-center sm:gap-3">
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                >
                  {isSubmitting ? "Saving..." : "Save Module"}
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
