import type { Metadata } from "next";
import {
  getModule,
  getLineItems,
  getDimensions,
  getDimensionItems,
  getCells,
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

  // Fetch all data in parallel
  const [mod, lineItems, dimensions, cells] = await Promise.all([
    getModule(moduleId),
    getLineItems(moduleId),
    getDimensions(modelId),
    getCells(moduleId),
  ]);

  // Fetch dimension items for all dimensions
  const dimensionItemsNested = await Promise.all(
    dimensions.map((d) => getDimensionItems(d.id))
  );
  const dimensionItems: DimensionItem[] = dimensionItemsNested.flat();

  return (
    <div className="flex flex-col gap-4 p-6">
      {/* Module header */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2 text-sm text-gray-400">
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

        <div className="mt-1 flex items-center gap-4 text-xs text-gray-400">
          <span>{lineItems.length} line items</span>
          <span>{dimensions.length} dimensions</span>
          <span>{cells.length} cells</span>
        </div>
      </div>

      {/* Grid */}
      <ModuleGridClient
        moduleId={moduleId}
        lineItems={lineItems}
        dimensions={dimensions}
        dimensionItems={dimensionItems}
        initialCells={cells}
      />
    </div>
  );
}
