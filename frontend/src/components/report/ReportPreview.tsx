"use client";

import type { ReportWithSections, ReportSection } from "./ReportBuilder";

// ── Page dimension constants (in CSS px at 96dpi) ────────────────────────────

const MM_TO_PX = 96 / 25.4; // 1mm approx 3.78px at 96dpi

const PAGE_SIZES: Record<string, { width: number; height: number }> = {
  a4: { width: 210, height: 297 },
  letter: { width: 215.9, height: 279.4 },
  custom: { width: 210, height: 297 }, // fallback to A4
};

interface Props {
  report: ReportWithSections;
}

export default function ReportPreview({ report }: Props) {
  const baseSize = PAGE_SIZES[report.page_size] ?? PAGE_SIZES.a4;
  const isLandscape = report.orientation === "landscape";
  const pageWidthMm = isLandscape ? baseSize.height : baseSize.width;
  const pageHeightMm = isLandscape ? baseSize.width : baseSize.height;

  const pageWidthPx = pageWidthMm * MM_TO_PX;
  const pageHeightPx = pageHeightMm * MM_TO_PX;

  const marginTop = report.margin_top * MM_TO_PX;
  const marginRight = report.margin_right * MM_TO_PX;
  const marginBottom = report.margin_bottom * MM_TO_PX;
  const marginLeft = report.margin_left * MM_TO_PX;

  const contentWidth = pageWidthPx - marginLeft - marginRight;

  // Split sections into pages at page_break sections
  const pages: ReportSection[][] = [];
  let currentPage: ReportSection[] = [];
  for (const section of report.sections) {
    if (section.section_type === "page_break") {
      pages.push(currentPage);
      currentPage = [];
    } else {
      currentPage.push(section);
    }
  }
  if (currentPage.length > 0 || pages.length === 0) {
    pages.push(currentPage);
  }

  return (
    <div className="flex flex-col items-center gap-6 py-6">
      {pages.map((pageSections, pageIdx) => (
        <div
          key={pageIdx}
          className="relative bg-white shadow-lg"
          style={{
            width: `${pageWidthPx}px`,
            minHeight: `${pageHeightPx}px`,
            paddingTop: `${marginTop}px`,
            paddingRight: `${marginRight}px`,
            paddingBottom: `${marginBottom}px`,
            paddingLeft: `${marginLeft}px`,
          }}
        >
          {/* Header */}
          {report.header_html && (
            <div
              className="mb-4 border-b border-zinc-200 pb-2 text-xs text-zinc-500"
              style={{ width: `${contentWidth}px` }}
              dangerouslySetInnerHTML={{ __html: report.header_html }}
            />
          )}

          {/* Sections */}
          <div className="space-y-4" style={{ width: `${contentWidth}px` }}>
            {pageSections.length === 0 && (
              <div className="flex items-center justify-center py-20 text-sm text-zinc-300">
                Empty page
              </div>
            )}
            {pageSections.map((section) => (
              <SectionRenderer key={section.id} section={section} />
            ))}
          </div>

          {/* Footer */}
          {report.footer_html && (
            <div
              className="absolute bottom-0 left-0 right-0 border-t border-zinc-200 px-4 py-2 text-xs text-zinc-400"
              style={{
                marginLeft: `${marginLeft}px`,
                marginRight: `${marginRight}px`,
                marginBottom: `${marginBottom / 2}px`,
              }}
              dangerouslySetInnerHTML={{
                __html: report.footer_html.replace("{page}", String(pageIdx + 1)),
              }}
            />
          )}

          {/* Page number watermark */}
          <div className="absolute bottom-2 right-4 text-[10px] text-zinc-300">
            Page {pageIdx + 1} of {pages.length}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Section renderers ────────────────────────────────────────────────────────

function SectionRenderer({ section }: { section: ReportSection }) {
  const heightStyle = section.height_mm
    ? { minHeight: `${section.height_mm * MM_TO_PX}px` }
    : {};

  const config = section.content_config ?? {};

  switch (section.section_type) {
    case "narrative":
      return (
        <div className="report-section-narrative" style={heightStyle}>
          {section.title && (
            <h3 className="mb-2 text-sm font-semibold text-zinc-800">{section.title}</h3>
          )}
          {config.html ? (
            <div
              className="prose prose-sm max-w-none text-zinc-700"
              dangerouslySetInnerHTML={{ __html: config.html as string }}
            />
          ) : (
            <p className="text-sm italic text-zinc-300">Narrative content placeholder</p>
          )}
        </div>
      );

    case "grid":
      return (
        <div className="report-section-grid" style={heightStyle}>
          {section.title && (
            <h3 className="mb-2 text-sm font-semibold text-zinc-800">{section.title}</h3>
          )}
          <div className="flex items-center justify-center rounded border border-zinc-200 bg-zinc-50 py-8 text-xs text-zinc-400">
            Grid: {(config.module_name as string) ?? "Data grid placeholder"}
          </div>
        </div>
      );

    case "chart":
      return (
        <div className="report-section-chart" style={heightStyle}>
          {section.title && (
            <h3 className="mb-2 text-sm font-semibold text-zinc-800">{section.title}</h3>
          )}
          <div className="flex items-center justify-center rounded border border-zinc-200 bg-zinc-50 py-12 text-xs text-zinc-400">
            Chart: {(config.chart_type as string) ?? "Visualization placeholder"}
          </div>
        </div>
      );

    case "kpi_row":
      return (
        <div className="report-section-kpi" style={heightStyle}>
          {section.title && (
            <h3 className="mb-2 text-sm font-semibold text-zinc-800">{section.title}</h3>
          )}
          <div className="grid grid-cols-4 gap-3">
            {((config.kpis as Array<{ label: string; value: string }>) ?? [
              { label: "KPI 1", value: "--" },
              { label: "KPI 2", value: "--" },
              { label: "KPI 3", value: "--" },
              { label: "KPI 4", value: "--" },
            ]).map((kpi, i) => (
              <div key={i} className="rounded border border-zinc-200 bg-zinc-50 p-3 text-center">
                <p className="text-xs text-zinc-400">{kpi.label}</p>
                <p className="mt-1 text-lg font-semibold text-zinc-800">{kpi.value}</p>
              </div>
            ))}
          </div>
        </div>
      );

    case "spacer":
      return (
        <div
          className="report-section-spacer"
          style={{ height: section.height_mm ? `${section.height_mm * MM_TO_PX}px` : "40px" }}
        />
      );

    default:
      return null;
  }
}
