use std::collections::HashMap;
use std::error::Error;
use std::fmt;

use crate::value::CellValue;

use super::functions;
use super::parser::{ASTNode, BinaryOperator, UnaryOperator};

#[derive(Clone, Debug, PartialEq)]
pub enum FormulaValue {
    Number(f64),
    Text(String),
    Bool(bool),
    List(Vec<FormulaValue>),
    Map(HashMap<String, FormulaValue>),
    Null,
}

impl From<f64> for FormulaValue {
    fn from(value: f64) -> Self {
        FormulaValue::Number(value)
    }
}

impl From<i64> for FormulaValue {
    fn from(value: i64) -> Self {
        FormulaValue::Number(value as f64)
    }
}

impl From<bool> for FormulaValue {
    fn from(value: bool) -> Self {
        FormulaValue::Bool(value)
    }
}

impl From<&str> for FormulaValue {
    fn from(value: &str) -> Self {
        FormulaValue::Text(value.to_string())
    }
}

impl From<String> for FormulaValue {
    fn from(value: String) -> Self {
        FormulaValue::Text(value)
    }
}

impl From<CellValue> for FormulaValue {
    fn from(value: CellValue) -> Self {
        match value {
            CellValue::Number(n) => FormulaValue::Number(n),
            CellValue::Text(s) => FormulaValue::Text(s),
            CellValue::Bool(b) => FormulaValue::Bool(b),
        }
    }
}

impl TryFrom<FormulaValue> for CellValue {
    type Error = FormulaError;

    fn try_from(value: FormulaValue) -> Result<Self, Self::Error> {
        match value {
            FormulaValue::Number(n) => Ok(CellValue::Number(n)),
            FormulaValue::Text(s) => Ok(CellValue::Text(s)),
            FormulaValue::Bool(b) => Ok(CellValue::Bool(b)),
            other => Err(FormulaError::new(format!(
                "Cannot convert result value {:?} to CellValue",
                other
            ))),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FormulaError {
    message: String,
}

impl FormulaError {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

impl fmt::Display for FormulaError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl Error for FormulaError {}

pub type Context = HashMap<String, FormulaValue>;

#[derive(Clone, Debug, Default)]
pub struct Evaluator {
    context: Context,
}

impl Evaluator {
    pub fn new(context: Context) -> Self {
        Self { context }
    }

    pub fn evaluate(&self, node: &ASTNode) -> Result<FormulaValue, FormulaError> {
        match node {
            ASTNode::Number(value) => Ok(FormulaValue::Number(*value)),
            ASTNode::String(value) => Ok(FormulaValue::Text(value.clone())),
            ASTNode::Bool(value) => Ok(FormulaValue::Bool(*value)),
            ASTNode::Ident(name) => self.context.get(name).cloned().ok_or_else(|| {
                FormulaError::new(format!("Undefined variable: {:?}", name))
            }),
            ASTNode::UnaryOp { op, operand } => self.eval_unary(*op, operand),
            ASTNode::BinaryOp { op, left, right } => self.eval_binary(*op, left, right),
            ASTNode::FunctionCall { name, args } => functions::evaluate_function(self, name, args),
        }
    }

    fn eval_unary(&self, op: UnaryOperator, operand: &ASTNode) -> Result<FormulaValue, FormulaError> {
        let value = self.evaluate(operand)?;
        match op {
            UnaryOperator::Negate => Ok(FormulaValue::Number(-self.num(&value, "unary -")?)),
            UnaryOperator::Not => Ok(FormulaValue::Bool(!self.to_bool(&value))),
        }
    }

    fn eval_binary(
        &self,
        op: BinaryOperator,
        left: &ASTNode,
        right: &ASTNode,
    ) -> Result<FormulaValue, FormulaError> {
        match op {
            BinaryOperator::And => {
                let left_value = self.evaluate(left)?;
                if !self.to_bool(&left_value) {
                    return Ok(FormulaValue::Bool(false));
                }
                let right_value = self.evaluate(right)?;
                return Ok(FormulaValue::Bool(self.to_bool(&right_value)));
            }
            BinaryOperator::Or => {
                let left_value = self.evaluate(left)?;
                if self.to_bool(&left_value) {
                    return Ok(FormulaValue::Bool(true));
                }
                let right_value = self.evaluate(right)?;
                return Ok(FormulaValue::Bool(self.to_bool(&right_value)));
            }
            _ => {}
        }

        let left_value = self.evaluate(left)?;
        let right_value = self.evaluate(right)?;

        match op {
            BinaryOperator::Add => {
                if matches!(left_value, FormulaValue::Text(_))
                    || matches!(right_value, FormulaValue::Text(_))
                {
                    return Ok(FormulaValue::Text(format!(
                        "{}{}",
                        self.coerce_string(&left_value),
                        self.coerce_string(&right_value)
                    )));
                }
                Ok(FormulaValue::Number(
                    self.num(&left_value, "+")? + self.num(&right_value, "+")?,
                ))
            }
            BinaryOperator::Subtract => Ok(FormulaValue::Number(
                self.num(&left_value, "-")? - self.num(&right_value, "-")?,
            )),
            BinaryOperator::Multiply => Ok(FormulaValue::Number(
                self.num(&left_value, "*")? * self.num(&right_value, "*")?,
            )),
            BinaryOperator::Divide => {
                let divisor = self.num(&right_value, "/")?;
                if divisor == 0.0 {
                    return Err(FormulaError::new("Division by zero"));
                }
                Ok(FormulaValue::Number(self.num(&left_value, "/")? / divisor))
            }
            BinaryOperator::Power => Ok(FormulaValue::Number(
                self.num(&left_value, "^")?
                    .powf(self.num(&right_value, "^")?),
            )),
            BinaryOperator::Equal => Ok(FormulaValue::Bool(values_equal(&left_value, &right_value))),
            BinaryOperator::NotEqual => {
                Ok(FormulaValue::Bool(!values_equal(&left_value, &right_value)))
            }
            BinaryOperator::LessThan => Ok(FormulaValue::Bool(
                self.compare_values(&left_value, &right_value)? < 0,
            )),
            BinaryOperator::GreaterThan => Ok(FormulaValue::Bool(
                self.compare_values(&left_value, &right_value)? > 0,
            )),
            BinaryOperator::LessEqual => Ok(FormulaValue::Bool(
                self.compare_values(&left_value, &right_value)? <= 0,
            )),
            BinaryOperator::GreaterEqual => Ok(FormulaValue::Bool(
                self.compare_values(&left_value, &right_value)? >= 0,
            )),
            BinaryOperator::And | BinaryOperator::Or => unreachable!(),
        }
    }

    pub(crate) fn compare_values(
        &self,
        left: &FormulaValue,
        right: &FormulaValue,
    ) -> Result<i8, FormulaError> {
        if let (Some(a), Some(b)) = (self.numeric_comparison_value(left), self.numeric_comparison_value(right)) {
            if a < b {
                return Ok(-1);
            }
            if a > b {
                return Ok(1);
            }
            return Ok(0);
        }

        if let (FormulaValue::Text(a), FormulaValue::Text(b)) = (left, right) {
            if a < b {
                return Ok(-1);
            }
            if a > b {
                return Ok(1);
            }
            return Ok(0);
        }

        Err(FormulaError::new(format!(
            "Cannot compare {} with {}",
            type_name(left),
            type_name(right)
        )))
    }

    pub(crate) fn to_bool(&self, value: &FormulaValue) -> bool {
        match value {
            FormulaValue::Bool(v) => *v,
            FormulaValue::Number(v) => *v != 0.0,
            FormulaValue::Text(v) => !v.is_empty(),
            FormulaValue::Null => false,
            FormulaValue::List(v) => !v.is_empty(),
            FormulaValue::Map(v) => !v.is_empty(),
        }
    }

    pub(crate) fn num(&self, value: &FormulaValue, context_label: &str) -> Result<f64, FormulaError> {
        match value {
            FormulaValue::Bool(v) => Ok(if *v { 1.0 } else { 0.0 }),
            FormulaValue::Number(v) => Ok(*v),
            _ => Err(FormulaError::new(format!(
                "Expected a number in {}, got {}: {}",
                context_label,
                type_name(value),
                self.coerce_string(value)
            ))),
        }
    }

    pub(crate) fn str_value(
        &self,
        value: &FormulaValue,
        context_label: &str,
    ) -> Result<String, FormulaError> {
        match value {
            FormulaValue::Text(v) => Ok(v.clone()),
            _ => Err(FormulaError::new(format!(
                "Expected a string in {}, got {}: {}",
                context_label,
                type_name(value),
                self.coerce_string(value)
            ))),
        }
    }

    pub(crate) fn check_arity(
        &self,
        name: &str,
        args: &[FormulaValue],
        expected: usize,
    ) -> Result<(), FormulaError> {
        if args.len() != expected {
            return Err(FormulaError::new(format!(
                "{} requires exactly {} argument(s), got {}",
                name,
                expected,
                args.len()
            )));
        }
        Ok(())
    }

    pub(crate) fn flatten_numbers(
        &self,
        args: &[FormulaValue],
        context_label: &str,
    ) -> Result<Vec<f64>, FormulaError> {
        let mut result = Vec::new();
        for arg in args {
            match arg {
                FormulaValue::List(values) => {
                    for item in values {
                        result.push(self.num(item, context_label)?);
                    }
                }
                _ => result.push(self.num(arg, context_label)?),
            }
        }
        Ok(result)
    }

    pub(crate) fn coerce_string(&self, value: &FormulaValue) -> String {
        match value {
            FormulaValue::Number(v) => format_number_like_python(*v),
            FormulaValue::Text(v) => v.clone(),
            FormulaValue::Bool(v) => {
                if *v {
                    "True".to_string()
                } else {
                    "False".to_string()
                }
            }
            FormulaValue::Null => "None".to_string(),
            FormulaValue::List(values) => {
                let rendered = values
                    .iter()
                    .map(|v| self.coerce_string(v))
                    .collect::<Vec<String>>()
                    .join(", ");
                format!("[{}]", rendered)
            }
            FormulaValue::Map(values) => {
                let mut entries = values
                    .iter()
                    .map(|(k, v)| format!("{:?}: {}", k, self.coerce_string(v)))
                    .collect::<Vec<String>>();
                entries.sort();
                format!("{{{}}}", entries.join(", "))
            }
        }
    }

    fn numeric_comparison_value(&self, value: &FormulaValue) -> Option<f64> {
        match value {
            FormulaValue::Number(v) => Some(*v),
            FormulaValue::Bool(v) => Some(if *v { 1.0 } else { 0.0 }),
            _ => None,
        }
    }
}

fn format_number_like_python(value: f64) -> String {
    if value.is_finite() && value.fract() == 0.0 {
        format!("{:.1}", value)
    } else {
        value.to_string()
    }
}

fn type_name(value: &FormulaValue) -> &'static str {
    match value {
        FormulaValue::Number(_) => "float",
        FormulaValue::Text(_) => "str",
        FormulaValue::Bool(_) => "bool",
        FormulaValue::List(_) => "list",
        FormulaValue::Map(_) => "dict",
        FormulaValue::Null => "NoneType",
    }
}

fn values_equal(left: &FormulaValue, right: &FormulaValue) -> bool {
    match (left, right) {
        (FormulaValue::Number(a), FormulaValue::Number(b)) => a == b,
        (FormulaValue::Bool(a), FormulaValue::Bool(b)) => a == b,
        (FormulaValue::Text(a), FormulaValue::Text(b)) => a == b,
        (FormulaValue::Null, FormulaValue::Null) => true,
        (FormulaValue::List(a), FormulaValue::List(b)) => a == b,
        (FormulaValue::Map(a), FormulaValue::Map(b)) => a == b,
        (FormulaValue::Number(a), FormulaValue::Bool(b))
        | (FormulaValue::Bool(b), FormulaValue::Number(a)) => *a == if *b { 1.0 } else { 0.0 },
        _ => false,
    }
}
