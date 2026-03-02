"use client";

import PageCard from "./PageCard";
import ContextSelectorBar from "./ContextSelectorBar";
import type { UXCardData } from "./PageCard";
import type { SelectorState } from "./ContextSelectorBar";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ReportPageProps {
  page: {
    id: string;
    name: string;
    description: string | null;
    layout_config: Record<string, unknown> | null;
    cards: UXCardData[];
    context_selectors: SelectorState[];
  };
  isEditMode?: boolean;
  contextValues?: Record<string, string[]>;
  cardFilters?: Record<string, string | null>;
  onContextChange?: (selectors: SelectorState[]) => void;
  onDeleteCard?: (cardId: string) => void;
  onUpdateCard?: (cardId: string, patch: Partial<UXCardData>) => void;
  onCardEmitLink?: (
    sourceCardId: string,
    value: string | null,
    targetCardIds: string[]
  ) => void;
  onNavigatePage?: (targetPageId: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * ReportPage renders a print/export-friendly layout.
 *
 * Cards are stacked vertically in sort_order, each occupying full width,
 * producing a scrollable, pageable document suitable for management
 * reporting.  The layout is optimized for readability and PDF export.
 */
export default function ReportPage({
  page,
  isEditMode = false,
  contextValues = {},
  cardFilters = {},
  onContextChange,
  onDeleteCard,
  onUpdateCard,
  onCardEmitLink,
  onNavigatePage,
}: ReportPageProps) {
  const cards = [...page.cards].sort((a, b) => a.sort_order - b.sort_order);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      {/* Report header */}
      <div className="border-b border-zinc-200 pb-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-zinc-900">{page.name}</h1>
            {page.description && (
              <p className="mt-1 text-sm text-zinc-500">{page.description}</p>
            )}
          </div>
          <span className="rounded-full bg-orange-50 px-2 py-0.5 text-xs font-medium text-orange-600">
            Report
          </span>
        </div>
      </div>

      {/* Context selectors */}
      {page.context_selectors.length > 0 && (
        <ContextSelectorBar
          selectors={page.context_selectors}
          onChange={onContextChange}
        />
      )}

      {/* Report body -- stacked cards */}
      {cards.length === 0 ? (
        <div className="flex h-48 items-center justify-center rounded-lg border-2 border-dashed border-zinc-200 text-sm text-zinc-400">
          This report has no content cards yet
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {cards.map((card) => (
            <section key={card.id} className="min-h-[220px]">
              <PageCard
                card={card}
                isEditMode={isEditMode}
                contextValues={contextValues}
                linkedFilter={cardFilters[card.id] ?? null}
                onDelete={onDeleteCard}
                onUpdate={onUpdateCard}
                onEmitLink={onCardEmitLink}
                onNavigatePage={onNavigatePage}
              />
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
