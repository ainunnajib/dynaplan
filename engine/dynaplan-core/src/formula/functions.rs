use chrono::{Datelike, Duration, NaiveDate, Weekday};

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
    "YEARVALUE",
    "MONTHVALUE",
    "QUARTERVALUE",
    "WEEKVALUE",
    "HALFYEARVALUE",
    "CURRENTPERIODSTART",
    "CURRENTPERIODEND",
    "PERIODSTART",
    "PERIODEND",
    "TIMESUM",
    "TIMEAVERAGE",
    "TIMECOUNT",
    "LAG",
    "LEAD",
    "OFFSET",
    "MOVINGSUM",
    "MOVINGAVERAGE",
    "CUMULATE",
    "PREVIOUS",
    "NEXT",
    "INPERIOD",
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
        "YEARVALUE" => fn_period_value(evaluator, name, &args, PeriodUnit::Year),
        "MONTHVALUE" => fn_period_value(evaluator, name, &args, PeriodUnit::Month),
        "QUARTERVALUE" => fn_period_value(evaluator, name, &args, PeriodUnit::Quarter),
        "WEEKVALUE" => fn_period_value(evaluator, name, &args, PeriodUnit::Week),
        "HALFYEARVALUE" => fn_period_value(evaluator, name, &args, PeriodUnit::HalfYear),
        "CURRENTPERIODSTART" => fn_current_period_start(evaluator, name, &args),
        "CURRENTPERIODEND" => fn_current_period_end(evaluator, name, &args),
        "PERIODSTART" => fn_period_start(evaluator, name, &args),
        "PERIODEND" => fn_period_end(evaluator, name, &args),
        "TIMESUM" => fn_time_sum(evaluator, name, &args),
        "TIMEAVERAGE" => fn_time_average(evaluator, name, &args),
        "TIMECOUNT" => fn_time_count(evaluator, name, &args),
        "LAG" => fn_lag(evaluator, name, &args),
        "LEAD" => fn_lead(evaluator, name, &args),
        "OFFSET" => fn_offset(evaluator, name, &args),
        "MOVINGSUM" => fn_moving_sum(evaluator, name, &args),
        "MOVINGAVERAGE" => fn_moving_average(evaluator, name, &args),
        "CUMULATE" => fn_cumulate(evaluator, name, &args),
        "PREVIOUS" => fn_previous(evaluator, name, &args),
        "NEXT" => fn_next(evaluator, name, &args),
        "INPERIOD" => fn_in_period(evaluator, name, &args),
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

#[derive(Clone, Copy)]
enum PeriodUnit {
    Year,
    Month,
    Quarter,
    Week,
    HalfYear,
}

fn check_arity_range(
    name: &str,
    args: &[FormulaValue],
    min_expected: usize,
    max_expected: usize,
) -> Result<(), FormulaError> {
    if args.len() < min_expected || args.len() > max_expected {
        return Err(FormulaError::new(format!(
            "{} requires between {} and {} argument(s), got {}",
            name,
            min_expected,
            max_expected,
            args.len()
        )));
    }
    Ok(())
}

fn context_first<'a>(evaluator: &'a Evaluator, keys: &[&str]) -> Option<&'a FormulaValue> {
    keys.iter().find_map(|key| evaluator.context_value(key))
}

fn resolve_current_period<'a>(evaluator: &'a Evaluator) -> Option<&'a FormulaValue> {
    context_first(
        evaluator,
        &["CURRENT_PERIOD", "current_period", "_current_period"],
    )
}

fn resolve_time_periods<'a>(evaluator: &'a Evaluator) -> Option<&'a Vec<FormulaValue>> {
    context_first(
        evaluator,
        &["TIME_PERIODS", "time_periods", "_time_periods", "PERIODS", "periods"],
    )
    .and_then(|value| match value {
        FormulaValue::List(items) => Some(items),
        _ => None,
    })
}

fn resolve_current_index(
    evaluator: &Evaluator,
    series_len: usize,
    context_label: &str,
) -> Result<usize, FormulaError> {
    if series_len == 0 {
        return Ok(0);
    }

    let raw = context_first(
        evaluator,
        &["CURRENT_INDEX", "current_index", "_current_index"],
    );
    let Some(raw) = raw else {
        return Ok(series_len - 1);
    };

    let index = evaluator.num(raw, context_label)?.trunc() as i64;
    Ok(index.clamp(0, (series_len as i64) - 1) as usize)
}

fn series_and_index(
    evaluator: &Evaluator,
    value: &FormulaValue,
    context_label: &str,
) -> Result<(Vec<FormulaValue>, usize), FormulaError> {
    if let FormulaValue::Map(mapping) = value {
        if let Some(series_value) = mapping.get("series") {
            let FormulaValue::List(series) = series_value else {
                return Err(FormulaError::new(format!(
                    "{} expects 'series' to be a list",
                    context_label
                )));
            };

            if series.is_empty() {
                return Ok((Vec::new(), 0));
            }

            let index = if let Some(idx_value) = mapping.get("index") {
                evaluator.num(idx_value, context_label)?.trunc() as i64
            } else {
                resolve_current_index(evaluator, series.len(), context_label)? as i64
            };

            return Ok((
                series.clone(),
                index.clamp(0, (series.len() as i64) - 1) as usize,
            ));
        }
    }

    if let FormulaValue::List(series) = value {
        if series.is_empty() {
            return Ok((Vec::new(), 0));
        }
        return Ok((
            series.clone(),
            resolve_current_index(evaluator, series.len(), context_label)?,
        ));
    }

    if let Some(FormulaValue::List(series)) =
        context_first(evaluator, &["TIME_SERIES", "time_series", "_time_series"])
    {
        if !series.is_empty() {
            return Ok((
                series.clone(),
                resolve_current_index(evaluator, series.len(), context_label)?,
            ));
        }
    }

    Ok((vec![value.clone()], 0))
}

fn shift_series_value(
    series: &[FormulaValue],
    index: usize,
    delta: i64,
    default: FormulaValue,
) -> FormulaValue {
    if series.is_empty() {
        return default;
    }
    let target = index as i64 + delta;
    if target < 0 || target >= series.len() as i64 {
        return default;
    }
    series[target as usize].clone()
}

fn build_time_pairs(
    evaluator: &Evaluator,
    values: &FormulaValue,
) -> Vec<(Option<FormulaValue>, FormulaValue)> {
    match values {
        FormulaValue::Map(mapping) => mapping
            .iter()
            .map(|(period, value)| (Some(FormulaValue::Text(period.clone())), value.clone()))
            .collect(),
        FormulaValue::List(items) => {
            if let Some(periods) = resolve_time_periods(evaluator) {
                let mut out = Vec::with_capacity(items.len());
                let limit = periods.len().min(items.len());
                for idx in 0..limit {
                    out.push((Some(periods[idx].clone()), items[idx].clone()));
                }
                for item in &items[limit..] {
                    out.push((None, item.clone()));
                }
                out
            } else {
                items.iter().map(|item| (None, item.clone())).collect()
            }
        }
        other => vec![(resolve_current_period(evaluator).cloned(), other.clone())],
    }
}

fn filter_time_pairs_by_range(
    pairs: &[(Option<FormulaValue>, FormulaValue)],
    start_period: Option<&FormulaValue>,
    end_period: Option<&FormulaValue>,
    context_label: &str,
) -> Result<Vec<(Option<FormulaValue>, FormulaValue)>, FormulaError> {
    if start_period.is_none() && end_period.is_none() {
        return Ok(pairs.to_vec());
    }

    let min_date = NaiveDate::from_ymd_opt(1, 1, 1).unwrap();
    let max_date = NaiveDate::from_ymd_opt(9999, 12, 31).unwrap();

    let range_start = if let Some(value) = start_period {
        period_bounds(value, context_label)?.0
    } else {
        min_date
    };

    let range_end = if let Some(value) = end_period {
        period_bounds(value, context_label)?.1
    } else {
        max_date
    };

    let mut out = Vec::new();
    for (period, value) in pairs {
        let Some(period_value) = period else {
            continue;
        };
        let Ok((start, end)) = period_bounds(period_value, context_label) else {
            continue;
        };
        if end >= range_start && start <= range_end {
            out.push((Some(period_value.clone()), value.clone()));
        }
    }
    Ok(out)
}

fn fn_period_value(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
    unit: PeriodUnit,
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 2)?;
    let values = &args[0];

    if !matches!(values, FormulaValue::List(_) | FormulaValue::Map(_)) {
        return Ok(FormulaValue::Number(evaluator.num(values, name)?));
    }

    let target = if args.len() == 2 {
        Some(&args[1])
    } else {
        resolve_current_period(evaluator)
    };

    let target_component = match target {
        Some(value) => Some(period_component(value, unit, name)?),
        None => None,
    };

    let pairs = build_time_pairs(evaluator, values);
    let mut total = 0.0;
    let mut matched = false;

    for (period, value) in pairs {
        let number = evaluator.num(&value, name)?;
        if let Some(target_value) = target_component {
            let Some(period_value) = period else {
                continue;
            };
            let Ok(component) = period_component(&period_value, unit, name) else {
                continue;
            };
            if component == target_value {
                total += number;
                matched = true;
            }
        } else {
            total += number;
            matched = true;
        }
    }

    if target_component.is_some() && !matched {
        return Ok(FormulaValue::Number(0.0));
    }
    Ok(FormulaValue::Number(total))
}

fn fn_current_period_start(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 0, 1)?;
    let period = if args.len() == 1 {
        Some(&args[0])
    } else {
        resolve_current_period(evaluator)
    };
    let Some(period) = period else {
        return Err(FormulaError::new(
            "CURRENTPERIODSTART requires a period argument or current period context",
        ));
    };
    let (start, _) = period_bounds(period, name)?;
    Ok(FormulaValue::Text(start.to_string()))
}

fn fn_current_period_end(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 0, 1)?;
    let period = if args.len() == 1 {
        Some(&args[0])
    } else {
        resolve_current_period(evaluator)
    };
    let Some(period) = period else {
        return Err(FormulaError::new(
            "CURRENTPERIODEND requires a period argument or current period context",
        ));
    };
    let (_, end) = period_bounds(period, name)?;
    Ok(FormulaValue::Text(end.to_string()))
}

fn fn_period_start(
    _evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    let (start, _) = period_bounds(&args[0], name)?;
    Ok(FormulaValue::Text(start.to_string()))
}

fn fn_period_end(
    _evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    let (_, end) = period_bounds(&args[0], name)?;
    Ok(FormulaValue::Text(end.to_string()))
}

fn fn_time_sum(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 3)?;
    let pairs = build_time_pairs(evaluator, &args[0]);
    let filtered = filter_time_pairs_by_range(
        &pairs,
        args.get(1),
        args.get(2),
        name,
    )?;
    let total = filtered
        .iter()
        .map(|(_, value)| evaluator.num(value, name))
        .collect::<Result<Vec<f64>, FormulaError>>()?
        .iter()
        .sum();
    Ok(FormulaValue::Number(total))
}

fn fn_time_average(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 3)?;
    let pairs = build_time_pairs(evaluator, &args[0]);
    let filtered = filter_time_pairs_by_range(
        &pairs,
        args.get(1),
        args.get(2),
        name,
    )?;
    let values = filtered
        .iter()
        .map(|(_, value)| evaluator.num(value, name))
        .collect::<Result<Vec<f64>, FormulaError>>()?;
    if values.is_empty() {
        return Err(FormulaError::new("TIMEAVERAGE called with empty range"));
    }
    Ok(FormulaValue::Number(values.iter().sum::<f64>() / values.len() as f64))
}

fn fn_time_count(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 3)?;
    let pairs = build_time_pairs(evaluator, &args[0]);
    let filtered = filter_time_pairs_by_range(
        &pairs,
        args.get(1),
        args.get(2),
        name,
    )?;
    let count = filtered
        .iter()
        .filter(|(_, value)| !matches!(value, FormulaValue::Null))
        .count();
    Ok(FormulaValue::Number(count as f64))
}

fn fn_lag(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 3)?;
    let (series, index) = series_and_index(evaluator, &args[0], name)?;
    let offset = evaluator.num(&args[1], name)?.trunc() as i64;
    let default = args.get(2).cloned().unwrap_or(FormulaValue::Number(0.0));
    Ok(shift_series_value(&series, index, -offset, default))
}

fn fn_lead(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 3)?;
    let (series, index) = series_and_index(evaluator, &args[0], name)?;
    let offset = evaluator.num(&args[1], name)?.trunc() as i64;
    let default = args.get(2).cloned().unwrap_or(FormulaValue::Number(0.0));
    Ok(shift_series_value(&series, index, offset, default))
}

fn fn_offset(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 3)?;
    let (series, index) = series_and_index(evaluator, &args[0], name)?;
    let offset = evaluator.num(&args[1], name)?.trunc() as i64;
    let default = args.get(2).cloned().unwrap_or(FormulaValue::Number(0.0));
    Ok(shift_series_value(&series, index, offset, default))
}

fn fn_moving_sum(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let (series, index) = series_and_index(evaluator, &args[0], name)?;
    let window = evaluator.num(&args[1], name)?.trunc() as i64;
    if window <= 0 {
        return Err(FormulaError::new("MOVINGSUM window must be > 0"));
    }
    if series.is_empty() {
        return Ok(FormulaValue::Number(0.0));
    }
    let start = (index as i64 - window + 1).max(0) as usize;
    let mut total = 0.0;
    for value in &series[start..=index] {
        total += evaluator.num(value, name)?;
    }
    Ok(FormulaValue::Number(total))
}

fn fn_moving_average(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let (series, index) = series_and_index(evaluator, &args[0], name)?;
    let window = evaluator.num(&args[1], name)?.trunc() as i64;
    if window <= 0 {
        return Err(FormulaError::new("MOVINGAVERAGE window must be > 0"));
    }
    if series.is_empty() {
        return Err(FormulaError::new("MOVINGAVERAGE called with empty list"));
    }
    let start = (index as i64 - window + 1).max(0) as usize;
    let slice = &series[start..=index];
    let mut total = 0.0;
    for value in slice {
        total += evaluator.num(value, name)?;
    }
    Ok(FormulaValue::Number(total / slice.len() as f64))
}

fn fn_cumulate(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    let (series, index) = series_and_index(evaluator, &args[0], name)?;
    if series.is_empty() {
        return Ok(FormulaValue::Number(0.0));
    }
    let mut total = 0.0;
    for value in &series[0..=index] {
        total += evaluator.num(value, name)?;
    }
    Ok(FormulaValue::Number(total))
}

fn fn_previous(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 2)?;
    let (series, index) = series_and_index(evaluator, &args[0], name)?;
    let default = args.get(1).cloned().unwrap_or(FormulaValue::Number(0.0));
    Ok(shift_series_value(&series, index, -1, default))
}

fn fn_next(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 2)?;
    let (series, index) = series_and_index(evaluator, &args[0], name)?;
    let default = args.get(1).cloned().unwrap_or(FormulaValue::Number(0.0));
    Ok(shift_series_value(&series, index, 1, default))
}

fn fn_in_period(
    _evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let target_date = coerce_date(&args[0], name)?;
    let (start, end) = period_bounds(&args[1], name)?;
    Ok(FormulaValue::Bool(target_date >= start && target_date <= end))
}

fn coerce_date(value: &FormulaValue, context_label: &str) -> Result<NaiveDate, FormulaError> {
    match value {
        FormulaValue::Text(raw) => parse_date_text(raw, context_label),
        _ => Err(FormulaError::new(format!(
            "Expected a date in {}, got {:?}",
            context_label, value
        ))),
    }
}

fn parse_date_text(text: &str, context_label: &str) -> Result<NaiveDate, FormulaError> {
    let trimmed = text.trim();
    if let Ok(parsed) = NaiveDate::parse_from_str(trimmed, "%Y-%m-%d") {
        return Ok(parsed);
    }
    if trimmed.len() >= 10 {
        if let Ok(parsed) = NaiveDate::parse_from_str(&trimmed[0..10], "%Y-%m-%d") {
            return Ok(parsed);
        }
    }
    Err(FormulaError::new(format!(
        "Expected a date in {}, got {:?}",
        context_label, text
    )))
}

fn period_bounds(
    value: &FormulaValue,
    context_label: &str,
) -> Result<(NaiveDate, NaiveDate), FormulaError> {
    match value {
        FormulaValue::Map(mapping) => {
            if let (Some(start), Some(end)) = (mapping.get("start_date"), mapping.get("end_date")) {
                let start_date = coerce_date(start, context_label)?;
                let end_date = coerce_date(end, context_label)?;
                if start_date > end_date {
                    return Err(FormulaError::new("Period start_date must be <= end_date"));
                }
                return Ok((start_date, end_date));
            }

            if let (Some(start), Some(end)) = (mapping.get("start"), mapping.get("end")) {
                let start_date = coerce_date(start, context_label)?;
                let end_date = coerce_date(end, context_label)?;
                if start_date > end_date {
                    return Err(FormulaError::new("Period start must be <= end"));
                }
                return Ok((start_date, end_date));
            }

            if let Some(code) = mapping.get("code") {
                return period_bounds(code, context_label);
            }

            Err(FormulaError::new(format!(
                "Expected a recognizable period in {}, got map without bounds",
                context_label
            )))
        }
        FormulaValue::Number(raw_year) => {
            let year = raw_year.trunc() as i32;
            if year < 1 {
                return Err(FormulaError::new(format!("Invalid period year: {}", year)));
            }
            let start = NaiveDate::from_ymd_opt(year, 1, 1).ok_or_else(|| {
                FormulaError::new(format!("Invalid period year: {}", year))
            })?;
            let end = NaiveDate::from_ymd_opt(year, 12, 31).ok_or_else(|| {
                FormulaError::new(format!("Invalid period year: {}", year))
            })?;
            Ok((start, end))
        }
        FormulaValue::Text(text) => parse_period_text(text, context_label),
        _ => Err(FormulaError::new(format!(
            "Expected a recognizable period in {}, got {:?}",
            context_label, value
        ))),
    }
}

fn parse_period_text(
    text: &str,
    context_label: &str,
) -> Result<(NaiveDate, NaiveDate), FormulaError> {
    let trimmed = text.trim();

    if let Ok(parsed) = parse_date_text(trimmed, context_label) {
        return Ok((parsed, parsed));
    }

    let upper = trimmed.to_ascii_uppercase();
    let parts = upper.split('-').collect::<Vec<&str>>();

    if parts.len() == 1 && parts[0].starts_with("FY") && parts[0].len() == 6 {
        let year = parts[0][2..].parse::<i32>().map_err(|_| {
            FormulaError::new(format!("Invalid fiscal year period: {:?}", text))
        })?;
        let start = NaiveDate::from_ymd_opt(year, 1, 1).ok_or_else(|| {
            FormulaError::new(format!("Invalid fiscal year period: {:?}", text))
        })?;
        let end = NaiveDate::from_ymd_opt(year, 12, 31).ok_or_else(|| {
            FormulaError::new(format!("Invalid fiscal year period: {:?}", text))
        })?;
        return Ok((start, end));
    }

    let year = parse_year_token(parts[0]).ok_or_else(|| {
        FormulaError::new(format!("Expected a recognizable period in {}, got {:?}", context_label, text))
    })?;

    if parts.len() == 2 {
        if parts[1].len() == 2 && parts[1].starts_with('Q') {
            let quarter = parts[1][1..2].parse::<u32>().map_err(|_| {
                FormulaError::new(format!("Invalid quarter period: {:?}", text))
            })?;
            if !(1..=4).contains(&quarter) {
                return Err(FormulaError::new(format!(
                    "Invalid quarter period: {:?}",
                    text
                )));
            }
            let start_month = (quarter - 1) * 3 + 1;
            let start = NaiveDate::from_ymd_opt(year, start_month, 1).ok_or_else(|| {
                FormulaError::new(format!("Invalid quarter period: {:?}", text))
            })?;
            let end_month = start_month + 2;
            let end = last_day_of_month(year, end_month)?;
            return Ok((start, end));
        }

        if parts[1].len() == 2 && parts[1].starts_with('H') {
            let half = parts[1][1..2].parse::<u32>().map_err(|_| {
                FormulaError::new(format!("Invalid half-year period: {:?}", text))
            })?;
            if !(1..=2).contains(&half) {
                return Err(FormulaError::new(format!(
                    "Invalid half-year period: {:?}",
                    text
                )));
            }
            let start_month = if half == 1 { 1 } else { 7 };
            let end_month = if half == 1 { 6 } else { 12 };
            let start = NaiveDate::from_ymd_opt(year, start_month, 1).ok_or_else(|| {
                FormulaError::new(format!("Invalid half-year period: {:?}", text))
            })?;
            let end = last_day_of_month(year, end_month)?;
            return Ok((start, end));
        }

        if parts[1].starts_with('W') {
            let week = parts[1][1..].parse::<u32>().map_err(|_| {
                FormulaError::new(format!("Invalid ISO week period: {:?}", text))
            })?;
            let start = NaiveDate::from_isoywd_opt(year, week, Weekday::Mon).ok_or_else(|| {
                FormulaError::new(format!("Invalid ISO week period: {:?}", text))
            })?;
            return Ok((start, start + Duration::days(6)));
        }

        if parts[1].len() == 2 {
            let month = parts[1].parse::<u32>().map_err(|_| {
                FormulaError::new(format!("Invalid month period: {:?}", text))
            })?;
            let start = NaiveDate::from_ymd_opt(year, month, 1).ok_or_else(|| {
                FormulaError::new(format!("Invalid month period: {:?}", text))
            })?;
            let end = last_day_of_month(year, month)?;
            return Ok((start, end));
        }
    }

    if parts.len() == 3 && parts[2].starts_with('W') && parts[1].len() == 2 {
        let month = parts[1].parse::<u32>().map_err(|_| {
            FormulaError::new(format!("Invalid month-week period: {:?}", text))
        })?;
        let week = parts[2][1..].parse::<u32>().map_err(|_| {
            FormulaError::new(format!("Invalid month-week period: {:?}", text))
        })?;
        if week == 0 {
            return Err(FormulaError::new(format!(
                "Invalid month-week period: {:?}",
                text
            )));
        }
        let start_month = NaiveDate::from_ymd_opt(year, month, 1).ok_or_else(|| {
            FormulaError::new(format!("Invalid month-week period: {:?}", text))
        })?;
        let start = start_month + Duration::days(((week - 1) * 7) as i64);
        if start.month() != month {
            return Err(FormulaError::new(format!(
                "Invalid month-week period: {:?}",
                text
            )));
        }
        let month_end = last_day_of_month(year, month)?;
        let end = if start + Duration::days(6) > month_end {
            month_end
        } else {
            start + Duration::days(6)
        };
        return Ok((start, end));
    }

    Err(FormulaError::new(format!(
        "Expected a recognizable period in {}, got {:?}",
        context_label, text
    )))
}

fn parse_year_token(token: &str) -> Option<i32> {
    if token.starts_with("FY") && token.len() == 6 {
        token[2..].parse::<i32>().ok()
    } else if token.len() == 4 {
        token.parse::<i32>().ok()
    } else {
        None
    }
}

fn last_day_of_month(year: i32, month: u32) -> Result<NaiveDate, FormulaError> {
    let next_month = if month == 12 {
        NaiveDate::from_ymd_opt(year + 1, 1, 1)
    } else {
        NaiveDate::from_ymd_opt(year, month + 1, 1)
    }
    .ok_or_else(|| FormulaError::new(format!("Invalid month value: {}/{}", year, month)))?;
    Ok(next_month - Duration::days(1))
}

fn period_component(
    value: &FormulaValue,
    unit: PeriodUnit,
    context_label: &str,
) -> Result<i32, FormulaError> {
    if let FormulaValue::Number(raw) = value {
        return Ok(raw.trunc() as i32);
    }

    if let FormulaValue::Map(mapping) = value {
        let key_candidates: &[&str] = match unit {
            PeriodUnit::Year => &["year"],
            PeriodUnit::Month => &["month"],
            PeriodUnit::Quarter => &["quarter", "q"],
            PeriodUnit::Week => &["week", "week_number"],
            PeriodUnit::HalfYear => &["half", "half_year", "halfyear", "h"],
        };
        for key in key_candidates {
            if let Some(raw) = mapping.get(*key) {
                return Ok(raw_number_i32(raw, context_label)?);
            }
        }
    }

    let (start, _) = period_bounds(value, context_label)?;
    Ok(match unit {
        PeriodUnit::Year => start.year(),
        PeriodUnit::Month => start.month() as i32,
        PeriodUnit::Quarter => ((start.month0() / 3) + 1) as i32,
        PeriodUnit::Week => start.iso_week().week() as i32,
        PeriodUnit::HalfYear => {
            if start.month() <= 6 {
                1
            } else {
                2
            }
        }
    })
}

fn raw_number_i32(value: &FormulaValue, context_label: &str) -> Result<i32, FormulaError> {
    match value {
        FormulaValue::Number(v) => Ok(v.trunc() as i32),
        FormulaValue::Bool(v) => Ok(if *v { 1 } else { 0 }),
        _ => Err(FormulaError::new(format!(
            "Expected numeric selector in {}, got {:?}",
            context_label, value
        ))),
    }
}
