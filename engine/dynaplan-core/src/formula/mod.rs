use std::collections::{HashMap, HashSet};
use std::error::Error;
use std::fmt;

use crate::value::CellValue;

pub mod evaluator;
pub mod functions;
pub mod parser;
pub mod tokenizer;

pub use evaluator::{Context, Evaluator, FormulaError, FormulaValue};
pub use functions::{is_builtin_function, BUILTIN_FUNCTIONS};
pub use parser::{parse, ASTNode, BinaryOperator, ParseError, Parser, UnaryOperator};
pub use tokenizer::{tokenize, Token, TokenType, TokenizerError};

#[derive(Clone, Debug)]
pub enum FormulaEngineError {
    Tokenizer(TokenizerError),
    Parse(ParseError),
    Eval(FormulaError),
}

impl fmt::Display for FormulaEngineError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            FormulaEngineError::Tokenizer(err) => write!(f, "Tokenizer error: {}", err),
            FormulaEngineError::Parse(err) => write!(f, "Parse error: {}", err),
            FormulaEngineError::Eval(err) => write!(f, "Formula error: {}", err),
        }
    }
}

impl Error for FormulaEngineError {}

impl From<TokenizerError> for FormulaEngineError {
    fn from(value: TokenizerError) -> Self {
        FormulaEngineError::Tokenizer(value)
    }
}

impl From<ParseError> for FormulaEngineError {
    fn from(value: ParseError) -> Self {
        FormulaEngineError::Parse(value)
    }
}

impl From<FormulaError> for FormulaEngineError {
    fn from(value: FormulaError) -> Self {
        FormulaEngineError::Eval(value)
    }
}

pub fn parse_formula(text: &str) -> Result<ASTNode, FormulaEngineError> {
    let tokens = tokenize(text)?;
    let mut parser = Parser::new(tokens);
    parser.parse().map_err(FormulaEngineError::from)
}

pub fn evaluate_formula(
    text: &str,
    context: HashMap<String, FormulaValue>,
) -> Result<FormulaValue, FormulaEngineError> {
    let ast = parse_formula(text)?;
    let evaluator = Evaluator::new(context);
    evaluator.evaluate(&ast).map_err(FormulaEngineError::from)
}

pub fn evaluate_formula_cell_context(
    text: &str,
    context: HashMap<String, CellValue>,
) -> Result<CellValue, FormulaEngineError> {
    let converted = context
        .into_iter()
        .map(|(k, v)| (k, FormulaValue::from(v)))
        .collect::<HashMap<String, FormulaValue>>();
    let result = evaluate_formula(text, converted)?;
    CellValue::try_from(result).map_err(FormulaEngineError::from)
}

pub fn validate_formula(text: &str) -> Vec<String> {
    if text.trim().is_empty() {
        return vec!["Formula is empty".to_string()];
    }

    if let Err(err) = tokenize(text) {
        return vec![format!("Tokenizer error: {}", err)];
    }

    if let Err(err) = parse_formula(text) {
        return vec![format!("Syntax error: {}", err)];
    }

    Vec::new()
}

pub fn get_references(text: &str) -> HashSet<String> {
    let Ok(ast) = parse_formula(text) else {
        return HashSet::new();
    };

    let mut refs = HashSet::new();
    collect_refs(&ast, &mut refs);
    refs
}

fn collect_refs(node: &ASTNode, refs: &mut HashSet<String>) {
    match node {
        ASTNode::Ident(name) => {
            refs.insert(name.clone());
        }
        ASTNode::BinaryOp { left, right, .. } => {
            collect_refs(left, refs);
            collect_refs(right, refs);
        }
        ASTNode::UnaryOp { operand, .. } => {
            collect_refs(operand, refs);
        }
        ASTNode::FunctionCall { args, .. } => {
            for arg in args {
                collect_refs(arg, refs);
            }
        }
        ASTNode::Number(_) | ASTNode::String(_) | ASTNode::Bool(_) => {}
    }
}

#[cfg(test)]
mod tests;
