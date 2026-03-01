use std::error::Error;
use std::fmt;

use super::tokenizer::{tokenize, Token, TokenType, TokenizerError};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BinaryOperator {
    Add,
    Subtract,
    Multiply,
    Divide,
    Power,
    And,
    Or,
    Equal,
    NotEqual,
    LessThan,
    GreaterThan,
    LessEqual,
    GreaterEqual,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum UnaryOperator {
    Negate,
    Not,
}

#[derive(Clone, Debug, PartialEq)]
pub enum ASTNode {
    Number(f64),
    String(String),
    Bool(bool),
    Ident(String),
    BinaryOp {
        op: BinaryOperator,
        left: Box<ASTNode>,
        right: Box<ASTNode>,
    },
    UnaryOp {
        op: UnaryOperator,
        operand: Box<ASTNode>,
    },
    FunctionCall {
        name: String,
        args: Vec<ASTNode>,
    },
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ParseError {
    message: String,
}

impl ParseError {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl Error for ParseError {}

impl From<TokenizerError> for ParseError {
    fn from(value: TokenizerError) -> Self {
        ParseError::new(value.to_string())
    }
}

pub struct Parser {
    tokens: Vec<Token>,
    pos: usize,
}

impl Parser {
    pub fn new(tokens: Vec<Token>) -> Self {
        Self { tokens, pos: 0 }
    }

    pub fn parse(&mut self) -> Result<ASTNode, ParseError> {
        let node = self.parse_or()?;
        if !self.at_end() {
            if let Some(tok) = self.peek() {
                return Err(ParseError::new(format!(
                    "Unexpected token {:?} at pos {}",
                    tok.value, tok.pos
                )));
            }
        }
        Ok(node)
    }

    fn parse_or(&mut self) -> Result<ASTNode, ParseError> {
        let mut left = self.parse_and()?;
        while self
            .peek()
            .map(|t| t.token_type == TokenType::Logical && t.value == "OR")
            .unwrap_or(false)
        {
            self.consume();
            let right = self.parse_and()?;
            left = ASTNode::BinaryOp {
                op: BinaryOperator::Or,
                left: Box::new(left),
                right: Box::new(right),
            };
        }
        Ok(left)
    }

    fn parse_and(&mut self) -> Result<ASTNode, ParseError> {
        let mut left = self.parse_not()?;
        while self
            .peek()
            .map(|t| t.token_type == TokenType::Logical && t.value == "AND")
            .unwrap_or(false)
        {
            self.consume();
            let right = self.parse_not()?;
            left = ASTNode::BinaryOp {
                op: BinaryOperator::And,
                left: Box::new(left),
                right: Box::new(right),
            };
        }
        Ok(left)
    }

    fn parse_not(&mut self) -> Result<ASTNode, ParseError> {
        if self
            .peek()
            .map(|t| t.token_type == TokenType::Logical && t.value == "NOT")
            .unwrap_or(false)
        {
            self.consume();
            let operand = self.parse_not()?;
            return Ok(ASTNode::UnaryOp {
                op: UnaryOperator::Not,
                operand: Box::new(operand),
            });
        }
        self.parse_comparison()
    }

    fn parse_comparison(&mut self) -> Result<ASTNode, ParseError> {
        let left = self.parse_add()?;
        if self
            .peek()
            .map(|t| t.token_type == TokenType::Comparison)
            .unwrap_or(false)
        {
            let op_token = self
                .consume()
                .ok_or_else(|| ParseError::new("Unexpected end of input"))?;
            let right = self.parse_add()?;
            let op = match op_token.value.as_str() {
                "=" => BinaryOperator::Equal,
                "<>" => BinaryOperator::NotEqual,
                "<" => BinaryOperator::LessThan,
                ">" => BinaryOperator::GreaterThan,
                "<=" => BinaryOperator::LessEqual,
                ">=" => BinaryOperator::GreaterEqual,
                _ => {
                    return Err(ParseError::new(format!(
                        "Unknown comparison operator {:?} at pos {}",
                        op_token.value, op_token.pos
                    )));
                }
            };

            return Ok(ASTNode::BinaryOp {
                op,
                left: Box::new(left),
                right: Box::new(right),
            });
        }
        Ok(left)
    }

    fn parse_add(&mut self) -> Result<ASTNode, ParseError> {
        let mut left = self.parse_mul()?;
        loop {
            let op = match self.peek() {
                Some(tok) if tok.token_type == TokenType::Operator && tok.value == "+" => {
                    Some(BinaryOperator::Add)
                }
                Some(tok) if tok.token_type == TokenType::Operator && tok.value == "-" => {
                    Some(BinaryOperator::Subtract)
                }
                _ => None,
            };

            let Some(op) = op else {
                break;
            };

            self.consume();
            let right = self.parse_mul()?;
            left = ASTNode::BinaryOp {
                op,
                left: Box::new(left),
                right: Box::new(right),
            };
        }
        Ok(left)
    }

    fn parse_mul(&mut self) -> Result<ASTNode, ParseError> {
        let mut left = self.parse_pow()?;
        loop {
            let op = match self.peek() {
                Some(tok) if tok.token_type == TokenType::Operator && tok.value == "*" => {
                    Some(BinaryOperator::Multiply)
                }
                Some(tok) if tok.token_type == TokenType::Operator && tok.value == "/" => {
                    Some(BinaryOperator::Divide)
                }
                _ => None,
            };

            let Some(op) = op else {
                break;
            };

            self.consume();
            let right = self.parse_pow()?;
            left = ASTNode::BinaryOp {
                op,
                left: Box::new(left),
                right: Box::new(right),
            };
        }
        Ok(left)
    }

    fn parse_pow(&mut self) -> Result<ASTNode, ParseError> {
        let base = self.parse_unary()?;
        if self
            .peek()
            .map(|t| t.token_type == TokenType::Operator && t.value == "^")
            .unwrap_or(false)
        {
            self.consume();
            let exp = self.parse_unary()?;
            return Ok(ASTNode::BinaryOp {
                op: BinaryOperator::Power,
                left: Box::new(base),
                right: Box::new(exp),
            });
        }
        Ok(base)
    }

    fn parse_unary(&mut self) -> Result<ASTNode, ParseError> {
        if self
            .peek()
            .map(|t| t.token_type == TokenType::Operator && t.value == "-")
            .unwrap_or(false)
        {
            self.consume();
            let operand = self.parse_unary()?;
            return Ok(ASTNode::UnaryOp {
                op: UnaryOperator::Negate,
                operand: Box::new(operand),
            });
        }
        self.parse_primary()
    }

    fn parse_primary(&mut self) -> Result<ASTNode, ParseError> {
        let tok = self
            .peek()
            .cloned()
            .ok_or_else(|| ParseError::new("Unexpected end of input"))?;

        if tok.token_type == TokenType::Number {
            self.consume();
            let value = tok.value.parse::<f64>().map_err(|_| {
                ParseError::new(format!("Invalid number {:?} at pos {}", tok.value, tok.pos))
            })?;
            return Ok(ASTNode::Number(value));
        }

        if tok.token_type == TokenType::String {
            self.consume();
            return Ok(ASTNode::String(parse_string_literal(&tok.value)));
        }

        if tok.token_type == TokenType::Boolean {
            self.consume();
            return Ok(ASTNode::Bool(tok.value == "TRUE"));
        }

        if tok.token_type == TokenType::Identifier || tok.token_type == TokenType::Logical {
            self.consume();
            let name = tok.value.clone();

            if self
                .peek()
                .map(|t| t.token_type == TokenType::LParen)
                .unwrap_or(false)
            {
                self.consume();
                let args = self.parse_arg_list()?;
                self.expect(TokenType::RParen, None)?;
                return Ok(ASTNode::FunctionCall {
                    name: name.to_ascii_uppercase(),
                    args,
                });
            }

            if tok.token_type == TokenType::Logical {
                return Err(ParseError::new(format!(
                    "Unexpected keyword {:?} at pos {}",
                    name, tok.pos
                )));
            }

            return Ok(ASTNode::Ident(name));
        }

        if tok.token_type == TokenType::LParen {
            self.consume();
            let node = self.parse_or()?;
            self.expect(TokenType::RParen, None)?;
            return Ok(node);
        }

        Err(ParseError::new(format!(
            "Unexpected token {:?} (type={:?}) at pos {}",
            tok.value, tok.token_type, tok.pos
        )))
    }

    fn parse_arg_list(&mut self) -> Result<Vec<ASTNode>, ParseError> {
        let mut args = Vec::new();
        if self
            .peek()
            .map(|t| t.token_type == TokenType::RParen)
            .unwrap_or(false)
        {
            return Ok(args);
        }

        args.push(self.parse_or()?);
        while self
            .peek()
            .map(|t| t.token_type == TokenType::Comma)
            .unwrap_or(false)
        {
            self.consume();
            args.push(self.parse_or()?);
        }

        Ok(args)
    }

    fn peek(&self) -> Option<&Token> {
        self.tokens.get(self.pos)
    }

    fn consume(&mut self) -> Option<Token> {
        let token = self.tokens.get(self.pos).cloned();
        if token.is_some() {
            self.pos += 1;
        }
        token
    }

    fn expect(&mut self, token_type: TokenType, value: Option<&str>) -> Result<Token, ParseError> {
        let tok = self.peek().cloned().ok_or_else(|| {
            ParseError::new(format!(
                "Expected {:?} but reached end of input",
                token_type
            ))
        })?;

        if tok.token_type != token_type {
            return Err(ParseError::new(format!(
                "Expected token type {:?} but got {:?} ({:?}) at pos {}",
                token_type, tok.token_type, tok.value, tok.pos
            )));
        }

        if let Some(expected) = value {
            if tok.value != expected {
                return Err(ParseError::new(format!(
                    "Expected {:?} but got {:?} at pos {}",
                    expected, tok.value, tok.pos
                )));
            }
        }

        self.consume()
            .ok_or_else(|| ParseError::new("Unexpected end of input"))
    }

    fn at_end(&self) -> bool {
        self.pos >= self.tokens.len()
    }
}

pub fn parse(text: &str) -> Result<ASTNode, ParseError> {
    let tokens = tokenize(text)?;
    let mut parser = Parser::new(tokens);
    parser.parse()
}

fn parse_string_literal(raw: &str) -> String {
    if raw.starts_with('"') && raw.ends_with('"') && raw.len() >= 2 {
        raw[1..raw.len() - 1]
            .replace("\\\"", "\"")
            .replace("\\\\", "\\")
    } else if raw.starts_with('\'') && raw.ends_with('\'') && raw.len() >= 2 {
        raw[1..raw.len() - 1]
            .replace("\\'", "'")
            .replace("\\\\", "\\")
    } else {
        raw.to_string()
    }
}
