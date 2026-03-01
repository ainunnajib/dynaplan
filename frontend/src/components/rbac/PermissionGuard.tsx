"use client";

import { useCallback, useEffect, useState } from "react";

type WorkspaceRole = "owner" | "admin" | "editor" | "viewer";
type ModelPermission = "full_access" | "edit_data" | "view_only" | "no_access";

interface PermissionsResponse {
  workspace_role: WorkspaceRole | null;
  model_permission: ModelPermission | null;
}

interface Props {
  token: string;
  workspaceId?: string;
  modelId?: string;
  requiredPermission:
    | { kind: "workspace"; minRole: WorkspaceRole }
    | { kind: "model"; minPermission: ModelPermission };
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

const ROLE_ORDER: WorkspaceRole[] = ["viewer", "editor", "admin", "owner"];
const PERMISSION_ORDER: ModelPermission[] = ["no_access", "view_only", "edit_data", "full_access"];

function hasWorkspaceRole(actual: WorkspaceRole | null, required: WorkspaceRole): boolean {
  if (!actual) return false;
  return ROLE_ORDER.indexOf(actual) >= ROLE_ORDER.indexOf(required);
}

function hasModelPermission(actual: ModelPermission | null, required: ModelPermission): boolean {
  if (!actual) return false;
  return PERMISSION_ORDER.indexOf(actual) >= PERMISSION_ORDER.indexOf(required);
}

export default function PermissionGuard({
  token,
  workspaceId,
  modelId,
  requiredPermission,
  children,
  fallback,
}: Props) {
  const [permissions, setPermissions] = useState<PermissionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchPermissions = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const params = new URLSearchParams();
      if (workspaceId) params.set("workspace_id", workspaceId);
      if (modelId) params.set("model_id", modelId);

      const resp = await fetch(`/api/me/permissions?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        throw new Error(`Permission check failed (${resp.status})`);
      }
      const data: PermissionsResponse = await resp.json();
      setPermissions(data);
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : "Failed to check permissions");
    } finally {
      setLoading(false);
    }
  }, [token, workspaceId, modelId]);

  useEffect(() => {
    fetchPermissions();
  }, [fetchPermissions]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <span className="text-sm text-zinc-400">Checking permissions...</span>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {fetchError}
      </div>
    );
  }

  let allowed = false;
  if (permissions) {
    if (requiredPermission.kind === "workspace") {
      allowed = hasWorkspaceRole(permissions.workspace_role, requiredPermission.minRole);
    } else {
      allowed = hasModelPermission(permissions.model_permission, requiredPermission.minPermission);
    }
  }

  if (!allowed) {
    if (fallback !== undefined) {
      return <>{fallback}</>;
    }
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
        <div className="rounded-full bg-zinc-100 p-4 mb-4">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-8 w-8 text-zinc-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
        </div>
        <h3 className="text-base font-semibold text-zinc-900 mb-1">Access Denied</h3>
        <p className="text-sm text-zinc-500 max-w-sm">
          You do not have the required permissions to view this content. Contact your workspace
          administrator if you believe this is a mistake.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
