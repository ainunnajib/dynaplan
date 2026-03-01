"""
Tokenizer for the Dynaplan formula engine.

Converts a raw formula string into a flat list of typed tokens.
Anaplan-compatible syntax: identifiers may contain dots (e.g. Product.Price).
"""

from typing import List, Optional
from dataclasses import dataclass, field
import re


# ---------------------------------------------------------------------------
# Token types
# ---------------------------------------------------------------------------

class TokenType:
    NUMBER        = "NUMBER"
    STRING        = "STRING"
    BOOLEAN       = "BOOLEAN"
    IDENTIFIER    = "IDENTIFIER"
    OPERATOR      = "OPERATOR"       # + - * / ^
    COMPARISON    = "COMPARISON"     # = <> < > <= >=
    LOGICAL       = "LOGICAL"        # AND OR NOT
    LPAREN        = "LPAREN"
    RPAREN        = "RPAREN"
    COMMA         = "COMMA"
    EOF           = "EOF"


@dataclass
class Token:
    type: str
    value: str
    pos: int = field(default=0)

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r}, pos={self.pos})"


# ---------------------------------------------------------------------------
# Tokenizer error
# ---------------------------------------------------------------------------

class TokenizerError(Exception):
    """Raised when the tokenizer encounters unexpected input."""


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

# Ordered list of (token_type, compiled_regex) pairs.
# The order matters — longer/more-specific patterns must come first.
_TOKEN_PATTERNS = [
    # Whitespace — skipped
    (None, re.compile(r'[ \t\r\n]+')),

    # Numbers (integer or float, including scientific notation)
    (TokenType.NUMBER, re.compile(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?')),

    # Strings — single or double quoted
    (TokenType.STRING, re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')),

    # Two-character comparison operators must come before single-char ones
    (TokenType.COMPARISON, re.compile(r'<>|<=|>=')),

    # Single-character comparison operators
    (TokenType.COMPARISON, re.compile(r'[<>=]')),

    # Arithmetic operators
    (TokenType.OPERATOR, re.compile(r'[+\-*/^]')),

    # Parentheses & comma
    (TokenType.LPAREN, re.compile(r'\(')),
    (TokenType.RPAREN, re.compile(r'\)')),
    (TokenType.COMMA,  re.compile(r',')),

    # Identifiers (including dotted names like Product.Price) and keywords
    # Must come after string pattern so quoted strings are not confused.
    (TokenType.IDENTIFIER, re.compile(r'[A-Za-z_][A-Za-z0-9_.]*')),
]

# Keywords that override IDENTIFIER type
_BOOLEAN_KEYWORDS = {"TRUE", "FALSE"}
_LOGICAL_KEYWORDS = {"AND", "OR", "NOT"}


def tokenize(text: str) -> List[Token]:
    """
    Tokenize *text* and return a list of Token objects.

    Raises TokenizerError on unexpected characters.
    The returned list does NOT include an EOF token; callers that need one
    should append it themselves.
    """
    tokens: List[Token] = []
    pos = 0
    length = len(text)

    while pos < length:
        matched = False

        for token_type, pattern in _TOKEN_PATTERNS:
            m = pattern.match(text, pos)
            if m is None:
                continue

            raw = m.group(0)
            matched = True

            if token_type is None:
                # Whitespace — skip
                pass
            else:
                actual_type = token_type

                # Reclassify identifiers that are keywords
                if token_type == TokenType.IDENTIFIER:
                    upper = raw.upper()
                    if upper in _BOOLEAN_KEYWORDS:
                        actual_type = TokenType.BOOLEAN
                        raw = upper          # normalise to upper-case
                    elif upper in _LOGICAL_KEYWORDS:
                        actual_type = TokenType.LOGICAL
                        raw = upper

                tokens.append(Token(type=actual_type, value=raw, pos=pos))

            pos = m.end()
            break

        if not matched:
            raise TokenizerError(
                f"Unexpected character {text[pos]!r} at position {pos}"
            )

    return tokens
