"""
High-level formula API for the Dynaplan formula engine.

This module is the single entry point that callers should use.
It wires together tokenizer → parser → evaluator.

Public API
----------
parse_formula(text)          -> ASTNode
evaluate_formula(text, ctx)  -> Any
validate_formula(text)       -> List[str]   (empty = valid)
get_references(text)         -> Set[str]
"""

from typing import Any, Dict, List, Optional, Set

from .tokenizer import tokenize, TokenizerError
from .parser import (
    ASTNode,
    Identifier,
    FunctionCall,
    BinaryOp,
    UnaryOp,
    Comparison,
    Parser,
    ParseError,
)
from .evaluator import Evaluator, FormulaError


# ---------------------------------------------------------------------------
# parse_formula
# ---------------------------------------------------------------------------

def parse_formula(text: str) -> ASTNode:
    """
    Tokenize and parse *text* into an AST.

    Raises:
        TokenizerError  — if the input contains unexpected characters.
        ParseError      — if the token stream is syntactically invalid.
    """
    tokens = tokenize(text)
    return Parser(tokens).parse()


# ---------------------------------------------------------------------------
# evaluate_formula
# ---------------------------------------------------------------------------

def evaluate_formula(text: str, context: Optional[Dict[str, Any]] = None) -> Any:
    """
    Parse and evaluate *text* using the given *context*.

    *context* maps variable names to their values (numbers, strings,
    booleans, or lists).

    Raises:
        TokenizerError  — on lex errors.
        ParseError      — on syntax errors.
        FormulaError    — on runtime errors (undefined var, divide by zero …).
    """
    ast = parse_formula(text)
    return Evaluator(context or {}).evaluate(ast)


# ---------------------------------------------------------------------------
# validate_formula
# ---------------------------------------------------------------------------

def validate_formula(text: str) -> List[str]:
    """
    Attempt to parse *text* and return a list of error messages.

    An empty list means the formula is syntactically valid.
    Note: variable names are not resolved during validation, so an
    undefined-variable error will only surface at evaluation time.
    """
    errors: List[str] = []
    if not text or not text.strip():
        errors.append("Formula is empty")
        return errors

    try:
        tokenize(text)
    except TokenizerError as exc:
        errors.append(f"Tokenizer error: {exc}")
        return errors   # no point continuing if tokenization fails

    try:
        parse_formula(text)
    except ParseError as exc:
        errors.append(f"Syntax error: {exc}")

    return errors


# ---------------------------------------------------------------------------
# get_references
# ---------------------------------------------------------------------------

def get_references(text: str) -> Set[str]:
    """
    Return the set of variable names referenced in *text*.

    Function names (e.g. SUM, IF) are excluded; only free Identifier nodes
    and the *key* argument of LOOKUP calls are included.

    Returns an empty set if the formula cannot be parsed.
    """
    try:
        ast = parse_formula(text)
    except (TokenizerError, ParseError):
        return set()

    refs: Set[str] = set()
    _collect_refs(ast, refs)
    return refs


# ---------------------------------------------------------------------------
# Internal helper: walk the AST and collect Identifier names
# ---------------------------------------------------------------------------

# Built-in function names — we do not treat these as variable references
_BUILTIN_FUNCTIONS: Set[str] = {
    "ABS", "ROUND", "MIN", "MAX", "POWER", "SQRT", "LOG",
    "SUM", "AVERAGE", "COUNT", "ITEMCOUNT",
    "IF", "AND", "OR", "NOT", "ISBLANK",
    "CONCATENATE", "LEFT", "RIGHT", "LEN", "UPPER", "LOWER", "TRIM",
    "LOOKUP",
}


def _collect_refs(node: ASTNode, refs: Set[str]) -> None:
    """Recursively walk *node* and add all Identifier names to *refs*."""

    if isinstance(node, Identifier):
        refs.add(node.name)
        return

    if isinstance(node, BinaryOp):
        _collect_refs(node.left, refs)
        _collect_refs(node.right, refs)
        return

    if isinstance(node, UnaryOp):
        _collect_refs(node.operand, refs)
        return

    if isinstance(node, Comparison):
        _collect_refs(node.left, refs)
        _collect_refs(node.right, refs)
        return

    if isinstance(node, FunctionCall):
        # Function name itself is NOT a variable reference
        for arg in node.args:
            _collect_refs(arg, refs)
        return

    # Literals (Number, String, Boolean) have no references — nothing to do
