use super::evaluator::{Evaluator, FormulaError, FormulaValue};
use super::parser::ASTNode;

pub const BUILTIN_FUNCTIONS: &[&str] = &[
    "ABS",
    "ROUND",
    "MIN",
    "MAX",
    "POWER",
    "SQRT",
    "LOG",
    "SUM",
    "AVERAGE",
    "COUNT",
    "IF",
    "AND",
    "OR",
    "NOT",
    "ISBLANK",
    "CONCATENATE",
    "LEFT",
    "RIGHT",
    "LEN",
    "UPPER",
    "LOWER",
    "TRIM",
    "LOOKUP",
];

pub fn is_builtin_function(name: &str) -> bool {
    let upper = name.to_ascii_uppercase();
    BUILTIN_FUNCTIONS.iter().any(|f| *f == upper)
}

pub(crate) fn evaluate_function(
    evaluator: &Evaluator,
    name: &str,
    arg_nodes: &[ASTNode],
) -> Result<FormulaValue, FormulaError> {
    if name == "IF" {
        return fn_if(evaluator, arg_nodes);
    }

    let args = arg_nodes
        .iter()
        .map(|node| evaluator.evaluate(node))
        .collect::<Result<Vec<FormulaValue>, FormulaError>>()?;

    match name {
        "ABS" => {
            evaluator.check_arity(name, &args, 1)?;
            Ok(FormulaValue::Number(evaluator.num(&args[0], name)?.abs()))
        }
        "ROUND" => {
            evaluator.check_arity(name, &args, 2)?;
            let n = evaluator.num(&args[0], name)?;
            let decimals = evaluator.num(&args[1], name)?.trunc() as i32;
            let factor = 10f64.powi(decimals);
            Ok(FormulaValue::Number((n * factor).round() / factor))
        }
        "MIN" => {
            if args.is_empty() {
                return Err(FormulaError::new("MIN requires at least one argument"));
            }
            let flat = evaluator.flatten_numbers(&args, name)?;
            let value = flat
                .into_iter()
                .reduce(f64::min)
                .ok_or_else(|| FormulaError::new("MIN requires at least one argument"))?;
            Ok(FormulaValue::Number(value))
        }
        "MAX" => {
            if args.is_empty() {
                return Err(FormulaError::new("MAX requires at least one argument"));
            }
            let flat = evaluator.flatten_numbers(&args, name)?;
            let value = flat
                .into_iter()
                .reduce(f64::max)
                .ok_or_else(|| FormulaError::new("MAX requires at least one argument"))?;
            Ok(FormulaValue::Number(value))
        }
        "POWER" => {
            evaluator.check_arity(name, &args, 2)?;
            Ok(FormulaValue::Number(
                evaluator.num(&args[0], name)?
                    .powf(evaluator.num(&args[1], name)?),
            ))
        }
        "SQRT" => {
            evaluator.check_arity(name, &args, 1)?;
            let n = evaluator.num(&args[0], name)?;
            if n < 0.0 {
                return Err(FormulaError::new(format!("SQRT of negative number: {}", n)));
            }
            Ok(FormulaValue::Number(n.sqrt()))
        }
        "LOG" => {
            if args.len() != 1 && args.len() != 2 {
                return Err(FormulaError::new("LOG requires 1 or 2 arguments"));
            }
            let x = evaluator.num(&args[0], name)?;
            if x <= 0.0 {
                return Err(FormulaError::new(format!(
                    "LOG of non-positive number: {}",
                    x
                )));
            }
            if args.len() == 2 {
                let base = evaluator.num(&args[1], name)?;
                Ok(FormulaValue::Number(x.log(base)))
            } else {
                Ok(FormulaValue::Number(x.log10()))
            }
        }
        "SUM" => {
            if args.is_empty() {
                return Err(FormulaError::new("SUM requires at least one argument"));
            }
            let flat = evaluator.flatten_numbers(&args, name)?;
            Ok(FormulaValue::Number(flat.iter().sum()))
        }
        "AVERAGE" => {
            if args.is_empty() {
                return Err(FormulaError::new("AVERAGE requires at least one argument"));
            }
            let flat = evaluator.flatten_numbers(&args, name)?;
            if flat.is_empty() {
                return Err(FormulaError::new("AVERAGE called with empty list"));
            }
            Ok(FormulaValue::Number(flat.iter().sum::<f64>() / flat.len() as f64))
        }
        "COUNT" => {
            if args.is_empty() {
                return Err(FormulaError::new("COUNT requires at least one argument"));
            }
            let count = args
                .iter()
                .map(|arg| match arg {
                    FormulaValue::List(values) => values.len(),
                    _ => 1,
                })
                .sum::<usize>();
            Ok(FormulaValue::Number(count as f64))
        }
        "AND" => Ok(FormulaValue::Bool(args.iter().all(|a| evaluator.to_bool(a)))),
        "OR" => Ok(FormulaValue::Bool(args.iter().any(|a| evaluator.to_bool(a)))),
        "NOT" => {
            evaluator.check_arity(name, &args, 1)?;
            Ok(FormulaValue::Bool(!evaluator.to_bool(&args[0])))
        }
        "ISBLANK" => {
            evaluator.check_arity(name, &args, 1)?;
            let value = &args[0];
            let blank = match value {
                FormulaValue::Null => true,
                FormulaValue::Text(v) => v.is_empty(),
                FormulaValue::Number(v) => *v == 0.0,
                FormulaValue::Bool(v) => !*v,
                _ => false,
            };
            Ok(FormulaValue::Bool(blank))
        }
        "CONCATENATE" => Ok(FormulaValue::Text(
            args.iter()
                .map(|arg| evaluator.coerce_string(arg))
                .collect::<Vec<String>>()
                .join(""),
        )),
        "LEFT" => {
            evaluator.check_arity(name, &args, 2)?;
            let s = evaluator.str_value(&args[0], name)?;
            let n = evaluator.num(&args[1], name)?.trunc() as i64;
            Ok(FormulaValue::Text(left_slice(&s, n)))
        }
        "RIGHT" => {
            evaluator.check_arity(name, &args, 2)?;
            let s = evaluator.str_value(&args[0], name)?;
            let n = evaluator.num(&args[1], name)?.trunc() as i64;
            Ok(FormulaValue::Text(right_slice(&s, n)))
        }
        "LEN" => {
            evaluator.check_arity(name, &args, 1)?;
            let s = evaluator.str_value(&args[0], name)?;
            Ok(FormulaValue::Number(s.chars().count() as f64))
        }
        "UPPER" => {
            evaluator.check_arity(name, &args, 1)?;
            Ok(FormulaValue::Text(
                evaluator.str_value(&args[0], name)?.to_uppercase(),
            ))
        }
        "LOWER" => {
            evaluator.check_arity(name, &args, 1)?;
            Ok(FormulaValue::Text(
                evaluator.str_value(&args[0], name)?.to_lowercase(),
            ))
        }
        "TRIM" => {
            evaluator.check_arity(name, &args, 1)?;
            Ok(FormulaValue::Text(
                evaluator
                    .str_value(&args[0], name)?
                    .trim()
                    .to_string(),
            ))
        }
        "LOOKUP" => {
            if args.is_empty() {
                return Err(FormulaError::new("LOOKUP requires at least one argument"));
            }
            let key = args[0].clone();
            if args.len() == 2 {
                if let FormulaValue::Map(mapping) = &args[1] {
                    let lookup_key = match &key {
                        FormulaValue::Text(v) => v.clone(),
                        _ => evaluator.coerce_string(&key),
                    };
                    if let Some(value) = mapping.get(&lookup_key) {
                        return Ok(value.clone());
                    }
                    return Err(FormulaError::new(format!(
                        "LOOKUP: key {:?} not found",
                        lookup_key
                    )));
                }
            }
            Ok(key)
        }
        _ => Err(FormulaError::new(format!("Unknown function: {:?}", name))),
    }
}

fn fn_if(evaluator: &Evaluator, arg_nodes: &[ASTNode]) -> Result<FormulaValue, FormulaError> {
    if arg_nodes.len() != 3 {
        return Err(FormulaError::new(format!(
            "IF requires exactly 3 arguments, got {}",
            arg_nodes.len()
        )));
    }

    let condition = evaluator.evaluate(&arg_nodes[0])?;
    if evaluator.to_bool(&condition) {
        evaluator.evaluate(&arg_nodes[1])
    } else {
        evaluator.evaluate(&arg_nodes[2])
    }
}

fn left_slice(value: &str, n: i64) -> String {
    let chars: Vec<char> = value.chars().collect();
    if n >= 0 {
        chars.into_iter().take(n as usize).collect()
    } else {
        let end = chars.len().saturating_sub((-n) as usize);
        chars.into_iter().take(end).collect()
    }
}

fn right_slice(value: &str, n: i64) -> String {
    if n <= 0 {
        return String::new();
    }
    let chars: Vec<char> = value.chars().collect();
    let start = chars.len().saturating_sub(n as usize);
    chars.into_iter().skip(start).collect()
}
