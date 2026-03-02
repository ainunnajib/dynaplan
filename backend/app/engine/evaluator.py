"""
AST evaluator for the Dynaplan formula engine.

Walks the AST produced by parser.py and computes a result value given a
context dict that maps variable names to their values.

Built-in functions (case-insensitive, stored upper-case):
    Math        : ABS, ROUND, MIN, MAX, POWER, SQRT, LOG
    Aggregation : SUM, AVERAGE, COUNT, ITEMCOUNT
    Logical     : IF, AND, OR, NOT, ISBLANK
    Text        : CONCATENATE, LEFT, RIGHT, LEN, UPPER, LOWER, TRIM
    Lookup      : LOOKUP
    Time        : YEARVALUE, MONTHVALUE, QUARTERVALUE, WEEKVALUE, HALFYEARVALUE,
                  CURRENTPERIODSTART, CURRENTPERIODEND, PERIODSTART, PERIODEND,
                  TIMESUM, TIMEAVERAGE, TIMECOUNT, LAG, LEAD, OFFSET,
                  MOVINGSUM, MOVINGAVERAGE, CUMULATE, PREVIOUS, NEXT, INPERIOD
"""

import calendar
import math
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .parser import (
    ASTNode,
    NumberLiteral,
    StringLiteral,
    BooleanLiteral,
    Identifier,
    BinaryOp,
    UnaryOp,
    FunctionCall,
    Comparison,
)


# ---------------------------------------------------------------------------
# FormulaError
# ---------------------------------------------------------------------------

class FormulaError(Exception):
    """Raised when formula evaluation encounters a runtime error."""


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

Context = Dict[str, Any]


class Evaluator:
    """
    Evaluate an AST node against a variable context.

    Usage::

        result = Evaluator(context).evaluate(ast)
    """

    def __init__(self, context: Optional[Context] = None) -> None:
        self._ctx: Context = context or {}

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def evaluate(self, node: ASTNode) -> Any:
        """Recursively evaluate *node* and return its value."""
        if isinstance(node, NumberLiteral):
            return node.value

        if isinstance(node, StringLiteral):
            return node.value

        if isinstance(node, BooleanLiteral):
            return node.value

        if isinstance(node, Identifier):
            name = node.name
            if name not in self._ctx:
                raise FormulaError(f"Undefined variable: {name!r}")
            return self._ctx[name]

        if isinstance(node, UnaryOp):
            return self._eval_unary(node)

        if isinstance(node, BinaryOp):
            return self._eval_binary(node)

        if isinstance(node, Comparison):
            return self._eval_comparison(node)

        if isinstance(node, FunctionCall):
            return self._eval_function(node)

        raise FormulaError(f"Unknown AST node type: {type(node).__name__}")

    # ------------------------------------------------------------------
    # Unary operators
    # ------------------------------------------------------------------

    def _eval_unary(self, node: UnaryOp) -> Any:
        val = self.evaluate(node.operand)
        if node.op == "-":
            if not isinstance(val, (int, float)):
                raise FormulaError(
                    f"Unary minus requires a number, got {type(val).__name__}"
                )
            return -val
        if node.op == "NOT":
            return not self._to_bool(val)
        raise FormulaError(f"Unknown unary operator: {node.op!r}")

    # ------------------------------------------------------------------
    # Binary operators
    # ------------------------------------------------------------------

    def _eval_binary(self, node: BinaryOp) -> Any:
        op = node.op

        # Short-circuit logical operators
        if op == "AND":
            left = self.evaluate(node.left)
            if not self._to_bool(left):
                return False
            return self._to_bool(self.evaluate(node.right))

        if op == "OR":
            left = self.evaluate(node.left)
            if self._to_bool(left):
                return True
            return self._to_bool(self.evaluate(node.right))

        left = self.evaluate(node.left)
        right = self.evaluate(node.right)

        if op == "+":
            # Support string concatenation with +
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            return self._num(left, "+") + self._num(right, "+")

        if op == "-":
            return self._num(left, "-") - self._num(right, "-")

        if op == "*":
            return self._num(left, "*") * self._num(right, "*")

        if op == "/":
            divisor = self._num(right, "/")
            if divisor == 0:
                raise FormulaError("Division by zero")
            return self._num(left, "/") / divisor

        if op == "^":
            base = self._num(left, "^")
            exp = self._num(right, "^")
            return math.pow(base, exp)

        raise FormulaError(f"Unknown binary operator: {op!r}")

    # ------------------------------------------------------------------
    # Comparison operators
    # ------------------------------------------------------------------

    def _eval_comparison(self, node: Comparison) -> bool:
        left = self.evaluate(node.left)
        right = self.evaluate(node.right)
        op = node.op

        if op == "=":
            return left == right
        if op == "<>":
            return left != right
        if op == "<":
            return self._cmp_values(left, right) < 0
        if op == ">":
            return self._cmp_values(left, right) > 0
        if op == "<=":
            return self._cmp_values(left, right) <= 0
        if op == ">=":
            return self._cmp_values(left, right) >= 0

        raise FormulaError(f"Unknown comparison operator: {op!r}")

    def _cmp_values(self, a: Any, b: Any) -> int:
        try:
            if a < b:
                return -1
            if a > b:
                return 1
            return 0
        except TypeError:
            raise FormulaError(
                f"Cannot compare {type(a).__name__} with {type(b).__name__}"
            )

    # ------------------------------------------------------------------
    # Built-in functions
    # ------------------------------------------------------------------

    def _eval_function(self, node: FunctionCall) -> Any:
        name = node.name   # already upper-cased by parser

        # IF is special — lazy evaluation of branches
        if name == "IF":
            return self._fn_if(node.args)

        # Evaluate all arguments eagerly for other functions
        args = [self.evaluate(a) for a in node.args]

        # --- Math ---
        if name == "ABS":
            self._check_arity(name, args, 1)
            return abs(self._num(args[0], name))

        if name == "ROUND":
            self._check_arity(name, args, 2)
            n = self._num(args[0], name)
            decimals = int(self._num(args[1], name))
            return round(n, decimals)

        if name == "MIN":
            if len(args) == 0:
                raise FormulaError("MIN requires at least one argument")
            flat = self._flatten_numbers(args, name)
            return min(flat)

        if name == "MAX":
            if len(args) == 0:
                raise FormulaError("MAX requires at least one argument")
            flat = self._flatten_numbers(args, name)
            return max(flat)

        if name == "POWER":
            self._check_arity(name, args, 2)
            return math.pow(self._num(args[0], name), self._num(args[1], name))

        if name == "SQRT":
            self._check_arity(name, args, 1)
            n = self._num(args[0], name)
            if n < 0:
                raise FormulaError(f"SQRT of negative number: {n}")
            return math.sqrt(n)

        if name == "LOG":
            # LOG(x) = log10(x),  LOG(x, base)
            if len(args) not in (1, 2):
                raise FormulaError("LOG requires 1 or 2 arguments")
            x = self._num(args[0], name)
            if x <= 0:
                raise FormulaError(f"LOG of non-positive number: {x}")
            if len(args) == 2:
                base = self._num(args[1], name)
                return math.log(x, base)
            return math.log10(x)

        # --- Aggregation ---
        if name == "SUM":
            if len(args) == 0:
                raise FormulaError("SUM requires at least one argument")
            flat = self._flatten_numbers(args, name)
            return sum(flat)

        if name == "AVERAGE":
            if len(args) == 0:
                raise FormulaError("AVERAGE requires at least one argument")
            flat = self._flatten_numbers(args, name)
            if len(flat) == 0:
                raise FormulaError("AVERAGE called with empty list")
            return sum(flat) / len(flat)

        if name == "COUNT":
            if len(args) == 0:
                raise FormulaError("COUNT requires at least one argument")
            flat: List[Any] = []
            for a in args:
                if isinstance(a, list):
                    flat.extend(a)
                else:
                    flat.append(a)
            return float(len(flat))

        if name == "ITEMCOUNT":
            self._check_arity(name, args, 1)
            if not isinstance(args[0], list):
                raise FormulaError("ITEMCOUNT requires a list argument")
            return float(len(args[0]))

        # --- Logical ---
        if name == "AND":
            return all(self._to_bool(a) for a in args)

        if name == "OR":
            return any(self._to_bool(a) for a in args)

        if name == "NOT":
            self._check_arity(name, args, 1)
            return not self._to_bool(args[0])

        if name == "ISBLANK":
            self._check_arity(name, args, 1)
            v = args[0]
            return v is None or v == "" or v == 0

        # --- Text ---
        if name == "CONCATENATE":
            return "".join(str(a) for a in args)

        if name == "LEFT":
            self._check_arity(name, args, 2)
            s = self._str(args[0], name)
            n = int(self._num(args[1], name))
            return s[:n]

        if name == "RIGHT":
            self._check_arity(name, args, 2)
            s = self._str(args[0], name)
            n = int(self._num(args[1], name))
            return s[-n:] if n > 0 else ""

        if name == "LEN":
            self._check_arity(name, args, 1)
            return float(len(self._str(args[0], name)))

        if name == "UPPER":
            self._check_arity(name, args, 1)
            return self._str(args[0], name).upper()

        if name == "LOWER":
            self._check_arity(name, args, 1)
            return self._str(args[0], name).lower()

        if name == "TRIM":
            self._check_arity(name, args, 1)
            return self._str(args[0], name).strip()

        # --- Lookup ---
        if name == "LOOKUP":
            # LOOKUP(key, list_name) — simplified: look up key in context
            if len(args) < 1:
                raise FormulaError("LOOKUP requires at least one argument")
            key = args[0]
            if len(args) == 2 and isinstance(args[1], dict):
                mapping = args[1]
                if key not in mapping:
                    raise FormulaError(f"LOOKUP: key {key!r} not found")
                return mapping[key]
            # If key itself is the result, just return it
            return key

        # --- Time ---
        if name in {
            "YEARVALUE",
            "MONTHVALUE",
            "QUARTERVALUE",
            "WEEKVALUE",
            "HALFYEARVALUE",
        }:
            return self._fn_period_value(name, args)

        if name == "CURRENTPERIODSTART":
            self._check_arity_range(name, args, 0, 1)
            period = args[0] if len(args) == 1 else self._resolve_current_period()
            if period is None:
                raise FormulaError("CURRENTPERIODSTART requires a period argument or current period context")
            start, _ = self._period_bounds(period, name)
            return start.isoformat()

        if name == "CURRENTPERIODEND":
            self._check_arity_range(name, args, 0, 1)
            period = args[0] if len(args) == 1 else self._resolve_current_period()
            if period is None:
                raise FormulaError("CURRENTPERIODEND requires a period argument or current period context")
            _, end = self._period_bounds(period, name)
            return end.isoformat()

        if name == "PERIODSTART":
            self._check_arity(name, args, 1)
            start, _ = self._period_bounds(args[0], name)
            return start.isoformat()

        if name == "PERIODEND":
            self._check_arity(name, args, 1)
            _, end = self._period_bounds(args[0], name)
            return end.isoformat()

        if name == "TIMESUM":
            self._check_arity_range(name, args, 1, 3)
            pairs = self._build_time_pairs(args[0])
            filtered = self._filter_time_pairs_by_range(
                pairs,
                args[1] if len(args) >= 2 else None,
                args[2] if len(args) >= 3 else None,
                name,
            )
            return sum(self._num(value, name) for _, value in filtered)

        if name == "TIMEAVERAGE":
            self._check_arity_range(name, args, 1, 3)
            pairs = self._build_time_pairs(args[0])
            filtered = self._filter_time_pairs_by_range(
                pairs,
                args[1] if len(args) >= 2 else None,
                args[2] if len(args) >= 3 else None,
                name,
            )
            values = [self._num(value, name) for _, value in filtered]
            if len(values) == 0:
                raise FormulaError("TIMEAVERAGE called with empty range")
            return sum(values) / len(values)

        if name == "TIMECOUNT":
            self._check_arity_range(name, args, 1, 3)
            pairs = self._build_time_pairs(args[0])
            filtered = self._filter_time_pairs_by_range(
                pairs,
                args[1] if len(args) >= 2 else None,
                args[2] if len(args) >= 3 else None,
                name,
            )
            return float(len([value for _, value in filtered if value is not None]))

        if name == "LAG":
            self._check_arity_range(name, args, 2, 3)
            series, index = self._series_and_index(args[0], name)
            offset = int(self._num(args[1], name))
            default = args[2] if len(args) == 3 else 0.0
            return self._shift_series_value(series, index, -offset, default)

        if name == "LEAD":
            self._check_arity_range(name, args, 2, 3)
            series, index = self._series_and_index(args[0], name)
            offset = int(self._num(args[1], name))
            default = args[2] if len(args) == 3 else 0.0
            return self._shift_series_value(series, index, offset, default)

        if name == "OFFSET":
            self._check_arity_range(name, args, 2, 3)
            series, index = self._series_and_index(args[0], name)
            offset = int(self._num(args[1], name))
            default = args[2] if len(args) == 3 else 0.0
            return self._shift_series_value(series, index, offset, default)

        if name == "MOVINGSUM":
            self._check_arity(name, args, 2)
            series, index = self._series_and_index(args[0], name)
            window = int(self._num(args[1], name))
            if window <= 0:
                raise FormulaError("MOVINGSUM window must be > 0")
            if len(series) == 0:
                return 0.0
            start = max(0, index - window + 1)
            return sum(self._num(series[i], name) for i in range(start, index + 1))

        if name == "MOVINGAVERAGE":
            self._check_arity(name, args, 2)
            series, index = self._series_and_index(args[0], name)
            window = int(self._num(args[1], name))
            if window <= 0:
                raise FormulaError("MOVINGAVERAGE window must be > 0")
            if len(series) == 0:
                raise FormulaError("MOVINGAVERAGE called with empty list")
            start = max(0, index - window + 1)
            values = [self._num(series[i], name) for i in range(start, index + 1)]
            if len(values) == 0:
                raise FormulaError("MOVINGAVERAGE called with empty window")
            return sum(values) / len(values)

        if name == "CUMULATE":
            self._check_arity(name, args, 1)
            series, index = self._series_and_index(args[0], name)
            if len(series) == 0:
                return 0.0
            return sum(self._num(series[i], name) for i in range(0, index + 1))

        if name == "PREVIOUS":
            self._check_arity_range(name, args, 1, 2)
            series, index = self._series_and_index(args[0], name)
            default = args[1] if len(args) == 2 else 0.0
            return self._shift_series_value(series, index, -1, default)

        if name == "NEXT":
            self._check_arity_range(name, args, 1, 2)
            series, index = self._series_and_index(args[0], name)
            default = args[1] if len(args) == 2 else 0.0
            return self._shift_series_value(series, index, 1, default)

        if name == "INPERIOD":
            self._check_arity(name, args, 2)
            target_date = self._coerce_date(args[0], name)
            start, end = self._period_bounds(args[1], name)
            return start <= target_date <= end

        raise FormulaError(f"Unknown function: {name!r}")

    # ------------------------------------------------------------------
    # IF — lazy
    # ------------------------------------------------------------------

    def _fn_if(self, arg_nodes: List[ASTNode]) -> Any:
        if len(arg_nodes) != 3:
            raise FormulaError(
                f"IF requires exactly 3 arguments, got {len(arg_nodes)}"
            )
        condition = self.evaluate(arg_nodes[0])
        if self._to_bool(condition):
            return self.evaluate(arg_nodes[1])
        return self.evaluate(arg_nodes[2])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _num(self, value: Any, context_label: str = "") -> float:
        if isinstance(value, bool):
            # bool is a subclass of int in Python; treat True=1, False=0
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        raise FormulaError(
            f"Expected a number{' in ' + context_label if context_label else ''}, "
            f"got {type(value).__name__}: {value!r}"
        )

    def _str(self, value: Any, context_label: str = "") -> str:
        if isinstance(value, str):
            return value
        raise FormulaError(
            f"Expected a string{' in ' + context_label if context_label else ''}, "
            f"got {type(value).__name__}: {value!r}"
        )

    def _to_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if value is None:
            return False
        return bool(value)

    def _check_arity(self, name: str, args: List[Any], expected: int) -> None:
        if len(args) != expected:
            raise FormulaError(
                f"{name} requires exactly {expected} argument(s), got {len(args)}"
            )

    def _check_arity_range(
        self,
        name: str,
        args: List[Any],
        min_expected: int,
        max_expected: int,
    ) -> None:
        if len(args) < min_expected or len(args) > max_expected:
            raise FormulaError(
                f"{name} requires between {min_expected} and {max_expected} "
                f"argument(s), got {len(args)}"
            )

    def _flatten_numbers(self, args: List[Any], context_label: str) -> List[float]:
        """Flatten nested lists and convert all elements to float."""
        result: List[float] = []
        for a in args:
            if isinstance(a, list):
                for item in a:
                    result.append(self._num(item, context_label))
            else:
                result.append(self._num(a, context_label))
        return result

    # ------------------------------------------------------------------
    # Time helpers
    # ------------------------------------------------------------------

    def _resolve_context_value(self, keys: List[str]) -> Any:
        for key in keys:
            if key in self._ctx:
                return self._ctx[key]
        return None

    def _resolve_current_period(self) -> Any:
        return self._resolve_context_value(
            ["CURRENT_PERIOD", "current_period", "_current_period"]
        )

    def _resolve_current_index(self, series_length: int) -> int:
        if series_length <= 0:
            return 0
        raw_index = self._resolve_context_value(
            ["CURRENT_INDEX", "current_index", "_current_index"]
        )
        if raw_index is None:
            return series_length - 1
        index = int(self._num(raw_index, "CURRENT_INDEX"))
        return max(0, min(series_length - 1, index))

    def _resolve_time_periods(self, override: Optional[Any] = None) -> List[Any]:
        if override is not None:
            if isinstance(override, list):
                return list(override)
            raise FormulaError("Time periods override must be a list")

        value = self._resolve_context_value(
            ["TIME_PERIODS", "time_periods", "_time_periods", "PERIODS", "periods"]
        )
        if value is None:
            return []
        if not isinstance(value, list):
            raise FormulaError("TIME_PERIODS context value must be a list")
        return list(value)

    def _series_and_index(self, value: Any, context_label: str) -> Tuple[List[Any], int]:
        if isinstance(value, dict) and "series" in value:
            series = value.get("series")
            if not isinstance(series, list):
                raise FormulaError(f"{context_label} expects 'series' to be a list")
            if len(series) == 0:
                return [], 0
            raw_index = value.get("index")
            if raw_index is None:
                raw_index = self._resolve_context_value(
                    ["CURRENT_INDEX", "current_index", "_current_index"]
                )
            if raw_index is None:
                return series, len(series) - 1
            index = int(self._num(raw_index, context_label))
            return series, max(0, min(len(series) - 1, index))

        if isinstance(value, list):
            if len(value) == 0:
                return [], 0
            return value, self._resolve_current_index(len(value))

        fallback_series = self._resolve_context_value(
            ["TIME_SERIES", "time_series", "_time_series"]
        )
        if isinstance(fallback_series, list) and len(fallback_series) > 0:
            return fallback_series, self._resolve_current_index(len(fallback_series))

        return [value], 0

    def _shift_series_value(
        self,
        series: List[Any],
        index: int,
        delta: int,
        default: Any,
    ) -> Any:
        if len(series) == 0:
            return default
        target = index + delta
        if target < 0 or target >= len(series):
            return default
        return series[target]

    def _build_time_pairs(self, values: Any) -> List[Tuple[Any, Any]]:
        if isinstance(values, dict):
            return [(period, value) for period, value in values.items()]

        if isinstance(values, list):
            periods = self._resolve_time_periods()
            pairs: List[Tuple[Any, Any]] = []
            if len(periods) > 0:
                limit = min(len(periods), len(values))
                for i in range(limit):
                    pairs.append((periods[i], values[i]))
                for i in range(limit, len(values)):
                    pairs.append((None, values[i]))
                return pairs
            return [(None, value) for value in values]

        return [(self._resolve_current_period(), values)]

    def _filter_time_pairs_by_range(
        self,
        pairs: List[Tuple[Any, Any]],
        start_period: Optional[Any],
        end_period: Optional[Any],
        context_label: str,
    ) -> List[Tuple[Any, Any]]:
        if start_period is None and end_period is None:
            return pairs

        range_start = date.min
        range_end = date.max
        if start_period is not None:
            range_start, _ = self._period_bounds(start_period, context_label)
        if end_period is not None:
            _, range_end = self._period_bounds(end_period, context_label)

        result: List[Tuple[Any, Any]] = []
        for period, value in pairs:
            if period is None:
                # Without period metadata there is no reliable range filtering.
                continue
            try:
                p_start, p_end = self._period_bounds(period, context_label)
            except FormulaError:
                continue
            if p_end >= range_start and p_start <= range_end:
                result.append((period, value))
        return result

    def _fn_period_value(self, name: str, args: List[Any]) -> float:
        self._check_arity_range(name, args, 1, 2)
        values = args[0]
        target = args[1] if len(args) == 2 else self._resolve_current_period()

        unit_by_name = {
            "YEARVALUE": "year",
            "MONTHVALUE": "month",
            "QUARTERVALUE": "quarter",
            "WEEKVALUE": "week",
            "HALFYEARVALUE": "half_year",
        }
        unit = unit_by_name[name]

        pairs = self._build_time_pairs(values)
        if len(pairs) == 0:
            return 0.0

        # Scalar inputs behave as identity.
        if not isinstance(values, (list, dict)):
            return self._num(values, name)

        target_value: Optional[int] = None
        if target is not None:
            target_value = self._period_component(target, unit, name)

        total = 0.0
        matched = False
        for period, value in pairs:
            amount = self._num(value, name)
            if target_value is None:
                total += amount
                matched = True
                continue

            if period is None:
                continue

            try:
                component = self._period_component(period, unit, name)
            except FormulaError:
                continue

            if component == target_value:
                total += amount
                matched = True

        if target_value is not None and not matched:
            return 0.0
        return total

    def _coerce_date(self, value: Any, context_label: str = "") -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        if isinstance(value, str):
            text = value.strip()
            if len(text) == 0:
                raise FormulaError(f"Expected a date in {context_label}, got empty string")

            try:
                return date.fromisoformat(text)
            except ValueError:
                pass

            try:
                normalized = text.replace("Z", "+00:00")
                return datetime.fromisoformat(normalized).date()
            except ValueError:
                pass

            # Common case: datetime-like text where date is the first 10 chars.
            if len(text) >= 10:
                try:
                    return date.fromisoformat(text[:10])
                except ValueError:
                    pass

        raise FormulaError(
            f"Expected a date{' in ' + context_label if context_label else ''}, got "
            f"{type(value).__name__}: {value!r}"
        )

    def _period_bounds(
        self, value: Any, context_label: str = ""
    ) -> Tuple[date, date]:
        if isinstance(value, dict):
            if "start_date" in value and "end_date" in value:
                start = self._coerce_date(value["start_date"], context_label)
                end = self._coerce_date(value["end_date"], context_label)
                if start > end:
                    raise FormulaError("Period start_date must be <= end_date")
                return start, end

            if "start" in value and "end" in value:
                start = self._coerce_date(value["start"], context_label)
                end = self._coerce_date(value["end"], context_label)
                if start > end:
                    raise FormulaError("Period start must be <= end")
                return start, end

            if "code" in value:
                return self._period_bounds(value["code"], context_label)

        if isinstance(value, datetime):
            d = value.date()
            return d, d
        if isinstance(value, date):
            return value, value

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            year = int(value)
            if year < 1:
                raise FormulaError(f"Invalid period year: {year}")
            return date(year, 1, 1), date(year, 12, 31)

        if isinstance(value, str):
            text = value.strip()
            if len(text) == 0:
                raise FormulaError("Period text cannot be empty")

            # First allow plain dates / datetimes.
            try:
                d = self._coerce_date(text, context_label)
                return d, d
            except FormulaError:
                pass

            # FY year: FY2024
            m = re.match(r"^FY(\d{4})$", text, flags=re.IGNORECASE)
            if m:
                year = int(m.group(1))
                return date(year, 1, 1), date(year, 12, 31)

            # FY quarter / calendar quarter: FY2024-Q2 or 2024-Q2
            m = re.match(r"^(?:FY)?(\d{4})-Q([1-4])$", text, flags=re.IGNORECASE)
            if m:
                year = int(m.group(1))
                quarter = int(m.group(2))
                start_month = (quarter - 1) * 3 + 1
                start = date(year, start_month, 1)
                end_month = start_month + 2
                end_day = calendar.monthrange(year, end_month)[1]
                end = date(year, end_month, end_day)
                return start, end

            # FY half / calendar half: FY2024-H2 or 2024-H1
            m = re.match(r"^(?:FY)?(\d{4})-H([12])$", text, flags=re.IGNORECASE)
            if m:
                year = int(m.group(1))
                half = int(m.group(2))
                start_month = 1 if half == 1 else 7
                end_month = 6 if half == 1 else 12
                start = date(year, start_month, 1)
                end_day = calendar.monthrange(year, end_month)[1]
                end = date(year, end_month, end_day)
                return start, end

            # Month period: 2024-03
            m = re.match(r"^(\d{4})-(\d{2})$", text)
            if m:
                year = int(m.group(1))
                month = int(m.group(2))
                if month < 1 or month > 12:
                    raise FormulaError(f"Invalid month in period: {text!r}")
                start = date(year, month, 1)
                end = date(year, month, calendar.monthrange(year, month)[1])
                return start, end

            # ISO week period: 2024-W05
            m = re.match(r"^(\d{4})-W(\d{1,2})$", text, flags=re.IGNORECASE)
            if m:
                year = int(m.group(1))
                week = int(m.group(2))
                try:
                    start = date.fromisocalendar(year, week, 1)
                    end = date.fromisocalendar(year, week, 7)
                except ValueError:
                    raise FormulaError(f"Invalid ISO week in period: {text!r}")
                return start, end

            # Month-local week code used by generated time-calendar overflow labels:
            # YYYY-MM-WN (e.g. 2024-01-W1)
            m = re.match(r"^(\d{4})-(\d{2})-W(\d{1,2})$", text, flags=re.IGNORECASE)
            if m:
                year = int(m.group(1))
                month = int(m.group(2))
                week = int(m.group(3))
                if month < 1 or month > 12 or week < 1:
                    raise FormulaError(f"Invalid month-week period: {text!r}")
                start = date(year, month, 1) + timedelta(days=(week - 1) * 7)
                if start.month != month:
                    raise FormulaError(f"Invalid month-week period: {text!r}")
                month_end = date(year, month, calendar.monthrange(year, month)[1])
                end = min(start + timedelta(days=6), month_end)
                return start, end

        raise FormulaError(
            f"Expected a recognizable period{' in ' + context_label if context_label else ''}, "
            f"got {type(value).__name__}: {value!r}"
        )

    def _period_component(self, value: Any, unit: str, context_label: str) -> int:
        if isinstance(value, bool):
            raise FormulaError(f"Boolean is not a valid {unit} selector in {context_label}")

        if isinstance(value, (int, float)):
            return int(value)

        if isinstance(value, dict):
            map_keys = {
                "year": ["year"],
                "month": ["month"],
                "quarter": ["quarter", "q"],
                "week": ["week", "week_number"],
                "half_year": ["half", "half_year", "halfyear", "h"],
            }
            for key in map_keys.get(unit, []):
                if key in value:
                    return int(self._num(value[key], context_label))

        start, _ = self._period_bounds(value, context_label)
        if unit == "year":
            return start.year
        if unit == "month":
            return start.month
        if unit == "quarter":
            return ((start.month - 1) // 3) + 1
        if unit == "week":
            return int(start.isocalendar()[1])
        if unit == "half_year":
            return 1 if start.month <= 6 else 2
        raise FormulaError(f"Unknown period unit: {unit}")
