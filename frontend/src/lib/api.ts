const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "dynaplan_token";

function normalizePath(path: string): string {
  const [rawPath, rawQuery] = path.split("?");
  let normalized = rawPath;

  // Frontend still uses legacy "/api/*" paths in many places.
  if (normalized === "/api") {
    normalized = "/";
  } else if (normalized.startsWith("/api/")) {
    normalized = normalized.slice(4);
  }

  // Backend lists models by workspace at "/models/workspace/{workspace_id}".
  const workspaceModelsMatch = normalized.match(/^\/workspaces\/([^/]+)\/models$/);
  if (workspaceModelsMatch) {
    normalized = `/models/workspace/${workspaceModelsMatch[1]}`;
  }

  // FastAPI route is defined at "/workspaces/" and may redirect if slash is missing.
  if (normalized === "/workspaces") {
    normalized = "/workspaces/";
  }

  return rawQuery ? `${normalized}?${rawQuery}` : normalized;
}

async function getAuthToken(): Promise<string | null> {
  if (typeof window !== "undefined") {
    return localStorage.getItem(TOKEN_KEY);
  }

  try {
    const { cookies } = await import("next/headers");
    const cookieStore = await cookies();
    return cookieStore.get(TOKEN_KEY)?.value ?? null;
  } catch {
    return null;
  }
}

export async function fetchApi<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getAuthToken();
  const normalizedPath = normalizePath(path);
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${normalizedPath}`, {
    cache: options.cache ?? "no-store",
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const message =
      (errorBody as { error?: string; detail?: string }).error ??
      (errorBody as { error?: string; detail?: string }).detail ??
      `Request failed: ${response.status} ${response.statusText}`;
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// ── Type definitions matching backend schemas ─────────────────────────────────

export interface Workspace {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceQuotaUsageModel {
  model_id: string;
  model_name: string;
  dimension_count: number;
  cell_count: number;
  storage_used_bytes: number;
  storage_used_mb: number;
}

export interface WorkspaceQuotaUsage {
  workspace_id: string;
  max_models: number;
  max_cells_per_model: number;
  max_dimensions_per_model: number;
  storage_limit_mb: number;
  model_count: number;
  total_dimension_count: number;
  total_cell_count: number;
  storage_used_bytes: number;
  storage_used_mb: number;
  models: WorkspaceQuotaUsageModel[];
}

export interface PlanningModel {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  // Newer backend responses expose is_archived, while older UI code used status.
  is_archived?: boolean;
  status?: "active" | "archived";
  created_at: string;
  updated_at: string;
}

export function getModelStatus(model: PlanningModel): "active" | "archived" {
  if (model.status) return model.status;
  return model.is_archived ? "archived" : "active";
}

export interface Module {
  id: string;
  model_id: string;
  name: string;
  description: string | null;
  conditional_format_rules: ConditionalFormatRule[];
  created_at: string;
  updated_at: string;
}

export type LineItemFormat =
  | "number"
  | "text"
  | "boolean"
  | "date"
  | "list"
  | "currency"
  | "percentage";

export interface LineItem {
  id: string;
  module_id: string;
  name: string;
  formula: string | null;
  format: LineItemFormat;
  // Backend currently returns applies_to_dimensions.
  // Keep legacy field for compatibility with older payloads.
  applies_to_dimensions?: string[];
  applies_to_dimension_ids?: string[];
  summary_method:
    | "sum"
    | "average"
    | "min"
    | "max"
    | "none"
    | "formula"
    | "first"
    | "last"
    | "opening_balance"
    | "closing_balance"
    | "weighted_average"
    | null;
  conditional_format_rules: ConditionalFormatRule[];
  created_at: string;
  updated_at: string;
}

export function getLineItemDimensionIds(lineItem: LineItem): string[] {
  return lineItem.applies_to_dimension_ids ?? lineItem.applies_to_dimensions ?? [];
}

export interface Dimension {
  id: string;
  model_id: string;
  name: string;
  type: "custom" | "time" | "version" | "numbered" | "composite";
  dimension_type?: "custom" | "time" | "version" | "numbered" | "composite";
  created_at: string;
  updated_at: string;
}

export interface DimensionItem {
  id: string;
  dimension_id: string;
  name: string;
  code?: string;
  parent_id: string | null;
  order: number;
  sort_order?: number;
  created_at: string;
  updated_at: string;
}

export interface CellValue {
  line_item_id: string;
  dimension_member_ids: string[];
  value: number | string | boolean | null;
}

export interface ModuleCellsPageResponse {
  cells: CellValue[];
  total_count: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export interface DimensionItemsPageResponse {
  items: DimensionItem[];
  total_count: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export type ConditionalFormatOperator =
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "eq"
  | "neq";

export type ConditionalNumberFormat = "number" | "currency" | "percentage";

export interface ConditionalFormatStyle {
  background_color?: string | null;
  text_color?: string | null;
  bold?: boolean | null;
  italic?: boolean | null;
  number_format?: ConditionalNumberFormat | null;
  icon?: string | null;
}

export interface ConditionalFormatRule {
  id: string;
  name?: string | null;
  enabled: boolean;
  operator: ConditionalFormatOperator;
  value: number | string | boolean;
  style: ConditionalFormatStyle;
}

export interface SavedViewSortConfig {
  column_key: string | null;
  direction: "asc" | "desc";
}

export interface SavedViewConfig {
  row_dims: string[];
  col_dims: string[];
  filters: Record<string, string[]>;
  sort: SavedViewSortConfig;
}

export const DEFAULT_SAVED_VIEW_CONFIG: SavedViewConfig = {
  row_dims: [],
  col_dims: [],
  filters: {},
  sort: {
    column_key: null,
    direction: "asc",
  },
};

export interface SavedView {
  id: string;
  user_id: string;
  module_id: string;
  name: string;
  view_config: SavedViewConfig;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface SavedViewCreateInput {
  name: string;
  view_config?: SavedViewConfig;
  is_default?: boolean;
}

export interface SavedViewUpdateInput {
  name?: string;
  view_config?: SavedViewConfig;
  is_default?: boolean;
}

export type DataHubColumnType =
  | "text"
  | "integer"
  | "number"
  | "boolean"
  | "date"
  | "datetime";

export interface DataHubColumnSchema {
  name: string;
  data_type: DataHubColumnType;
  nullable: boolean;
}

export interface DataHubTable {
  id: string;
  model_id: string;
  name: string;
  description: string | null;
  schema_definition: DataHubColumnSchema[];
  row_count: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface DataHubRow {
  id: string;
  table_id: string;
  sort_order: number;
  row_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DataHubRowsListResponse {
  total_count: number;
  rows: DataHubRow[];
}

export interface DataHubLineage {
  id: string;
  table_id: string;
  target_model_id: string;
  target_module_id: string | null;
  mapping_config: Record<string, unknown>;
  records_published: number;
  last_published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DataHubImportResponse {
  table: DataHubTable;
  rows_imported: number;
}

export interface DataHubTransformResponse {
  table: DataHubTable;
  rows_before: number;
  rows_after: number;
}

export interface DataHubPublishResponse {
  table_id: string;
  lineage_id: string;
  target_model_id: string;
  target_module_id: string | null;
  rows_processed: number;
  cells_written: number;
  last_published_at: string | null;
}

// ── API helpers ───────────────────────────────────────────────────────────────

export async function getWorkspaces(): Promise<Workspace[]> {
  return fetchApi<Workspace[]>("/api/workspaces/");
}

export async function getWorkspaceQuotaUsage(
  workspaceId: string
): Promise<WorkspaceQuotaUsage> {
  return fetchApi<WorkspaceQuotaUsage>(
    `/api/workspaces/${workspaceId}/quota/usage`
  );
}

export async function getModels(workspaceId: string): Promise<PlanningModel[]> {
  return fetchApi<PlanningModel[]>(
    `/api/workspaces/${workspaceId}/models`
  );
}

export async function getModel(modelId: string): Promise<PlanningModel> {
  return fetchApi<PlanningModel>(`/api/models/${modelId}`);
}

export async function getModules(modelId: string): Promise<Module[]> {
  return fetchApi<Module[]>(`/api/models/${modelId}/modules`);
}

export async function getModule(moduleId: string): Promise<Module> {
  return fetchApi<Module>(`/api/modules/${moduleId}`);
}

export async function getLineItems(moduleId: string): Promise<LineItem[]> {
  return fetchApi<LineItem[]>(`/api/modules/${moduleId}/line-items`);
}

export async function getDimensions(modelId: string): Promise<Dimension[]> {
  const rows = await fetchApi<Array<Dimension & { dimension_type?: Dimension["type"] }>>(
    `/api/models/${modelId}/dimensions`
  );
  return rows.map((row) => ({
    ...row,
    type: row.type ?? row.dimension_type ?? "custom",
  }));
}

export async function getDimensionItems(
  dimensionId: string
): Promise<DimensionItem[]> {
  const allItems: DimensionItem[] = [];
  let offset = 0;
  const limit = 500;

  while (true) {
    const page = await getDimensionItemsPage(dimensionId, { offset, limit });
    allItems.push(...page.items);
    if (!page.has_more) break;
    offset += page.limit;
  }

  return allItems;
}

export async function getDimensionItemsPage(
  dimensionId: string,
  params?: { offset?: number; limit?: number; search?: string }
): Promise<DimensionItemsPageResponse> {
  const searchParams = new URLSearchParams();
  if (params?.offset !== undefined) {
    searchParams.set("offset", String(params.offset));
  }
  if (params?.limit !== undefined) {
    searchParams.set("limit", String(params.limit));
  }
  if (params?.search) {
    searchParams.set("search", params.search);
  }
  const query = searchParams.toString();
  const payload = await fetchApi<
    Omit<DimensionItemsPageResponse, "items"> & {
      items: Array<DimensionItem & { sort_order?: number }>;
    }
  >(`/api/dimensions/${dimensionId}/items/page${query ? `?${query}` : ""}`);
  return {
    ...payload,
    items: payload.items.map((row) => ({
      ...row,
      order: row.order ?? row.sort_order ?? 0,
    })),
  };
}

export async function getCells(moduleId: string): Promise<CellValue[]> {
  return fetchApi<CellValue[]>(`/api/modules/${moduleId}/cells`);
}

export async function getCellsPage(
  moduleId: string,
  params?: { offset?: number; limit?: number }
): Promise<ModuleCellsPageResponse> {
  const searchParams = new URLSearchParams();
  if (params?.offset !== undefined) {
    searchParams.set("offset", String(params.offset));
  }
  if (params?.limit !== undefined) {
    searchParams.set("limit", String(params.limit));
  }
  const query = searchParams.toString();
  return fetchApi<ModuleCellsPageResponse>(
    `/api/modules/${moduleId}/cells/page${query ? `?${query}` : ""}`
  );
}

export async function updateCell(
  moduleId: string,
  cell: CellValue
): Promise<CellValue> {
  return fetchApi<CellValue>(`/api/modules/${moduleId}/cells`, {
    method: "PUT",
    body: JSON.stringify(cell),
  });
}

export async function getSavedViews(moduleId: string): Promise<SavedView[]> {
  return fetchApi<SavedView[]>(`/api/modules/${moduleId}/saved-views`);
}

export async function createSavedView(
  moduleId: string,
  data: SavedViewCreateInput
): Promise<SavedView> {
  return fetchApi<SavedView>(`/api/modules/${moduleId}/saved-views`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSavedView(
  savedViewId: string,
  data: SavedViewUpdateInput
): Promise<SavedView> {
  return fetchApi<SavedView>(`/api/saved-views/${savedViewId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function setSavedViewDefault(savedViewId: string): Promise<SavedView> {
  return fetchApi<SavedView>(`/api/saved-views/${savedViewId}/default`, {
    method: "PUT",
  });
}

export async function deleteSavedView(savedViewId: string): Promise<void> {
  return fetchApi<void>(`/api/saved-views/${savedViewId}`, {
    method: "DELETE",
  });
}

export async function getDataHubTables(modelId: string): Promise<DataHubTable[]> {
  return fetchApi<DataHubTable[]>(`/api/models/${modelId}/data-hub/tables`);
}

export async function createDataHubTable(
  modelId: string,
  data: {
    name: string;
    description?: string;
    schema_definition?: DataHubColumnSchema[];
  }
): Promise<DataHubTable> {
  return fetchApi<DataHubTable>(`/api/models/${modelId}/data-hub/tables`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateDataHubTable(
  tableId: string,
  data: {
    name?: string;
    description?: string | null;
    schema_definition?: DataHubColumnSchema[];
  }
): Promise<DataHubTable> {
  return fetchApi<DataHubTable>(`/api/data-hub/tables/${tableId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteDataHubTable(tableId: string): Promise<void> {
  return fetchApi<void>(`/api/data-hub/tables/${tableId}`, {
    method: "DELETE",
  });
}

export async function getDataHubRows(
  tableId: string,
  params?: { offset?: number; limit?: number }
): Promise<DataHubRowsListResponse> {
  const search = new URLSearchParams();
  if (params?.offset !== undefined) {
    search.set("offset", String(params.offset));
  }
  if (params?.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  const query = search.toString();
  return fetchApi<DataHubRowsListResponse>(
    `/api/data-hub/tables/${tableId}/rows${query ? `?${query}` : ""}`
  );
}

export async function replaceDataHubRows(
  tableId: string,
  rows: Array<Record<string, unknown>>,
  inferSchema = false
): Promise<DataHubTable> {
  return fetchApi<DataHubTable>(`/api/data-hub/tables/${tableId}/rows`, {
    method: "PUT",
    body: JSON.stringify({
      rows,
      infer_schema: inferSchema,
    }),
  });
}

export async function appendDataHubRows(
  tableId: string,
  rows: Array<Record<string, unknown>>,
  inferSchema = false
): Promise<DataHubTable> {
  return fetchApi<DataHubTable>(`/api/data-hub/tables/${tableId}/rows/append`, {
    method: "POST",
    body: JSON.stringify({
      rows,
      infer_schema: inferSchema,
    }),
  });
}

export async function importDataHubRows(
  tableId: string,
  data: {
    connection_id?: string;
    connector_type?: string;
    connector_config?: Record<string, unknown>;
    replace_existing?: boolean;
    infer_schema?: boolean;
  }
): Promise<DataHubImportResponse> {
  return fetchApi<DataHubImportResponse>(`/api/data-hub/tables/${tableId}/import`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function transformDataHubRows(
  tableId: string,
  data: {
    operations: Array<{
      operation_type: "transform" | "filter" | "map" | "aggregate";
      config: Record<string, unknown>;
      name?: string;
    }>;
    replace_existing?: boolean;
  }
): Promise<DataHubTransformResponse> {
  return fetchApi<DataHubTransformResponse>(`/api/data-hub/tables/${tableId}/transform`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function publishDataHubTable(
  tableId: string,
  data: {
    module_id: string;
    line_item_map: Record<string, string>;
    dimension_columns?: string[];
    dimension_member_map?: Record<string, Record<string, string>>;
    static_dimension_members?: string[];
    version_id?: string;
    allow_null_values?: boolean;
    batch_size?: number;
  }
): Promise<DataHubPublishResponse> {
  return fetchApi<DataHubPublishResponse>(`/api/data-hub/tables/${tableId}/publish`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getDataHubLineage(tableId: string): Promise<DataHubLineage[]> {
  return fetchApi<DataHubLineage[]>(`/api/data-hub/tables/${tableId}/lineage`);
}

// ── Dashboard types ───────────────────────────────────────────────────────────

export type WidgetType = "grid" | "chart" | "kpi_card" | "text" | "image";

export interface DashboardWidget {
  id: string;
  dashboard_id: string;
  widget_type: WidgetType;
  title: string | null;
  config: Record<string, unknown> | null;
  position_x: number;
  position_y: number;
  width: number;
  height: number;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface Dashboard {
  id: string;
  name: string;
  description: string | null;
  model_id: string;
  owner_id: string;
  is_published: boolean;
  layout: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface DashboardWithWidgets extends Dashboard {
  widgets: DashboardWidget[];
}

// ── Dashboard API helpers ─────────────────────────────────────────────────────

export async function getDashboards(modelId: string): Promise<Dashboard[]> {
  return fetchApi<Dashboard[]>(`/api/models/${modelId}/dashboards`);
}

export async function getDashboard(dashboardId: string): Promise<DashboardWithWidgets> {
  return fetchApi<DashboardWithWidgets>(`/api/dashboards/${dashboardId}`);
}

export async function createDashboard(
  modelId: string,
  data: { name: string; description?: string; layout?: Record<string, unknown> }
): Promise<Dashboard> {
  return fetchApi<Dashboard>(`/api/models/${modelId}/dashboards`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateDashboard(
  dashboardId: string,
  data: {
    name?: string;
    description?: string;
    is_published?: boolean;
    layout?: Record<string, unknown>;
  }
): Promise<Dashboard> {
  return fetchApi<Dashboard>(`/api/dashboards/${dashboardId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteDashboard(dashboardId: string): Promise<void> {
  return fetchApi<void>(`/api/dashboards/${dashboardId}`, { method: "DELETE" });
}

export async function addWidget(
  dashboardId: string,
  data: {
    widget_type: WidgetType;
    title?: string;
    config?: Record<string, unknown>;
    position_x: number;
    position_y: number;
    width?: number;
    height?: number;
    sort_order?: number;
  }
): Promise<DashboardWidget> {
  return fetchApi<DashboardWidget>(`/api/dashboards/${dashboardId}/widgets`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateWidget(
  widgetId: string,
  data: {
    title?: string;
    config?: Record<string, unknown>;
    position_x?: number;
    position_y?: number;
    width?: number;
    height?: number;
    sort_order?: number;
  }
): Promise<DashboardWidget> {
  return fetchApi<DashboardWidget>(`/api/widgets/${widgetId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteWidget(widgetId: string): Promise<void> {
  return fetchApi<void>(`/api/widgets/${widgetId}`, { method: "DELETE" });
}

// ── UX App Builder types ─────────────────────────────────────────────────────

export type UXPageType = "board" | "worksheet" | "report";
export type UXCardType =
  | "grid"
  | "chart"
  | "button"
  | "filter"
  | "text"
  | "kpi"
  | "image";

export interface UXContextSelector {
  id: string;
  page_id: string;
  dimension_id: string;
  label: string;
  allow_multi_select: boolean;
  default_member_id: string | null;
  sort_order: number;
}

export interface UXPageCard {
  id: string;
  page_id: string;
  card_type: UXCardType;
  title: string | null;
  config: Record<string, unknown> | null;
  position_x: number;
  position_y: number;
  width: number;
  height: number;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface UXPage {
  id: string;
  model_id: string;
  owner_id: string;
  parent_page_id: string | null;
  name: string;
  page_type: UXPageType;
  description: string | null;
  layout_config: Record<string, unknown> | null;
  is_published: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface UXPageDetail extends UXPage {
  cards: UXPageCard[];
  context_selectors: UXContextSelector[];
}

export interface UXPageCreateInput {
  name: string;
  page_type: UXPageType;
  parent_page_id?: string | null;
  description?: string;
  layout_config?: Record<string, unknown>;
  sort_order?: number;
}

export interface UXPageUpdateInput {
  name?: string;
  parent_page_id?: string | null;
  description?: string | null;
  layout_config?: Record<string, unknown> | null;
  sort_order?: number;
}

export interface UXPageCardCreateInput {
  card_type: UXCardType;
  title?: string;
  config?: Record<string, unknown>;
  position_x?: number;
  position_y?: number;
  width?: number;
  height?: number;
  sort_order?: number;
}

export interface UXPageCardUpdateInput {
  title?: string | null;
  config?: Record<string, unknown>;
  position_x?: number;
  position_y?: number;
  width?: number;
  height?: number;
  sort_order?: number;
}

export interface UXContextSelectorCreateInput {
  dimension_id: string;
  label: string;
  allow_multi_select?: boolean;
  default_member_id?: string | null;
  sort_order?: number;
}

// ── UX App Builder API helpers ───────────────────────────────────────────────

export async function getUXPages(modelId: string): Promise<UXPage[]> {
  return fetchApi<UXPage[]>(`/api/models/${modelId}/pages`);
}

export async function getUXPage(pageId: string): Promise<UXPageDetail> {
  return fetchApi<UXPageDetail>(`/api/pages/${pageId}`);
}

export async function createUXPage(
  modelId: string,
  data: UXPageCreateInput
): Promise<UXPage> {
  return fetchApi<UXPage>(`/api/models/${modelId}/pages`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateUXPage(
  pageId: string,
  data: UXPageUpdateInput
): Promise<UXPage> {
  return fetchApi<UXPage>(`/api/pages/${pageId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteUXPage(pageId: string): Promise<void> {
  return fetchApi<void>(`/api/pages/${pageId}`, { method: "DELETE" });
}

export async function publishUXPage(
  pageId: string,
  isPublished: boolean
): Promise<UXPage> {
  return fetchApi<UXPage>(`/api/pages/${pageId}/publish`, {
    method: "PUT",
    body: JSON.stringify({ is_published: isPublished }),
  });
}

export async function reorderUXPages(
  modelId: string,
  pageIds: string[]
): Promise<UXPage[]> {
  return fetchApi<UXPage[]>(`/api/models/${modelId}/pages/reorder`, {
    method: "PUT",
    body: JSON.stringify({ page_ids: pageIds }),
  });
}

export async function addUXCard(
  pageId: string,
  data: UXPageCardCreateInput
): Promise<UXPageCard> {
  return fetchApi<UXPageCard>(`/api/pages/${pageId}/cards`, {
    method: "POST",
    body: JSON.stringify({
      position_x: 0,
      position_y: 0,
      width: 6,
      height: 4,
      sort_order: 0,
      ...data,
    }),
  });
}

export async function updateUXCard(
  cardId: string,
  data: UXPageCardUpdateInput
): Promise<UXPageCard> {
  return fetchApi<UXPageCard>(`/api/cards/${cardId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteUXCard(cardId: string): Promise<void> {
  return fetchApi<void>(`/api/cards/${cardId}`, { method: "DELETE" });
}

export async function reorderUXCards(
  pageId: string,
  cardIds: string[]
): Promise<UXPageCard[]> {
  return fetchApi<UXPageCard[]>(`/api/pages/${pageId}/cards/reorder`, {
    method: "PUT",
    body: JSON.stringify({ card_ids: cardIds }),
  });
}

export async function addUXContextSelector(
  pageId: string,
  data: UXContextSelectorCreateInput
): Promise<UXContextSelector> {
  return fetchApi<UXContextSelector>(`/api/pages/${pageId}/context-selectors`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteUXContextSelector(selectorId: string): Promise<void> {
  return fetchApi<void>(`/api/context-selectors/${selectorId}`, {
    method: "DELETE",
  });
}
