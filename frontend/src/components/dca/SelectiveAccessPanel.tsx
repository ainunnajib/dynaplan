"use client";

import { useCallback, useEffect, useState } from "react";

type AccessLevel = "read" | "write" | "none";

interface SelectiveAccessRule {
  id: string;
  model_id: string;
  name: string;
  dimension_id: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

interface SelectiveAccessGrant {
  id: string;
  rule_id: string;
  user_id: string;
  dimension_item_id: string;
  access_level: AccessLevel;
  created_at: string;
}

interface Props {
  modelId: string;
  token: string;
}

const ACCESS_LEVEL_COLORS: Record<AccessLevel, string> = {
  write: "bg-green-100 text-green-800",
  read: "bg-blue-100 text-blue-800",
  none: "bg-red-100 text-red-800",
};

const ACCESS_LEVEL_LABELS: Record<AccessLevel, string> = {
  write: "Write",
  read: "Read",
  none: "None",
};

const ACCESS_LEVELS: AccessLevel[] = ["write", "read", "none"];

export default function SelectiveAccessPanel({ modelId, token }: Props) {
  const [rules, setRules] = useState<SelectiveAccessRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create rule form
  const [newRuleName, setNewRuleName] = useState("");
  const [newRuleDimensionId, setNewRuleDimensionId] = useState("");
  const [newRuleDescription, setNewRuleDescription] = useState("");
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Selected rule for managing grants
  const [selectedRule, setSelectedRule] = useState<SelectiveAccessRule | null>(null);
  const [grants, setGrants] = useState<SelectiveAccessGrant[]>([]);
  const [grantsLoading, setGrantsLoading] = useState(false);

  // Add grant form
  const [grantUserId, setGrantUserId] = useState("");
  const [grantDimItemId, setGrantDimItemId] = useState("");
  const [grantAccessLevel, setGrantAccessLevel] = useState<AccessLevel>("read");
  const [grantError, setGrantError] = useState<string | null>(null);
  const [grantLoading, setGrantLoading] = useState(false);

  const authHeaders = useCallback(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token]
  );

  const fetchRules = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`/api/models/${modelId}/selective-access`, {
        headers: authHeaders(),
      });
      if (!resp.ok) throw new Error(`Failed to load rules (${resp.status})`);
      setRules(await resp.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [modelId, authHeaders]);

  const fetchGrants = useCallback(
    async (ruleId: string) => {
      setGrantsLoading(true);
      try {
        const resp = await fetch(`/api/selective-access/${ruleId}/grants`, {
          headers: authHeaders(),
        });
        if (!resp.ok) throw new Error(`Failed to load grants (${resp.status})`);
        setGrants(await resp.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setGrantsLoading(false);
      }
    },
    [authHeaders]
  );

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  useEffect(() => {
    if (selectedRule) {
      fetchGrants(selectedRule.id);
    } else {
      setGrants([]);
    }
  }, [selectedRule, fetchGrants]);

  const handleCreateRule = useCallback(async () => {
    if (!newRuleName.trim() || !newRuleDimensionId.trim()) return;
    setCreateError(null);
    setCreateLoading(true);
    try {
      const resp = await fetch(`/api/models/${modelId}/selective-access`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          name: newRuleName.trim(),
          dimension_id: newRuleDimensionId.trim(),
          description: newRuleDescription.trim() || null,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${resp.status}`);
      }
      setNewRuleName("");
      setNewRuleDimensionId("");
      setNewRuleDescription("");
      await fetchRules();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create rule");
    } finally {
      setCreateLoading(false);
    }
  }, [modelId, newRuleName, newRuleDimensionId, newRuleDescription, authHeaders, fetchRules]);

  const handleAddGrant = useCallback(async () => {
    if (!selectedRule || !grantUserId.trim() || !grantDimItemId.trim()) return;
    setGrantError(null);
    setGrantLoading(true);
    try {
      const resp = await fetch(`/api/selective-access/${selectedRule.id}/grants`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          user_id: grantUserId.trim(),
          dimension_item_id: grantDimItemId.trim(),
          access_level: grantAccessLevel,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${resp.status}`);
      }
      setGrantUserId("");
      setGrantDimItemId("");
      setGrantAccessLevel("read");
      await fetchGrants(selectedRule.id);
    } catch (err) {
      setGrantError(err instanceof Error ? err.message : "Failed to add grant");
    } finally {
      setGrantLoading(false);
    }
  }, [selectedRule, grantUserId, grantDimItemId, grantAccessLevel, authHeaders, fetchGrants]);

  const handleRemoveGrant = useCallback(
    async (grantId: string) => {
      if (!selectedRule) return;
      try {
        const resp = await fetch(
          `/api/selective-access/${selectedRule.id}/grants/${grantId}`,
          { method: "DELETE", headers: authHeaders() }
        );
        if (!resp.ok) throw new Error(`Failed to remove grant (${resp.status})`);
        await fetchGrants(selectedRule.id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to remove grant");
      }
    },
    [selectedRule, authHeaders, fetchGrants]
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900 mb-4">Selective Access Rules</h2>

        {/* Create rule form */}
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 mb-4">
          <h3 className="text-sm font-medium text-zinc-700 mb-3">Create Rule</h3>
          <div className="flex flex-col gap-2">
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <label className="block text-xs text-zinc-500 mb-1">Rule Name</label>
                <input
                  type="text"
                  value={newRuleName}
                  onChange={(e) => setNewRuleName(e.target.value)}
                  placeholder="e.g. Product Access"
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:border-violet-500 focus:ring-violet-200"
                  disabled={createLoading}
                />
              </div>
              <div className="flex-1">
                <label className="block text-xs text-zinc-500 mb-1">Dimension ID</label>
                <input
                  type="text"
                  value={newRuleDimensionId}
                  onChange={(e) => setNewRuleDimensionId(e.target.value)}
                  placeholder="UUID"
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:border-violet-500 focus:ring-violet-200"
                  disabled={createLoading}
                />
              </div>
              <button
                type="button"
                onClick={handleCreateRule}
                disabled={!newRuleName.trim() || !newRuleDimensionId.trim() || createLoading}
                className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
              >
                {createLoading ? "Creating..." : "Create"}
              </button>
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Description (optional)</label>
              <input
                type="text"
                value={newRuleDescription}
                onChange={(e) => setNewRuleDescription(e.target.value)}
                placeholder="Optional description"
                className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:border-violet-500 focus:ring-violet-200"
                disabled={createLoading}
              />
            </div>
          </div>
          {createError && <p className="mt-2 text-xs text-red-600">{createError}</p>}
        </div>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-4">
            {error}
          </div>
        )}

        {/* Rules list */}
        {loading ? (
          <p className="text-sm text-zinc-400 py-4 text-center">Loading rules...</p>
        ) : rules.length === 0 ? (
          <p className="text-sm text-zinc-400 py-4 text-center">No selective access rules configured.</p>
        ) : (
          <div className="rounded-lg border border-zinc-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 border-b border-zinc-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-zinc-600">Name</th>
                  <th className="text-left px-4 py-3 font-medium text-zinc-600">Description</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {rules.map((rule) => (
                  <tr
                    key={rule.id}
                    className={`hover:bg-zinc-50 transition-colors cursor-pointer ${
                      selectedRule?.id === rule.id ? "bg-violet-50" : ""
                    }`}
                    onClick={() => setSelectedRule(selectedRule?.id === rule.id ? null : rule)}
                  >
                    <td className="px-4 py-3 text-zinc-900 font-medium">{rule.name}</td>
                    <td className="px-4 py-3 text-zinc-500">{rule.description || "-"}</td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-xs text-zinc-400">
                        {selectedRule?.id === rule.id ? "Selected" : "Click to manage"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Grants panel for selected rule */}
      {selectedRule && (
        <div>
          <h3 className="text-md font-semibold text-zinc-900 mb-3">
            Grants for: {selectedRule.name}
          </h3>

          {/* Add grant form */}
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 mb-4">
            <h4 className="text-sm font-medium text-zinc-700 mb-3">Add Grant</h4>
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <label className="block text-xs text-zinc-500 mb-1">User ID</label>
                <input
                  type="text"
                  value={grantUserId}
                  onChange={(e) => setGrantUserId(e.target.value)}
                  placeholder="User UUID"
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:border-violet-500 focus:ring-violet-200"
                  disabled={grantLoading}
                />
              </div>
              <div className="flex-1">
                <label className="block text-xs text-zinc-500 mb-1">Dimension Item ID</label>
                <input
                  type="text"
                  value={grantDimItemId}
                  onChange={(e) => setGrantDimItemId(e.target.value)}
                  placeholder="Dimension Item UUID"
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:border-violet-500 focus:ring-violet-200"
                  disabled={grantLoading}
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Access Level</label>
                <select
                  value={grantAccessLevel}
                  onChange={(e) => setGrantAccessLevel(e.target.value as AccessLevel)}
                  className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:outline-none focus:ring-2 focus:border-violet-500 focus:ring-violet-200"
                  disabled={grantLoading}
                >
                  {ACCESS_LEVELS.map((level) => (
                    <option key={level} value={level}>
                      {ACCESS_LEVEL_LABELS[level]}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={handleAddGrant}
                disabled={!grantUserId.trim() || !grantDimItemId.trim() || grantLoading}
                className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
              >
                {grantLoading ? "Adding..." : "Add"}
              </button>
            </div>
            {grantError && <p className="mt-2 text-xs text-red-600">{grantError}</p>}
          </div>

          {/* Grants table */}
          {grantsLoading ? (
            <p className="text-sm text-zinc-400 py-4 text-center">Loading grants...</p>
          ) : grants.length === 0 ? (
            <p className="text-sm text-zinc-400 py-4 text-center">No grants for this rule.</p>
          ) : (
            <div className="rounded-lg border border-zinc-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-zinc-50 border-b border-zinc-200">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-zinc-600">User ID</th>
                    <th className="text-left px-4 py-3 font-medium text-zinc-600">Dimension Item ID</th>
                    <th className="text-left px-4 py-3 font-medium text-zinc-600">Access</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {grants.map((grant) => (
                    <tr key={grant.id} className="hover:bg-zinc-50 transition-colors">
                      <td className="px-4 py-3 text-zinc-900 font-mono text-xs">
                        {grant.user_id.slice(0, 8)}...
                      </td>
                      <td className="px-4 py-3 text-zinc-900 font-mono text-xs">
                        {grant.dimension_item_id.slice(0, 8)}...
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                            ACCESS_LEVEL_COLORS[grant.access_level]
                          }`}
                        >
                          {ACCESS_LEVEL_LABELS[grant.access_level]}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => handleRemoveGrant(grant.id)}
                          className="rounded-md border border-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-600 hover:border-red-300 hover:text-red-600 transition-colors"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
