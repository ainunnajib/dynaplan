"use client";

import PageCard from "./PageCard";
import ContextSelectorBar from "./ContextSelectorBar";
import type { UXCardData } from "./PageCard";
import type { SelectorState } from "./ContextSelectorBar";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WorksheetPageProps {
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
 * WorksheetPage renders a full-width grid experience.
 *
 * Unlike the Board layout (free-form card grid), a Worksheet displays a
 * single primary grid card that fills the viewport width, optimized for
 * data-entry workflows.  Additional cards (charts, KPIs) are rendered
 * below the primary grid in a stacked layout.
 */
export default function WorksheetPage({
  page,
  isEditMode = false,
  contextValues = {},
  cardFilters = {},
  onContextChange,
  onDeleteCard,
  onUpdateCard,
  onCardEmitLink,
  onNavigatePage,
}: WorksheetPageProps) {
  // The primary card is the first grid-type card; fallback to the first card.
  const primaryCard = page.cards.find((c) => c.card_type === "grid") ?? page.cards[0] ?? null;
  const secondaryCards = page.cards.filter((c) => c !== primaryCard);

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900">{page.name}</h1>
          {page.description && (
            <p className="mt-0.5 text-sm text-zinc-500">{page.description}</p>
          )}
        </div>
        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-600">
          Worksheet
        </span>
      </div>

      {/* Context selectors */}
      {page.context_selectors.length > 0 && (
        <ContextSelectorBar
          selectors={page.context_selectors}
          onChange={onContextChange}
        />
      )}

      {/* Primary grid area */}
      {primaryCard ? (
        <div className="min-h-[360px]">
          <PageCard
            card={primaryCard}
            isEditMode={isEditMode}
            contextValues={contextValues}
            linkedFilter={cardFilters[primaryCard.id] ?? null}
            onDelete={onDeleteCard}
            onUpdate={onUpdateCard}
            onEmitLink={onCardEmitLink}
            onNavigatePage={onNavigatePage}
          />
        </div>
      ) : (
        <div className="flex h-64 items-center justify-center rounded-lg border-2 border-dashed border-zinc-200 text-sm text-zinc-400">
          No grid card configured for this worksheet
        </div>
      )}

      {/* Secondary cards in stacked layout */}
      {secondaryCards.length > 0 && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          {secondaryCards.map((card) => (
            <div key={card.id} className="min-h-[220px]">
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
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
