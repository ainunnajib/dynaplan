"use client";

import { useState } from "react";
import PageCard from "./PageCard";
import ContextSelectorBar from "./ContextSelectorBar";
import type { UXCardData } from "./PageCard";
import type { SelectorState } from "./ContextSelectorBar";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UXPageData {
  id: string;
  model_id: string;
  name: string;
  page_type: "board" | "worksheet" | "report";
  description: string | null;
  layout_config: Record<string, unknown> | null;
  is_published: boolean;
  sort_order: number;
  cards: UXCardData[];
  context_selectors: SelectorState[];
}

interface BoardPageProps {
  page: UXPageData;
  isEditMode?: boolean;
  onDeleteCard?: (cardId: string) => void;
  onUpdateCard?: (cardId: string, patch: Partial<UXCardData>) => void;
  onContextChange?: (selectors: SelectorState[]) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GRID_COLS = 12;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BoardPage({
  page,
  isEditMode = false,
  onDeleteCard,
  onUpdateCard,
  onContextChange,
}: BoardPageProps) {
  const cards = page.cards;

  const getCardStyle = (card: UXCardData) => ({
    gridColumn: `${card.position_x + 1} / span ${card.width}`,
    gridRow: `${card.position_y + 1} / span ${card.height}`,
  });

  return (
    <div className="flex flex-col gap-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900">{page.name}</h1>
          {page.description && (
            <p className="mt-0.5 text-sm text-zinc-500">{page.description}</p>
          )}
        </div>
        <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-600">
          Board
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

      {/* Card grid */}
      {cards.length === 0 ? (
        <div className="flex h-64 items-center justify-center rounded-lg border-2 border-dashed border-zinc-200 text-sm text-zinc-400">
          {isEditMode
            ? "Add cards to build your board"
            : "This board has no cards yet"}
        </div>
      ) : (
        <div
          className="grid gap-2"
          style={{
            gridTemplateColumns: `repeat(${GRID_COLS}, 1fr)`,
            gridAutoRows: "80px",
          }}
        >
          {cards.map((card) => (
            <div key={card.id} style={getCardStyle(card)}>
              <PageCard
                card={card}
                isEditMode={isEditMode}
                onDelete={onDeleteCard}
                onUpdate={onUpdateCard}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
