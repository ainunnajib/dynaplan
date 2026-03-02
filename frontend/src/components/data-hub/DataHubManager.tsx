"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import {
  createDataHubTable,
  deleteDataHubTable,
  getDataHubLineage,
  getDataHubRows,
  getDataHubTables,
  importDataHubRows,
  publishDataHubTable,
  replaceDataHubRows,
  transformDataHubRows,
  type DataHubLineage,
  type DataHubRow,
  type DataHubTable,
} from "@/lib/api";

interface DataHubManagerProps {
  modelId: string;
}

const DEFAULT_ROWS_JSON = `[
  { "product_code": "P1", "amount": 100 },
  { "product_code": "P2", "amount": 200 }
]`;

const DEFAULT_TRANSFORM_JSON = `[
  {
    "operation_type": "transform",
    "config": { "casts": { "amount": "float" } }
  },
  {
    "operation_type": "filter",
    "config": { "expression": "amount > 0" }
  }
]`;

const DEFAULT_LINE_ITEM_MAP_JSON = `{
  "amount": "<line_item_uuid>"
}`;

const DEFAULT_DIMENSION_MAP_JSON = `{
  "product_code": {
    "P1": "<dimension_member_uuid_1>",
    "P2": "<dimension_member_uuid_2>"
  }
}`;

function parseJsonValue<T>(raw: string, label: string): T {
  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new Error(`Invalid ${label} JSON`);
  }
}

export default function DataHubManager({ modelId }: DataHubManagerProps) {
  const { token } = useAuth();
  const [tables, setTables] = useState<DataHubTable[]>([]);
  const [selectedTableId, setSelectedTableId] = useState<string>("");
  const [rows, setRows] = useState<DataHubRow[]>([]);
  const [lineage, setLineage] = useState<DataHubLineage[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const [newTableName, setNewTableName] = useState<string>("");
  const [rowsJson, setRowsJson] = useState<string>(DEFAULT_ROWS_JSON);
  const [importPath, setImportPath] = useState<string>("");
  const [transformJson, setTransformJson] = useState<string>(DEFAULT_TRANSFORM_JSON);
  const [publishModuleId, setPublishModuleId] = useState<string>("");
  const [lineItemMapJson, setLineItemMapJson] = useState<string>(DEFAULT_LINE_ITEM_MAP_JSON);
  const [dimensionColumnsRaw, setDimensionColumnsRaw] = useState<string>("product_code");
  const [dimensionMapJson, setDimensionMapJson] = useState<string>(DEFAULT_DIMENSION_MAP_JSON);

  const selectedTable = useMemo(
    () => tables.find((table) => table.id === selectedTableId) ?? null,
    [selectedTableId, tables]
  );

  const loadTables = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const fetchedTables = await getDataHubTables(modelId);
      setTables(fetchedTables);
      if (fetchedTables.length > 0) {
        setSelectedTableId((current) =>
          fetchedTables.some((table) => table.id === current)
            ? current
            : fetchedTables[0].id
        );
      } else {
        setSelectedTableId("");
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Data Hub tables");
    } finally {
      setLoading(false);
    }
  }, [modelId, token]);

  const loadTableDetails = useCallback(async () => {
    if (!token || !selectedTableId) {
      setRows([]);
      setLineage([]);
      return;
    }
    try {
      const [rowPayload, lineagePayload] = await Promise.all([
        getDataHubRows(selectedTableId, { offset: 0, limit: 100 }),
        getDataHubLineage(selectedTableId),
      ]);
      setRows(rowPayload.rows);
      setLineage(lineagePayload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load table details");
    }
  }, [selectedTableId, token]);

  useEffect(() => {
    void loadTables();
  }, [loadTables]);

  useEffect(() => {
    void loadTableDetails();
  }, [loadTableDetails]);

  const handleCreateTable = useCallback(async () => {
    if (!newTableName.trim()) return;
    try {
      await createDataHubTable(modelId, { name: newTableName.trim() });
      setNewTableName("");
      setStatusMessage("Created Data Hub table");
      await loadTables();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create Data Hub table");
    }
  }, [loadTables, modelId, newTableName]);

  const handleDeleteTable = useCallback(async () => {
    if (!selectedTableId) return;
    try {
      await deleteDataHubTable(selectedTableId);
      setStatusMessage("Deleted Data Hub table");
      await loadTables();
      setRows([]);
      setLineage([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete Data Hub table");
    }
  }, [loadTables, selectedTableId]);

  const handleReplaceRows = useCallback(async () => {
    if (!selectedTableId) return;
    try {
      const parsedRows = parseJsonValue<Array<Record<string, unknown>>>(rowsJson, "rows");
      await replaceDataHubRows(selectedTableId, parsedRows, true);
      setStatusMessage(`Replaced ${parsedRows.length} row(s)`);
      await loadTables();
      await loadTableDetails();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to replace rows");
    }
  }, [loadTableDetails, loadTables, rowsJson, selectedTableId]);

  const handleImportFromLocalFile = useCallback(async () => {
    if (!selectedTableId || !importPath.trim()) return;
    try {
      const response = await importDataHubRows(selectedTableId, {
        connector_type: "local_file",
        connector_config: { path: importPath.trim(), format: "csv" },
        replace_existing: true,
        infer_schema: true,
      });
      setStatusMessage(`Imported ${response.rows_imported} row(s) from ${importPath.trim()}`);
      await loadTables();
      await loadTableDetails();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import rows");
    }
  }, [importPath, loadTableDetails, loadTables, selectedTableId]);

  const handleTransformRows = useCallback(async () => {
    if (!selectedTableId) return;
    try {
      const operations = parseJsonValue<
        Array<{
          operation_type: "transform" | "filter" | "map" | "aggregate";
          config: Record<string, unknown>;
          name?: string;
        }>
      >(transformJson, "transform operations");
      const transformed = await transformDataHubRows(selectedTableId, {
        operations,
        replace_existing: true,
      });
      setStatusMessage(
        `Transformed rows (${transformed.rows_before} -> ${transformed.rows_after})`
      );
      await loadTables();
      await loadTableDetails();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to transform rows");
    }
  }, [loadTableDetails, loadTables, selectedTableId, transformJson]);

  const handlePublish = useCallback(async () => {
    if (!selectedTableId || !publishModuleId.trim()) return;
    try {
      const lineItemMap = parseJsonValue<Record<string, string>>(
        lineItemMapJson,
        "line_item_map"
      );
      const dimensionMemberMap = parseJsonValue<Record<string, Record<string, string>>>(
        dimensionMapJson,
        "dimension_member_map"
      );
      const dimensionColumns = dimensionColumnsRaw
        .split(",")
        .map((value) => value.trim())
        .filter((value) => value.length > 0);

      const publishResult = await publishDataHubTable(selectedTableId, {
        module_id: publishModuleId.trim(),
        line_item_map: lineItemMap,
        dimension_columns: dimensionColumns,
        dimension_member_map: dimensionMemberMap,
      });
      setStatusMessage(
        `Published ${publishResult.cells_written} cell(s) to module ${publishResult.target_module_id}`
      );
      await loadTableDetails();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish table");
    }
  }, [
    dimensionColumnsRaw,
    dimensionMapJson,
    lineItemMapJson,
    loadTableDetails,
    publishModuleId,
    selectedTableId,
  ]);

  if (!token) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-4">
        <h2 className="text-base font-semibold text-zinc-900">Data Hub</h2>
        <p className="mt-1 text-sm text-zinc-500">Sign in to manage staging tables.</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-900">Data Hub</h2>
          <p className="text-sm text-zinc-500">
            Stage connector data, transform in-place, and publish to model modules.
          </p>
        </div>
        <div className="flex w-full gap-2 sm:w-auto">
          <input
            value={newTableName}
            onChange={(event) => setNewTableName(event.target.value)}
            placeholder="new_table_name"
            className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm sm:w-56"
          />
          <button
            onClick={handleCreateTable}
            className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white hover:bg-zinc-700"
          >
            Create
          </button>
        </div>
      </div>

      {loading ? (
        <p className="mt-4 text-sm text-zinc-500">Loading Data Hub...</p>
      ) : (
        <>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
            <select
              value={selectedTableId}
              onChange={(event) => setSelectedTableId(event.target.value)}
              className="rounded border border-zinc-300 px-2 py-1.5 text-sm"
            >
              {tables.length === 0 && <option value="">No tables</option>}
              {tables.map((table) => (
                <option key={table.id} value={table.id}>
                  {table.name} ({table.row_count} rows)
                </option>
              ))}
            </select>
            <button
              onClick={handleDeleteTable}
              disabled={!selectedTableId}
              className="rounded border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Delete Table
            </button>
          </div>

          {selectedTable && (
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div className="space-y-3 rounded border border-zinc-200 bg-zinc-50 p-3">
                <h3 className="text-sm font-medium text-zinc-800">Rows</h3>
                <textarea
                  value={rowsJson}
                  onChange={(event) => setRowsJson(event.target.value)}
                  rows={8}
                  className="w-full rounded border border-zinc-300 px-2 py-1.5 font-mono text-xs"
                />
                <button
                  onClick={handleReplaceRows}
                  className="rounded border border-zinc-300 px-3 py-1.5 text-sm hover:bg-white"
                >
                  Replace Rows (Infer Schema)
                </button>

                <div className="space-y-2 pt-2">
                  <input
                    value={importPath}
                    onChange={(event) => setImportPath(event.target.value)}
                    placeholder="/absolute/path/to/file.csv"
                    className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm"
                  />
                  <button
                    onClick={handleImportFromLocalFile}
                    className="rounded border border-zinc-300 px-3 py-1.5 text-sm hover:bg-white"
                  >
                    Import From Local File Connector
                  </button>
                </div>

                <div className="max-h-40 overflow-auto rounded border border-zinc-200 bg-white p-2">
                  {rows.length === 0 ? (
                    <p className="text-xs text-zinc-400">No rows loaded.</p>
                  ) : (
                    <pre className="text-xs text-zinc-700">
                      {JSON.stringify(rows.slice(0, 10).map((row) => row.row_data), null, 2)}
                    </pre>
                  )}
                </div>
              </div>

              <div className="space-y-3 rounded border border-zinc-200 bg-zinc-50 p-3">
                <h3 className="text-sm font-medium text-zinc-800">Transform + Publish</h3>
                <textarea
                  value={transformJson}
                  onChange={(event) => setTransformJson(event.target.value)}
                  rows={6}
                  className="w-full rounded border border-zinc-300 px-2 py-1.5 font-mono text-xs"
                />
                <button
                  onClick={handleTransformRows}
                  className="rounded border border-zinc-300 px-3 py-1.5 text-sm hover:bg-white"
                >
                  Run Transform Operations
                </button>

                <input
                  value={publishModuleId}
                  onChange={(event) => setPublishModuleId(event.target.value)}
                  placeholder="target module UUID"
                  className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm"
                />
                <textarea
                  value={lineItemMapJson}
                  onChange={(event) => setLineItemMapJson(event.target.value)}
                  rows={3}
                  className="w-full rounded border border-zinc-300 px-2 py-1.5 font-mono text-xs"
                />
                <input
                  value={dimensionColumnsRaw}
                  onChange={(event) => setDimensionColumnsRaw(event.target.value)}
                  placeholder="dimension columns (comma separated)"
                  className="w-full rounded border border-zinc-300 px-2 py-1.5 text-sm"
                />
                <textarea
                  value={dimensionMapJson}
                  onChange={(event) => setDimensionMapJson(event.target.value)}
                  rows={4}
                  className="w-full rounded border border-zinc-300 px-2 py-1.5 font-mono text-xs"
                />
                <button
                  onClick={handlePublish}
                  className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
                >
                  Publish To Module
                </button>

                <div className="max-h-32 overflow-auto rounded border border-zinc-200 bg-white p-2">
                  {lineage.length === 0 ? (
                    <p className="text-xs text-zinc-400">No lineage recorded yet.</p>
                  ) : (
                    <pre className="text-xs text-zinc-700">
                      {JSON.stringify(lineage, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {statusMessage && (
        <p className="mt-3 rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
          {statusMessage}
        </p>
      )}
      {error && (
        <p className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </section>
  );
}
