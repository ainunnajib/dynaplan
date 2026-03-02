use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use chrono::{Datelike, Duration, NaiveDate, NaiveDateTime, Weekday};

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
    "SUMIF",
    "COUNTIF",
    "AVERAGEIF",
    "MEDIAN",
    "STDEV",
    "VARIANCE",
    "PERCENTILE",
    "LARGE",
    "SMALL",
    "GROWTH",
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
    "MID",
    "FIND",
    "SUBSTITUTE",
    "TEXT",
    "VALUE",
    "TEXTLIST",
    "MAKETEXT",
    "CEILING",
    "FLOOR",
    "MOD",
    "SIGN",
    "FINDITEM",
    "ITEM",
    "PARENT",
    "CHILDREN",
    "ISLEAF",
    "ISANCESTOR",
    "LOOKUP",
    "SELECT",
    "NAME",
    "CODE",
    "RANK",
    "RANKLIST",
    "COLLECT",
    "POST",
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
    "YEARTODATE",
    "MONTHTODATE",
    "DATE",
    "DATEVALUE",
    "TODAY",
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
        "CEILING" => {
            evaluator.check_arity(name, &args, 1)?;
            Ok(FormulaValue::Number(evaluator.num(&args[0], name)?.ceil()))
        }
        "FLOOR" => {
            evaluator.check_arity(name, &args, 1)?;
            Ok(FormulaValue::Number(evaluator.num(&args[0], name)?.floor()))
        }
        "MOD" => {
            evaluator.check_arity(name, &args, 2)?;
            let divisor = evaluator.num(&args[1], name)?;
            if divisor == 0.0 {
                return Err(FormulaError::new("MOD divisor cannot be zero"));
            }
            Ok(FormulaValue::Number(evaluator.num(&args[0], name)? % divisor))
        }
        "SIGN" => {
            evaluator.check_arity(name, &args, 1)?;
            let value = evaluator.num(&args[0], name)?;
            Ok(FormulaValue::Number(if value > 0.0 {
                1.0
            } else if value < 0.0 {
                -1.0
            } else {
                0.0
            }))
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
            if args.len() == 2
                && matches!(args[0], FormulaValue::Map(_) | FormulaValue::List(_))
                && matches!(args[1], FormulaValue::Map(_))
            {
                return fn_sum_mapped(evaluator, name, &args);
            }
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
        "SUMIF" => fn_sumif(evaluator, name, &args),
        "COUNTIF" => fn_countif(evaluator, name, &args),
        "AVERAGEIF" => fn_averageif(evaluator, name, &args),
        "MEDIAN" => fn_median(evaluator, name, &args),
        "STDEV" => fn_stdev(evaluator, name, &args),
        "VARIANCE" => fn_variance(evaluator, name, &args),
        "PERCENTILE" => fn_percentile(evaluator, name, &args),
        "LARGE" => fn_large(evaluator, name, &args),
        "SMALL" => fn_small(evaluator, name, &args),
        "GROWTH" => fn_growth(evaluator, name, &args),
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
        "MID" => fn_mid(evaluator, name, &args),
        "FIND" => fn_find(evaluator, name, &args),
        "SUBSTITUTE" => fn_substitute(evaluator, name, &args),
        "TEXT" => fn_text(evaluator, name, &args),
        "VALUE" => fn_value(evaluator, name, &args),
        "TEXTLIST" => fn_textlist(evaluator, name, &args),
        "MAKETEXT" => fn_maketext(evaluator, name, &args),
        "FINDITEM" => fn_finditem(evaluator, name, &args),
        "ITEM" => fn_item(evaluator, name, &args),
        "PARENT" => fn_parent(evaluator, name, &args),
        "CHILDREN" => fn_children(evaluator, name, &args),
        "ISLEAF" => fn_isleaf(evaluator, name, &args),
        "ISANCESTOR" => fn_isancestor(evaluator, name, &args),
        "LOOKUP" => fn_lookup(evaluator, name, &args),
        "SELECT" => fn_select(evaluator, name, &args),
        "NAME" => fn_name(evaluator, name, &args),
        "CODE" => fn_code(evaluator, name, &args),
        "RANK" => fn_rank(evaluator, name, &args),
        "RANKLIST" => fn_ranklist(evaluator, name, &args),
        "COLLECT" => fn_collect(evaluator, name, &args),
        "POST" => fn_post(evaluator, name, &args),
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
        "YEARTODATE" => fn_year_to_date(evaluator, name, &args),
        "MONTHTODATE" => fn_month_to_date(evaluator, name, &args),
        "DATE" => fn_date(evaluator, name, &args),
        "DATEVALUE" => fn_date_value(evaluator, name, &args),
        "TODAY" => fn_today(evaluator, name, &args),
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

fn mid_slice(value: &str, start: i64, length: i64) -> String {
    if length <= 0 {
        return String::new();
    }
    let chars: Vec<char> = value.chars().collect();
    let start_index = if start <= 1 { 0 } else { (start - 1) as usize };
    chars
        .into_iter()
        .skip(start_index)
        .take(length as usize)
        .collect::<String>()
}

fn compact_number_text(value: f64) -> String {
    if value.is_finite() && value.fract() == 0.0 {
        return format!("{}", value as i64);
    }

    let mut text = value.to_string();
    if text.contains('.') {
        while text.ends_with('0') {
            text.pop();
        }
        if text.ends_with('.') {
            text.pop();
        }
    }
    text
}

fn coerce_text_output(value: &FormulaValue) -> String {
    match value {
        FormulaValue::Null => String::new(),
        FormulaValue::Bool(v) => {
            if *v {
                "TRUE".to_string()
            } else {
                "FALSE".to_string()
            }
        }
        FormulaValue::Number(v) => compact_number_text(*v),
        FormulaValue::Text(v) => v.clone(),
        FormulaValue::List(values) => values
            .iter()
            .map(coerce_text_output)
            .collect::<Vec<String>>()
            .join(", "),
        FormulaValue::Map(values) => {
            for key in ["name", "code", "id", "key", "item", "member"] {
                if let Some(raw) = values.get(key) {
                    if !matches!(raw, FormulaValue::Null) {
                        return coerce_text_output(raw);
                    }
                }
            }
            format!("{:?}", values)
        }
    }
}

fn parse_numeric_pattern_decimals(pattern: &str) -> Option<(usize, bool, bool)> {
    let trimmed = pattern.trim();
    if trimmed.is_empty() {
        return None;
    }

    let is_percent = trimmed.ends_with('%');
    let core = if is_percent {
        &trimmed[0..trimmed.len() - 1]
    } else {
        trimmed
    };

    if core.is_empty() {
        return None;
    }

    let mut chars = core.chars().peekable();
    while let Some(ch) = chars.peek() {
        if *ch == '#' || *ch == '0' || *ch == ',' {
            chars.next();
        } else {
            break;
        }
    }

    let mut decimals = 0usize;
    if matches!(chars.peek(), Some('.')) {
        chars.next();
        while let Some(ch) = chars.peek() {
            if *ch == '#' || *ch == '0' {
                decimals += 1;
                chars.next();
            } else {
                break;
            }
        }
    }

    if chars.next().is_some() {
        return None;
    }

    let use_grouping = core.contains(',');
    Some((decimals, is_percent, use_grouping))
}

fn format_number_pattern(value: f64, pattern: &str) -> Option<String> {
    let (decimals, is_percent, use_grouping) = parse_numeric_pattern_decimals(pattern)?;
    let number_to_format = if is_percent { value * 100.0 } else { value };
    let formatted = if use_grouping {
        format_with_grouping(number_to_format, decimals)
    } else {
        format!("{:.*}", decimals, number_to_format)
    };
    if is_percent {
        Some(format!("{}%", formatted))
    } else {
        Some(formatted)
    }
}

fn format_with_grouping(value: f64, decimals: usize) -> String {
    let mut fixed = format!("{:.*}", decimals, value);
    let mut sign = String::new();
    if fixed.starts_with('-') {
        sign.push('-');
        fixed = fixed[1..].to_string();
    }

    let parts = fixed.split('.').collect::<Vec<&str>>();
    let integer_part = parts.get(0).copied().unwrap_or("0");
    let frac_part = if parts.len() > 1 {
        Some(parts[1].to_string())
    } else {
        None
    };

    let reversed = integer_part.chars().rev().collect::<Vec<char>>();
    let mut grouped = String::new();
    for (idx, ch) in reversed.iter().enumerate() {
        if idx > 0 && idx % 3 == 0 {
            grouped.push(',');
        }
        grouped.push(*ch);
    }
    let grouped = grouped.chars().rev().collect::<String>();

    if let Some(frac) = frac_part {
        format!("{}{}.{}", sign, grouped, frac)
    } else {
        format!("{}{}", sign, grouped)
    }
}

fn fn_mid(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 3, 3)?;
    let text = evaluator.str_value(&args[0], name)?;
    let start = evaluator.num(&args[1], name)?.trunc() as i64;
    let length = evaluator.num(&args[2], name)?.trunc() as i64;
    Ok(FormulaValue::Text(mid_slice(&text, start, length)))
}

fn fn_find(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let search = evaluator.str_value(&args[0], name)?;
    let text = evaluator.str_value(&args[1], name)?;
    if search.is_empty() {
        return Ok(FormulaValue::Number(1.0));
    }
    if let Some(byte_idx) = text.find(&search) {
        let position = text[0..byte_idx].chars().count() + 1;
        return Ok(FormulaValue::Number(position as f64));
    }
    Ok(FormulaValue::Number(0.0))
}

fn fn_substitute(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 3, 3)?;
    let text = evaluator.str_value(&args[0], name)?;
    let old_text = evaluator.str_value(&args[1], name)?;
    let new_text = evaluator.str_value(&args[2], name)?;
    Ok(FormulaValue::Text(text.replace(&old_text, &new_text)))
}

fn fn_text(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 2)?;
    let number = evaluator.num(&args[0], name)?;

    if args.len() == 1 {
        return Ok(FormulaValue::Text(compact_number_text(number)));
    }

    let pattern = evaluator.str_value(&args[1], name)?.trim().to_string();
    if pattern.is_empty() || pattern.eq_ignore_ascii_case("GENERAL") {
        return Ok(FormulaValue::Text(compact_number_text(number)));
    }

    if let Some(formatted) = format_number_pattern(number, &pattern) {
        return Ok(FormulaValue::Text(formatted));
    }

    Ok(FormulaValue::Text(compact_number_text(number)))
}

fn fn_value(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    if matches!(&args[0], FormulaValue::Number(_) | FormulaValue::Bool(_)) {
        return Ok(FormulaValue::Number(evaluator.num(&args[0], name)?));
    }

    let text = evaluator.str_value(&args[0], name)?.trim().to_string();
    if text.is_empty() {
        return Err(FormulaError::new(format!(
            "{} requires a non-empty text value",
            name
        )));
    }

    let mut normalized = text.replace(',', "").replace('$', "");
    let is_percent = normalized.ends_with('%');
    if is_percent {
        normalized = normalized[0..normalized.len() - 1].to_string();
    }

    let parsed = normalized.parse::<f64>().map_err(|_| {
        FormulaError::new(format!("{} cannot parse numeric text: {:?}", name, text))
    })?;
    if is_percent {
        Ok(FormulaValue::Number(parsed / 100.0))
    } else {
        Ok(FormulaValue::Number(parsed))
    }
}

fn fn_textlist(
    _evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    if let FormulaValue::List(values) = &args[0] {
        let rendered = values
            .iter()
            .map(coerce_text_output)
            .collect::<Vec<String>>()
            .join(", ");
        return Ok(FormulaValue::Text(rendered));
    }
    Ok(FormulaValue::Text(coerce_text_output(&args[0])))
}

fn fn_maketext(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 128)?;
    let mut result = evaluator.str_value(&args[0], name)?;
    let rendered_args = args[1..]
        .iter()
        .map(coerce_text_output)
        .collect::<Vec<String>>();

    for (idx, rendered) in rendered_args.iter().enumerate() {
        result = result.replace(&format!("{{{}}}", idx), rendered);
    }
    for rendered in &rendered_args {
        if !result.contains("{}") {
            break;
        }
        result = result.replacen("{}", rendered, 1);
    }

    Ok(FormulaValue::Text(result))
}

fn push_unique(target: &mut Vec<String>, value: String) {
    if !target.iter().any(|existing| existing == &value) {
        target.push(value);
    }
}

fn append_token_candidates(evaluator: &Evaluator, value: &FormulaValue, out: &mut Vec<String>) {
    if matches!(value, FormulaValue::Null) {
        return;
    }

    push_unique(out, evaluator.coerce_string(value));

    if let FormulaValue::Number(number) = value {
        if number.is_finite() && number.fract() == 0.0 {
            push_unique(out, format!("{}", *number as i64));
        }
    }

    if let FormulaValue::Bool(boolean) = value {
        if *boolean {
            push_unique(out, "true".to_string());
            push_unique(out, "TRUE".to_string());
        } else {
            push_unique(out, "false".to_string());
            push_unique(out, "FALSE".to_string());
        }
    }
}

fn member_key_candidates(evaluator: &Evaluator, value: &FormulaValue) -> Vec<String> {
    let mut out = Vec::new();
    match value {
        FormulaValue::Map(mapping) => {
            for key in ["id", "code", "name", "key", "item", "member"] {
                if let Some(raw) = mapping.get(key) {
                    append_token_candidates(evaluator, raw, &mut out);
                }
            }
        }
        _ => append_token_candidates(evaluator, value, &mut out),
    }
    if out.is_empty() {
        out.push(evaluator.coerce_string(value));
    }
    out
}

fn mapping_lookup_by_candidates(
    mapping: &HashMap<String, FormulaValue>,
    candidates: &[String],
) -> Option<FormulaValue> {
    for candidate in candidates {
        if let Some(value) = mapping.get(candidate) {
            return Some(value.clone());
        }
    }
    None
}

fn source_key_tokens(source_key: &str) -> Vec<String> {
    if source_key.contains('|') {
        source_key
            .split('|')
            .filter(|token| !token.is_empty())
            .map(|token| token.to_string())
            .collect()
    } else {
        vec![source_key.to_string()]
    }
}

fn contains_all_tokens(tokens: &[String], required: &[String]) -> bool {
    required.iter().all(|token| tokens.iter().any(|candidate| candidate == token))
}

fn list_members(value: &FormulaValue, context_label: &str) -> Result<Vec<FormulaValue>, FormulaError> {
    match value {
        FormulaValue::List(items) => Ok(items.clone()),
        FormulaValue::Map(mapping) => {
            for key in ["members", "items", "list"] {
                if let Some(FormulaValue::List(items)) = mapping.get(key) {
                    return Ok(items.clone());
                }
            }
            Ok(mapping.values().cloned().collect::<Vec<FormulaValue>>())
        }
        _ => Err(FormulaError::new(format!(
            "{} requires a list-like argument",
            context_label
        ))),
    }
}

fn match_member(evaluator: &Evaluator, left: &FormulaValue, right: &FormulaValue) -> bool {
    let left_candidates = member_key_candidates(evaluator, left);
    let right_candidates = member_key_candidates(evaluator, right);
    left_candidates
        .iter()
        .any(|left_value| right_candidates.iter().any(|right_value| right_value == left_value))
        || left == right
}

fn find_member_record(
    evaluator: &Evaluator,
    item: &FormulaValue,
) -> Option<HashMap<String, FormulaValue>> {
    if let FormulaValue::Map(mapping) = item {
        return Some(mapping.clone());
    }

    let candidates = member_key_candidates(evaluator, item);
    for key in [
        "MEMBERS_BY_ID",
        "members_by_id",
        "MEMBER_MAP",
        "member_map",
        "MEMBERS_BY_CODE",
        "members_by_code",
        "MEMBERS_BY_NAME",
        "members_by_name",
    ] {
        if let Some(FormulaValue::Map(mapping)) = evaluator.context_value(key) {
            if let Some(FormulaValue::Map(member)) = mapping_lookup_by_candidates(mapping, &candidates) {
                return Some(member);
            }
        }
    }

    for key in ["DIMENSION_MEMBERS", "dimension_members", "_dimension_members"] {
        if let Some(FormulaValue::List(members)) = evaluator.context_value(key) {
            for member in members {
                if let FormulaValue::Map(record) = member {
                    if match_member(evaluator, &FormulaValue::Map(record.clone()), item) {
                        return Some(record.clone());
                    }
                }
            }
        }
    }

    None
}

fn resolve_parent_value(evaluator: &Evaluator, item: &FormulaValue) -> Option<FormulaValue> {
    if let FormulaValue::Map(mapping) = item {
        if let Some(parent) = mapping.get("parent") {
            return Some(parent.clone());
        }
        if let Some(parent) = mapping.get("parent_id") {
            return Some(parent.clone());
        }
    }

    if let Some(record) = find_member_record(evaluator, item) {
        if let Some(parent) = record.get("parent") {
            return Some(parent.clone());
        }
        if let Some(parent) = record.get("parent_id") {
            return Some(parent.clone());
        }
    }

    let candidates = member_key_candidates(evaluator, item);
    for key in ["PARENT_MAP", "parent_map", "_parent_map", "PARENTS", "parents"] {
        if let Some(FormulaValue::Map(mapping)) = evaluator.context_value(key) {
            if let Some(parent) = mapping_lookup_by_candidates(mapping, &candidates) {
                return Some(parent);
            }
        }
    }

    None
}

fn resolve_children_values(evaluator: &Evaluator, item: &FormulaValue) -> Vec<FormulaValue> {
    if let FormulaValue::Map(mapping) = item {
        if let Some(raw) = mapping.get("children") {
            return match raw {
                FormulaValue::List(items) => items.clone(),
                FormulaValue::Null => Vec::new(),
                other => vec![other.clone()],
            };
        }
    }

    if let Some(record) = find_member_record(evaluator, item) {
        if let Some(raw) = record.get("children") {
            return match raw {
                FormulaValue::List(items) => items.clone(),
                FormulaValue::Null => Vec::new(),
                other => vec![other.clone()],
            };
        }
    }

    let candidates = member_key_candidates(evaluator, item);
    for key in ["CHILDREN_MAP", "children_map", "_children_map", "CHILDREN", "children"] {
        if let Some(FormulaValue::Map(mapping)) = evaluator.context_value(key) {
            if let Some(value) = mapping_lookup_by_candidates(mapping, &candidates) {
                return match value {
                    FormulaValue::List(items) => items,
                    FormulaValue::Null => Vec::new(),
                    other => vec![other],
                };
            }
        }
    }

    if let Some(FormulaValue::List(members)) =
        context_first(evaluator, &["DIMENSION_MEMBERS", "dimension_members", "_dimension_members"])
    {
        let mut derived = Vec::new();
        for member in members {
            if let FormulaValue::Map(record) = member {
                let parent = record
                    .get("parent")
                    .or_else(|| record.get("parent_id"))
                    .cloned()
                    .unwrap_or(FormulaValue::Null);
                if match_member(evaluator, &parent, item) {
                    derived.push(FormulaValue::Map(record.clone()));
                }
            }
        }
        if !derived.is_empty() {
            return derived;
        }
    }

    Vec::new()
}

fn list_name_candidates(evaluator: &Evaluator, list_value: &FormulaValue) -> Vec<String> {
    let mut names = Vec::new();
    match list_value {
        FormulaValue::Text(name) => push_unique(&mut names, name.clone()),
        FormulaValue::Map(mapping) => {
            for key in ["name", "id", "code", "list", "dimension"] {
                if let Some(raw) = mapping.get(key) {
                    append_token_candidates(evaluator, raw, &mut names);
                }
            }
        }
        FormulaValue::List(_) => {}
        _ => push_unique(&mut names, evaluator.coerce_string(list_value)),
    }
    names
}

fn sanitize_context_name(name: &str) -> String {
    name.chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() {
                ch.to_ascii_uppercase()
            } else {
                '_'
            }
        })
        .collect::<String>()
        .trim_matches('_')
        .to_string()
}

fn lookup_current_item_by_name(evaluator: &Evaluator, list_name: &str) -> Option<FormulaValue> {
    let mut candidates = Vec::new();
    push_unique(&mut candidates, list_name.to_string());
    push_unique(&mut candidates, list_name.to_ascii_uppercase());
    push_unique(&mut candidates, list_name.to_ascii_lowercase());
    let sanitized = sanitize_context_name(list_name);
    if !sanitized.is_empty() {
        push_unique(&mut candidates, sanitized.clone());
    }

    for key in ["CURRENT_ITEMS", "current_items", "_current_items", "ITEMS", "items"] {
        if let Some(FormulaValue::Map(mapping)) = evaluator.context_value(key) {
            if let Some(value) = mapping_lookup_by_candidates(mapping, &candidates) {
                return Some(value);
            }
        }
    }

    if !sanitized.is_empty() {
        if let Some(value) = evaluator.context_value(&format!("CURRENT_ITEM_{}", sanitized)) {
            return Some(value.clone());
        }
        if let Some(value) = evaluator.context_value(&format!("ITEM_{}", sanitized)) {
            return Some(value.clone());
        }
    }
    if let Some(value) = evaluator.context_value(&format!("CURRENT_ITEM.{}", list_name)) {
        return Some(value.clone());
    }
    if let Some(value) = evaluator.context_value(&format!("CURRENT_ITEM:{}", list_name)) {
        return Some(value.clone());
    }
    None
}

fn lookup_values_from_source_map(
    evaluator: &Evaluator,
    source: &HashMap<String, FormulaValue>,
    mapping: &FormulaValue,
) -> Vec<FormulaValue> {
    let mut single_lookup = |value: &FormulaValue| {
        let candidates = member_key_candidates(evaluator, value);
        mapping_lookup_by_candidates(source, &candidates)
    };

    let FormulaValue::Map(mapping_map) = mapping else {
        return single_lookup(mapping).map_or_else(Vec::new, |value| vec![value]);
    };

    for selector in ["key", "item", "member", "id", "name", "code", "select", "target"] {
        if let Some(selector_value) = mapping_map.get(selector) {
            if let Some(value) = single_lookup(selector_value) {
                return vec![value];
            }
        }
    }

    if let Some(FormulaValue::List(keys)) = mapping_map.get("keys") {
        let mut selected = Vec::new();
        for key in keys {
            if let Some(value) = single_lookup(key) {
                selected.push(value);
            }
        }
        if !selected.is_empty() {
            return selected;
        }
    }

    if mapping_map.len() == 1 {
        if let Some((_, value)) = mapping_map.iter().next() {
            if let Some(found) = single_lookup(value) {
                return vec![found];
            }
        }
    }

    let mut required = Vec::new();
    for (key, value) in mapping_map {
        if matches!(
            key.as_str(),
            "key"
                | "item"
                | "member"
                | "id"
                | "name"
                | "code"
                | "select"
                | "target"
                | "keys"
                | "index"
                | "indexes"
                | "default"
                | "weights"
        ) {
            continue;
        }
        let candidates = member_key_candidates(evaluator, value);
        if let Some(token) = candidates.first() {
            push_unique(&mut required, token.clone());
        }
    }
    if required.is_empty() {
        for value in mapping_map.values() {
            let candidates = member_key_candidates(evaluator, value);
            if let Some(token) = candidates.first() {
                push_unique(&mut required, token.clone());
            }
        }
    }
    if required.is_empty() {
        return Vec::new();
    }

    let mut matched = source
        .iter()
        .filter_map(|(key, value)| {
            let tokens = source_key_tokens(key);
            if contains_all_tokens(&tokens, &required) {
                Some((key.clone(), value.clone()))
            } else {
                None
            }
        })
        .collect::<Vec<(String, FormulaValue)>>();
    matched.sort_by(|left, right| left.0.cmp(&right.0));
    matched.into_iter().map(|(_, value)| value).collect()
}

fn lookup_values_from_source_list(
    evaluator: &Evaluator,
    source: &[FormulaValue],
    mapping: &FormulaValue,
    context_label: &str,
) -> Result<Vec<FormulaValue>, FormulaError> {
    let at_index = |index: i64| -> Vec<FormulaValue> {
        if index < 0 || index >= source.len() as i64 {
            return Vec::new();
        }
        vec![source[index as usize].clone()]
    };

    if let FormulaValue::Map(mapping_map) = mapping {
        if let Some(value) = mapping_map.get("index") {
            let index = evaluator.num(value, context_label)?.trunc() as i64;
            return Ok(at_index(index));
        }

        if let Some(FormulaValue::List(indexes)) = mapping_map.get("indexes") {
            let mut selected = Vec::new();
            for raw_index in indexes {
                let index = evaluator.num(raw_index, context_label)?.trunc() as i64;
                if index >= 0 && index < source.len() as i64 {
                    selected.push(source[index as usize].clone());
                }
            }
            return Ok(selected);
        }

        for selector in ["item", "member", "id", "name", "code", "select", "target"] {
            if let Some(target) = mapping_map.get(selector) {
                return Ok(source
                    .iter()
                    .filter(|item| match_member(evaluator, item, target))
                    .cloned()
                    .collect::<Vec<FormulaValue>>());
            }
        }

        return Ok(Vec::new());
    }

    if let FormulaValue::Number(index) = mapping {
        return Ok(at_index(index.trunc() as i64));
    }

    Ok(source
        .iter()
        .filter(|item| match_member(evaluator, item, mapping))
        .cloned()
        .collect::<Vec<FormulaValue>>())
}

fn rank_series_target(
    evaluator: &Evaluator,
    expr: &FormulaValue,
    dimension: &FormulaValue,
    context_label: &str,
) -> Result<(Vec<f64>, f64), FormulaError> {
    if let FormulaValue::List(values) = expr {
        if values.is_empty() {
            return Err(FormulaError::new(format!(
                "{} requires a non-empty expression list",
                context_label
            )));
        }
        let series = values
            .iter()
            .map(|value| evaluator.num(value, context_label))
            .collect::<Result<Vec<f64>, FormulaError>>()?;
        let index = resolve_current_index(evaluator, series.len(), context_label)?;
        return Ok((series.clone(), series[index]));
    }

    if let FormulaValue::Map(values) = expr {
        if values.is_empty() {
            return Err(FormulaError::new(format!(
                "{} requires a non-empty expression map",
                context_label
            )));
        }
        let series = values
            .values()
            .map(|value| evaluator.num(value, context_label))
            .collect::<Result<Vec<f64>, FormulaError>>()?;
        let candidates = member_key_candidates(evaluator, dimension);
        for candidate in candidates {
            if let Some(value) = values.get(&candidate) {
                return Ok((series, evaluator.num(value, context_label)?));
            }
        }
        return Ok((series.clone(), *series.last().unwrap_or(&0.0)));
    }

    let target = evaluator.num(expr, context_label)?;
    let series = match dimension {
        FormulaValue::List(values) => values
            .iter()
            .map(|value| evaluator.num(value, context_label))
            .collect::<Result<Vec<f64>, FormulaError>>()?,
        FormulaValue::Map(values) => values
            .values()
            .map(|value| evaluator.num(value, context_label))
            .collect::<Result<Vec<f64>, FormulaError>>()?,
        _ => vec![target],
    };
    if series.is_empty() {
        return Err(FormulaError::new(format!(
            "{} requires a non-empty dimension",
            context_label
        )));
    }
    Ok((series, target))
}

fn fn_finditem(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;

    if let FormulaValue::Map(mapping) = &args[0] {
        let candidates = member_key_candidates(evaluator, &args[1]);
        if let Some(found) = mapping_lookup_by_candidates(mapping, &candidates) {
            return Ok(found);
        }
    }

    let members = list_members(&args[0], name)?;
    for member in members {
        if match_member(evaluator, &member, &args[1]) {
            return Ok(member);
        }
    }
    Ok(FormulaValue::Null)
}

fn fn_item(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    let list_value = &args[0];
    let list_names = list_name_candidates(evaluator, list_value);

    for list_name in &list_names {
        if let Some(current) = lookup_current_item_by_name(evaluator, list_name) {
            return Ok(current);
        }
    }

    if list_names.is_empty() && matches!(list_value, FormulaValue::List(_)) {
        for key in ["CURRENT_ITEMS", "current_items", "_current_items"] {
            if let Some(FormulaValue::Map(mapping)) = evaluator.context_value(key) {
                if mapping.len() == 1 {
                    if let Some(value) = mapping.values().next() {
                        return Ok(value.clone());
                    }
                }
            }
        }
    }

    if let Some(generic) = context_first(evaluator, &["CURRENT_ITEM", "current_item", "_current_item"]) {
        if let FormulaValue::Map(mapping) = generic {
            if !list_names.is_empty() {
                if let Some(found) = mapping_lookup_by_candidates(mapping, &list_names) {
                    return Ok(found);
                }
            }
        }
        return Ok(generic.clone());
    }

    if !matches!(list_value, FormulaValue::List(_) | FormulaValue::Map(_)) {
        return Ok(list_value.clone());
    }

    Err(FormulaError::new("ITEM requires current item context"))
}

fn fn_parent(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    Ok(resolve_parent_value(evaluator, &args[0]).unwrap_or(FormulaValue::Null))
}

fn fn_children(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    Ok(FormulaValue::List(resolve_children_values(evaluator, &args[0])))
}

fn fn_isleaf(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    Ok(FormulaValue::Bool(
        resolve_children_values(evaluator, &args[0]).is_empty(),
    ))
}

fn fn_isancestor(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    if match_member(evaluator, &args[0], &args[1]) {
        return Ok(FormulaValue::Bool(false));
    }

    let mut seen = Vec::new();
    let mut current = args[1].clone();
    for _ in 0..256 {
        let Some(parent) = resolve_parent_value(evaluator, &current) else {
            return Ok(FormulaValue::Bool(false));
        };
        if match_member(evaluator, &parent, &args[0]) {
            return Ok(FormulaValue::Bool(true));
        }
        if let Some(token) = member_key_candidates(evaluator, &parent).first() {
            if seen.iter().any(|existing| existing == token) {
                return Ok(FormulaValue::Bool(false));
            }
            seen.push(token.clone());
        }
        current = parent;
    }
    Ok(FormulaValue::Bool(false))
}

fn fn_lookup(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 2)?;
    if args.len() == 1 {
        return Ok(args[0].clone());
    }

    let source_or_key = &args[0];
    let mapping = &args[1];

    if let FormulaValue::Map(source) = source_or_key {
        let selected = lookup_values_from_source_map(evaluator, source, mapping);
        return Ok(selected.into_iter().next().unwrap_or(FormulaValue::Null));
    }

    if let FormulaValue::List(source) = source_or_key {
        let selected = lookup_values_from_source_list(evaluator, source, mapping, name)?;
        return Ok(selected.into_iter().next().unwrap_or(FormulaValue::Null));
    }

    if let FormulaValue::Map(mapping_map) = mapping {
        let candidates = member_key_candidates(evaluator, source_or_key);
        if let Some(found) = mapping_lookup_by_candidates(mapping_map, &candidates) {
            return Ok(found);
        }
        return Err(FormulaError::new(format!(
            "{}: key {:?} not found",
            name,
            evaluator.coerce_string(source_or_key)
        )));
    }

    Ok(source_or_key.clone())
}

fn fn_select(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    if let FormulaValue::Map(source) = &args[0] {
        let selected = lookup_values_from_source_map(evaluator, source, &args[1]);
        return Ok(selected.into_iter().next().unwrap_or(FormulaValue::Null));
    }
    if let FormulaValue::List(source) = &args[0] {
        let selected = lookup_values_from_source_list(evaluator, source, &args[1], name)?;
        return Ok(selected.into_iter().next().unwrap_or(FormulaValue::Null));
    }
    fn_lookup(evaluator, name, args)
}

fn fn_sum_mapped(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let values = match (&args[0], &args[1]) {
        (FormulaValue::Map(source), FormulaValue::Map(_)) => {
            lookup_values_from_source_map(evaluator, source, &args[1])
        }
        (FormulaValue::List(source), FormulaValue::Map(_)) => {
            let selected = lookup_values_from_source_list(evaluator, source, &args[1], name)?;
            if selected.is_empty() {
                source.clone()
            } else {
                selected
            }
        }
        _ => evaluator
            .flatten_numbers(args, name)?
            .into_iter()
            .map(FormulaValue::Number)
            .collect::<Vec<FormulaValue>>(),
    };

    let total = values
        .iter()
        .map(|value| evaluator.num(value, name))
        .collect::<Result<Vec<f64>, FormulaError>>()?
        .iter()
        .sum::<f64>();
    Ok(FormulaValue::Number(total))
}

fn range_values(value: &FormulaValue) -> Vec<FormulaValue> {
    match value {
        FormulaValue::List(values) => values.clone(),
        FormulaValue::Map(values) => {
            let mut keys = values.keys().cloned().collect::<Vec<String>>();
            keys.sort();
            keys.into_iter()
                .filter_map(|key| values.get(&key).cloned())
                .collect::<Vec<FormulaValue>>()
        }
        other => vec![other.clone()],
    }
}

fn range_numbers(
    evaluator: &Evaluator,
    value: &FormulaValue,
    context_label: &str,
) -> Result<Vec<f64>, FormulaError> {
    let values = range_values(value);
    values
        .iter()
        .map(|item| evaluator.num(item, context_label))
        .collect::<Result<Vec<f64>, FormulaError>>()
}

fn maybe_num(value: &FormulaValue) -> Option<f64> {
    match value {
        FormulaValue::Number(v) => Some(*v),
        FormulaValue::Bool(v) => Some(if *v { 1.0 } else { 0.0 }),
        FormulaValue::Text(text) => {
            let trimmed = text.trim();
            if trimmed.is_empty() {
                return None;
            }
            trimmed.parse::<f64>().ok()
        }
        _ => None,
    }
}

fn coerce_criteria_operand(text: &str) -> FormulaValue {
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return FormulaValue::Text(String::new());
    }

    if trimmed.len() >= 2
        && ((trimmed.starts_with('"') && trimmed.ends_with('"'))
            || (trimmed.starts_with('\'') && trimmed.ends_with('\'')))
    {
        return FormulaValue::Text(trimmed[1..trimmed.len() - 1].to_string());
    }

    let upper = trimmed.to_ascii_uppercase();
    if upper == "TRUE" {
        return FormulaValue::Bool(true);
    }
    if upper == "FALSE" {
        return FormulaValue::Bool(false);
    }

    if let Ok(parsed) = trimmed.parse::<f64>() {
        return FormulaValue::Number(parsed);
    }

    FormulaValue::Text(trimmed.to_string())
}

fn criteria_matches(
    value: &FormulaValue,
    criteria: &FormulaValue,
    context_label: &str,
) -> Result<bool, FormulaError> {
    let mut operator = "=";
    let mut operand = criteria.clone();

    if let FormulaValue::Text(criteria_text) = criteria {
        let trimmed = criteria_text.trim();
        let mut matched_prefix = false;
        for prefix in [">=", "<=", "<>", ">", "<", "="] {
            if trimmed.starts_with(prefix) {
                operator = prefix;
                operand = coerce_criteria_operand(&trimmed[prefix.len()..]);
                matched_prefix = true;
                break;
            }
        }
        if !matched_prefix {
            operand = coerce_criteria_operand(trimmed);
        }
    }

    let left_num = maybe_num(value);
    let right_num = maybe_num(&operand);

    if operator == "=" {
        if let (Some(left), Some(right)) = (left_num, right_num) {
            return Ok(left == right);
        }
        return Ok(coerce_text_output(value) == coerce_text_output(&operand));
    }

    if operator == "<>" {
        if let (Some(left), Some(right)) = (left_num, right_num) {
            return Ok(left != right);
        }
        return Ok(coerce_text_output(value) != coerce_text_output(&operand));
    }

    if let (Some(left), Some(right)) = (left_num, right_num) {
        return Ok(match operator {
            ">" => left > right,
            "<" => left < right,
            ">=" => left >= right,
            "<=" => left <= right,
            _ => {
                return Err(FormulaError::new(format!(
                    "{} received unsupported criteria {:?}",
                    context_label,
                    coerce_text_output(criteria)
                )))
            }
        });
    }

    let left_text = coerce_text_output(value);
    let right_text = coerce_text_output(&operand);
    Ok(match operator {
        ">" => left_text > right_text,
        "<" => left_text < right_text,
        ">=" => left_text >= right_text,
        "<=" => left_text <= right_text,
        _ => {
            return Err(FormulaError::new(format!(
                "{} received unsupported criteria {:?}",
                context_label,
                coerce_text_output(criteria)
            )))
        }
    })
}

fn sample_variance(values: &[f64], context_label: &str) -> Result<f64, FormulaError> {
    if values.len() < 2 {
        return Err(FormulaError::new(format!(
            "{} requires at least 2 values",
            context_label
        )));
    }

    let mean = values.iter().sum::<f64>() / values.len() as f64;
    let sum_sq = values
        .iter()
        .map(|value| (value - mean) * (value - mean))
        .sum::<f64>();
    Ok(sum_sq / (values.len() as f64 - 1.0))
}

fn percentile(values: &[f64], mut k: f64, context_label: &str) -> Result<f64, FormulaError> {
    if values.is_empty() {
        return Err(FormulaError::new(format!(
            "{} called with empty range",
            context_label
        )));
    }

    if k > 1.0 && k <= 100.0 {
        k /= 100.0;
    }
    if k < 0.0 || k > 1.0 {
        return Err(FormulaError::new(format!(
            "{} requires k between 0 and 1 inclusive",
            context_label
        )));
    }

    let mut ordered = values.to_vec();
    ordered.sort_by(|left, right| {
        left.partial_cmp(right)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    if ordered.len() == 1 {
        return Ok(ordered[0]);
    }

    let rank = k * (ordered.len() as f64 - 1.0);
    let lower = rank.floor() as usize;
    let upper = rank.ceil() as usize;
    if lower == upper {
        return Ok(ordered[lower]);
    }

    let weight = rank - lower as f64;
    Ok(ordered[lower] + (ordered[upper] - ordered[lower]) * weight)
}

fn growth_known_pairs(
    evaluator: &Evaluator,
    known_y: &FormulaValue,
    known_x: &FormulaValue,
    context_label: &str,
) -> Result<(Vec<f64>, Vec<f64>), FormulaError> {
    if let (FormulaValue::Map(y_map), FormulaValue::Map(x_map)) = (known_y, known_x) {
        let mut keys = y_map
            .keys()
            .filter(|key| x_map.contains_key(*key))
            .cloned()
            .collect::<Vec<String>>();
        keys.sort();
        if keys.is_empty() {
            return Err(FormulaError::new(
                "GROWTH requires known_y and known_x maps to share at least one key",
            ));
        }

        let mut y_values = Vec::with_capacity(keys.len());
        let mut x_values = Vec::with_capacity(keys.len());
        for key in keys {
            if let (Some(y), Some(x)) = (y_map.get(&key), x_map.get(&key)) {
                y_values.push(evaluator.num(y, context_label)?);
                x_values.push(evaluator.num(x, context_label)?);
            }
        }
        return Ok((y_values, x_values));
    }

    let y_items = range_values(known_y);
    let x_items = range_values(known_x);
    if y_items.len() != x_items.len() {
        return Err(FormulaError::new(
            "GROWTH requires known_y and known_x with matching lengths",
        ));
    }
    if y_items.is_empty() {
        return Err(FormulaError::new("GROWTH requires at least one known data point"));
    }

    let y_values = y_items
        .iter()
        .map(|value| evaluator.num(value, context_label))
        .collect::<Result<Vec<f64>, FormulaError>>()?;
    let x_values = x_items
        .iter()
        .map(|value| evaluator.num(value, context_label))
        .collect::<Result<Vec<f64>, FormulaError>>()?;
    Ok((y_values, x_values))
}

fn fn_sumif(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let values = range_values(&args[0]);
    let mut total = 0.0;
    for value in values {
        if criteria_matches(&value, &args[1], name)? {
            total += evaluator.num(&value, name)?;
        }
    }
    Ok(FormulaValue::Number(total))
}

fn fn_countif(
    _evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let values = range_values(&args[0]);
    let mut count = 0usize;
    for value in values {
        if criteria_matches(&value, &args[1], name)? {
            count += 1;
        }
    }
    Ok(FormulaValue::Number(count as f64))
}

fn fn_averageif(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let values = range_values(&args[0]);
    let mut matched = Vec::new();
    for value in values {
        if criteria_matches(&value, &args[1], name)? {
            matched.push(evaluator.num(&value, name)?);
        }
    }
    if matched.is_empty() {
        return Err(FormulaError::new("AVERAGEIF found no matching values"));
    }
    Ok(FormulaValue::Number(
        matched.iter().sum::<f64>() / matched.len() as f64,
    ))
}

fn fn_median(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    let mut values = range_numbers(evaluator, &args[0], name)?;
    if values.is_empty() {
        return Err(FormulaError::new("MEDIAN called with empty range"));
    }
    values.sort_by(|left, right| {
        left.partial_cmp(right)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let mid = values.len() / 2;
    if values.len() % 2 == 1 {
        return Ok(FormulaValue::Number(values[mid]));
    }
    Ok(FormulaValue::Number((values[mid - 1] + values[mid]) / 2.0))
}

fn fn_stdev(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    let values = range_numbers(evaluator, &args[0], name)?;
    let variance = sample_variance(&values, name)?;
    Ok(FormulaValue::Number(variance.sqrt()))
}

fn fn_variance(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    let values = range_numbers(evaluator, &args[0], name)?;
    Ok(FormulaValue::Number(sample_variance(&values, name)?))
}

fn fn_percentile(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let values = range_numbers(evaluator, &args[0], name)?;
    let k = evaluator.num(&args[1], name)?;
    Ok(FormulaValue::Number(percentile(&values, k, name)?))
}

fn fn_large(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let mut values = range_numbers(evaluator, &args[0], name)?;
    let k = evaluator.num(&args[1], name)?.trunc() as i64;
    if k <= 0 {
        return Err(FormulaError::new("LARGE requires k >= 1"));
    }
    values.sort_by(|left, right| {
        right
            .partial_cmp(left)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    if k as usize > values.len() {
        return Err(FormulaError::new("LARGE k is out of bounds for range length"));
    }
    Ok(FormulaValue::Number(values[(k as usize) - 1]))
}

fn fn_small(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let mut values = range_numbers(evaluator, &args[0], name)?;
    let k = evaluator.num(&args[1], name)?.trunc() as i64;
    if k <= 0 {
        return Err(FormulaError::new("SMALL requires k >= 1"));
    }
    values.sort_by(|left, right| {
        left.partial_cmp(right)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    if k as usize > values.len() {
        return Err(FormulaError::new("SMALL k is out of bounds for range length"));
    }
    Ok(FormulaValue::Number(values[(k as usize) - 1]))
}

fn fn_growth(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 3, 3)?;
    let (known_y, known_x) = growth_known_pairs(evaluator, &args[0], &args[1], name)?;
    if known_y.len() < 2 {
        return Err(FormulaError::new(
            "GROWTH requires at least 2 known data points",
        ));
    }

    let mean_x = known_x.iter().sum::<f64>() / known_x.len() as f64;
    let mean_y = known_y.iter().sum::<f64>() / known_y.len() as f64;
    let denominator = known_x
        .iter()
        .map(|value| (value - mean_x) * (value - mean_x))
        .sum::<f64>();
    if denominator == 0.0 {
        return Err(FormulaError::new(
            "GROWTH requires known_x values with non-zero variance",
        ));
    }

    let numerator = known_x
        .iter()
        .zip(known_y.iter())
        .map(|(x, y)| (x - mean_x) * (y - mean_y))
        .sum::<f64>();
    let slope = numerator / denominator;
    let intercept = mean_y - slope * mean_x;

    match &args[2] {
        FormulaValue::Map(values) => {
            let mut result = HashMap::new();
            for (key, value) in values {
                let x = evaluator.num(value, name)?;
                result.insert(key.clone(), FormulaValue::Number(intercept + slope * x));
            }
            Ok(FormulaValue::Map(result))
        }
        FormulaValue::List(values) => {
            let mut result = Vec::with_capacity(values.len());
            for value in values {
                let x = evaluator.num(value, name)?;
                result.push(FormulaValue::Number(intercept + slope * x));
            }
            Ok(FormulaValue::List(result))
        }
        value => {
            let x = evaluator.num(value, name)?;
            Ok(FormulaValue::Number(intercept + slope * x))
        }
    }
}

fn fn_name(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    if let FormulaValue::Map(mapping) = &args[0] {
        if let Some(value) = mapping.get("name") {
            return Ok(FormulaValue::Text(evaluator.coerce_string(value)));
        }
        if let Some(value) = mapping.get("id") {
            return Ok(FormulaValue::Text(evaluator.coerce_string(value)));
        }
    }
    if let Some(record) = find_member_record(evaluator, &args[0]) {
        if let Some(value) = record.get("name") {
            return Ok(FormulaValue::Text(evaluator.coerce_string(value)));
        }
        if let Some(value) = record.get("id") {
            return Ok(FormulaValue::Text(evaluator.coerce_string(value)));
        }
    }
    Ok(FormulaValue::Text(evaluator.coerce_string(&args[0])))
}

fn fn_code(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    if let FormulaValue::Map(mapping) = &args[0] {
        if let Some(value) = mapping.get("code") {
            return Ok(FormulaValue::Text(evaluator.coerce_string(value)));
        }
        if let Some(value) = mapping.get("id") {
            return Ok(FormulaValue::Text(evaluator.coerce_string(value)));
        }
    }
    if let Some(record) = find_member_record(evaluator, &args[0]) {
        if let Some(value) = record.get("code") {
            return Ok(FormulaValue::Text(evaluator.coerce_string(value)));
        }
        if let Some(value) = record.get("id") {
            return Ok(FormulaValue::Text(evaluator.coerce_string(value)));
        }
    }
    Ok(FormulaValue::Text(evaluator.coerce_string(&args[0])))
}

fn fn_rank(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    let (series, target) = rank_series_target(evaluator, &args[0], &args[1], name)?;
    let higher = series.iter().filter(|value| **value > target).count();
    Ok(FormulaValue::Number((higher + 1) as f64))
}

fn fn_ranklist(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 3, 3)?;
    let limit = evaluator.num(&args[2], name)?.trunc() as i64;
    if limit < 0 {
        return Err(FormulaError::new(format!("{} requires n >= 0", name)));
    }
    if limit == 0 {
        return Ok(FormulaValue::List(Vec::new()));
    }
    let limit = limit as usize;

    if let FormulaValue::Map(values) = &args[0] {
        let mut ranked = values
            .iter()
            .map(|(key, value)| {
                Ok((key.clone(), evaluator.num(value, name)?))
            })
            .collect::<Result<Vec<(String, f64)>, FormulaError>>()?;
        ranked.sort_by(|left, right| {
            right
                .1
                .partial_cmp(&left.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| left.0.cmp(&right.0))
        });
        return Ok(FormulaValue::List(
            ranked
                .into_iter()
                .take(limit)
                .map(|(key, _)| FormulaValue::Text(key))
                .collect::<Vec<FormulaValue>>(),
        ));
    }

    if let FormulaValue::List(values) = &args[0] {
        if values.is_empty() {
            return Ok(FormulaValue::List(Vec::new()));
        }
        let scores = values
            .iter()
            .map(|value| evaluator.num(value, name))
            .collect::<Result<Vec<f64>, FormulaError>>()?;

        let labels = match &args[1] {
            FormulaValue::List(dim_values) if dim_values.len() == values.len() => {
                dim_values.clone()
            }
            _ => values.clone(),
        };

        let mut order = (0..scores.len()).collect::<Vec<usize>>();
        order.sort_by(|left, right| {
            scores[*right]
                .partial_cmp(&scores[*left])
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| left.cmp(right))
        });
        return Ok(FormulaValue::List(
            order
                .into_iter()
                .take(limit)
                .map(|index| labels[index].clone())
                .collect::<Vec<FormulaValue>>(),
        ));
    }

    if let FormulaValue::Map(values) = &args[1] {
        let mut ranked = values
            .iter()
            .map(|(key, value)| {
                Ok((key.clone(), evaluator.num(value, name)?))
            })
            .collect::<Result<Vec<(String, f64)>, FormulaError>>()?;
        ranked.sort_by(|left, right| {
            right
                .1
                .partial_cmp(&left.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| left.0.cmp(&right.0))
        });
        return Ok(FormulaValue::List(
            ranked
                .into_iter()
                .take(limit)
                .map(|(key, _)| FormulaValue::Text(key))
                .collect::<Vec<FormulaValue>>(),
        ));
    }

    if let FormulaValue::List(values) = &args[1] {
        let mut ranked = values
            .iter()
            .map(|value| evaluator.num(value, name))
            .collect::<Result<Vec<f64>, FormulaError>>()?;
        ranked.sort_by(|left, right| {
            right
                .partial_cmp(left)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        return Ok(FormulaValue::List(
            ranked
                .into_iter()
                .take(limit)
                .map(FormulaValue::Number)
                .collect::<Vec<FormulaValue>>(),
        ));
    }

    Ok(FormulaValue::List(vec![args[0].clone()]))
}

fn fn_collect(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    match (&args[0], &args[1]) {
        (FormulaValue::Map(values), FormulaValue::List(dimension)) => {
            let mut selected = Vec::new();
            for item in dimension {
                let candidates = member_key_candidates(evaluator, item);
                if let Some(value) = mapping_lookup_by_candidates(values, &candidates) {
                    selected.push(value);
                }
            }
            if !selected.is_empty() {
                return Ok(FormulaValue::List(selected));
            }
            let mut keys = values.keys().cloned().collect::<Vec<String>>();
            keys.sort();
            Ok(FormulaValue::List(
                keys.into_iter()
                    .filter_map(|key| values.get(&key).cloned())
                    .collect::<Vec<FormulaValue>>(),
            ))
        }
        (FormulaValue::Map(values), FormulaValue::Map(_)) => {
            let selected = lookup_values_from_source_map(evaluator, values, &args[1]);
            if !selected.is_empty() {
                return Ok(FormulaValue::List(selected));
            }
            let mut keys = values.keys().cloned().collect::<Vec<String>>();
            keys.sort();
            Ok(FormulaValue::List(
                keys.into_iter()
                    .filter_map(|key| values.get(&key).cloned())
                    .collect::<Vec<FormulaValue>>(),
            ))
        }
        (FormulaValue::Map(values), _) => {
            let mut keys = values.keys().cloned().collect::<Vec<String>>();
            keys.sort();
            Ok(FormulaValue::List(
                keys.into_iter()
                    .filter_map(|key| values.get(&key).cloned())
                    .collect::<Vec<FormulaValue>>(),
            ))
        }
        (FormulaValue::List(values), _) => Ok(FormulaValue::List(values.clone())),
        (value, FormulaValue::List(dimension)) => Ok(FormulaValue::List(
            dimension.iter().map(|_| value.clone()).collect::<Vec<FormulaValue>>(),
        )),
        (value, FormulaValue::Map(mapping)) => {
            if let Some(count) = mapping.get("count") {
                let repeat = evaluator.num(count, name)?.trunc() as i64;
                if repeat < 0 {
                    return Err(FormulaError::new(format!("{} requires count >= 0", name)));
                }
                return Ok(FormulaValue::List(
                    (0..repeat).map(|_| value.clone()).collect::<Vec<FormulaValue>>(),
                ));
            }
            Ok(FormulaValue::List(vec![value.clone()]))
        }
        (value, _) => Ok(FormulaValue::List(vec![value.clone()])),
    }
}

fn fn_post(
    _evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 2, 2)?;
    Ok(args[1].clone())
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

fn fn_year_to_date(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 0, 1)?;
    let period = if args.len() == 1 {
        &args[0]
    } else if let Some(current) = resolve_current_period(evaluator) {
        current
    } else {
        let today = current_system_date();
        return Ok(FormulaValue::Text(format!("YTD {:04}", today.year())));
    };

    let (start, _) = period_bounds(period, name)?;
    Ok(FormulaValue::Text(format!("YTD {:04}", start.year())))
}

fn fn_month_to_date(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 0, 1)?;
    let period = if args.len() == 1 {
        &args[0]
    } else if let Some(current) = resolve_current_period(evaluator) {
        current
    } else {
        let today = current_system_date();
        return Ok(FormulaValue::Text(format!(
            "MTD {:04}-{:02}",
            today.year(),
            today.month()
        )));
    };

    let (start, _) = period_bounds(period, name)?;
    Ok(FormulaValue::Text(format!(
        "MTD {:04}-{:02}",
        start.year(),
        start.month()
    )))
}

fn fn_date(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 3, 3)?;
    let year = evaluator.num(&args[0], name)?.trunc() as i32;
    let month = evaluator.num(&args[1], name)?.trunc() as u32;
    let day = evaluator.num(&args[2], name)?.trunc() as u32;

    let date_value = NaiveDate::from_ymd_opt(year, month, day).ok_or_else(|| {
        FormulaError::new("DATE produced an invalid date")
    })?;
    Ok(FormulaValue::Text(date_value.to_string()))
}

fn fn_date_value(
    evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 1, 1)?;
    let parsed = coerce_date(&args[0], name)?;
    Ok(FormulaValue::Text(parsed.to_string()))
}

fn fn_today(
    _evaluator: &Evaluator,
    name: &str,
    args: &[FormulaValue],
) -> Result<FormulaValue, FormulaError> {
    check_arity_range(name, args, 0, 0)?;
    Ok(FormulaValue::Text(current_system_date().to_string()))
}

fn current_system_date() -> NaiveDate {
    let duration = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    let seconds = duration.as_secs() as i64;
    NaiveDateTime::from_timestamp_opt(seconds, 0)
        .map(|dt| dt.date())
        .unwrap_or_else(|| NaiveDate::from_ymd_opt(1970, 1, 1).unwrap())
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
