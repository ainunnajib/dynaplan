import Link from "next/link";
import { getModel, getModules, getLineItems, getDimensions } from "@/lib/api";
import type { PlanningModel, Module, LineItem, Dimension } from "@/lib/api";
import BlueprintTable from "@/components/module/BlueprintTable";

export const metadata = {
  title: "Blueprint — Dynaplan",
};

interface PageProps {
  params: Promise<{ modelId: string }>;
}

export default async function BlueprintPage({ params }: PageProps) {
  const { modelId } = await params;

  let model: PlanningModel | null = null;
  let modules: Module[] = [];
  let dimensions: Dimension[] = [];
  let moduleLineItems: Record<string, LineItem[]> = {};
  let fetchError: string | null = null;

  try {
    [model, modules, dimensions] = await Promise.all([
      getModel(modelId),
      getModules(modelId),
      getDimensions(modelId),
    ]);

    const lineItemResults = await Promise.all(
      modules.map(async (mod) => {
        const items = await getLineItems(mod.id);
        return { moduleId: mod.id, items };
      })
    );

    moduleLineItems = Object.fromEntries(
      lineItemResults.map((r) => [r.moduleId, r.items])
    );
  } catch (err) {
    fetchError = err instanceof Error ? err.message : "Failed to load blueprint";
  }

  return (
    <div className="min-h-screen bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <div className="mx-auto max-w-7xl">
          <nav className="mb-1 flex items-center gap-1 text-xs text-zinc-500">
            <Link href="/workspaces" className="hover:text-zinc-800">
              Workspaces
            </Link>
            <span>/</span>
            <Link href={`/models/${modelId}`} className="hover:text-zinc-800">
              {model?.name ?? modelId}
            </Link>
            <span>/</span>
            <span className="text-zinc-800">Blueprint</span>
          </nav>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-zinc-900">Blueprint</h1>
              <p className="text-sm text-zinc-500">
                {model?.name} — all modules and line items
              </p>
            </div>
            <Link
              href={`/models/${modelId}`}
              className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
            >
              Back to Model
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {fetchError ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {fetchError}
          </div>
        ) : (
          <BlueprintTable
            modelId={modelId}
            modules={modules}
            moduleLineItems={moduleLineItems}
            dimensions={dimensions}
          />
        )}
      </main>
    </div>
  );
}
