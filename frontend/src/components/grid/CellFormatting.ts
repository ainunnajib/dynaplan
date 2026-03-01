export type CellFormat = "number" | "text" | "boolean" | "date" | "list" | "percentage" | "currency";

/**
 * Format a cell value for display.
 * @param value  Raw stored value (number, string, boolean, null)
 * @param format Format type
 * @param decimals Number of decimal places (for number/percentage)
 */
export function formatCellValue(
  value: number | string | boolean | null | undefined,
  format: CellFormat,
  decimals = 2
): string {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  switch (format) {
    case "number": {
      const num = Number(value);
      if (isNaN(num)) return String(value);
      if (num < 0) {
        return `(${Math.abs(num).toLocaleString(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })})`;
      }
      return num.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    }

    case "percentage": {
      const num = Number(value);
      if (isNaN(num)) return String(value);
      const pct = num * 100;
      if (pct < 0) {
        return `(${Math.abs(pct).toLocaleString(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })}%)`;
      }
      return `${pct.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}%`;
    }

    case "currency": {
      const num = Number(value);
      if (isNaN(num)) return String(value);
      if (num < 0) {
        return `($${Math.abs(num).toLocaleString(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })})`;
      }
      return `$${num.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}`;
    }

    case "boolean": {
      if (typeof value === "boolean") return value ? "true" : "false";
      const lower = String(value).toLowerCase();
      if (lower === "true" || lower === "1") return "true";
      if (lower === "false" || lower === "0") return "false";
      return String(value);
    }

    case "date": {
      // Expect ISO date string YYYY-MM-DD or ISO datetime
      if (typeof value === "string" && value.length >= 10) {
        const d = new Date(value);
        if (!isNaN(d.getTime())) {
          return d.toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
          });
        }
      }
      return String(value);
    }

    case "text":
    case "list":
    default:
      return String(value);
  }
}

/**
 * Parse user-typed input string into a typed value appropriate for the format.
 * Returns the parsed value, or the original string if parsing cannot be done.
 */
export function parseCellInput(
  input: string,
  format: CellFormat
): number | string | boolean | null {
  const trimmed = input.trim();

  if (trimmed === "") return null;

  switch (format) {
    case "number": {
      // Strip commas and parentheses (negative notation)
      let cleaned = trimmed.replace(/,/g, "");
      let negative = false;
      if (cleaned.startsWith("(") && cleaned.endsWith(")")) {
        cleaned = cleaned.slice(1, -1);
        negative = true;
      } else if (cleaned.startsWith("-")) {
        cleaned = cleaned.slice(1);
        negative = true;
      }
      const num = parseFloat(cleaned);
      if (isNaN(num)) return trimmed;
      return negative ? -num : num;
    }

    case "percentage": {
      // Allow "12.5" or "12.5%" — store as decimal (0.125)
      let cleaned = trimmed.replace(/,/g, "").replace(/%$/, "");
      let negative = false;
      if (cleaned.startsWith("(") && cleaned.endsWith(")")) {
        cleaned = cleaned.slice(1, -1);
        negative = true;
      } else if (cleaned.startsWith("-")) {
        cleaned = cleaned.slice(1);
        negative = true;
      }
      const num = parseFloat(cleaned);
      if (isNaN(num)) return trimmed;
      const decimal = (negative ? -num : num) / 100;
      return decimal;
    }

    case "boolean": {
      const lower = trimmed.toLowerCase();
      if (lower === "true" || lower === "1" || lower === "yes") return true;
      if (lower === "false" || lower === "0" || lower === "no") return false;
      return trimmed;
    }

    case "date": {
      // Return ISO date string YYYY-MM-DD
      const d = new Date(trimmed);
      if (!isNaN(d.getTime())) {
        return d.toISOString().slice(0, 10);
      }
      return trimmed;
    }

    case "currency": {
      // Strip currency symbol, commas, and parentheses
      let cleaned = trimmed.replace(/[$,]/g, "");
      let negative = false;
      if (cleaned.startsWith("(") && cleaned.endsWith(")")) {
        cleaned = cleaned.slice(1, -1);
        negative = true;
      } else if (cleaned.startsWith("-")) {
        cleaned = cleaned.slice(1);
        negative = true;
      }
      const num = parseFloat(cleaned);
      if (isNaN(num)) return trimmed;
      return negative ? -num : num;
    }

    case "text":
    case "list":
    default:
      return trimmed;
  }
}

/**
 * Validate user input for a given format.
 * Returns an error message string if invalid, or null if valid.
 */
export function validateCellInput(
  input: string,
  format: CellFormat
): string | null {
  const trimmed = input.trim();

  if (trimmed === "") return null; // empty is always allowed (clear the cell)

  switch (format) {
    case "number": {
      let cleaned = trimmed.replace(/,/g, "");
      if (cleaned.startsWith("(") && cleaned.endsWith(")")) {
        cleaned = cleaned.slice(1, -1);
      }
      cleaned = cleaned.replace(/^-/, "");
      if (isNaN(parseFloat(cleaned)) || !/^[\d.]+$/.test(cleaned)) {
        return "Must be a valid number (e.g. 1,234.56 or (1,234.56) for negative)";
      }
      return null;
    }

    case "percentage": {
      let cleaned = trimmed.replace(/,/g, "").replace(/%$/, "");
      if (cleaned.startsWith("(") && cleaned.endsWith(")")) {
        cleaned = cleaned.slice(1, -1);
      }
      cleaned = cleaned.replace(/^-/, "");
      if (isNaN(parseFloat(cleaned)) || !/^[\d.]+$/.test(cleaned)) {
        return "Must be a valid percentage (e.g. 12.5 or 12.5%)";
      }
      return null;
    }

    case "boolean": {
      const lower = trimmed.toLowerCase();
      const valid = ["true", "false", "1", "0", "yes", "no"];
      if (!valid.includes(lower)) {
        return "Must be true or false";
      }
      return null;
    }

    case "date": {
      const d = new Date(trimmed);
      if (isNaN(d.getTime())) {
        return "Must be a valid date (e.g. 2024-01-15)";
      }
      return null;
    }

    case "currency": {
      let cleaned = trimmed.replace(/[$,]/g, "");
      if (cleaned.startsWith("(") && cleaned.endsWith(")")) {
        cleaned = cleaned.slice(1, -1);
      }
      cleaned = cleaned.replace(/^-/, "");
      if (isNaN(parseFloat(cleaned)) || !/^[\d.]+$/.test(cleaned)) {
        return "Must be a valid currency amount (e.g. $1,234.56 or ($1,234.56) for negative)";
      }
      return null;
    }

    case "text":
    case "list":
    default:
      return null;
  }
}
