"use client";

import { useState, useRef, useEffect, useCallback, KeyboardEvent } from "react";
import { CellFormat, formatCellValue, parseCellInput, validateCellInput } from "./CellFormatting";

type CellState = "viewing" | "editing" | "saving" | "error";

interface EditableCellProps {
  value: number | string | boolean | null | undefined;
  format: CellFormat;
  onChange: (value: number | string | boolean | null) => Promise<void>;
  isCalculated?: boolean;
  formula?: string;
  decimals?: number;
  /** Called when Tab is pressed to move focus to next cell */
  onTabNext?: () => void;
  /** Called when Shift+Tab is pressed to move focus to previous cell */
  onTabPrev?: () => void;
}

export default function EditableCell({
  value,
  format,
  onChange,
  isCalculated = false,
  formula,
  decimals = 2,
  onTabNext,
  onTabPrev,
}: EditableCellProps) {
  const [cellState, setCellState] = useState<CellState>("viewing");
  const [editValue, setEditValue] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showTooltip, setShowTooltip] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const checkboxRef = useRef<HTMLInputElement>(null);

  // Focus input when entering edit mode
  useEffect(() => {
    if (cellState === "editing") {
      if (format === "boolean") {
        checkboxRef.current?.focus();
      } else {
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    }
  }, [cellState, format]);

  const startEditing = useCallback(() => {
    if (isCalculated) return;
    // Initialise the text input from the current raw value
    if (format === "boolean") {
      // Boolean cells toggle directly without an intermediate text state
      return;
    }
    if (format === "date") {
      // Normalise to YYYY-MM-DD for the <input type="date"> element
      let dateStr = "";
      if (value !== null && value !== undefined && value !== "") {
        const d = new Date(String(value));
        if (!isNaN(d.getTime())) {
          dateStr = d.toISOString().slice(0, 10);
        } else {
          dateStr = String(value);
        }
      }
      setEditValue(dateStr);
    } else {
      setEditValue(value !== null && value !== undefined ? String(value) : "");
    }
    setErrorMessage(null);
    setCellState("editing");
  }, [isCalculated, format, value]);

  const cancelEditing = useCallback(() => {
    setEditValue("");
    setErrorMessage(null);
    setCellState("viewing");
  }, []);

  const commitEdit = useCallback(async () => {
    if (cellState !== "editing") return;

    const validationError = validateCellInput(editValue, format);
    if (validationError) {
      setErrorMessage(validationError);
      setCellState("error");
      return;
    }

    const parsed = parseCellInput(editValue, format);

    setCellState("saving");
    setErrorMessage(null);
    try {
      await onChange(parsed);
      setCellState("viewing");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Save failed");
      setCellState("error");
    }
  }, [cellState, editValue, format, onChange]);

  const handleBooleanToggle = useCallback(async () => {
    if (isCalculated) return;
    const current =
      typeof value === "boolean"
        ? value
        : value === "true" || value === "1" || value === 1;
    const next = !current;
    setCellState("saving");
    try {
      await onChange(next);
      setCellState("viewing");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Save failed");
      setCellState("error");
    }
  }, [isCalculated, value, onChange]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        void commitEdit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        cancelEditing();
      } else if (e.key === "Tab") {
        e.preventDefault();
        void commitEdit().then(() => {
          if (e.shiftKey) {
            onTabPrev?.();
          } else {
            onTabNext?.();
          }
        });
      }
    },
    [commitEdit, cancelEditing, onTabNext, onTabPrev]
  );

  const displayValue = formatCellValue(value, format, decimals);

  // ---- Boolean cell ----
  if (format === "boolean") {
    const checked =
      typeof value === "boolean"
        ? value
        : value === "true" || value === "1" || value === 1;

    return (
      <div className="flex items-center justify-center w-full h-full px-2 py-1">
        {cellState === "saving" ? (
          <span className="inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        ) : (
          <input
            ref={checkboxRef}
            type="checkbox"
            checked={!!checked}
            disabled={isCalculated}
            onChange={() => void handleBooleanToggle()}
            className={[
              "w-4 h-4 rounded accent-blue-600 cursor-pointer",
              isCalculated ? "opacity-50 cursor-not-allowed" : "",
              cellState === "error" ? "outline outline-red-500" : "",
            ]
              .filter(Boolean)
              .join(" ")}
          />
        )}
        {errorMessage && (
          <span className="ml-1 text-xs text-red-500 truncate">{errorMessage}</span>
        )}
      </div>
    );
  }

  // ---- Calculated cell (read-only with formula tooltip) ----
  if (isCalculated) {
    return (
      <div
        className="relative w-full h-full"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <div
          className={[
            "w-full h-full px-2 py-1 text-sm select-none bg-zinc-50 text-zinc-400 cursor-not-allowed",
            format === "number" || format === "percentage" ? "text-right" : "text-left",
          ].join(" ")}
        >
          {displayValue}
        </div>
        {showTooltip && formula && (
          <div className="absolute z-50 bottom-full left-0 mb-1 px-2 py-1 text-xs bg-zinc-800 text-white rounded shadow-lg whitespace-nowrap pointer-events-none">
            ={formula}
          </div>
        )}
      </div>
    );
  }

  // ---- Editing state ----
  if (cellState === "editing" || cellState === "error") {
    return (
      <div className="relative w-full h-full">
        <input
          ref={inputRef}
          type={format === "date" ? "date" : "text"}
          value={editValue}
          onChange={(e) => {
            setEditValue(e.target.value);
            if (cellState === "error") {
              // Re-validate on change to clear error once fixed
              const err = validateCellInput(e.target.value, format);
              if (!err) {
                setCellState("editing");
                setErrorMessage(null);
              }
            }
          }}
          onBlur={() => void commitEdit()}
          onKeyDown={handleKeyDown}
          className={[
            "w-full h-full px-2 py-1 text-sm outline-none border-2 rounded",
            format === "number" || format === "percentage"
              ? "text-right"
              : "text-left",
            cellState === "error"
              ? "border-red-500 bg-red-50 focus:ring-1 focus:ring-red-400"
              : "border-blue-500 bg-white focus:ring-1 focus:ring-blue-400",
          ]
            .filter(Boolean)
            .join(" ")}
          autoComplete="off"
          spellCheck={false}
        />
        {errorMessage && (
          <div className="absolute z-50 top-full left-0 mt-0.5 px-2 py-1 text-xs bg-red-600 text-white rounded shadow whitespace-nowrap pointer-events-none">
            {errorMessage}
          </div>
        )}
      </div>
    );
  }

  // ---- Saving state ----
  if (cellState === "saving") {
    return (
      <div
        className={[
          "flex items-center w-full h-full px-2 py-1 text-sm bg-white text-zinc-400",
          format === "number" || format === "percentage"
            ? "justify-end"
            : "justify-start",
        ].join(" ")}
      >
        <span className="mr-1 inline-block w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        {displayValue}
      </div>
    );
  }

  // ---- Viewing state ----
  return (
    <div
      role="gridcell"
      tabIndex={0}
      onDoubleClick={startEditing}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === "F2") {
          e.preventDefault();
          startEditing();
        }
      }}
      onFocus={() => {
        // Nothing — require explicit double-click or Enter to enter edit mode
      }}
      className={[
        "w-full h-full px-2 py-1 text-sm select-none cursor-pointer",
        "hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-400",
        format === "number" || format === "percentage" ? "text-right" : "text-left",
      ].join(" ")}
    >
      {displayValue || <span className="text-zinc-300">&nbsp;</span>}
    </div>
  );
}
