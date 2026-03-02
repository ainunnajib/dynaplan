import type { Metadata } from "next";
import {
  getModule,
  getLineItems,
  getDimensions,
  getDimensionItems,
  type DimensionItem,
} from "@/lib/api";
import ModuleGridClient from "./ModuleGridClient";

interface ModulePageProps {
  params: Promise<{ modelId: string; moduleId: string }>;
}

export async function generateMetadata({
  params,
}: ModulePageProps): Promise<Metadata> {
  const { moduleId } = await params;
  try {
    const mod = await getModule(moduleId);
    return { title: `${mod.name} — Dynaplan` };
  } catch {
    return { title: "Module — Dynaplan" };
  }
}

export default async function ModulePage({ params }: ModulePageProps) {
  const { modelId, moduleId } = await params;

  // Keep SSR payload small to avoid Cloud Run memory pressure on large modules.
  // Cell values are hydrated client-side in the grid.
  const [mod, lineItems, dimensions] = await Promise.all([
    getModule(moduleId),
    getLineItems(moduleId),
    getDimensions(modelId),
  ]);

  // Fetch dimension items for all dimensions
  const dimensionItemsNested = await Promise.all(
    dimensions.map((d) => getDimensionItems(d.id))
  );
  const dimensionItems: DimensionItem[] = dimensionItemsNested.flat();

  return (
    <div className="flex flex-col gap-4 p-3 sm:p-4 md:p-6">
      {/* Module header */}
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-1.5 text-sm text-gray-400">
          <a
            href={`/models/${modelId}`}
            className="hover:text-blue-600 hover:underline"
          >
            Model
          </a>
          <span>/</span>
          <span>Modules</span>
          <span>/</span>
          <span className="text-gray-600">{mod.name}</span>
        </div>

        <h1 className="text-2xl font-semibold text-gray-900">{mod.name}</h1>

        {mod.description && (
          <p className="text-sm text-gray-500">{mod.description}</p>
        )}

        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-400">
          <span>{lineItems.length} line items</span>
          <span>{dimensions.length} dimensions</span>
          <span>cells loaded on demand</span>
        </div>
      </div>

      {/* Grid */}
      <ModuleGridClient
        moduleId={moduleId}
        lineItems={lineItems}
        dimensions={dimensions}
        dimensionItems={dimensionItems}
        initialCells={[]}
      />
    </div>
  );
}
