"""
AST evaluator for the Dynaplan formula engine.

Walks the AST produced by parser.py and computes a result value given a
context dict that maps variable names to their values.

Built-in functions (case-insensitive, stored upper-case):
    Math        : ABS, ROUND, MIN, MAX, POWER, SQRT, LOG
    Aggregation : SUM, AVERAGE, COUNT, ITEMCOUNT, SUMIF, COUNTIF, AVERAGEIF,
                  MEDIAN, STDEV, VARIANCE, PERCENTILE, LARGE, SMALL, GROWTH
    Logical     : IF, AND, OR, NOT, ISBLANK
    Text        : CONCATENATE, LEFT, RIGHT, LEN, UPPER, LOWER, TRIM,
                  MID, FIND, SUBSTITUTE, TEXT, VALUE, TEXTLIST, MAKETEXT
    Lookup      : FINDITEM, ITEM, PARENT, CHILDREN, ISLEAF, ISANCESTOR,
                  LOOKUP, SELECT, NAME, CODE, RANK, RANKLIST, COLLECT, POST
    Time        : YEARVALUE, MONTHVALUE, QUARTERVALUE, WEEKVALUE, HALFYEARVALUE,
                  CURRENTPERIODSTART, CURRENTPERIODEND, PERIODSTART, PERIODEND,
                  TIMESUM, TIMEAVERAGE, TIMECOUNT, LAG, LEAD, OFFSET,
                  MOVINGSUM, MOVINGAVERAGE, CUMULATE, PREVIOUS, NEXT, INPERIOD,
                  PERIODOFFSET,
                  YEARTODATE, MONTHTODATE, DATE, DATEVALUE, TODAY
    Math (extra): CEILING, FLOOR, MOD, SIGN
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
            if (
                len(args) == 2
                and isinstance(args[1], dict)
                and isinstance(args[0], (dict, list))
            ):
                return self._fn_sum_mapped(args[0], args[1], name)
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

        if name == "SUMIF":
            self._check_arity(name, args, 2)
            values = self._range_values(args[0])
            matched = [
                value
                for value in values
                if self._criteria_matches(value, args[1], name)
            ]
            return sum(self._num(value, name) for value in matched)

        if name == "COUNTIF":
            self._check_arity(name, args, 2)
            values = self._range_values(args[0])
            return float(
                len(
                    [
                        value
                        for value in values
                        if self._criteria_matches(value, args[1], name)
                    ]
                )
            )

        if name == "AVERAGEIF":
            self._check_arity(name, args, 2)
            values = self._range_values(args[0])
            matched = [
                self._num(value, name)
                for value in values
                if self._criteria_matches(value, args[1], name)
            ]
            if len(matched) == 0:
                raise FormulaError("AVERAGEIF found no matching values")
            return sum(matched) / len(matched)

        if name == "MEDIAN":
            self._check_arity(name, args, 1)
            values = sorted(self._range_numbers(args[0], name))
            if len(values) == 0:
                raise FormulaError("MEDIAN called with empty range")
            mid = len(values) // 2
            if len(values) % 2 == 1:
                return values[mid]
            return (values[mid - 1] + values[mid]) / 2.0

        if name == "STDEV":
            self._check_arity(name, args, 1)
            values = self._range_numbers(args[0], name)
            variance = self._sample_variance(values, name)
            return math.sqrt(variance)

        if name == "VARIANCE":
            self._check_arity(name, args, 1)
            values = self._range_numbers(args[0], name)
            return self._sample_variance(values, name)

        if name == "PERCENTILE":
            self._check_arity(name, args, 2)
            values = self._range_numbers(args[0], name)
            k = self._num(args[1], name)
            return self._percentile(values, k, name)

        if name == "LARGE":
            self._check_arity(name, args, 2)
            values = sorted(self._range_numbers(args[0], name), reverse=True)
            k = int(self._num(args[1], name))
            if k <= 0:
                raise FormulaError("LARGE requires k >= 1")
            if k > len(values):
                raise FormulaError("LARGE k is out of bounds for range length")
            return values[k - 1]

        if name == "SMALL":
            self._check_arity(name, args, 2)
            values = sorted(self._range_numbers(args[0], name))
            k = int(self._num(args[1], name))
            if k <= 0:
                raise FormulaError("SMALL requires k >= 1")
            if k > len(values):
                raise FormulaError("SMALL k is out of bounds for range length")
            return values[k - 1]

        if name == "GROWTH":
            self._check_arity(name, args, 3)
            known_y_values, known_x_values = self._growth_known_pairs(
                args[0], args[1], name
            )
            if len(known_y_values) < 2:
                raise FormulaError("GROWTH requires at least 2 known data points")

            mean_x = sum(known_x_values) / len(known_x_values)
            mean_y = sum(known_y_values) / len(known_y_values)
            denominator = sum((x - mean_x) ** 2 for x in known_x_values)
            if denominator == 0:
                raise FormulaError("GROWTH requires known_x values with non-zero variance")

            numerator = sum(
                (known_x_values[i] - mean_x) * (known_y_values[i] - mean_y)
                for i in range(len(known_x_values))
            )
            slope = numerator / denominator
            intercept = mean_y - slope * mean_x

            new_x = args[2]
            if isinstance(new_x, dict):
                return {
                    key: intercept + slope * self._num(value, name)
                    for key, value in new_x.items()
                }
            if isinstance(new_x, list):
                return [intercept + slope * self._num(value, name) for value in new_x]
            return intercept + slope * self._num(new_x, name)

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

        if name == "MID":
            self._check_arity(name, args, 3)
            text = self._str(args[0], name)
            start = int(self._num(args[1], name))
            length = int(self._num(args[2], name))
            if length <= 0:
                return ""
            start_index = max(0, start - 1)
            return text[start_index:start_index + length]

        if name == "FIND":
            self._check_arity(name, args, 2)
            search_text = self._str(args[0], name)
            full_text = self._str(args[1], name)
            if len(search_text) == 0:
                return 1.0
            index = full_text.find(search_text)
            return 0.0 if index < 0 else float(index + 1)

        if name == "SUBSTITUTE":
            self._check_arity(name, args, 3)
            text = self._str(args[0], name)
            old_text = self._str(args[1], name)
            new_text = self._str(args[2], name)
            return text.replace(old_text, new_text)

        if name == "TEXT":
            self._check_arity_range(name, args, 1, 2)
            format_pattern = args[1] if len(args) == 2 else None
            return self._fn_text(args[0], format_pattern)

        if name == "VALUE":
            self._check_arity(name, args, 1)
            return self._fn_value(args[0], name)

        if name == "TEXTLIST":
            self._check_arity(name, args, 1)
            return self._fn_textlist(args[0])

        if name == "MAKETEXT":
            self._check_arity_range(name, args, 1, 128)
            return self._fn_maketext(args[0], args[1:])

        if name == "CEILING":
            self._check_arity(name, args, 1)
            return float(math.ceil(self._num(args[0], name)))

        if name == "FLOOR":
            self._check_arity(name, args, 1)
            return float(math.floor(self._num(args[0], name)))

        if name == "MOD":
            self._check_arity(name, args, 2)
            divisor = self._num(args[1], name)
            if divisor == 0:
                raise FormulaError("MOD divisor cannot be zero")
            return self._num(args[0], name) % divisor

        if name == "SIGN":
            self._check_arity(name, args, 1)
            number = self._num(args[0], name)
            if number > 0:
                return 1.0
            if number < 0:
                return -1.0
            return 0.0

        # --- Lookup & cross-module ---
        if name == "FINDITEM":
            self._check_arity(name, args, 2)
            return self._fn_finditem(args[0], args[1])

        if name == "ITEM":
            self._check_arity(name, args, 1)
            return self._fn_item(args[0])

        if name == "PARENT":
            self._check_arity(name, args, 1)
            return self._resolve_parent(args[0])

        if name == "CHILDREN":
            self._check_arity(name, args, 1)
            return self._resolve_children(args[0])

        if name == "ISLEAF":
            self._check_arity(name, args, 1)
            return len(self._resolve_children(args[0])) == 0

        if name == "ISANCESTOR":
            self._check_arity(name, args, 2)
            return self._fn_isancestor(args[0], args[1])

        if name == "LOOKUP":
            self._check_arity_range(name, args, 1, 2)
            if len(args) == 1:
                return args[0]
            return self._fn_lookup(args[0], args[1], name)

        if name == "SELECT":
            self._check_arity(name, args, 2)
            return self._fn_select(args[0], args[1], name)

        if name == "NAME":
            self._check_arity(name, args, 1)
            return self._fn_name(args[0])

        if name == "CODE":
            self._check_arity(name, args, 1)
            return self._fn_code(args[0])

        if name == "RANK":
            self._check_arity(name, args, 2)
            return self._fn_rank(args[0], args[1], name)

        if name == "RANKLIST":
            self._check_arity(name, args, 3)
            return self._fn_ranklist(args[0], args[1], args[2], name)

        if name == "COLLECT":
            self._check_arity(name, args, 2)
            return self._fn_collect(args[0], args[1], name)

        if name == "POST":
            self._check_arity(name, args, 2)
            return self._fn_post(args[0], args[1])

        # --- Time ---
        if name in {
            "YEARVALUE",
            "MONTHVALUE",
            "QUARTERVALUE",
            "WEEKVALUE",
            "HALFYEARVALUE",
        }:
            return self._fn_period_value(name, args)

        if name == "YEARTODATE":
            self._check_arity_range(name, args, 0, 1)
            period = args[0] if len(args) == 1 else self._resolve_current_period()
            if period is None:
                period = date.today()
            start, _ = self._period_bounds(period, name)
            return f"YTD {start.year:04d}"

        if name == "MONTHTODATE":
            self._check_arity_range(name, args, 0, 1)
            period = args[0] if len(args) == 1 else self._resolve_current_period()
            if period is None:
                period = date.today()
            start, _ = self._period_bounds(period, name)
            return f"MTD {start.year:04d}-{start.month:02d}"

        if name == "DATE":
            self._check_arity(name, args, 3)
            year = int(self._num(args[0], name))
            month = int(self._num(args[1], name))
            day = int(self._num(args[2], name))
            try:
                return date(year, month, day).isoformat()
            except ValueError as exc:
                raise FormulaError(f"DATE produced an invalid date: {exc}")

        if name == "DATEVALUE":
            self._check_arity(name, args, 1)
            return self._coerce_date(args[0], name).isoformat()

        if name == "TODAY":
            self._check_arity(name, args, 0)
            return date.today().isoformat()

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

        if name == "PERIODOFFSET":
            self._check_arity_range(name, args, 2, 3)
            target_periods = self._resolve_time_periods(args[2] if len(args) == 3 else None)
            return self._period_offset(args[0], int(self._num(args[1], name)), target_periods, name)

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

    def _range_values(self, value: Any) -> List[Any]:
        if isinstance(value, list):
            return list(value)
        if isinstance(value, dict):
            return [item for item in value.values()]
        return [value]

    def _range_numbers(self, value: Any, context_label: str) -> List[float]:
        return [self._num(item, context_label) for item in self._range_values(value)]

    def _try_num(self, value: Any) -> Optional[float]:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if len(text) == 0:
                return None
            try:
                return float(text)
            except ValueError:
                return None
        return None

    def _coerce_criteria_operand(self, value: str) -> Any:
        text = value.strip()
        if len(text) == 0:
            return ""

        if (
            len(text) >= 2
            and (
                (text.startswith('"') and text.endswith('"'))
                or (text.startswith("'") and text.endswith("'"))
            )
        ):
            return text[1:-1]

        upper = text.upper()
        if upper == "TRUE":
            return True
        if upper == "FALSE":
            return False

        try:
            return float(text)
        except ValueError:
            return text

    def _criteria_matches(self, value: Any, criteria: Any, context_label: str) -> bool:
        operator = "="
        operand = criteria

        if isinstance(criteria, str):
            text = criteria.strip()
            for prefix in (">=", "<=", "<>", ">", "<", "="):
                if text.startswith(prefix):
                    operator = prefix
                    operand = self._coerce_criteria_operand(text[len(prefix):])
                    break
            else:
                operand = self._coerce_criteria_operand(text)

        left_num = self._try_num(value)
        right_num = self._try_num(operand)

        if operator == "=":
            if left_num is not None and right_num is not None:
                return left_num == right_num
            return self._coerce_text_value(value) == self._coerce_text_value(operand)

        if operator == "<>":
            if left_num is not None and right_num is not None:
                return left_num != right_num
            return self._coerce_text_value(value) != self._coerce_text_value(operand)

        if left_num is not None and right_num is not None:
            if operator == ">":
                return left_num > right_num
            if operator == "<":
                return left_num < right_num
            if operator == ">=":
                return left_num >= right_num
            if operator == "<=":
                return left_num <= right_num
        else:
            left_text = self._coerce_text_value(value)
            right_text = self._coerce_text_value(operand)
            if operator == ">":
                return left_text > right_text
            if operator == "<":
                return left_text < right_text
            if operator == ">=":
                return left_text >= right_text
            if operator == "<=":
                return left_text <= right_text

        raise FormulaError(f"{context_label} received unsupported criteria: {criteria!r}")

    def _sample_variance(self, values: List[float], context_label: str) -> float:
        if len(values) < 2:
            raise FormulaError(f"{context_label} requires at least 2 values")
        mean = sum(values) / len(values)
        return sum((value - mean) ** 2 for value in values) / (len(values) - 1)

    def _percentile(self, values: List[float], k: float, context_label: str) -> float:
        if len(values) == 0:
            raise FormulaError(f"{context_label} called with empty range")
        if k > 1.0 and k <= 100.0:
            k = k / 100.0
        if k < 0.0 or k > 1.0:
            raise FormulaError(f"{context_label} requires k between 0 and 1 inclusive")

        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]

        rank = k * (len(ordered) - 1)
        lower = int(math.floor(rank))
        upper = int(math.ceil(rank))
        if lower == upper:
            return ordered[lower]
        weight = rank - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * weight

    def _growth_known_pairs(
        self,
        known_y: Any,
        known_x: Any,
        context_label: str,
    ) -> Tuple[List[float], List[float]]:
        if isinstance(known_y, dict) and isinstance(known_x, dict):
            keys = [key for key in known_y.keys() if key in known_x]
            if len(keys) == 0:
                raise FormulaError(
                    "GROWTH requires known_y and known_x maps to share at least one key"
                )
            y_values = [self._num(known_y[key], context_label) for key in keys]
            x_values = [self._num(known_x[key], context_label) for key in keys]
            return y_values, x_values

        y_items = self._range_values(known_y)
        x_items = self._range_values(known_x)
        if len(y_items) != len(x_items):
            raise FormulaError("GROWTH requires known_y and known_x with matching lengths")
        if len(y_items) == 0:
            raise FormulaError("GROWTH requires at least one known data point")

        y_values = [self._num(value, context_label) for value in y_items]
        x_values = [self._num(value, context_label) for value in x_items]
        return y_values, x_values

    def _coerce_text_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, float):
            if math.isfinite(value) and value.is_integer():
                return str(int(value))
            return f"{value:g}"
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    def _parse_numeric_pattern_decimals(self, pattern: str) -> Optional[int]:
        normalized = pattern.strip()
        if len(normalized) == 0:
            return None

        plain_match = re.fullmatch(r"[#,0]+(?:\.([0#]+))?", normalized)
        if plain_match:
            fractional = plain_match.group(1)
            return 0 if fractional is None else len(fractional)

        percent_match = re.fullmatch(r"[#,0]+(?:\.([0#]+))?%", normalized)
        if percent_match:
            fractional = percent_match.group(1)
            return 0 if fractional is None else len(fractional)

        return None

    def _fn_text(self, value: Any, format_pattern: Optional[Any]) -> str:
        number = self._num(value, "TEXT")
        if format_pattern is None:
            return self._coerce_text_value(number)

        pattern = self._str(format_pattern, "TEXT").strip()
        if len(pattern) == 0 or pattern.upper() == "GENERAL":
            return self._coerce_text_value(number)

        decimals = self._parse_numeric_pattern_decimals(pattern)
        if decimals is not None:
            is_percent = pattern.endswith("%")
            number_to_format = number * 100.0 if is_percent else number
            use_grouping = "," in pattern
            if use_grouping:
                formatted = f"{number_to_format:,.{decimals}f}"
            else:
                formatted = f"{number_to_format:.{decimals}f}"
            if is_percent:
                return f"{formatted}%"
            return formatted

        try:
            return format(number, pattern)
        except (TypeError, ValueError):
            return self._coerce_text_value(number)

    def _fn_value(self, value: Any, context_label: str) -> float:
        if isinstance(value, (int, float, bool)):
            return self._num(value, context_label)

        text = self._str(value, context_label).strip()
        if len(text) == 0:
            raise FormulaError(f"{context_label} requires a non-empty text value")

        normalized = text.replace(",", "").replace("$", "")
        is_percent = normalized.endswith("%")
        if is_percent:
            normalized = normalized[:-1]

        try:
            parsed = float(normalized)
        except ValueError:
            raise FormulaError(f"{context_label} cannot parse numeric text: {text!r}")

        if is_percent:
            return parsed / 100.0
        return parsed

    def _fn_textlist(self, value: Any) -> str:
        if isinstance(value, list):
            return ", ".join(self._fn_textlist(item) for item in value)

        if isinstance(value, dict):
            for key in ("name", "code", "id", "key", "item", "member"):
                if key in value and value.get(key) is not None:
                    return self._coerce_text_value(value.get(key))

        return self._coerce_text_value(value)

    def _fn_maketext(self, pattern_value: Any, arg_values: List[Any]) -> str:
        pattern = self._str(pattern_value, "MAKETEXT")
        rendered_args = [self._coerce_text_value(value) for value in arg_values]
        result = pattern

        for index, rendered in enumerate(rendered_args):
            result = result.replace("{" + str(index) + "}", rendered)

        for rendered in rendered_args:
            if "{}" not in result:
                break
            result = result.replace("{}", rendered, 1)

        return result

    # ------------------------------------------------------------------
    # Lookup & cross-module helpers
    # ------------------------------------------------------------------

    def _list_members(self, value: Any, context_label: str) -> List[Any]:
        if isinstance(value, list):
            return list(value)

        if isinstance(value, dict):
            for key in ("members", "items", "list"):
                raw = value.get(key)
                if isinstance(raw, list):
                    return list(raw)
            return list(value.values())

        raise FormulaError(f"{context_label} requires a list-like argument")

    def _member_key_candidates(self, value: Any) -> List[Any]:
        candidates: List[Any] = []

        def _append(candidate: Any) -> None:
            if candidate is None:
                return
            for existing in candidates:
                if existing == candidate or str(existing) == str(candidate):
                    return
            candidates.append(candidate)

        if isinstance(value, dict):
            for key in ("id", "code", "name", "key", "item", "member"):
                if key in value:
                    _append(value.get(key))
        else:
            _append(value)

        # Also add string forms to support mixed key types.
        for candidate in list(candidates):
            _append(str(candidate))
        return candidates

    def _coerce_key_token(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, dict):
            for key in ("id", "code", "name", "key", "item", "member"):
                if key in value and value.get(key) is not None:
                    return str(value.get(key))
            return None
        if isinstance(value, (list, tuple, set)):
            return None
        return str(value)

    def _source_key_tokens(self, source_key: Any) -> List[str]:
        if isinstance(source_key, str):
            return [token for token in source_key.split("|") if token]
        if isinstance(source_key, (list, tuple, set)):
            return [str(token) for token in source_key]
        token = self._coerce_key_token(source_key)
        if token is not None:
            return [token]
        return [str(source_key)]

    def _find_in_mapping_by_candidates(
        self, mapping: Dict[Any, Any], candidates: List[Any]
    ) -> Any:
        for candidate in candidates:
            if candidate in mapping:
                return mapping[candidate]
            candidate_str = str(candidate)
            if candidate_str in mapping:
                return mapping[candidate_str]
        return None

    def _match_member(self, left: Any, right: Any) -> bool:
        left_candidates = self._member_key_candidates(left)
        right_candidates = self._member_key_candidates(right)
        for left_candidate in left_candidates:
            for right_candidate in right_candidates:
                if (
                    left_candidate == right_candidate
                    or str(left_candidate) == str(right_candidate)
                ):
                    return True
        return left == right

    def _find_member_record(self, item: Any) -> Optional[Dict[str, Any]]:
        if isinstance(item, dict):
            return item

        candidates = self._member_key_candidates(item)

        for key in (
            "MEMBERS_BY_ID",
            "members_by_id",
            "MEMBER_MAP",
            "member_map",
            "MEMBERS_BY_CODE",
            "members_by_code",
            "MEMBERS_BY_NAME",
            "members_by_name",
        ):
            value = self._ctx.get(key)
            if isinstance(value, dict):
                found = self._find_in_mapping_by_candidates(value, candidates)
                if isinstance(found, dict):
                    return found

        for key in ("DIMENSION_MEMBERS", "dimension_members", "_dimension_members"):
            value = self._ctx.get(key)
            if isinstance(value, list):
                for member in value:
                    if isinstance(member, dict) and self._match_member(member, item):
                        return member
        return None

    def _resolve_parent(self, item: Any) -> Any:
        if isinstance(item, dict):
            if "parent" in item:
                return item.get("parent")
            if "parent_id" in item:
                return item.get("parent_id")

        record = self._find_member_record(item)
        if isinstance(record, dict):
            if "parent" in record:
                return record.get("parent")
            if "parent_id" in record:
                return record.get("parent_id")

        candidates = self._member_key_candidates(item)
        for key in ("PARENT_MAP", "parent_map", "_parent_map", "PARENTS", "parents"):
            value = self._ctx.get(key)
            if isinstance(value, dict):
                found = self._find_in_mapping_by_candidates(value, candidates)
                if found is not None:
                    return found
        return None

    def _resolve_children(self, item: Any) -> List[Any]:
        if isinstance(item, dict) and "children" in item:
            raw = item.get("children")
            if isinstance(raw, list):
                return list(raw)
            if raw is None:
                return []
            return [raw]

        record = self._find_member_record(item)
        if isinstance(record, dict) and "children" in record:
            raw = record.get("children")
            if isinstance(raw, list):
                return list(raw)
            if raw is None:
                return []
            return [raw]

        candidates = self._member_key_candidates(item)
        for key in ("CHILDREN_MAP", "children_map", "_children_map", "CHILDREN", "children"):
            value = self._ctx.get(key)
            if isinstance(value, dict):
                found = self._find_in_mapping_by_candidates(value, candidates)
                if isinstance(found, list):
                    return list(found)
                if found is None:
                    continue
                return [found]

        members = self._resolve_context_value(
            ["DIMENSION_MEMBERS", "dimension_members", "_dimension_members"]
        )
        if isinstance(members, list):
            children: List[Any] = []
            for member in members:
                if not isinstance(member, dict):
                    continue
                parent = member.get("parent")
                if parent is None:
                    parent = member.get("parent_id")
                if self._match_member(parent, item):
                    children.append(member)
            if len(children) > 0:
                return children

        return []

    def _fn_finditem(self, list_value: Any, name: Any) -> Any:
        if isinstance(list_value, dict):
            direct = self._find_in_mapping_by_candidates(
                list_value, self._member_key_candidates(name)
            )
            if direct is not None:
                return direct

        members = self._list_members(list_value, "FINDITEM")
        for member in members:
            if self._match_member(member, name):
                return member
        return None

    def _list_name_candidates(self, list_value: Any) -> List[str]:
        names: List[str] = []

        def _append(value: Any) -> None:
            if value is None:
                return
            text = str(value)
            if len(text) == 0:
                return
            if text not in names:
                names.append(text)

        if isinstance(list_value, str):
            _append(list_value)
        elif isinstance(list_value, dict):
            for key in ("name", "id", "code", "list", "dimension"):
                if key in list_value:
                    _append(list_value.get(key))
        elif not isinstance(list_value, list):
            _append(list_value)

        return names

    def _sanitize_context_name(self, name: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()

    def _lookup_current_item_by_name(self, list_name: str) -> Any:
        name_candidates = [list_name, list_name.upper(), list_name.lower()]
        sanitized = self._sanitize_context_name(list_name)
        if sanitized:
            name_candidates.append(sanitized)

        for key in ("CURRENT_ITEMS", "current_items", "_current_items", "ITEMS", "items"):
            mapping = self._ctx.get(key)
            if isinstance(mapping, dict):
                found = self._find_in_mapping_by_candidates(mapping, name_candidates)
                if found is not None:
                    return found

        direct_keys = [
            f"CURRENT_ITEM_{sanitized}",
            f"ITEM_{sanitized}",
            f"CURRENT_ITEM.{list_name}",
            f"CURRENT_ITEM:{list_name}",
        ]
        for key in direct_keys:
            if key in self._ctx:
                return self._ctx[key]
        return None

    def _fn_item(self, list_value: Any) -> Any:
        list_names = self._list_name_candidates(list_value)

        for list_name in list_names:
            current = self._lookup_current_item_by_name(list_name)
            if current is not None:
                return current

        # If the list argument is already a value list (rather than a named list
        # token), fall back to a single-entry CURRENT_ITEMS map when available.
        if len(list_names) == 0 and isinstance(list_value, list):
            for key in ("CURRENT_ITEMS", "current_items", "_current_items"):
                mapping = self._ctx.get(key)
                if isinstance(mapping, dict) and len(mapping) == 1:
                    return list(mapping.values())[0]

        generic = self._resolve_context_value(["CURRENT_ITEM", "current_item", "_current_item"])
        if generic is not None:
            if isinstance(generic, dict) and len(list_names) > 0:
                found = self._find_in_mapping_by_candidates(generic, list_names)
                if found is not None:
                    return found
            return generic

        # If the argument itself is already a scalar member token, use it directly.
        if not isinstance(list_value, (list, dict)):
            return list_value

        raise FormulaError("ITEM requires current item context")

    def _fn_isancestor(self, ancestor: Any, descendant: Any) -> bool:
        if self._match_member(ancestor, descendant):
            return False

        seen_tokens: List[str] = []
        current = descendant
        for _ in range(0, 256):
            parent = self._resolve_parent(current)
            if parent is None:
                return False
            if self._match_member(parent, ancestor):
                return True
            token = self._coerce_key_token(parent)
            if token is not None:
                if token in seen_tokens:
                    return False
                seen_tokens.append(token)
            current = parent
        return False

    def _lookup_values_from_source_map(self, source: Dict[Any, Any], mapping: Any) -> List[Any]:
        if not isinstance(mapping, dict):
            found = self._find_in_mapping_by_candidates(
                source, self._member_key_candidates(mapping)
            )
            return [] if found is None else [found]

        for selector in ("key", "item", "member", "id", "name", "code", "select", "target"):
            if selector not in mapping:
                continue
            found = self._find_in_mapping_by_candidates(
                source, self._member_key_candidates(mapping.get(selector))
            )
            if found is not None:
                return [found]

        keys_value = mapping.get("keys")
        if isinstance(keys_value, list):
            selected: List[Any] = []
            for key_value in keys_value:
                found = self._find_in_mapping_by_candidates(
                    source, self._member_key_candidates(key_value)
                )
                if found is not None:
                    selected.append(found)
            if len(selected) > 0:
                return selected

        if len(mapping) == 1:
            value = list(mapping.values())[0]
            found = self._find_in_mapping_by_candidates(
                source, self._member_key_candidates(value)
            )
            if found is not None:
                return [found]

        reserved = {
            "key",
            "item",
            "member",
            "id",
            "name",
            "code",
            "select",
            "target",
            "keys",
            "index",
            "indexes",
            "default",
            "weights",
        }
        required_tokens: List[str] = []
        for map_key, map_value in mapping.items():
            if map_key in reserved:
                continue
            token = self._coerce_key_token(map_value)
            if token is not None and token not in required_tokens:
                required_tokens.append(token)

        if len(required_tokens) == 0:
            for map_value in mapping.values():
                token = self._coerce_key_token(map_value)
                if token is not None and token not in required_tokens:
                    required_tokens.append(token)

        if len(required_tokens) == 0:
            return []

        matches: List[Tuple[str, Any]] = []
        for source_key, source_value in source.items():
            tokens = self._source_key_tokens(source_key)
            if all(token in tokens for token in required_tokens):
                matches.append((str(source_key), source_value))

        matches.sort(key=lambda row: row[0])
        return [value for _, value in matches]

    def _lookup_values_from_source_list(
        self, source: List[Any], mapping: Any, context_label: str
    ) -> List[Any]:
        def _at_index(index: int) -> List[Any]:
            if index < 0 or index >= len(source):
                return []
            return [source[index]]

        if isinstance(mapping, dict):
            if "index" in mapping:
                index = int(self._num(mapping.get("index"), context_label))
                return _at_index(index)

            indexes = mapping.get("indexes")
            if isinstance(indexes, list):
                selected: List[Any] = []
                for raw_index in indexes:
                    index = int(self._num(raw_index, context_label))
                    if 0 <= index < len(source):
                        selected.append(source[index])
                return selected

            for selector in ("item", "member", "id", "name", "code", "select", "target"):
                if selector in mapping:
                    target = mapping.get(selector)
                    return [
                        item
                        for item in source
                        if self._match_member(item, target)
                    ]
            return []

        if isinstance(mapping, (int, float)) and not isinstance(mapping, bool):
            return _at_index(int(self._num(mapping, context_label)))

        return [
            item for item in source if self._match_member(item, mapping)
        ]

    def _fn_lookup(self, source_or_key: Any, mapping: Any, context_label: str) -> Any:
        if isinstance(source_or_key, dict):
            selected = self._lookup_values_from_source_map(source_or_key, mapping)
            if len(selected) == 0:
                return None
            return selected[0]

        if isinstance(source_or_key, list):
            selected = self._lookup_values_from_source_list(
                source_or_key, mapping, context_label
            )
            if len(selected) == 0:
                return None
            return selected[0]

        if isinstance(mapping, dict):
            found = self._find_in_mapping_by_candidates(
                mapping, self._member_key_candidates(source_or_key)
            )
            if found is None:
                raise FormulaError(f"{context_label}: key {source_or_key!r} not found")
            return found

        return source_or_key

    def _fn_select(self, source: Any, mapping: Any, context_label: str) -> Any:
        if isinstance(source, dict):
            selected = self._lookup_values_from_source_map(source, mapping)
            if len(selected) == 0:
                return None
            return selected[0]

        if isinstance(source, list):
            selected = self._lookup_values_from_source_list(source, mapping, context_label)
            if len(selected) == 0:
                return None
            return selected[0]

        return self._fn_lookup(source, mapping, context_label)

    def _fn_sum_mapped(self, source: Any, mapping: Dict[Any, Any], context_label: str) -> float:
        values: List[Any]

        if isinstance(source, dict):
            values = self._lookup_values_from_source_map(source, mapping)
        elif isinstance(source, list):
            selected = self._lookup_values_from_source_list(source, mapping, context_label)
            values = selected if len(selected) > 0 else list(source)
        else:
            return self._num(source, context_label)

        if len(values) == 0:
            return 0.0
        return sum(self._num(value, context_label) for value in values)

    def _fn_name(self, item: Any) -> str:
        if isinstance(item, dict):
            if item.get("name") is not None:
                return str(item.get("name"))
            if item.get("id") is not None:
                return str(item.get("id"))

        record = self._find_member_record(item)
        if isinstance(record, dict):
            if record.get("name") is not None:
                return str(record.get("name"))
            if record.get("id") is not None:
                return str(record.get("id"))

        return str(item)

    def _fn_code(self, item: Any) -> str:
        if isinstance(item, dict):
            if item.get("code") is not None:
                return str(item.get("code"))
            if item.get("id") is not None:
                return str(item.get("id"))

        record = self._find_member_record(item)
        if isinstance(record, dict):
            if record.get("code") is not None:
                return str(record.get("code"))
            if record.get("id") is not None:
                return str(record.get("id"))

        return str(item)

    def _rank_series_and_target(
        self,
        expr: Any,
        dimension: Any,
        context_label: str,
    ) -> Tuple[List[float], float]:
        if isinstance(expr, list):
            if len(expr) == 0:
                raise FormulaError(f"{context_label} requires a non-empty expression list")
            series = [self._num(value, context_label) for value in expr]
            index = self._resolve_current_index(len(series))
            return series, series[index]

        if isinstance(expr, dict):
            if len(expr) == 0:
                raise FormulaError(f"{context_label} requires a non-empty expression map")
            series = [self._num(value, context_label) for value in expr.values()]
            for candidate in self._member_key_candidates(dimension):
                if candidate in expr:
                    return series, self._num(expr[candidate], context_label)
                candidate_str = str(candidate)
                if candidate_str in expr:
                    return series, self._num(expr[candidate_str], context_label)
            return series, series[-1]

        target = self._num(expr, context_label)
        if isinstance(dimension, list):
            series = [self._num(value, context_label) for value in dimension]
        elif isinstance(dimension, dict):
            series = [self._num(value, context_label) for value in dimension.values()]
        else:
            series = [target]

        if len(series) == 0:
            raise FormulaError(f"{context_label} requires a non-empty dimension")
        return series, target

    def _fn_rank(self, expr: Any, dimension: Any, context_label: str) -> float:
        series, target = self._rank_series_and_target(expr, dimension, context_label)
        higher_count = len([value for value in series if value > target])
        return float(higher_count + 1)

    def _fn_ranklist(self, expr: Any, dimension: Any, n: Any, context_label: str) -> List[Any]:
        limit = int(self._num(n, context_label))
        if limit < 0:
            raise FormulaError(f"{context_label} requires n >= 0")
        if limit == 0:
            return []

        if isinstance(expr, dict):
            ranked = [
                (str(key), self._num(value, context_label))
                for key, value in expr.items()
            ]
            ranked.sort(key=lambda row: (-row[1], row[0]))
            return [key for key, _ in ranked[:limit]]

        if isinstance(expr, list):
            if len(expr) == 0:
                return []
            scores = [self._num(value, context_label) for value in expr]
            labels: List[Any]
            if isinstance(dimension, list) and len(dimension) == len(expr):
                labels = list(dimension)
            else:
                labels = list(expr)
            order = sorted(
                range(len(scores)),
                key=lambda index: (-scores[index], index),
            )
            return [labels[index] for index in order[:limit]]

        if isinstance(dimension, dict):
            ranked = [
                (str(key), self._num(value, context_label))
                for key, value in dimension.items()
            ]
            ranked.sort(key=lambda row: (-row[1], row[0]))
            return [key for key, _ in ranked[:limit]]

        if isinstance(dimension, list):
            scores = [self._num(value, context_label) for value in dimension]
            scores.sort(reverse=True)
            return scores[:limit]

        return [expr] if limit > 0 else []

    def _fn_collect(self, expr: Any, dimension: Any, context_label: str) -> List[Any]:
        if isinstance(expr, dict):
            if isinstance(dimension, list):
                selected: List[Any] = []
                for item in dimension:
                    found = self._find_in_mapping_by_candidates(
                        expr, self._member_key_candidates(item)
                    )
                    if found is not None:
                        selected.append(found)
                if len(selected) > 0:
                    return selected

            if isinstance(dimension, dict):
                selected = self._lookup_values_from_source_map(expr, dimension)
                if len(selected) > 0:
                    return selected

            return [
                expr[key]
                for key in sorted(expr.keys(), key=lambda map_key: str(map_key))
            ]

        if isinstance(expr, list):
            return list(expr)

        if isinstance(dimension, list):
            return [expr for _ in dimension]

        if isinstance(dimension, dict) and "count" in dimension:
            count = int(self._num(dimension.get("count"), context_label))
            if count < 0:
                raise FormulaError(f"{context_label} requires count >= 0")
            return [expr for _ in range(count)]

        return [expr]

    def _post_target_key(self, target: Any) -> str:
        if isinstance(target, dict):
            for key in ("target", "line_item", "line_item_id", "id", "name", "code"):
                if key in target and target.get(key) is not None:
                    return str(target.get(key))
            normalized = sorted(
                [(str(key), str(value)) for key, value in target.items()],
                key=lambda row: row[0],
            )
            return str(normalized)

        if isinstance(target, (list, tuple)):
            return "|".join(str(item) for item in target)

        return str(target)

    def _fn_post(self, target: Any, value: Any) -> Any:
        for key in ("_POST_WRITES", "POST_WRITES", "post_writes"):
            writes = self._ctx.get(key)
            if isinstance(writes, dict):
                writes[self._post_target_key(target)] = value
                break

        sink = self._ctx.get("_post_sink")
        if callable(sink):
            try:
                sink(target, value)
            except Exception as exc:
                raise FormulaError(f"POST sink failed: {exc}")

        return value

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

            context_bounds = self._period_bounds_from_context(text, context_label)
            if context_bounds is not None:
                return context_bounds

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

            # Retail period code (requires persisted calendar metadata in context):
            # FY2024-P01 or FY2024-W01
            if re.match(r"^FY\d{4}-(?:P\d{2}|W\d{1,2})$", text, flags=re.IGNORECASE):
                raise FormulaError(
                    f"{context_label or 'Period'} '{text}' requires TIME_PERIODS "
                    "context entries with start_date and end_date"
                )

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

    def _period_bounds_from_context(
        self,
        period_code: str,
        context_label: str,
    ) -> Optional[Tuple[date, date]]:
        normalized_code = period_code.strip().upper()
        for period in self._resolve_time_periods():
            if not isinstance(period, dict):
                continue
            candidate = None
            for key in ("code", "id", "name"):
                raw_candidate = period.get(key)
                if raw_candidate is not None:
                    candidate = str(raw_candidate).strip().upper()
                    break
            if candidate != normalized_code:
                continue
            if "start_date" in period and "end_date" in period:
                start = self._coerce_date(period.get("start_date"), context_label)
                end = self._coerce_date(period.get("end_date"), context_label)
                if start > end:
                    raise FormulaError("Period start_date must be <= end_date")
                return start, end
            if "start" in period and "end" in period:
                start = self._coerce_date(period.get("start"), context_label)
                end = self._coerce_date(period.get("end"), context_label)
                if start > end:
                    raise FormulaError("Period start must be <= end")
                return start, end
        return None

    def _period_identity(self, period: Any) -> Optional[str]:
        if isinstance(period, dict):
            for key in ("code", "id", "name"):
                value = period.get(key)
                if value is not None:
                    return str(value)
            return None
        if isinstance(period, datetime):
            return period.date().isoformat()
        if isinstance(period, date):
            return period.isoformat()
        if isinstance(period, (str, int, float)) and not isinstance(period, bool):
            return str(period)
        return None

    def _normalized_period_identity(self, period: Any) -> Optional[str]:
        raw = self._period_identity(period)
        if raw is None:
            return None
        return raw.strip().upper()

    def _period_offset(
        self,
        period: Any,
        offset: int,
        periods: List[Any],
        context_label: str,
    ) -> Any:
        if len(periods) > 0:
            source_id = self._normalized_period_identity(period)
            if source_id is None:
                raise FormulaError(
                    f"{context_label} period argument is not a recognizable period identifier"
                )
            source_index: Optional[int] = None
            for idx, candidate in enumerate(periods):
                candidate_id = self._normalized_period_identity(candidate)
                if candidate_id == source_id:
                    source_index = idx
                    break
            if source_index is None:
                raise FormulaError(
                    f"{context_label} could not find period {self._period_identity(period)!r} "
                    "inside TIME_PERIODS"
                )
            target_index = source_index + offset
            if target_index < 0 or target_index >= len(periods):
                raise FormulaError(f"{context_label} offset moved outside available periods")
            resolved = self._period_identity(periods[target_index])
            if resolved is None:
                raise FormulaError(f"{context_label} target period has no usable code/id/name")
            return resolved

        if isinstance(period, (datetime, date)):
            d = self._coerce_date(period, context_label)
            return (d + timedelta(days=offset)).isoformat()

        if isinstance(period, (int, float)) and not isinstance(period, bool):
            year = int(period)
            shifted_year = year + offset
            if shifted_year < 1:
                raise FormulaError(f"{context_label} produced an invalid year")
            return shifted_year

        if not isinstance(period, str):
            raise FormulaError(
                f"{context_label} expects a period string when TIME_PERIODS is not provided"
            )

        text = period.strip()
        if len(text) == 0:
            raise FormulaError(f"{context_label} period cannot be empty")

        match = re.match(r"^FY(\d{4})$", text, flags=re.IGNORECASE)
        if match:
            return f"FY{int(match.group(1)) + offset:04d}"

        match = re.match(r"^(\d{4})$", text)
        if match:
            return f"{int(match.group(1)) + offset:04d}"

        match = re.match(r"^(FY)?(\d{4})-Q([1-4])$", text, flags=re.IGNORECASE)
        if match:
            has_fy = match.group(1) is not None
            year = int(match.group(2))
            quarter = int(match.group(3))
            ordinal = (year * 4) + (quarter - 1) + offset
            if ordinal < 0:
                raise FormulaError(f"{context_label} produced an invalid quarter")
            target_year = ordinal // 4
            target_quarter = (ordinal % 4) + 1
            prefix = "FY" if has_fy else ""
            return f"{prefix}{target_year:04d}-Q{target_quarter}"

        match = re.match(r"^(FY)?(\d{4})-H([12])$", text, flags=re.IGNORECASE)
        if match:
            has_fy = match.group(1) is not None
            year = int(match.group(2))
            half = int(match.group(3))
            ordinal = (year * 2) + (half - 1) + offset
            if ordinal < 0:
                raise FormulaError(f"{context_label} produced an invalid half-year")
            target_year = ordinal // 2
            target_half = (ordinal % 2) + 1
            prefix = "FY" if has_fy else ""
            return f"{prefix}{target_year:04d}-H{target_half}"

        match = re.match(r"^(\d{4})-(\d{2})$", text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            ordinal = (year * 12) + (month - 1) + offset
            if ordinal < 0:
                raise FormulaError(f"{context_label} produced an invalid month")
            target_year = ordinal // 12
            target_month = (ordinal % 12) + 1
            return f"{target_year:04d}-{target_month:02d}"

        match = re.match(r"^(\d{4})-W(\d{1,2})$", text, flags=re.IGNORECASE)
        if match:
            year = int(match.group(1))
            week = int(match.group(2))
            try:
                start = date.fromisocalendar(year, week, 1)
            except ValueError:
                raise FormulaError(f"Invalid ISO week in {context_label}: {text!r}")
            shifted = start + timedelta(days=offset * 7)
            iso_year, iso_week, _ = shifted.isocalendar()
            return f"{iso_year:04d}-W{iso_week:02d}"

        match = re.match(r"^FY(\d{4})-P(\d{2})$", text, flags=re.IGNORECASE)
        if match:
            year = int(match.group(1))
            period_number = int(match.group(2))
            if period_number < 1 or period_number > 12:
                raise FormulaError(f"Invalid retail period in {context_label}: {text!r}")
            ordinal = (year * 12) + (period_number - 1) + offset
            if ordinal < 0:
                raise FormulaError(f"{context_label} produced an invalid retail period")
            target_year = ordinal // 12
            target_period = (ordinal % 12) + 1
            return f"FY{target_year:04d}-P{target_period:02d}"

        match = re.match(r"^FY(\d{4})-W(\d{1,2})$", text, flags=re.IGNORECASE)
        if match:
            year = int(match.group(1))
            week = int(match.group(2))
            if week < 1 or week > 53:
                raise FormulaError(f"Invalid retail week in {context_label}: {text!r}")
            ordinal = (year * 53) + (week - 1) + offset
            if ordinal < 0:
                raise FormulaError(f"{context_label} produced an invalid retail week")
            target_year = ordinal // 53
            target_week = (ordinal % 53) + 1
            return f"FY{target_year:04d}-W{target_week:02d}"

        raise FormulaError(
            f"{context_label} does not support offset for period format {text!r} "
            "without TIME_PERIODS context"
        )
