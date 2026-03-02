import type {
  ConditionalFormatRule,
  ConditionalNumberFormat,
} from "@/lib/api";
import type { CellFormat } from "./CellFormatting";

export interface ResolvedConditionalFormatting {
  backgroundColor?: string;
  textColor?: string;
  bold?: boolean;
  italic?: boolean;
  displayFormat?: CellFormat;
  icon?: string;
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string") {
    const parsed = Number(value.trim());
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function toBoolean(value: unknown): boolean | null {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "true" || normalized === "1" || normalized === "yes") {
      return true;
    }
    if (normalized === "false" || normalized === "0" || normalized === "no") {
      return false;
    }
  }
  return null;
}

function toComparableString(value: unknown): string {
  return String(value).trim().toLowerCase();
}

function matchesRule(
  cellValue: number | string | boolean | null,
  rule: ConditionalFormatRule
): boolean {
  if (cellValue === null || cellValue === undefined || cellValue === "") {
    return false;
  }

  if (rule.operator === "gt" || rule.operator === "gte" || rule.operator === "lt" || rule.operator === "lte") {
    const left = toNumber(cellValue);
    const right = toNumber(rule.value);
    if (left === null || right === null) return false;
    if (rule.operator === "gt") return left > right;
    if (rule.operator === "gte") return left >= right;
    if (rule.operator === "lt") return left < right;
    return left <= right;
  }

  const leftBool = toBoolean(cellValue);
  const rightBool = toBoolean(rule.value);
  if (leftBool !== null && rightBool !== null) {
    return rule.operator === "eq" ? leftBool === rightBool : leftBool !== rightBool;
  }

  const leftNum = toNumber(cellValue);
  const rightNum = toNumber(rule.value);
  if (leftNum !== null && rightNum !== null) {
    return rule.operator === "eq" ? leftNum === rightNum : leftNum !== rightNum;
  }

  const leftText = toComparableString(cellValue);
  const rightText = toComparableString(rule.value);
  return rule.operator === "eq" ? leftText === rightText : leftText !== rightText;
}

function mapNumberFormat(numberFormat: ConditionalNumberFormat): CellFormat {
  if (numberFormat === "currency") return "currency";
  if (numberFormat === "percentage") return "percentage";
  return "number";
}

function normalizeIcon(icon: string): string {
  const normalized = icon.trim().toLowerCase();
  if (normalized === "arrow-up") return "^";
  if (normalized === "arrow-down") return "v";
  if (normalized === "check") return "+";
  if (normalized === "cross") return "x";
  if (normalized === "warning") return "!";
  if (normalized === "star") return "*";
  if (normalized === "dot") return ".";
  return icon.trim();
}

export function resolveConditionalFormatting(
  cellValue: number | string | boolean | null,
  rules: ConditionalFormatRule[] | undefined
): ResolvedConditionalFormatting {
  if (!rules || rules.length === 0) {
    return {};
  }

  const resolved: ResolvedConditionalFormatting = {};
  for (const rule of rules) {
    if (!rule.enabled) continue;
    if (!matchesRule(cellValue, rule)) continue;

    if (rule.style.background_color) {
      resolved.backgroundColor = rule.style.background_color;
    }
    if (rule.style.text_color) {
      resolved.textColor = rule.style.text_color;
    }
    if (typeof rule.style.bold === "boolean") {
      resolved.bold = rule.style.bold;
    }
    if (typeof rule.style.italic === "boolean") {
      resolved.italic = rule.style.italic;
    }
    if (rule.style.number_format) {
      resolved.displayFormat = mapNumberFormat(rule.style.number_format);
    }
    if (rule.style.icon) {
      resolved.icon = normalizeIcon(rule.style.icon);
    }
  }

  return resolved;
}
