"use client";

import type { Dimension } from "@/lib/api";

interface DimensionSelectorProps {
  dimensions: Dimension[];
  selectedIds: string[];
  onChange: (selectedIds: string[]) => void;
  disabled?: boolean;
}

export default function DimensionSelector({
  dimensions,
  selectedIds,
  onChange,
  disabled = false,
}: DimensionSelectorProps) {
  function toggle(id: string) {
    if (disabled) return;
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((sid) => sid !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  }

  if (dimensions.length === 0) {
    return (
      <span className="text-xs text-zinc-400 italic">No dimensions defined</span>
    );
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {dimensions.map((dim) => {
        const isSelected = selectedIds.includes(dim.id);
        return (
          <button
            key={dim.id}
            type="button"
            onClick={() => toggle(dim.id)}
            disabled={disabled}
            title={`${dim.name} (${dim.type})`}
            className={[
              "flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium transition-colors",
              isSelected
                ? "border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100"
                : "border-zinc-200 bg-zinc-50 text-zinc-500 hover:border-zinc-300 hover:text-zinc-700",
              disabled ? "cursor-default opacity-60" : "cursor-pointer",
            ].join(" ")}
          >
            <DimensionTypeIcon type={dim.type} />
            {dim.name}
            {isSelected && <CheckIcon className="h-3 w-3 ml-0.5" />}
          </button>
        );
      })}
    </div>
  );
}

function DimensionTypeIcon({ type }: { type: Dimension["type"] }) {
  if (type === "time") {
    return (
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    );
  }
  if (type === "version") {
    return (
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6.429 9.75 2.25 12l4.179 2.25m0-4.5 5.571 3 5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L21.75 12l-4.179 2.25m0 0 4.179 2.25L12 21.75 2.25 16.5l4.179-2.25m11.142 0-5.571 3-5.571-3" />
      </svg>
    );
  }
  if (type === "numbered") {
    return (
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h9m-9 5.25h9m-9 5.25h9M4.5 6.75h.008v.008H4.5V6.75Zm0 5.25h.008v.008H4.5V12Zm0 5.25h.008v.008H4.5v-.008Z" />
      </svg>
    );
  }
  if (type === "composite") {
    return (
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="m12 3-8.25 4.5v9L12 21l8.25-4.5v-9L12 3Z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="m3.75 7.5 8.25 4.5 8.25-4.5M12 12v9" />
      </svg>
    );
  }
  // custom
  return (
    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM3.75 12h.007v.008H3.75V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  );
}
