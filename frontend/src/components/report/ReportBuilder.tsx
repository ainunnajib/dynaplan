"use client";

import { useState, useCallback } from "react";
import { fetchApi } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

export type PageSize = "a4" | "letter" | "custom";
export type Orientation = "portrait" | "landscape";
export type SectionType = "narrative" | "grid" | "chart" | "kpi_row" | "page_break" | "spacer";

export interface ReportSection {
  id: string;
  report_id: string;
  section_type: SectionType;
  title: string | null;
  content_config: Record<string, unknown> | null;
  sort_order: number;
  height_mm: number | null;
  created_at: string;
  updated_at: string;
}

export interface Report {
  id: string;
  model_id: string;
  owner_id: string;
  name: string;
  description: string | null;
  page_size: PageSize;
  orientation: Orientation;
  margin_top: number;
  margin_right: number;
  margin_bottom: number;
  margin_left: number;
  header_html: string | null;
  footer_html: string | null;
  is_published: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReportWithSections extends Report {
  sections: ReportSection[];
}

// ── Section type metadata ────────────────────────────────────────────────────

const SECTION_TYPE_META: Record<SectionType, { label: string; icon: string; description: string }> = {
  narrative: { label: "Narrative", icon: "T", description: "Rich text block for commentary" },
  grid: { label: "Grid", icon: "#", description: "Data grid from a module" },
  chart: { label: "Chart", icon: "~", description: "Chart visualization" },
  kpi_row: { label: "KPI Row", icon: "K", description: "Key metric indicators" },
  page_break: { label: "Page Break", icon: "|", description: "Force a new page" },
  spacer: { label: "Spacer", icon: "-", description: "Vertical whitespace" },
};

// ── Props ────────────────────────────────────────────────────────────────────

interface Props {
  report: ReportWithSections;
  onReportChange: (updater: (prev: ReportWithSections | null) => ReportWithSections | null) => void;
}

// ── Component ────────────────────────────────────────────────────────────────

export default function ReportBuilder({ report, onReportChange }: Props) {
  const [addingSection, setAddingSection] = useState(false);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);

  const addSection = useCallback(
    async (sectionType: SectionType) => {
      const nextOrder = report.sections.length;
      const section = await fetchApi<ReportSection>(
        `/reports/${report.id}/sections`,
        {
          method: "POST",
          body: JSON.stringify({
            section_type: sectionType,
            title: SECTION_TYPE_META[sectionType].label,
            sort_order: nextOrder,
          }),
        }
      );
      onReportChange((prev) =>
        prev ? { ...prev, sections: [...prev.sections, section] } : prev
      );
      setAddingSection(false);
    },
    [report.id, report.sections.length, onReportChange]
  );

  const removeSection = useCallback(
    async (sectionId: string) => {
      await fetchApi(`/sections/${sectionId}`, { method: "DELETE" });
      onReportChange((prev) =>
        prev
          ? { ...prev, sections: prev.sections.filter((s) => s.id !== sectionId) }
          : prev
      );
    },
    [onReportChange]
  );

  const handleDragStart = (idx: number) => {
    setDragIdx(idx);
  };

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    setDragOverIdx(idx);
  };

  const handleDrop = useCallback(
    async (targetIdx: number) => {
      if (dragIdx === null || dragIdx === targetIdx) {
        setDragIdx(null);
        setDragOverIdx(null);
        return;
      }

      const sections = [...report.sections];
      const [moved] = sections.splice(dragIdx, 1);
      sections.splice(targetIdx, 0, moved);

      // Optimistic update
      onReportChange((prev) => (prev ? { ...prev, sections } : prev));

      // Persist
      const sectionIds = sections.map((s) => s.id);
      await fetchApi(`/reports/${report.id}/sections/reorder`, {
        method: "POST",
        body: JSON.stringify({ section_ids: sectionIds }),
      });

      setDragIdx(null);
      setDragOverIdx(null);
    },
    [dragIdx, report.id, report.sections, onReportChange]
  );

  return (
    <div className="space-y-4">
      {/* Report header */}
      <div className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900">{report.name}</h2>
          {report.description && (
            <p className="mt-1 text-sm text-zinc-500">{report.description}</p>
          )}
          <div className="mt-2 flex gap-3 text-xs text-zinc-400">
            <span>Page: {report.page_size.toUpperCase()}</span>
            <span>Orientation: {report.orientation}</span>
            <span>
              Margins: {report.margin_top}/{report.margin_right}/{report.margin_bottom}/{report.margin_left} mm
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {report.is_published && (
            <span className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
              Published
            </span>
          )}
        </div>
      </div>

      {/* Section list */}
      <div className="space-y-2">
        {report.sections.length === 0 && (
          <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-zinc-300 bg-white py-16 text-center">
            <p className="text-sm text-zinc-500">No sections yet</p>
            <p className="mt-1 text-xs text-zinc-400">
              Add narrative text, charts, grids, or KPI rows to build your report.
            </p>
          </div>
        )}

        {report.sections.map((section, idx) => (
          <div
            key={section.id}
            draggable
            onDragStart={() => handleDragStart(idx)}
            onDragOver={(e) => handleDragOver(e, idx)}
            onDrop={() => handleDrop(idx)}
            className={`group flex items-center gap-3 rounded-lg border bg-white p-3 shadow-sm transition ${
              dragOverIdx === idx ? "border-violet-400 bg-violet-50" : "border-zinc-200"
            } ${dragIdx === idx ? "opacity-50" : ""}`}
          >
            {/* Drag handle */}
            <button className="cursor-grab text-zinc-300 hover:text-zinc-500" aria-label="Drag to reorder">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 8h16M4 16h16" />
              </svg>
            </button>

            {/* Type badge */}
            <span className="flex h-8 w-8 items-center justify-center rounded bg-zinc-100 text-xs font-bold text-zinc-500">
              {SECTION_TYPE_META[section.section_type]?.icon ?? "?"}
            </span>

            {/* Section info */}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-zinc-800 truncate">
                {section.title ?? SECTION_TYPE_META[section.section_type]?.label ?? section.section_type}
              </p>
              <p className="text-xs text-zinc-400">
                {SECTION_TYPE_META[section.section_type]?.description}
                {section.height_mm != null && ` \u00B7 ${section.height_mm}mm`}
              </p>
            </div>

            {/* Delete button */}
            <button
              onClick={() => removeSection(section.id)}
              className="invisible text-zinc-300 hover:text-red-500 group-hover:visible"
              aria-label="Delete section"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
      </div>

      {/* Add section panel */}
      {addingSection ? (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
          <p className="mb-3 text-sm font-medium text-zinc-700">Add a section</p>
          <div className="grid grid-cols-3 gap-2">
            {(Object.keys(SECTION_TYPE_META) as SectionType[]).map((st) => (
              <button
                key={st}
                onClick={() => addSection(st)}
                className="flex flex-col items-center gap-1 rounded-lg border border-zinc-200 p-3 text-center transition hover:border-violet-400 hover:bg-violet-50"
              >
                <span className="text-lg font-bold text-zinc-500">{SECTION_TYPE_META[st].icon}</span>
                <span className="text-xs font-medium text-zinc-700">{SECTION_TYPE_META[st].label}</span>
              </button>
            ))}
          </div>
          <button
            onClick={() => setAddingSection(false)}
            className="mt-3 text-xs text-zinc-400 hover:text-zinc-600"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={() => setAddingSection(true)}
          className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-zinc-300 bg-white py-3 text-sm text-zinc-500 transition hover:border-violet-400 hover:text-violet-600"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Add Section
        </button>
      )}
    </div>
  );
}
