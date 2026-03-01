import type { ReactNode } from "react";
import Link from "next/link";
import { getModel, getModules, getDimensions, getDimensionItems } from "@/lib/api";
import type { PlanningModel, Module, Dimension } from "@/lib/api";
import ModuleCard from "@/components/module/ModuleCard";
import CreateModuleDialog from "@/components/module/CreateModuleDialog";

export const metadata = {
  title: "Model — Dynaplan",
};

interface PageProps {
  params: Promise<{ modelId: string }>;
}

export default async function ModelPage({ params }: PageProps) {
  const { modelId } = await params;

  let model: PlanningModel | null = null;
  let modules: Module[] = [];
  let dimensions: Dimension[] = [];
  let fetchError: string | null = null;

  try {
    [model, modules, dimensions] = await Promise.all([
      getModel(modelId),
      getModules(modelId),
      getDimensions(modelId),
    ]);
  } catch (err) {
    fetchError = err instanceof Error ? err.message : "Failed to load model";
  }

  // Fetch dimension item counts in parallel
  let dimensionCounts: Record<string, number> = {};
  if (dimensions.length > 0) {
    try {
      const counts = await Promise.all(
        dimensions.map(async (dim) => {
          const items = await getDimensionItems(dim.id);
          return { id: dim.id, count: items.length };
        })
      );
      dimensionCounts = Object.fromEntries(counts.map((c) => [c.id, c.count]));
    } catch {
      // non-fatal — counts just won't show
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <div className="mx-auto max-w-6xl">
          <nav className="mb-1 flex items-center gap-1 text-xs text-zinc-500">
            <Link href="/workspaces" className="hover:text-zinc-800">
              Workspaces
            </Link>
            {model && (
              <>
                <span>/</span>
                <Link
                  href={`/workspaces/${model.workspace_id}`}
                  className="hover:text-zinc-800"
                >
                  Workspace
                </Link>
              </>
            )}
            <span>/</span>
            <span className="text-zinc-800">{model?.name ?? modelId}</span>
          </nav>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-zinc-900">
                {model?.name ?? "Model"}
              </h1>
              {model?.description && (
                <p className="text-sm text-zinc-500">{model.description}</p>
              )}
            </div>
            <div className="flex items-center gap-3">
              <Link
                href={
                  model
                    ? `/workspaces/${model.workspace_id}/models/new`
                    : "/workspaces"
                }
                className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
              >
                Create Model
              </Link>
              <Link
                href={`/models/${modelId}/edit`}
                className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
              >
                Edit Model
              </Link>
              <Link
                href={`/models/${modelId}/blueprint`}
                className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
              >
                Blueprint View
              </Link>
              <CreateModuleDialog modelId={modelId} />
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        {fetchError ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {fetchError}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
            {/* Modules section */}
            <div className="lg:col-span-2">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-zinc-800">
                  Modules
                  {modules.length > 0 && (
                    <span className="ml-2 text-sm font-normal text-zinc-500">
                      ({modules.length})
                    </span>
                  )}
                </h2>
              </div>

              {modules.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-300 bg-white py-12 text-center">
                  <CubeIcon className="h-8 w-8 text-zinc-400" />
                  <h3 className="mt-3 text-sm font-medium text-zinc-600">No modules yet</h3>
                  <p className="mt-1 text-xs text-zinc-400">
                    Modules contain your line items and calculations.
                  </p>
                  <div className="mt-4">
                    <CreateModuleDialog modelId={modelId} />
                  </div>
                </div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {modules.map((mod) => (
                    <ModuleCard key={mod.id} module={mod} modelId={modelId} />
                  ))}
                </div>
              )}
            </div>

            {/* Dimensions sidebar */}
            <div>
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold text-zinc-800">
                  Dimensions
                  {dimensions.length > 0 && (
                    <span className="ml-2 text-sm font-normal text-zinc-500">
                      ({dimensions.length})
                    </span>
                  )}
                </h2>
              </div>

              {dimensions.length === 0 ? (
                <div className="rounded-lg border border-dashed border-zinc-300 bg-white p-6 text-center">
                  <p className="text-xs text-zinc-500">No dimensions defined</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {dimensions.map((dim) => (
                    <DimensionRow
                      key={dim.id}
                      dimension={dim}
                      itemCount={dimensionCounts[dim.id] ?? 0}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function DimensionRow({
  dimension,
  itemCount,
}: {
  dimension: Dimension;
  itemCount: number;
}) {
  const typeConfig: Record<
    Dimension["type"],
    { icon: ReactNode; color: string; label: string }
  > = {
    time: {
      icon: <ClockIcon className="h-3.5 w-3.5" />,
      color: "text-blue-600 bg-blue-50",
      label: "Time",
    },
    version: {
      icon: <LayersIcon className="h-3.5 w-3.5" />,
      color: "text-purple-600 bg-purple-50",
      label: "Version",
    },
    custom: {
      icon: <ListIcon className="h-3.5 w-3.5" />,
      color: "text-zinc-600 bg-zinc-100",
      label: "Custom",
    },
    numbered: {
      icon: <ListIcon className="h-3.5 w-3.5" />,
      color: "text-emerald-700 bg-emerald-50",
      label: "Numbered",
    },
  };

  const config = typeConfig[dimension.type];

  return (
    <div className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white px-3 py-2.5">
      <div className="flex items-center gap-2">
        <span className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-xs ${config.color}`}>
          {config.icon}
          {config.label}
        </span>
        <span className="text-sm font-medium text-zinc-800">{dimension.name}</span>
      </div>
      <span className="text-xs text-zinc-400">{itemCount} items</span>
    </div>
  );
}

function CubeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 7.5-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

function LayersIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.429 9.75 2.25 12l4.179 2.25m0-4.5 5.571 3 5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L21.75 12l-4.179 2.25m0 0 4.179 2.25L12 21.75 2.25 16.5l4.179-2.25m11.142 0-5.571 3-5.571-3" />
    </svg>
  );
}

function ListIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM3.75 12h.007v.008H3.75V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
    </svg>
  );
}
