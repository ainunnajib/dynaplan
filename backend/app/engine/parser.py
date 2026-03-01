"""
Recursive-descent parser for the Dynaplan formula engine.

Converts a token list (from tokenizer.py) into an Abstract Syntax Tree (AST).

Grammar (simplified, listed from lowest to highest precedence):
    expr        ::= or_expr
    or_expr     ::= and_expr  ('OR'  and_expr)*
    and_expr    ::= not_expr  ('AND' not_expr)*
    not_expr    ::= 'NOT' not_expr | cmp_expr
    cmp_expr    ::= add_expr  (CMP_OP add_expr)?
    add_expr    ::= mul_expr  (('+' | '-') mul_expr)*
    mul_expr    ::= pow_expr  (('*' | '/') pow_expr)*
    pow_expr    ::= unary     ('^' unary)*
    unary       ::= '-' unary | primary
    primary     ::= NUMBER | STRING | BOOLEAN
                  | IDENTIFIER '(' arg_list ')'   -- function call
                  | IDENTIFIER
                  | '(' expr ')'

arg_list    ::= expr (',' expr)*  |  empty

Operator precedence (highest to lowest):
    NOT
    ^
    * /
    + -
    comparisons  (= <> < > <= >=)
    AND
    OR
"""

from typing import List, Optional, Any
from dataclasses import dataclass, field

from .tokenizer import Token, TokenType, tokenize, TokenizerError


# ---------------------------------------------------------------------------
# AST node definitions
# ---------------------------------------------------------------------------

@dataclass
class ASTNode:
    """Base class for all AST nodes."""


@dataclass
class NumberLiteral(ASTNode):
    value: float


@dataclass
class StringLiteral(ASTNode):
    value: str


@dataclass
class BooleanLiteral(ASTNode):
    value: bool


@dataclass
class Identifier(ASTNode):
    name: str


@dataclass
class BinaryOp(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode


@dataclass
class UnaryOp(ASTNode):
    op: str
    operand: ASTNode


@dataclass
class FunctionCall(ASTNode):
    name: str
    args: List[ASTNode] = field(default_factory=list)


@dataclass
class Comparison(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode


# ---------------------------------------------------------------------------
# Parser error
# ---------------------------------------------------------------------------

class ParseError(Exception):
    """Raised when the parser encounters a syntax error."""


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class Parser:
    """
    Recursive-descent parser.

    Usage::

        parser = Parser(tokens)
        ast = parser.parse()
    """

    def __init__(self, tokens: List[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _peek(self) -> Optional[Token]:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, token_type: str, value: Optional[str] = None) -> Token:
        tok = self._peek()
        if tok is None:
            raise ParseError(
                f"Expected {token_type!r} but reached end of input"
            )
        if tok.type != token_type:
            raise ParseError(
                f"Expected token type {token_type!r} but got "
                f"{tok.type!r} ({tok.value!r}) at pos {tok.pos}"
            )
        if value is not None and tok.value != value:
            raise ParseError(
                f"Expected {value!r} but got {tok.value!r} at pos {tok.pos}"
            )
        return self._consume()

    def _at_end(self) -> bool:
        return self._pos >= len(self._tokens)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def parse(self) -> ASTNode:
        node = self._parse_or()
        if not self._at_end():
            tok = self._peek()
            raise ParseError(
                f"Unexpected token {tok.value!r} at pos {tok.pos}"
            )
        return node

    # ------------------------------------------------------------------
    # Grammar rules (lowest precedence first)
    # ------------------------------------------------------------------

    def _parse_or(self) -> ASTNode:
        left = self._parse_and()
        while self._peek() and self._peek().type == TokenType.LOGICAL and self._peek().value == "OR":
            self._consume()   # eat OR
            right = self._parse_and()
            left = BinaryOp(op="OR", left=left, right=right)
        return left

    def _parse_and(self) -> ASTNode:
        left = self._parse_not()
        while self._peek() and self._peek().type == TokenType.LOGICAL and self._peek().value == "AND":
            self._consume()   # eat AND
            right = self._parse_not()
            left = BinaryOp(op="AND", left=left, right=right)
        return left

    def _parse_not(self) -> ASTNode:
        tok = self._peek()
        if tok and tok.type == TokenType.LOGICAL and tok.value == "NOT":
            self._consume()
            operand = self._parse_not()
            return UnaryOp(op="NOT", operand=operand)
        return self._parse_comparison()

    def _parse_comparison(self) -> ASTNode:
        left = self._parse_add()
        tok = self._peek()
        if tok and tok.type == TokenType.COMPARISON:
            op = tok.value
            self._consume()
            right = self._parse_add()
            return Comparison(op=op, left=left, right=right)
        return left

    def _parse_add(self) -> ASTNode:
        left = self._parse_mul()
        while True:
            tok = self._peek()
            if tok and tok.type == TokenType.OPERATOR and tok.value in ("+", "-"):
                op = tok.value
                self._consume()
                right = self._parse_mul()
                left = BinaryOp(op=op, left=left, right=right)
            else:
                break
        return left

    def _parse_mul(self) -> ASTNode:
        left = self._parse_pow()
        while True:
            tok = self._peek()
            if tok and tok.type == TokenType.OPERATOR and tok.value in ("*", "/"):
                op = tok.value
                self._consume()
                right = self._parse_pow()
                left = BinaryOp(op=op, left=left, right=right)
            else:
                break
        return left

    def _parse_pow(self) -> ASTNode:
        base = self._parse_unary()
        tok = self._peek()
        if tok and tok.type == TokenType.OPERATOR and tok.value == "^":
            self._consume()
            # Right-associative
            exp = self._parse_unary()
            return BinaryOp(op="^", left=base, right=exp)
        return base

    def _parse_unary(self) -> ASTNode:
        tok = self._peek()
        if tok and tok.type == TokenType.OPERATOR and tok.value == "-":
            self._consume()
            operand = self._parse_unary()
            return UnaryOp(op="-", operand=operand)
        return self._parse_primary()

    def _parse_primary(self) -> ASTNode:
        tok = self._peek()
        if tok is None:
            raise ParseError("Unexpected end of input")

        # Number literal
        if tok.type == TokenType.NUMBER:
            self._consume()
            return NumberLiteral(value=float(tok.value))

        # String literal — strip surrounding quotes and handle escape sequences
        if tok.type == TokenType.STRING:
            self._consume()
            raw = tok.value
            if raw.startswith('"') and raw.endswith('"'):
                inner = raw[1:-1].replace('\\"', '"').replace('\\\\', '\\')
            elif raw.startswith("'") and raw.endswith("'"):
                inner = raw[1:-1].replace("\\'", "'").replace('\\\\', '\\')
            else:
                inner = raw
            return StringLiteral(value=inner)

        # Boolean literal
        if tok.type == TokenType.BOOLEAN:
            self._consume()
            return BooleanLiteral(value=tok.value == "TRUE")

        # Identifier or function call.
        # Also allow LOGICAL tokens (AND, OR, NOT) to be used as function
        # names with explicit parentheses — e.g. AND(a, b), NOT(x), OR(x, y).
        if tok.type in (TokenType.IDENTIFIER, TokenType.LOGICAL):
            name = tok.value
            self._consume()
            # Look ahead for '(' to distinguish function call from variable
            next_tok = self._peek()
            if next_tok and next_tok.type == TokenType.LPAREN:
                self._consume()  # eat '('
                args = self._parse_arg_list()
                self._expect(TokenType.RPAREN)
                return FunctionCall(name=name.upper(), args=args)
            # A bare LOGICAL keyword without '(' only makes sense in the
            # infix/prefix positions handled by _parse_and/_parse_or/_parse_not.
            # If we reach here it means the keyword appeared unexpectedly.
            if tok.type == TokenType.LOGICAL:
                raise ParseError(
                    f"Unexpected keyword {name!r} at pos {tok.pos}"
                )
            return Identifier(name=name)

        # Parenthesised expression
        if tok.type == TokenType.LPAREN:
            self._consume()  # eat '('
            node = self._parse_or()
            self._expect(TokenType.RPAREN)
            return node

        raise ParseError(
            f"Unexpected token {tok.value!r} (type={tok.type}) at pos {tok.pos}"
        )

    def _parse_arg_list(self) -> List[ASTNode]:
        """Parse a comma-separated argument list (possibly empty)."""
        args: List[ASTNode] = []
        # Empty arg list
        if self._peek() and self._peek().type == TokenType.RPAREN:
            return args
        args.append(self._parse_or())
        while self._peek() and self._peek().type == TokenType.COMMA:
            self._consume()  # eat ','
            args.append(self._parse_or())
        return args


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def parse(text: str) -> ASTNode:
    """
    Tokenize *text* and parse it into an AST.

    Raises TokenizerError or ParseError on invalid input.
    """
    tokens = tokenize(text)
    return Parser(tokens).parse()
