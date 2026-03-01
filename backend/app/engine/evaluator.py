"""
AST evaluator for the Dynaplan formula engine.

Walks the AST produced by parser.py and computes a result value given a
context dict that maps variable names to their values.

Built-in functions (case-insensitive, stored upper-case):
    Math        : ABS, ROUND, MIN, MAX, POWER, SQRT, LOG
    Aggregation : SUM, AVERAGE, COUNT
    Logical     : IF, AND, OR, NOT, ISBLANK
    Text        : CONCATENATE, LEFT, RIGHT, LEN, UPPER, LOWER, TRIM
    Lookup      : LOOKUP
"""

import math
from typing import Any, Dict, List, Optional

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
