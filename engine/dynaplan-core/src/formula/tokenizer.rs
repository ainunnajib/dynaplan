use std::error::Error;
use std::fmt;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TokenType {
    Number,
    String,
    Boolean,
    Identifier,
    Operator,
    Comparison,
    Logical,
    LParen,
    RParen,
    Comma,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Token {
    pub token_type: TokenType,
    pub value: String,
    pub pos: usize,
}

impl Token {
    pub fn new(token_type: TokenType, value: String, pos: usize) -> Self {
        Self {
            token_type,
            value,
            pos,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TokenizerError {
    message: String,
}

impl TokenizerError {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

impl fmt::Display for TokenizerError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl Error for TokenizerError {}

pub fn tokenize(text: &str) -> Result<Vec<Token>, TokenizerError> {
    let mut tokens = Vec::new();
    let mut pos = 0usize;
    let len = text.len();

    while pos < len {
        let ch = text[pos..].chars().next().ok_or_else(|| {
            TokenizerError::new(format!("Unexpected end of input at position {}", pos))
        })?;

        if ch.is_ascii_whitespace() {
            pos += ch.len_utf8();
            continue;
        }

        if ch.is_ascii_digit() {
            let end = scan_number(text, pos);
            tokens.push(Token::new(
                TokenType::Number,
                text[pos..end].to_string(),
                pos,
            ));
            pos = end;
            continue;
        }

        if ch == '"' || ch == '\'' {
            let start = pos;
            if let Some(end) = scan_string(text, start, ch) {
                tokens.push(Token::new(
                    TokenType::String,
                    text[start..end].to_string(),
                    start,
                ));
                pos = end;
                continue;
            }
            return Err(TokenizerError::new(format!(
                "Unexpected character {:?} at position {}",
                ch, start
            )));
        }

        if let Some(end) = scan_two_char_comparison(text, pos) {
            tokens.push(Token::new(
                TokenType::Comparison,
                text[pos..end].to_string(),
                pos,
            ));
            pos = end;
            continue;
        }

        if matches!(ch, '<' | '>' | '=') {
            let end = pos + ch.len_utf8();
            tokens.push(Token::new(
                TokenType::Comparison,
                text[pos..end].to_string(),
                pos,
            ));
            pos = end;
            continue;
        }

        if matches!(ch, '+' | '-' | '*' | '/' | '^') {
            let end = pos + ch.len_utf8();
            tokens.push(Token::new(
                TokenType::Operator,
                text[pos..end].to_string(),
                pos,
            ));
            pos = end;
            continue;
        }

        if ch == '(' {
            pos += 1;
            tokens.push(Token::new(TokenType::LParen, "(".to_string(), pos - 1));
            continue;
        }

        if ch == ')' {
            pos += 1;
            tokens.push(Token::new(TokenType::RParen, ")".to_string(), pos - 1));
            continue;
        }

        if ch == ',' {
            pos += 1;
            tokens.push(Token::new(TokenType::Comma, ",".to_string(), pos - 1));
            continue;
        }

        if is_identifier_start(ch) {
            let end = scan_identifier(text, pos);
            let raw = &text[pos..end];
            let upper = raw.to_ascii_uppercase();

            let (token_type, value) = match upper.as_str() {
                "TRUE" | "FALSE" => (TokenType::Boolean, upper),
                "AND" | "OR" | "NOT" => (TokenType::Logical, upper),
                _ => (TokenType::Identifier, raw.to_string()),
            };

            tokens.push(Token::new(token_type, value, pos));
            pos = end;
            continue;
        }

        return Err(TokenizerError::new(format!(
            "Unexpected character {:?} at position {}",
            ch, pos
        )));
    }

    Ok(tokens)
}

fn scan_two_char_comparison(text: &str, pos: usize) -> Option<usize> {
    if pos + 1 >= text.len() {
        return None;
    }
    let two = &text[pos..pos + 2];
    if two == "<>" || two == "<=" || two == ">=" {
        Some(pos + 2)
    } else {
        None
    }
}

fn scan_number(text: &str, start: usize) -> usize {
    let bytes = text.as_bytes();
    let mut pos = start;

    while pos < bytes.len() && bytes[pos].is_ascii_digit() {
        pos += 1;
    }

    if pos < bytes.len() && bytes[pos] == b'.' {
        let mut next = pos + 1;
        if next < bytes.len() && bytes[next].is_ascii_digit() {
            while next < bytes.len() && bytes[next].is_ascii_digit() {
                next += 1;
            }
            pos = next;
        }
    }

    if pos < bytes.len() && (bytes[pos] == b'e' || bytes[pos] == b'E') {
        let exp_start = pos;
        let mut next = pos + 1;
        if next < bytes.len() && (bytes[next] == b'+' || bytes[next] == b'-') {
            next += 1;
        }

        let digits_start = next;
        while next < bytes.len() && bytes[next].is_ascii_digit() {
            next += 1;
        }

        if next > digits_start {
            pos = next;
        } else {
            pos = exp_start;
        }
    }

    pos
}

fn scan_string(text: &str, start: usize, quote: char) -> Option<usize> {
    let mut pos = start + quote.len_utf8();

    while pos < text.len() {
        let ch = text[pos..].chars().next()?;
        if ch == '\\' {
            pos += ch.len_utf8();
            if pos < text.len() {
                let escaped = text[pos..].chars().next()?;
                pos += escaped.len_utf8();
            }
            continue;
        }

        pos += ch.len_utf8();
        if ch == quote {
            return Some(pos);
        }
    }

    None
}

fn is_identifier_start(ch: char) -> bool {
    ch.is_ascii_alphabetic() || ch == '_'
}

fn is_identifier_continue(ch: char) -> bool {
    ch.is_ascii_alphanumeric() || ch == '_' || ch == '.'
}

fn scan_identifier(text: &str, start: usize) -> usize {
    let mut pos = start;
    while pos < text.len() {
        let ch = match text[pos..].chars().next() {
            Some(c) => c,
            None => break,
        };
        if !is_identifier_continue(ch) {
            break;
        }
        pos += ch.len_utf8();
    }
    pos
}
