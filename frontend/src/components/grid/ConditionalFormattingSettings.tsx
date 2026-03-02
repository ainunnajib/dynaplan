"use client";

import { useEffect, useMemo, useState } from "react";
import {
  fetchApi,
  type ConditionalFormatOperator,
  type ConditionalFormatRule,
  type LineItem,
  type Module,
} from "@/lib/api";

interface ConditionalFormattingSettingsProps {
  moduleId: string;
  lineItems: LineItem[];
  moduleRules: ConditionalFormatRule[];
  onLineItemRulesSaved: (lineItemId: string, rules: ConditionalFormatRule[]) => void;
  onModuleRulesSaved: (rules: ConditionalFormatRule[]) => void;
}

type RuleScope = "line_item" | "module";

const OPERATOR_OPTIONS: Array<{ value: ConditionalFormatOperator; label: string }> = [
  { value: "gt", label: ">" },
  { value: "gte", label: ">=" },
  { value: "lt", label: "<" },
  { value: "lte", label: "<=" },
  { value: "eq", label: "=" },
  { value: "neq", label: "!=" },
];

function createFallbackUuid(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
    const random = Math.floor(Math.random() * 16);
    const value = character === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

function createRuleId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return createFallbackUuid();
}

function createDefaultRule(): ConditionalFormatRule {
  return {
    id: createRuleId(),
    name: "",
    enabled: true,
    operator: "gt",
    value: 0,
    style: {
      background_color: "#dbeafe",
      text_color: null,
      bold: null,
      italic: null,
      number_format: null,
      icon: null,
    },
  };
}

export default function ConditionalFormattingSettings({
  moduleId,
  lineItems,
  moduleRules,
  onLineItemRulesSaved,
  onModuleRulesSaved,
}: ConditionalFormattingSettingsProps) {
  const [scope, setScope] = useState<RuleScope>("line_item");
  const [selectedLineItemId, setSelectedLineItemId] = useState<string | null>(
    lineItems[0]?.id ?? null
  );
  const [draftRules, setDraftRules] = useState<ConditionalFormatRule[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedLineItemId && lineItems.length > 0) {
      setSelectedLineItemId(lineItems[0].id);
      return;
    }
    if (
      selectedLineItemId &&
      !lineItems.some((lineItem) => lineItem.id === selectedLineItemId)
    ) {
      setSelectedLineItemId(lineItems[0]?.id ?? null);
    }
  }, [lineItems, selectedLineItemId]);

  const selectedLineItem = useMemo(
    () => lineItems.find((lineItem) => lineItem.id === selectedLineItemId) ?? null,
    [lineItems, selectedLineItemId]
  );

  const activeRules = useMemo(() => {
    if (scope === "module") {
      return moduleRules;
    }
    return selectedLineItem?.conditional_format_rules ?? [];
  }, [moduleRules, scope, selectedLineItem]);

  useEffect(() => {
    setDraftRules(activeRules.map((rule) => ({ ...rule, style: { ...rule.style } })));
  }, [activeRules]);

  const isLineItemScopeDisabled = lineItems.length === 0;

  async function handleSaveRules() {
    setIsSaving(true);
    setError(null);
    try {
      if (scope === "module") {
        const updated = await fetchApi<Module>(`/api/modules/${moduleId}`, {
          method: "PATCH",
          body: JSON.stringify({
            conditional_format_rules: draftRules,
          }),
        });
        onModuleRulesSaved(updated.conditional_format_rules ?? []);
        return;
      }

      if (!selectedLineItemId) {
        setError("Select a line item first");
        return;
      }

      const updated = await fetchApi<LineItem>(`/api/line-items/${selectedLineItemId}`, {
        method: "PATCH",
        body: JSON.stringify({
          conditional_format_rules: draftRules,
        }),
      });
      onLineItemRulesSaved(selectedLineItemId, updated.conditional_format_rules ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save rules");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="rounded-md border border-zinc-200 bg-white px-3 py-3 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Conditional Formatting
        </p>

        <select
          value={scope}
          onChange={(event) => setScope(event.target.value as RuleScope)}
          className="h-8 rounded border border-zinc-300 bg-white px-2 text-sm text-zinc-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="line_item" disabled={isLineItemScopeDisabled}>
            Line Item Rules
          </option>
          <option value="module">Module Rules</option>
        </select>

        {scope === "line_item" && (
          <select
            value={selectedLineItemId ?? ""}
            onChange={(event) => setSelectedLineItemId(event.target.value || null)}
            className="h-8 min-w-[200px] rounded border border-zinc-300 bg-white px-2 text-sm text-zinc-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={lineItems.length === 0}
          >
            {lineItems.length === 0 && <option value="">No line items</option>}
            {lineItems.map((lineItem) => (
              <option key={lineItem.id} value={lineItem.id}>
                {lineItem.name}
              </option>
            ))}
          </select>
        )}

        <button
          type="button"
          onClick={() =>
            setDraftRules((prev) => [...prev, createDefaultRule()])
          }
          className="h-8 rounded border border-zinc-300 px-3 text-sm text-zinc-700 hover:bg-zinc-50"
          disabled={scope === "line_item" && !selectedLineItem}
        >
          Add Rule
        </button>

        <button
          type="button"
          onClick={() => void handleSaveRules()}
          className="h-8 rounded bg-blue-600 px-3 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isSaving || (scope === "line_item" && !selectedLineItem)}
        >
          {isSaving ? "Saving..." : "Save Rules"}
        </button>
      </div>

      {draftRules.length === 0 && (
        <p className="mt-2 text-xs text-zinc-500">
          No formatting rules configured for this scope.
        </p>
      )}

      <div className="mt-3 space-y-2">
        {draftRules.map((rule) => (
          <div
            key={rule.id}
            className="rounded border border-zinc-200 bg-zinc-50 px-2 py-2"
          >
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="checkbox"
                checked={rule.enabled}
                onChange={(event) =>
                  setDraftRules((prev) =>
                    prev.map((candidate) =>
                      candidate.id === rule.id
                        ? { ...candidate, enabled: event.target.checked }
                        : candidate
                    )
                  )
                }
                className="h-4 w-4 rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
              />

              <input
                type="text"
                value={rule.name ?? ""}
                onChange={(event) =>
                  setDraftRules((prev) =>
                    prev.map((candidate) =>
                      candidate.id === rule.id
                        ? { ...candidate, name: event.target.value }
                        : candidate
                    )
                  )
                }
                placeholder="Rule name (optional)"
                className="h-8 min-w-[150px] rounded border border-zinc-300 bg-white px-2 text-sm text-zinc-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />

              <select
                value={rule.operator}
                onChange={(event) =>
                  setDraftRules((prev) =>
                    prev.map((candidate) =>
                      candidate.id === rule.id
                        ? {
                            ...candidate,
                            operator: event.target.value as ConditionalFormatOperator,
                          }
                        : candidate
                    )
                  )
                }
                className="h-8 rounded border border-zinc-300 bg-white px-2 text-sm text-zinc-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {OPERATOR_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>

              <input
                type="text"
                value={String(rule.value)}
                onChange={(event) =>
                  setDraftRules((prev) =>
                    prev.map((candidate) =>
                      candidate.id === rule.id
                        ? { ...candidate, value: event.target.value }
                        : candidate
                    )
                  )
                }
                placeholder="Threshold"
                className="h-8 min-w-[120px] rounded border border-zinc-300 bg-white px-2 text-sm text-zinc-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />

              <label className="flex items-center gap-1 text-xs text-zinc-600">
                Bg
                <input
                  type="color"
                  value={rule.style.background_color ?? "#ffffff"}
                  onChange={(event) =>
                    setDraftRules((prev) =>
                      prev.map((candidate) =>
                        candidate.id === rule.id
                          ? {
                              ...candidate,
                              style: {
                                ...candidate.style,
                                background_color: event.target.value,
                              },
                            }
                          : candidate
                      )
                    )
                  }
                  className="h-8 w-8 cursor-pointer rounded border border-zinc-300 bg-white p-0"
                />
              </label>

              <label className="flex items-center gap-1 text-xs text-zinc-600">
                Text
                <input
                  type="color"
                  value={rule.style.text_color ?? "#111827"}
                  onChange={(event) =>
                    setDraftRules((prev) =>
                      prev.map((candidate) =>
                        candidate.id === rule.id
                          ? {
                              ...candidate,
                              style: {
                                ...candidate.style,
                                text_color: event.target.value,
                              },
                            }
                          : candidate
                      )
                    )
                  }
                  className="h-8 w-8 cursor-pointer rounded border border-zinc-300 bg-white p-0"
                />
              </label>

              <label className="flex items-center gap-1 text-xs text-zinc-600">
                <input
                  type="checkbox"
                  checked={Boolean(rule.style.bold)}
                  onChange={(event) =>
                    setDraftRules((prev) =>
                      prev.map((candidate) =>
                        candidate.id === rule.id
                          ? {
                              ...candidate,
                              style: {
                                ...candidate.style,
                                bold: event.target.checked ? true : null,
                              },
                            }
                          : candidate
                      )
                    )
                  }
                  className="h-4 w-4 rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
                />
                Bold
              </label>

              <label className="flex items-center gap-1 text-xs text-zinc-600">
                <input
                  type="checkbox"
                  checked={Boolean(rule.style.italic)}
                  onChange={(event) =>
                    setDraftRules((prev) =>
                      prev.map((candidate) =>
                        candidate.id === rule.id
                          ? {
                              ...candidate,
                              style: {
                                ...candidate.style,
                                italic: event.target.checked ? true : null,
                              },
                            }
                          : candidate
                      )
                    )
                  }
                  className="h-4 w-4 rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
                />
                Italic
              </label>

              <select
                value={rule.style.number_format ?? ""}
                onChange={(event) =>
                  setDraftRules((prev) =>
                    prev.map((candidate) =>
                      candidate.id === rule.id
                        ? {
                            ...candidate,
                            style: {
                              ...candidate.style,
                              number_format: event.target.value
                                ? (event.target.value as "number" | "currency" | "percentage")
                                : null,
                            },
                          }
                        : candidate
                    )
                  )
                }
                className="h-8 rounded border border-zinc-300 bg-white px-2 text-sm text-zinc-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">Number format</option>
                <option value="number">Number</option>
                <option value="currency">Currency</option>
                <option value="percentage">Percentage</option>
              </select>

              <input
                type="text"
                value={rule.style.icon ?? ""}
                onChange={(event) =>
                  setDraftRules((prev) =>
                    prev.map((candidate) =>
                      candidate.id === rule.id
                        ? {
                            ...candidate,
                            style: {
                              ...candidate.style,
                              icon: event.target.value || null,
                            },
                          }
                        : candidate
                    )
                  )
                }
                placeholder="Icon"
                className="h-8 w-24 rounded border border-zinc-300 bg-white px-2 text-sm text-zinc-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />

              <button
                type="button"
                onClick={() =>
                  setDraftRules((prev) =>
                    prev.filter((candidate) => candidate.id !== rule.id)
                  )
                }
                className="ml-auto h-8 rounded border border-red-300 bg-red-50 px-2 text-xs text-red-700 hover:bg-red-100"
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>

      {error && (
        <p className="mt-2 rounded bg-red-50 px-2 py-1 text-xs text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
