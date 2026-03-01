"use client";

import DataGrid from "@/components/grid/DataGrid";
import type {
  CellValue,
  Dimension,
  DimensionItem,
  LineItem,
} from "@/lib/api";

interface ModuleGridClientProps {
  moduleId: string;
  lineItems: LineItem[];
  dimensions: Dimension[];
  dimensionItems: DimensionItem[];
  initialCells: CellValue[];
}

/**
 * Client boundary for the module grid view.
 * Hands off to DataGrid which manages its own cell cache via useCellData.
 */
export default function ModuleGridClient({
  moduleId,
  lineItems,
  dimensions,
  dimensionItems,
  initialCells,
}: ModuleGridClientProps) {
  return (
    <DataGrid
      moduleId={moduleId}
      lineItems={lineItems}
      dimensions={dimensions}
      dimensionItems={dimensionItems}
      initialCells={initialCells}
    />
  );
}
