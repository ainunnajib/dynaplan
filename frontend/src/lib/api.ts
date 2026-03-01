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
  applies_to_dimension_ids: string[];
  summary_method: "sum" | "average" | "min" | "max" | "none" | null;
  created_at: string;
  updated_at: string;
}

export interface Dimension {
  id: string;
  model_id: string;
  name: string;
  type: "custom" | "time" | "version" | "numbered";
  created_at: string;
  updated_at: string;
}

export interface DimensionItem {
  id: string;
  dimension_id: string;
  name: string;
  parent_id: string | null;
  order: number;
  created_at: string;
  updated_at: string;
}

export interface CellValue {
  line_item_id: string;
  dimension_member_ids: string[];
  value: number | string | boolean | null;
}

// ── API helpers ───────────────────────────────────────────────────────────────

export async function getWorkspaces(): Promise<Workspace[]> {
  return fetchApi<Workspace[]>("/api/workspaces/");
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
  return fetchApi<Dimension[]>(`/api/models/${modelId}/dimensions`);
}

export async function getDimensionItems(
  dimensionId: string
): Promise<DimensionItem[]> {
  return fetchApi<DimensionItem[]>(
    `/api/dimensions/${dimensionId}/items`
  );
}

export async function getCells(moduleId: string): Promise<CellValue[]> {
  return fetchApi<CellValue[]>(`/api/modules/${moduleId}/cells`);
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
