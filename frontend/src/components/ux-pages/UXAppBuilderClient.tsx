"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import BoardPage from "./BoardPage";
import WorksheetPage from "./WorksheetPage";
import ReportPage from "./ReportPage";
import type { UXCardData } from "./PageCard";
import type { SelectorState } from "./ContextSelectorBar";
import {
  addUXCard,
  addUXContextSelector,
  deleteUXCard,
  deleteUXContextSelector,
  getDimensionItems,
  getDimensions,
  getUXPage,
  getUXPages,
  publishUXPage,
  updateUXCard,
  updateUXPage,
  type Dimension,
  type UXCardType,
  type UXPage,
  type UXPageCardUpdateInput,
  type UXPageDetail,
} from "@/lib/api";

interface UXAppBuilderClientProps {
  modelId: string;
  pageId: string;
}

type AppCardType = "grid" | "chart" | "button" | "filter" | "text";

const NEW_CARD_TYPES: Array<{ value: AppCardType; label: string }> = [
  { value: "grid", label: "Grid" },
  { value: "chart", label: "Chart" },
  { value: "button", label: "Button" },
  { value: "filter", label: "Filter" },
  { value: "text", label: "Text" },
];

export default function UXAppBuilderClient({
  modelId,
  pageId,
}: UXAppBuilderClientProps) {
  const router = useRouter();
  const [page, setPage] = useState<UXPageDetail | null>(null);
  const [pages, setPages] = useState<UXPage[]>([]);
  const [dimensions, setDimensions] = useState<Dimension[]>([]);
  const [selectors, setSelectors] = useState<SelectorState[]>([]);
  const [cardFilters, setCardFilters] = useState<Record<string, string | null>>({});
  const [selectedParentId, setSelectedParentId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [isEditMode, setIsEditMode] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showAddCardDialog, setShowAddCardDialog] = useState(false);
  const [newCardType, setNewCardType] = useState<AppCardType>("grid");
  const [newCardTitle, setNewCardTitle] = useState("");
  const [isAddingCard, setIsAddingCard] = useState(false);

  const [showSelectorDialog, setShowSelectorDialog] = useState(false);
  const [selectorDimensionId, setSelectorDimensionId] = useState("");
  const [selectorLabel, setSelectorLabel] = useState("");
  const [selectorMulti, setSelectorMulti] = useState(false);
  const [isAddingSelector, setIsAddingSelector] = useState(false);
  const [isSavingParent, setIsSavingParent] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [pageData, pageList, dimensionList] = await Promise.all([
        getUXPage(pageId),
        getUXPages(modelId),
        getDimensions(modelId),
      ]);

      const selectorStates = await Promise.all(
        pageData.context_selectors.map(async (selector) => {
          const items = await getDimensionItems(selector.dimension_id);
          const members = items.map((item) => ({
            id: item.id,
            label: item.name,
          }));
          const defaultSelected =
            selector.default_member_id &&
            members.some((member) => member.id === selector.default_member_id)
              ? [selector.default_member_id]
              : [];
          const fallbackSelected =
            defaultSelected.length > 0 || selector.allow_multi_select || members.length === 0
              ? defaultSelected
              : [members[0].id];

          return {
            selector,
            members,
            selectedIds: fallbackSelected,
          };
        })
      );

      setPage(pageData);
      setPages(pageList);
      setDimensions(dimensionList);
      setSelectors(selectorStates);
      setCardFilters({});
      setSelectedParentId(pageData.parent_page_id ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load app page");
    } finally {
      setIsLoading(false);
    }
  }, [modelId, pageId]);

  useEffect(() => {
    load();
  }, [load]);

  const pagesByParent = useMemo(() => {
    const groups = new Map<string, UXPage[]>();
    for (const current of pages) {
      const key = current.parent_page_id ?? "__root__";
      const list = groups.get(key) ?? [];
      list.push(current);
      groups.set(key, list);
    }
    for (const [, list] of groups) {
      list.sort((a, b) => {
        if (a.sort_order !== b.sort_order) {
          return a.sort_order - b.sort_order;
        }
        return a.name.localeCompare(b.name);
      });
    }
    return groups;
  }, [pages]);

  const contextValues = useMemo(() => {
    const values: Record<string, string[]> = {};
    for (const selectorState of selectors) {
      values[selectorState.selector.label] = selectorState.selectedIds
        .map((id) => selectorState.members.find((member) => member.id === id)?.label ?? id)
        .filter((value) => value.length > 0);
    }
    return values;
  }, [selectors]);

  const currentPageForView = useMemo(() => {
    if (!page) {
      return null;
    }

    return {
      ...page,
      cards: page.cards as UXCardData[],
      context_selectors: selectors,
    };
  }, [page, selectors]);

  const availableParentPages = useMemo(
    () => pages.filter((candidate) => candidate.id !== pageId),
    [pages, pageId]
  );

  const chartCardIds = useMemo(
    () =>
      page?.cards
        .filter((card) => card.card_type === "chart")
        .map((card) => card.id) ?? [],
    [page]
  );

  const handleCardEmitLink = useCallback(
    (sourceCardId: string, value: string | null, targetCardIds: string[]) => {
      if (!page) {
        return;
      }

      let targets = targetCardIds;
      if (targets.length === 0) {
        targets = page.cards
          .filter((card) => card.id !== sourceCardId && card.card_type === "chart")
          .map((card) => card.id);
      }

      setCardFilters((prev) => {
        if (value === null && targets.length === 0) {
          return {};
        }

        const next = { ...prev };
        for (const targetId of targets) {
          if (value === null) {
            delete next[targetId];
          } else {
            next[targetId] = value;
          }
        }
        return next;
      });
    },
    [page]
  );

  const handleNavigatePage = useCallback(
    (targetPageId: string) => {
      router.push(`/models/${modelId}/apps/${targetPageId}`);
    },
    [modelId, router]
  );

  async function handleTogglePublish() {
    if (!page) {
      return;
    }

    setIsPublishing(true);
    setError(null);
    try {
      const updated = await publishUXPage(page.id, !page.is_published);
      setPage((prev) => (prev ? { ...prev, is_published: updated.is_published } : prev));
      setPages((prev) =>
        prev.map((candidate) =>
          candidate.id === updated.id
            ? { ...candidate, is_published: updated.is_published }
            : candidate
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update publish state");
    } finally {
      setIsPublishing(false);
    }
  }

  async function handleSaveParent() {
    if (!page) {
      return;
    }

    setIsSavingParent(true);
    setError(null);
    try {
      const updated = await updateUXPage(page.id, {
        parent_page_id: selectedParentId || null,
      });
      setPage((prev) =>
        prev ? { ...prev, parent_page_id: updated.parent_page_id } : prev
      );
      setPages((prev) =>
        prev.map((candidate) =>
          candidate.id === updated.id
            ? { ...candidate, parent_page_id: updated.parent_page_id }
            : candidate
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to move page");
    } finally {
      setIsSavingParent(false);
    }
  }

  async function handleDeleteCard(cardId: string) {
    if (!page) {
      return;
    }

    setError(null);
    try {
      await deleteUXCard(cardId);
      setPage((prev) =>
        prev
          ? { ...prev, cards: prev.cards.filter((card) => card.id !== cardId) }
          : prev
      );
      setCardFilters((prev) => {
        const next = { ...prev };
        delete next[cardId];
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete card");
    }
  }

  async function handleUpdateCard(cardId: string, patch: Partial<UXCardData>) {
    setError(null);
    try {
      const payload: UXPageCardUpdateInput = {};
      if (patch.title !== undefined) payload.title = patch.title;
      if (patch.config !== undefined) payload.config = patch.config ?? undefined;
      if (patch.position_x !== undefined) payload.position_x = patch.position_x;
      if (patch.position_y !== undefined) payload.position_y = patch.position_y;
      if (patch.width !== undefined) payload.width = patch.width;
      if (patch.height !== undefined) payload.height = patch.height;
      if (patch.sort_order !== undefined) payload.sort_order = patch.sort_order;

      const updated = await updateUXCard(cardId, payload);
      setPage((prev) =>
        prev
          ? {
              ...prev,
              cards: prev.cards.map((card) =>
                card.id === cardId ? { ...card, ...updated } : card
              ),
            }
          : prev
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update card");
    }
  }

  async function handleAddCard() {
    if (!page) {
      return;
    }

    setIsAddingCard(true);
    setError(null);
    try {
      const config = defaultCardConfig(newCardType, chartCardIds);
      const created = await addUXCard(page.id, {
        card_type: newCardType as UXCardType,
        title: newCardTitle.trim() || undefined,
        position_x: 0,
        position_y: page.cards.length * 2,
        width: 6,
        height: newCardType === "text" ? 3 : 4,
        sort_order: page.cards.length,
        config,
      });
      setPage((prev) => (prev ? { ...prev, cards: [...prev.cards, created] } : prev));
      setShowAddCardDialog(false);
      setNewCardType("grid");
      setNewCardTitle("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add card");
    } finally {
      setIsAddingCard(false);
    }
  }

  async function handleAddSelector() {
    if (!page || !selectorDimensionId) {
      return;
    }

    setIsAddingSelector(true);
    setError(null);
    try {
      await addUXContextSelector(page.id, {
        dimension_id: selectorDimensionId,
        label:
          selectorLabel.trim() ||
          dimensions.find((dimension) => dimension.id === selectorDimensionId)?.name ||
          "Context",
        allow_multi_select: selectorMulti,
      });
      setShowSelectorDialog(false);
      setSelectorDimensionId("");
      setSelectorLabel("");
      setSelectorMulti(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add context selector");
    } finally {
      setIsAddingSelector(false);
    }
  }

  async function handleDeleteSelector(selectorId: string) {
    setError(null);
    try {
      await deleteUXContextSelector(selectorId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete context selector");
    }
  }

  function renderNavigationTree(parentId: string | null, depth: number) {
    const key = parentId ?? "__root__";
    const nodes = pagesByParent.get(key) ?? [];
    if (nodes.length === 0) {
      return null;
    }

    return (
      <div className={depth === 0 ? "space-y-2" : "space-y-2 border-l border-zinc-200 pl-3"}>
        {nodes.map((node) => {
          const isActive = node.id === pageId;
          return (
            <div key={node.id}>
              <button
                type="button"
                onClick={() => handleNavigatePage(node.id)}
                className={`w-full rounded-md px-2 py-1.5 text-left text-xs transition-colors ${
                  isActive
                    ? "bg-violet-100 text-violet-800"
                    : "text-zinc-700 hover:bg-zinc-100"
                }`}
              >
                <span className="block truncate font-medium">{node.name}</span>
                <span className="block text-[10px] uppercase text-zinc-500">
                  {node.page_type}
                </span>
              </button>
              {renderNavigationTree(node.id, depth + 1)}
            </div>
          );
        })}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
      </div>
    );
  }

  if (error && !page) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!page || !currentPageForView) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px,1fr]">
      <aside className="rounded-lg border border-zinc-200 bg-white p-3 shadow-sm">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Navigation
        </h2>
        <div className="mt-3">{renderNavigationTree(null, 0)}</div>
      </aside>

      <div className="min-w-0 space-y-4">
        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="rounded-lg border border-zinc-200 bg-white p-3 shadow-sm sm:p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold text-zinc-900">{page.name}</h1>
              <p className="text-xs text-zinc-500">
                {page.page_type} page
                {page.is_published ? " • Published" : " • Draft"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={handleTogglePublish}
                disabled={isPublishing}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  page.is_published
                    ? "border border-zinc-300 text-zinc-700 hover:bg-zinc-50"
                    : "border border-green-300 bg-green-50 text-green-700 hover:bg-green-100"
                }`}
              >
                {isPublishing ? "Saving..." : page.is_published ? "Unpublish" : "Publish"}
              </button>
              <button
                type="button"
                onClick={() => setShowAddCardDialog(true)}
                className="rounded-md bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-violet-700"
              >
                Add Card
              </button>
              <button
                type="button"
                onClick={() => setShowSelectorDialog(true)}
                className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 transition-colors hover:bg-zinc-50"
              >
                Add Context Selector
              </button>
              <button
                type="button"
                onClick={() => setIsEditMode((prev) => !prev)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  isEditMode
                    ? "bg-zinc-800 text-white hover:bg-zinc-700"
                    : "border border-zinc-300 text-zinc-700 hover:bg-zinc-50"
                }`}
              >
                {isEditMode ? "Done" : "Edit"}
              </button>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-[1fr,auto] md:items-end">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-700">
                Parent page
              </label>
              <select
                value={selectedParentId}
                onChange={(event) => setSelectedParentId(event.target.value)}
                className="w-full rounded-md border border-zinc-300 px-2.5 py-2 text-sm text-zinc-900 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
              >
                <option value="">Top-level page</option>
                {availableParentPages.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.name}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={handleSaveParent}
              disabled={isSavingParent}
              className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 disabled:opacity-50"
            >
              {isSavingParent ? "Saving..." : "Save Parent"}
            </button>
          </div>

          {selectors.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {selectors.map((selectorState) => (
                <div
                  key={selectorState.selector.id}
                  className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs text-zinc-700"
                >
                  <span>{selectorState.selector.label}</span>
                  <button
                    type="button"
                    onClick={() => handleDeleteSelector(selectorState.selector.id)}
                    className="rounded-full p-0.5 text-zinc-400 transition-colors hover:bg-red-100 hover:text-red-600"
                    title="Remove selector"
                  >
                    <XIcon className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-3 shadow-sm sm:p-4">
          {page.page_type === "worksheet" ? (
            <WorksheetPage
              page={currentPageForView}
              isEditMode={isEditMode}
              contextValues={contextValues}
              cardFilters={cardFilters}
              onDeleteCard={handleDeleteCard}
              onUpdateCard={handleUpdateCard}
              onCardEmitLink={handleCardEmitLink}
              onNavigatePage={handleNavigatePage}
              onContextChange={setSelectors}
            />
          ) : page.page_type === "report" ? (
            <ReportPage
              page={currentPageForView}
              isEditMode={isEditMode}
              contextValues={contextValues}
              cardFilters={cardFilters}
              onDeleteCard={handleDeleteCard}
              onUpdateCard={handleUpdateCard}
              onCardEmitLink={handleCardEmitLink}
              onNavigatePage={handleNavigatePage}
              onContextChange={setSelectors}
            />
          ) : (
            <BoardPage
              page={currentPageForView}
              isEditMode={isEditMode}
              contextValues={contextValues}
              cardFilters={cardFilters}
              onDeleteCard={handleDeleteCard}
              onUpdateCard={handleUpdateCard}
              onCardEmitLink={handleCardEmitLink}
              onNavigatePage={handleNavigatePage}
              onContextChange={setSelectors}
            />
          )}
        </div>
      </div>

      {showAddCardDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-semibold text-zinc-900">Add Card</h3>
            <p className="mt-1 text-xs text-zinc-500">
              Add an interactive card to this page.
            </p>

            <div className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-700">
                  Card type
                </label>
                <select
                  value={newCardType}
                  onChange={(event) => setNewCardType(event.target.value as AppCardType)}
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                >
                  {NEW_CARD_TYPES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-700">
                  Card title (optional)
                </label>
                <input
                  type="text"
                  value={newCardTitle}
                  onChange={(event) => setNewCardTitle(event.target.value)}
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  placeholder="e.g. Product performance"
                />
              </div>
            </div>

            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowAddCardDialog(false)}
                className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isAddingCard}
                onClick={handleAddCard}
                className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700 disabled:opacity-50"
              >
                {isAddingCard ? "Adding..." : "Add Card"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showSelectorDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-semibold text-zinc-900">Add Context Selector</h3>
            <p className="mt-1 text-xs text-zinc-500">
              Context selectors propagate dimension choices across all cards.
            </p>

            <div className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-700">
                  Dimension
                </label>
                <select
                  value={selectorDimensionId}
                  onChange={(event) => setSelectorDimensionId(event.target.value)}
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                >
                  <option value="">Select a dimension</option>
                  {dimensions.map((dimension) => (
                    <option key={dimension.id} value={dimension.id}>
                      {dimension.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-700">
                  Label (optional)
                </label>
                <input
                  type="text"
                  value={selectorLabel}
                  onChange={(event) => setSelectorLabel(event.target.value)}
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  placeholder="e.g. Region"
                />
              </div>
              <label className="flex items-center gap-2 text-xs text-zinc-700">
                <input
                  type="checkbox"
                  checked={selectorMulti}
                  onChange={(event) => setSelectorMulti(event.target.checked)}
                  className="rounded border-zinc-300 text-violet-600 focus:ring-violet-500"
                />
                Allow multiple selections
              </label>
            </div>

            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowSelectorDialog(false)}
                className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleAddSelector}
                disabled={isAddingSelector || !selectorDimensionId}
                className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700 disabled:opacity-50"
              >
                {isAddingSelector ? "Adding..." : "Add Selector"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function defaultCardConfig(cardType: AppCardType, chartCardIds: string[]): Record<string, unknown> {
  if (cardType === "grid") {
    return {
      rows: [
        { label: "Product Alpha", value: 42 },
        { label: "Product Beta", value: 31 },
        { label: "Product Gamma", value: 18 },
      ],
      link_targets: chartCardIds,
    };
  }

  if (cardType === "chart") {
    return {
      chart_type: "bar",
      series: [
        { label: "Product Alpha", value: 120 },
        { label: "Product Beta", value: 95 },
        { label: "Product Gamma", value: 70 },
      ],
    };
  }

  if (cardType === "filter") {
    return {
      options: ["Product Alpha", "Product Beta", "Product Gamma"],
      link_targets: chartCardIds,
    };
  }

  if (cardType === "button") {
    return {
      label: "Reset Filters",
      action: "clear_links",
      link_targets: chartCardIds,
    };
  }

  return {
    content: "Add notes or instructions for planners here.",
  };
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}
