"use client";

import { useCallback, useEffect, useState } from "react";
import DataGrid from "@/components/grid/DataGrid";
import ConditionalFormattingSettings from "@/components/grid/ConditionalFormattingSettings";
import SavedViewToolbar from "@/components/saved-view/SavedViewToolbar";
import type {
  CellValue,
  ConditionalFormatRule,
  Dimension,
  DimensionItem,
  LineItem,
  SavedViewConfig,
} from "@/lib/api";
import { DEFAULT_SAVED_VIEW_CONFIG as defaultSavedViewConfig } from "@/lib/api";

interface ModuleGridClientProps {
  modelId: string;
  moduleId: string;
  lineItems: LineItem[];
  dimensions: Dimension[];
  dimensionItems: DimensionItem[];
  initialCells: CellValue[];
  moduleConditionalFormatRules: ConditionalFormatRule[];
}

/**
 * Client boundary for the module grid view.
 * Hands off to DataGrid which manages its own cell cache via useCellData.
 */
export default function ModuleGridClient({
  modelId,
  moduleId,
  lineItems,
  dimensions,
  dimensionItems,
  initialCells,
  moduleConditionalFormatRules,
}: ModuleGridClientProps) {
  const [currentViewConfig, setCurrentViewConfig] = useState<SavedViewConfig>(
    defaultSavedViewConfig
  );
  const [lineItemsState, setLineItemsState] = useState<LineItem[]>(lineItems);
  const [moduleRules, setModuleRules] = useState<ConditionalFormatRule[]>(
    moduleConditionalFormatRules
  );

  useEffect(() => {
    setLineItemsState(lineItems);
  }, [lineItems]);

  useEffect(() => {
    setModuleRules(moduleConditionalFormatRules);
  }, [moduleConditionalFormatRules]);

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
      <ConditionalFormattingSettings
        moduleId={moduleId}
        lineItems={lineItemsState}
        moduleRules={moduleRules}
        onLineItemRulesSaved={(lineItemId, rules) => {
          setLineItemsState((prev) =>
            prev.map((lineItem) =>
              lineItem.id === lineItemId
                ? { ...lineItem, conditional_format_rules: rules }
                : lineItem
            )
          );
        }}
        onModuleRulesSaved={(rules) => {
          setModuleRules(rules);
        }}
      />
      <SavedViewToolbar
        moduleId={moduleId}
        currentViewConfig={currentViewConfig}
        onApplyViewConfig={handleViewConfigChange}
      />
      <DataGrid
        modelId={modelId}
        moduleId={moduleId}
        lineItems={lineItemsState}
        moduleConditionalFormatRules={moduleRules}
        dimensions={dimensions}
        dimensionItems={dimensionItems}
        initialCells={initialCells}
        appliedViewConfig={currentViewConfig}
        onViewConfigChange={handleViewConfigChange}
      />
    </div>
  );
}
