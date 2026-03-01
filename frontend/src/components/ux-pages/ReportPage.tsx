"use client";

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
  onContextChange?: (selectors: SelectorState[]) => void;
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
  onContextChange,
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
          pageId={page.id}
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
            <ReportSection key={card.id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Report section per card
// ---------------------------------------------------------------------------

function ReportSection({ card }: { card: UXCardData }) {
  const config = card.config ?? {};

  return (
    <section className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm print:shadow-none print:border-zinc-300">
      {card.title && (
        <div className="border-b border-zinc-100 bg-zinc-50 px-5 py-3 print:bg-white">
          <h2 className="text-sm font-semibold text-zinc-800">{card.title}</h2>
        </div>
      )}

      <div className="p-5">
        {card.card_type === "text" ? (
          <div className="prose prose-sm max-w-none">
            <p className="whitespace-pre-wrap text-sm text-zinc-700">
              {(config.content as string) ?? ""}
            </p>
          </div>
        ) : card.card_type === "kpi" ? (
          <div className="flex items-center gap-8">
            <div>
              <div className="text-3xl font-bold text-zinc-900">
                {config.value !== undefined
                  ? String(config.value)
                  : "--"}
              </div>
              {config.label ? (
                <div className="mt-1 text-xs text-zinc-500">
                  {String(config.label)}
                </div>
              ) : null}
            </div>
          </div>
        ) : card.card_type === "chart" ? (
          <div className="flex h-48 items-center justify-center text-sm text-zinc-400">
            Chart placeholder ({(config.chart_type as string) ?? "bar"})
          </div>
        ) : card.card_type === "grid" ? (
          <div className="flex h-48 items-center justify-center text-sm text-zinc-400">
            Grid placeholder
          </div>
        ) : card.card_type === "image" ? (
          <div className="flex items-center justify-center">
            {config.src ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={config.src as string}
                alt={(config.alt as string) ?? "Report image"}
                className="max-h-64 max-w-full object-contain"
              />
            ) : (
              <span className="text-xs text-zinc-400">No image configured</span>
            )}
          </div>
        ) : (
          <div className="text-xs text-zinc-400">
            {card.card_type} card
          </div>
        )}
      </div>
    </section>
  );
}
