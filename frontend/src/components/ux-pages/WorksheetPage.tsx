"use client";

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
  onContextChange?: (selectors: SelectorState[]) => void;
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
  onContextChange,
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
          pageId={page.id}
          selectors={page.context_selectors}
          onChange={onContextChange}
        />
      )}

      {/* Primary grid area */}
      {primaryCard ? (
        <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm">
          <div className="border-b border-zinc-100 bg-zinc-50 px-4 py-2">
            <span className="text-xs font-medium text-zinc-600">
              {primaryCard.title ?? "Data Grid"}
            </span>
          </div>
          <div className="min-h-[400px] p-0">
            {/* Placeholder for actual grid rendering (driven by module_id in config) */}
            <div className="flex h-full min-h-[400px] items-center justify-center text-sm text-zinc-400">
              Grid content will render here based on module configuration
            </div>
          </div>
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
            <div
              key={card.id}
              className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm"
            >
              <div className="border-b border-zinc-100 bg-zinc-50 px-3 py-2">
                <span className="text-xs font-medium text-zinc-600">
                  {card.title ?? card.card_type}
                </span>
              </div>
              <div className="flex h-32 items-center justify-center p-3 text-xs text-zinc-400">
                {card.card_type} card content
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
