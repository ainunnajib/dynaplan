"use client";

import { useState, useCallback, useRef, type ChangeEvent } from "react";

// Basic client-side formula validation (structural check only)
// Full validation goes through backend /validate-formula
function validateFormulaLocally(formula: string): { valid: boolean; error: string | null } {
  if (!formula.trim()) return { valid: true, error: null };

  // Check balanced parentheses
  let depth = 0;
  for (const ch of formula) {
    if (ch === "(") depth++;
    if (ch === ")") depth--;
    if (depth < 0) return { valid: false, error: "Unmatched closing parenthesis" };
  }
  if (depth !== 0) return { valid: false, error: "Unclosed parenthesis" };

  // Check for obvious syntax issues: trailing operator
  const trimmed = formula.trim();
  if (/[+\-*/,]$/.test(trimmed)) {
    return { valid: false, error: "Formula ends with an operator" };
  }

  return { valid: true, error: null };
}

interface FormulaInputProps {
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

type ValidationState = "idle" | "validating" | "valid" | "invalid";

export default function FormulaInput({
  value,
  onChange,
  onBlur,
  disabled = false,
  placeholder = "e.g. Revenue - Costs",
  className = "",
}: FormulaInputProps) {
  const [validationState, setValidationState] = useState<ValidationState>("idle");
  const [validationError, setValidationError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const validate = useCallback(async (formula: string) => {
    if (!formula.trim()) {
      setValidationState("idle");
      setValidationError(null);
      return;
    }

    // Local check first (instant feedback)
    const local = validateFormulaLocally(formula);
    if (!local.valid) {
      setValidationState("invalid");
      setValidationError(local.error);
      return;
    }

    // Attempt backend validation
    setValidationState("validating");
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/validate-formula`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ formula }),
        }
      );
      if (res.ok) {
        const data = (await res.json()) as { valid: boolean; error?: string };
        if (data.valid) {
          setValidationState("valid");
          setValidationError(null);
        } else {
          setValidationState("invalid");
          setValidationError(data.error ?? "Invalid formula");
        }
      } else {
        // Backend unavailable — fall back to local "valid" result
        setValidationState("valid");
        setValidationError(null);
      }
    } catch {
      // Network error — trust local validation
      setValidationState("valid");
      setValidationError(null);
    }
  }, []);

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const newValue = e.target.value;
    onChange(newValue);

    // Debounce validation
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void validate(newValue);
    }, 400);
  }

  function handleBlur() {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    void validate(value);
    onBlur?.();
  }

  const borderColor =
    validationState === "valid"
      ? "border-green-400 focus:ring-green-400 focus:border-green-400"
      : validationState === "invalid"
        ? "border-red-400 focus:ring-red-400 focus:border-red-400"
        : "border-zinc-300 focus:ring-blue-500 focus:border-blue-500";

  return (
    <div className={`relative ${className}`}>
      <div className="relative flex items-center">
        <input
          type="text"
          value={value}
          onChange={handleChange}
          onBlur={handleBlur}
          placeholder={placeholder}
          disabled={disabled}
          spellCheck={false}
          className={[
            "block w-full rounded-md border px-3 py-1.5 pr-8",
            "font-mono text-sm text-zinc-900 placeholder-zinc-400",
            "focus:outline-none focus:ring-1",
            "disabled:bg-zinc-50 disabled:text-zinc-400",
            borderColor,
          ].join(" ")}
        />

        {/* Validation status icon */}
        <div className="pointer-events-none absolute right-2.5 flex items-center">
          {validationState === "validating" && (
            <SpinnerIcon className="h-4 w-4 animate-spin text-zinc-400" />
          )}
          {validationState === "valid" && (
            <CheckCircleIcon className="h-4 w-4 text-green-500" />
          )}
          {validationState === "invalid" && (
            <XCircleIcon className="h-4 w-4 text-red-500" />
          )}
        </div>
      </div>

      {/* Validation error message */}
      {validationState === "invalid" && validationError && (
        <p className="mt-1 text-xs text-red-600">{validationError}</p>
      )}

      {/* Syntax hint */}
      {validationState === "idle" && (
        <p className="mt-0.5 text-xs text-zinc-400">
          Anaplan-compatible formula syntax.{" "}
          <span className="italic text-zinc-300">
            Autocomplete: TODO
          </span>
        </p>
      )}
    </div>
  );
}

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

function XCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}
