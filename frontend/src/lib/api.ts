const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "dynaplan_token";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export async function fetchApi<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
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
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
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
  type: "custom" | "time" | "version";
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
  return fetchApi<Workspace[]>("/api/workspaces");
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
