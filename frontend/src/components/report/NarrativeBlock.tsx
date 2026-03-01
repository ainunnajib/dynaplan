"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import type { ReportSection } from "./ReportBuilder";

interface Props {
  section: ReportSection;
  onSectionChange: (updated: ReportSection) => void;
  readOnly?: boolean;
}

/**
 * Rich-text narrative editor for report narrative sections.
 * Uses contentEditable with execCommand for basic formatting.
 */
export default function NarrativeBlock({ section, onSectionChange, readOnly = false }: Props) {
  const editorRef = useRef<HTMLDivElement>(null);
  const [isSaving, setIsSaving] = useState(false);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const config = section.content_config ?? {};
  const initialHtml = (config.html as string) ?? "";

  // Sync initial content
  useEffect(() => {
    if (editorRef.current && editorRef.current.innerHTML !== initialHtml) {
      editorRef.current.innerHTML = initialHtml;
    }
  }, [initialHtml]);

  const saveContent = useCallback(
    async (html: string) => {
      setIsSaving(true);
      try {
        const updated = await fetchApi<ReportSection>(`/sections/${section.id}`, {
          method: "PUT",
          body: JSON.stringify({
            content_config: { ...config, html },
          }),
        });
        onSectionChange(updated);
      } catch {
        // Silently fail; content stays local
      } finally {
        setIsSaving(false);
      }
    },
    [section.id, config, onSectionChange]
  );

  const handleInput = useCallback(() => {
    if (!editorRef.current) return;

    // Debounce save
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    saveTimeoutRef.current = setTimeout(() => {
      if (editorRef.current) {
        saveContent(editorRef.current.innerHTML);
      }
    }, 800);
  }, [saveContent]);

  const execCmd = (command: string, value?: string) => {
    document.execCommand(command, false, value);
    editorRef.current?.focus();
  };

  if (readOnly) {
    return (
      <div className="report-narrative">
        {section.title && (
          <h3 className="mb-2 text-sm font-semibold text-zinc-800">{section.title}</h3>
        )}
        <div
          className="prose prose-sm max-w-none text-zinc-700"
          dangerouslySetInnerHTML={{ __html: initialHtml }}
        />
      </div>
    );
  }

  return (
    <div className="report-narrative rounded-lg border border-zinc-200 bg-white">
      {/* Title */}
      {section.title && (
        <div className="border-b border-zinc-100 px-3 py-2">
          <h3 className="text-sm font-semibold text-zinc-800">{section.title}</h3>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-1 border-b border-zinc-100 px-3 py-1.5">
        <ToolbarButton label="Bold" onClick={() => execCmd("bold")}>
          <span className="font-bold">B</span>
        </ToolbarButton>
        <ToolbarButton label="Italic" onClick={() => execCmd("italic")}>
          <span className="italic">I</span>
        </ToolbarButton>
        <ToolbarButton label="Underline" onClick={() => execCmd("underline")}>
          <span className="underline">U</span>
        </ToolbarButton>

        <div className="mx-1 h-4 w-px bg-zinc-200" />

        <ToolbarButton label="Bulleted list" onClick={() => execCmd("insertUnorderedList")}>
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
          </svg>
        </ToolbarButton>
        <ToolbarButton label="Numbered list" onClick={() => execCmd("insertOrderedList")}>
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 6h13M8 12h13M8 18h13M3.5 6v.01M3.5 12v.01M3.5 18v.01" />
          </svg>
        </ToolbarButton>

        <div className="mx-1 h-4 w-px bg-zinc-200" />

        <ToolbarButton label="Heading" onClick={() => execCmd("formatBlock", "h3")}>
          H
        </ToolbarButton>
        <ToolbarButton label="Paragraph" onClick={() => execCmd("formatBlock", "p")}>
          P
        </ToolbarButton>

        {isSaving && (
          <span className="ml-auto text-[10px] text-zinc-400">Saving...</span>
        )}
      </div>

      {/* Editable area */}
      <div
        ref={editorRef}
        contentEditable
        suppressContentEditableWarning
        onInput={handleInput}
        className="prose prose-sm max-w-none min-h-[120px] px-3 py-3 text-zinc-700 focus:outline-none"
        role="textbox"
        aria-multiline="true"
        aria-label="Narrative text editor"
      />
    </div>
  );
}

// ── Toolbar button ──────────────────────────────────────────────────────────

function ToolbarButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={(e) => {
        e.preventDefault();
        onClick();
      }}
      title={label}
      className="flex h-7 w-7 items-center justify-center rounded text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700"
      aria-label={label}
    >
      {children}
    </button>
  );
}
