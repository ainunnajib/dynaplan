"use client";

import { useCallback, useState } from "react";
import DataGrid from "@/components/grid/DataGrid";
import SavedViewToolbar from "@/components/saved-view/SavedViewToolbar";
import type {
  CellValue,
  Dimension,
  DimensionItem,
  LineItem,
  SavedViewConfig,
} from "@/lib/api";
import { DEFAULT_SAVED_VIEW_CONFIG as defaultSavedViewConfig } from "@/lib/api";

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
  const [currentViewConfig, setCurrentViewConfig] = useState<SavedViewConfig>(
    defaultSavedViewConfig
  );

  const handleViewConfigChange = useCallback((nextConfig: SavedViewConfig) => {
    setCurrentViewConfig((prev) => {
      if (JSON.stringify(prev) === JSON.stringify(nextConfig)) {
        return prev;
      }
      return nextConfig;
    });
  }, []);

  return (
    <div className="flex flex-col gap-3">
      <SavedViewToolbar
        moduleId={moduleId}
        currentViewConfig={currentViewConfig}
        onApplyViewConfig={handleViewConfigChange}
      />
      <DataGrid
        moduleId={moduleId}
        lineItems={lineItems}
        dimensions={dimensions}
        dimensionItems={dimensionItems}
        initialCells={initialCells}
        appliedViewConfig={currentViewConfig}
        onViewConfigChange={handleViewConfigChange}
      />
    </div>
  );
}
