use std::collections::{HashMap, HashSet};

use super::*;

fn ctx(entries: Vec<(&str, FormulaValue)>) -> HashMap<String, FormulaValue> {
    entries
        .into_iter()
        .map(|(k, v)| (k.to_string(), v))
        .collect()
}

fn map(entries: Vec<(&str, FormulaValue)>) -> HashMap<String, FormulaValue> {
    entries
        .into_iter()
        .map(|(k, v)| (k.to_string(), v))
        .collect()
}

fn ev(expr: &str, entries: Vec<(&str, FormulaValue)>) -> FormulaValue {
    evaluate_formula(expr, ctx(entries)).expect("formula should evaluate")
}

fn as_number(value: FormulaValue) -> f64 {
    match value {
        FormulaValue::Number(v) => v,
        other => panic!("expected number, got {:?}", other),
    }
}

fn as_bool(value: FormulaValue) -> bool {
    match value {
        FormulaValue::Bool(v) => v,
        other => panic!("expected bool, got {:?}", other),
    }
}

fn as_text(value: FormulaValue) -> String {
    match value {
        FormulaValue::Text(v) => v,
        other => panic!("expected text, got {:?}", other),
    }
}

fn refs(values: &[&str]) -> HashSet<String> {
    values.iter().map(|v| v.to_string()).collect()
}

#[test]
fn tokenize_number_integer() {
    let tokens = tokenize("42").unwrap();
    assert_eq!(tokens.len(), 1);
    assert_eq!(tokens[0].token_type, TokenType::Number);
    assert_eq!(tokens[0].value, "42");
}

#[test]
fn tokenize_number_float() {
    let tokens = tokenize("3.14").unwrap();
    assert_eq!(tokens[0].token_type, TokenType::Number);
    assert_eq!(tokens[0].value, "3.14");
}

#[test]
fn tokenize_number_scientific_notation() {
    let tokens = tokenize("1.5e-2").unwrap();
    assert_eq!(tokens[0].token_type, TokenType::Number);
    assert_eq!(tokens[0].value, "1.5e-2");
}

#[test]
fn tokenize_string_double_quotes() {
    let tokens = tokenize("\"hello\"").unwrap();
    assert_eq!(tokens[0].token_type, TokenType::String);
}

#[test]
fn tokenize_boolean_true() {
    let tokens = tokenize("TRUE").unwrap();
    assert_eq!(tokens[0].token_type, TokenType::Boolean);
    assert_eq!(tokens[0].value, "TRUE");
}

#[test]
fn tokenize_boolean_false_lowercase() {
    let tokens = tokenize("false").unwrap();
    assert_eq!(tokens[0].token_type, TokenType::Boolean);
    assert_eq!(tokens[0].value, "FALSE");
}

#[test]
fn tokenize_logical_and() {
    let tokens = tokenize("AND").unwrap();
    assert_eq!(tokens[0].token_type, TokenType::Logical);
}

#[test]
fn tokenize_comparison_neq() {
    let tokens = tokenize("<>").unwrap();
    assert_eq!(tokens[0].token_type, TokenType::Comparison);
    assert_eq!(tokens[0].value, "<>");
}

#[test]
fn tokenize_dotted_identifier() {
    let tokens = tokenize("Product.Price").unwrap();
    assert_eq!(tokens[0].token_type, TokenType::Identifier);
    assert_eq!(tokens[0].value, "Product.Price");
}

#[test]
fn tokenize_arithmetic_expression() {
    let tokens = tokenize("Revenue * 0.15").unwrap();
    let kinds = tokens.iter().map(|t| t.token_type).collect::<Vec<TokenType>>();
    assert_eq!(
        kinds,
        vec![TokenType::Identifier, TokenType::Operator, TokenType::Number]
    );
}

#[test]
fn tokenize_unknown_character_raises() {
    assert!(tokenize("@Revenue").is_err());
}

#[test]
fn tokenize_whitespace_ignored() {
    let tokens = tokenize("  1  +  2  ").unwrap();
    assert_eq!(tokens.len(), 3);
}

#[test]
fn parse_number_literal() {
    let node = parse_formula("42").unwrap();
    assert_eq!(node, ASTNode::Number(42.0));
}

#[test]
fn parse_string_literal() {
    let node = parse_formula("\"hello\"").unwrap();
    assert_eq!(node, ASTNode::String("hello".to_string()));
}

#[test]
fn parse_boolean_literal() {
    let node = parse_formula("TRUE").unwrap();
    assert_eq!(node, ASTNode::Bool(true));
}

#[test]
fn parse_identifier() {
    let node = parse_formula("Revenue").unwrap();
    assert_eq!(node, ASTNode::Ident("Revenue".to_string()));
}

#[test]
fn parse_binary_add() {
    let node = parse_formula("2 + 3").unwrap();
    assert!(matches!(
        node,
        ASTNode::BinaryOp {
            op: BinaryOperator::Add,
            ..
        }
    ));
}

#[test]
fn parse_function_call() {
    let node = parse_formula("SUM(1, 2, 3)").unwrap();
    match node {
        ASTNode::FunctionCall { name, args } => {
            assert_eq!(name, "SUM");
            assert_eq!(args.len(), 3);
        }
        other => panic!("expected function call, got {:?}", other),
    }
}

#[test]
fn parse_unary_minus() {
    let node = parse_formula("-5").unwrap();
    assert!(matches!(
        node,
        ASTNode::UnaryOp {
            op: UnaryOperator::Negate,
            ..
        }
    ));
}

#[test]
fn parse_comparison() {
    let node = parse_formula("Revenue > 1000").unwrap();
    assert!(matches!(
        node,
        ASTNode::BinaryOp {
            op: BinaryOperator::GreaterThan,
            ..
        }
    ));
}

#[test]
fn parse_nested_function() {
    let node = parse_formula("IF(Revenue > 0, Revenue * 0.1, 0)").unwrap();
    match node {
        ASTNode::FunctionCall { name, args } => {
            assert_eq!(name, "IF");
            assert_eq!(args.len(), 3);
        }
        other => panic!("expected function call, got {:?}", other),
    }
}

#[test]
fn parse_mismatched_paren_raises() {
    assert!(parse_formula("(2 + 3").is_err());
}

#[test]
fn parse_extra_token_raises() {
    assert!(parse_formula("2 + 3 )").is_err());
}

#[test]
fn parse_empty_string_raises() {
    assert!(parse_formula("").is_err());
}

#[test]
fn parse_logical_keyword_as_function_name() {
    let node = parse_formula("NOT(TRUE)").unwrap();
    match node {
        ASTNode::FunctionCall { name, args } => {
            assert_eq!(name, "NOT");
            assert_eq!(args.len(), 1);
        }
        _ => panic!("expected function call"),
    }
}

#[test]
fn parse_unexpected_keyword_raises() {
    assert!(parse_formula("AND").is_err());
}

#[test]
fn addition() {
    assert_eq!(as_number(ev("2 + 3", vec![])), 5.0);
}

#[test]
fn subtraction() {
    assert_eq!(as_number(ev("10 - 4", vec![])), 6.0);
}

#[test]
fn multiplication() {
    assert_eq!(as_number(ev("3 * 4", vec![])), 12.0);
}

#[test]
fn division() {
    assert_eq!(as_number(ev("10 / 4", vec![])), 2.5);
}

#[test]
fn power() {
    assert_eq!(as_number(ev("2 ^ 3", vec![])), 8.0);
}

#[test]
fn operator_precedence_mul_over_add() {
    assert_eq!(as_number(ev("2 + 3 * 4", vec![])), 14.0);
}

#[test]
fn parentheses_override_precedence() {
    assert_eq!(as_number(ev("10 * (5 - 2)", vec![])), 30.0);
}

#[test]
fn unary_minus() {
    assert_eq!(as_number(ev("-5 + 10", vec![])), 5.0);
}

#[test]
fn nested_arithmetic() {
    assert_eq!(as_number(ev("(2 + 3) * (4 - 1)", vec![])), 15.0);
}

#[test]
fn division_by_zero_raises() {
    let result = evaluate_formula("10 / 0", HashMap::new());
    assert!(result.is_err());
}

#[test]
fn float_arithmetic() {
    let result = as_number(ev("0.1 + 0.2", vec![]));
    assert!((result - 0.3).abs() < 1e-9);
}

#[test]
fn single_variable() {
    let result = as_number(ev("Revenue * 0.15", vec![("Revenue", FormulaValue::Number(1000.0))]));
    assert_eq!(result, 150.0);
}

#[test]
fn multiple_variables() {
    let result = as_number(ev(
        "Price * Quantity",
        vec![
            ("Price", FormulaValue::Number(25.0)),
            ("Quantity", FormulaValue::Number(4.0)),
        ],
    ));
    assert_eq!(result, 100.0);
}

#[test]
fn undefined_variable_raises() {
    let result = evaluate_formula("Revenue", HashMap::new());
    assert!(result.is_err());
}

#[test]
fn variable_in_condition() {
    let result = as_bool(ev("Active", vec![("Active", FormulaValue::Bool(true))]));
    assert!(result);
}

#[test]
fn dotted_variable() {
    let result = as_number(ev(
        "Product.Price * 2",
        vec![("Product.Price", FormulaValue::Number(50.0))],
    ));
    assert_eq!(result, 100.0);
}

#[test]
fn greater_than_true() {
    assert!(as_bool(ev("5 > 3", vec![])));
}

#[test]
fn greater_than_false() {
    assert!(!as_bool(ev("3 > 5", vec![])));
}

#[test]
fn less_than() {
    assert!(as_bool(ev("2 < 10", vec![])));
}

#[test]
fn equal() {
    assert!(as_bool(ev("5 = 5", vec![])));
}

#[test]
fn not_equal() {
    let result = as_bool(ev(
        "Revenue <> 0",
        vec![("Revenue", FormulaValue::Number(100.0))],
    ));
    assert!(result);
}

#[test]
fn less_than_or_equal() {
    assert!(as_bool(ev("5 <= 5", vec![])));
}

#[test]
fn greater_than_or_equal() {
    assert!(as_bool(ev("6 >= 5", vec![])));
}

#[test]
fn if_true_branch() {
    assert_eq!(as_number(ev("IF(TRUE, 1, 0)", vec![])), 1.0);
}

#[test]
fn if_false_branch() {
    assert_eq!(as_number(ev("IF(FALSE, 1, 0)", vec![])), 0.0);
}

#[test]
fn if_with_comparison() {
    let result = as_number(ev(
        "IF(Revenue > 1000, Revenue * 0.1, Revenue * 0.05)",
        vec![("Revenue", FormulaValue::Number(2000.0))],
    ));
    assert_eq!(result, 200.0);
}

#[test]
fn if_with_comparison_false_branch() {
    let result = as_number(ev(
        "IF(Revenue > 1000, Revenue * 0.1, Revenue * 0.05)",
        vec![("Revenue", FormulaValue::Number(500.0))],
    ));
    assert_eq!(result, 25.0);
}

#[test]
fn and_both_true() {
    assert!(as_bool(ev("AND(TRUE, TRUE)", vec![])));
}

#[test]
fn and_one_false() {
    assert!(!as_bool(ev("AND(TRUE, FALSE)", vec![])));
}

#[test]
fn or_one_true() {
    assert!(as_bool(ev("OR(FALSE, TRUE)", vec![])));
}

#[test]
fn not_true() {
    assert!(!as_bool(ev("NOT(TRUE)", vec![])));
}

#[test]
fn not_false() {
    assert!(as_bool(ev("NOT(FALSE)", vec![])));
}

#[test]
fn isblank_zero() {
    assert!(as_bool(ev("ISBLANK(0)", vec![])));
}

#[test]
fn isblank_nonzero() {
    assert!(!as_bool(ev("ISBLANK(1)", vec![])));
}

#[test]
fn if_wrong_arity_raises() {
    assert!(evaluate_formula("IF(TRUE, 1)", HashMap::new()).is_err());
}

#[test]
fn abs_negative() {
    assert_eq!(as_number(ev("ABS(-5)", vec![])), 5.0);
}

#[test]
fn abs_positive() {
    assert_eq!(as_number(ev("ABS(3)", vec![])), 3.0);
}

#[test]
fn round_function() {
    assert_eq!(as_number(ev("ROUND(3.14159, 2)", vec![])), 3.14);
}

#[test]
fn round_to_zero() {
    assert_eq!(as_number(ev("ROUND(3.7, 0)", vec![])), 4.0);
}

#[test]
fn min_function() {
    assert_eq!(as_number(ev("MIN(3, 1, 2)", vec![])), 1.0);
}

#[test]
fn max_function() {
    assert_eq!(as_number(ev("MAX(3, 1, 2)", vec![])), 3.0);
}

#[test]
fn power_function() {
    assert_eq!(as_number(ev("POWER(2, 10)", vec![])), 1024.0);
}

#[test]
fn sqrt_function() {
    assert_eq!(as_number(ev("SQRT(9)", vec![])), 3.0);
}

#[test]
fn sqrt_negative_raises() {
    assert!(evaluate_formula("SQRT(-1)", HashMap::new()).is_err());
}

#[test]
fn log_base10() {
    let result = as_number(ev("LOG(100)", vec![]));
    assert!((result - 2.0).abs() < 1e-9);
}

#[test]
fn log_custom_base() {
    let result = as_number(ev("LOG(8, 2)", vec![]));
    assert!((result - 3.0).abs() < 1e-9);
}

#[test]
fn sum_literals() {
    assert_eq!(as_number(ev("SUM(1, 2, 3)", vec![])), 6.0);
}

#[test]
fn average() {
    assert_eq!(as_number(ev("AVERAGE(1, 2, 3)", vec![])), 2.0);
}

#[test]
fn count() {
    assert_eq!(as_number(ev("COUNT(1, 2, 3)", vec![])), 3.0);
}

#[test]
fn sum_with_variable_list() {
    let result = as_number(ev(
        "SUM(Items)",
        vec![(
            "Items",
            FormulaValue::List(vec![
                FormulaValue::Number(10.0),
                FormulaValue::Number(20.0),
                FormulaValue::Number(30.0),
            ]),
        )],
    ));
    assert_eq!(result, 60.0);
}

#[test]
fn average_with_variable_list() {
    let result = as_number(ev(
        "AVERAGE(Scores)",
        vec![(
            "Scores",
            FormulaValue::List(vec![
                FormulaValue::Number(80.0),
                FormulaValue::Number(90.0),
                FormulaValue::Number(100.0),
            ]),
        )],
    ));
    assert!((result - 90.0).abs() < 1e-9);
}

#[test]
fn sumif_numeric_criteria() {
    let result = as_number(ev(
        "SUMIF(Sales, \">15\")",
        vec![(
            "Sales",
            FormulaValue::List(vec![
                FormulaValue::Number(10.0),
                FormulaValue::Number(20.0),
                FormulaValue::Number(30.0),
            ]),
        )],
    ));
    assert_eq!(result, 50.0);
}

#[test]
fn countif_text_criteria() {
    let result = as_number(ev(
        "COUNTIF(Statuses, Criteria)",
        vec![
            (
                "Statuses",
                FormulaValue::List(vec![
                    FormulaValue::Text("Open".to_string()),
                    FormulaValue::Text("Closed".to_string()),
                    FormulaValue::Text("Open".to_string()),
                    FormulaValue::Text("Hold".to_string()),
                ]),
            ),
            ("Criteria", FormulaValue::Text("Open".to_string())),
        ],
    ));
    assert_eq!(result, 2.0);
}

#[test]
fn averageif_numeric_criteria() {
    let result = as_number(ev(
        "AVERAGEIF(Sales, Criteria)",
        vec![
            (
                "Sales",
                FormulaValue::List(vec![
                    FormulaValue::Number(10.0),
                    FormulaValue::Number(20.0),
                    FormulaValue::Number(30.0),
                ]),
            ),
            ("Criteria", FormulaValue::Text(">=20".to_string())),
        ],
    ));
    assert_eq!(result, 25.0);
}

#[test]
fn averageif_no_match_raises() {
    assert!(evaluate_formula(
        "AVERAGEIF(Sales, \">100\")",
        ctx(vec![(
            "Sales",
            FormulaValue::List(vec![
                FormulaValue::Number(10.0),
                FormulaValue::Number(20.0),
                FormulaValue::Number(30.0),
            ]),
        )]),
    )
    .is_err());
}

#[test]
fn median_odd_range() {
    let result = as_number(ev(
        "MEDIAN(Values)",
        vec![(
            "Values",
            FormulaValue::List(vec![
                FormulaValue::Number(7.0),
                FormulaValue::Number(1.0),
                FormulaValue::Number(3.0),
            ]),
        )],
    ));
    assert_eq!(result, 3.0);
}

#[test]
fn median_even_range() {
    let result = as_number(ev(
        "MEDIAN(Values)",
        vec![(
            "Values",
            FormulaValue::List(vec![
                FormulaValue::Number(1.0),
                FormulaValue::Number(2.0),
                FormulaValue::Number(3.0),
                FormulaValue::Number(4.0),
            ]),
        )],
    ));
    assert_eq!(result, 2.5);
}

#[test]
fn stdev_sample() {
    let result = as_number(ev(
        "STDEV(Values)",
        vec![(
            "Values",
            FormulaValue::List(vec![
                FormulaValue::Number(1.0),
                FormulaValue::Number(2.0),
                FormulaValue::Number(3.0),
            ]),
        )],
    ));
    assert!((result - 1.0).abs() < 1e-9);
}

#[test]
fn variance_sample() {
    let result = as_number(ev(
        "VARIANCE(Values)",
        vec![(
            "Values",
            FormulaValue::List(vec![
                FormulaValue::Number(1.0),
                FormulaValue::Number(2.0),
                FormulaValue::Number(3.0),
            ]),
        )],
    ));
    assert!((result - 1.0).abs() < 1e-9);
}

#[test]
fn percentile_with_fractional_k() {
    let result = as_number(ev(
        "PERCENTILE(Values, 0.25)",
        vec![(
            "Values",
            FormulaValue::List(vec![
                FormulaValue::Number(10.0),
                FormulaValue::Number(20.0),
                FormulaValue::Number(30.0),
                FormulaValue::Number(40.0),
            ]),
        )],
    ));
    assert_eq!(result, 17.5);
}

#[test]
fn percentile_accepts_percentage_k() {
    let result = as_number(ev(
        "PERCENTILE(Values, 25)",
        vec![(
            "Values",
            FormulaValue::List(vec![
                FormulaValue::Number(10.0),
                FormulaValue::Number(20.0),
                FormulaValue::Number(30.0),
                FormulaValue::Number(40.0),
            ]),
        )],
    ));
    assert_eq!(result, 17.5);
}

#[test]
fn large_and_small() {
    let entries = vec![(
        "Values",
        FormulaValue::List(vec![
            FormulaValue::Number(4.0),
            FormulaValue::Number(9.0),
            FormulaValue::Number(1.0),
            FormulaValue::Number(7.0),
        ]),
    )];
    assert_eq!(as_number(ev("LARGE(Values, 2)", entries.clone())), 7.0);
    assert_eq!(as_number(ev("SMALL(Values, 3)", entries)), 7.0);
}

#[test]
fn growth_linear_regression_scalar_new_x() {
    let result = as_number(ev(
        "GROWTH(KnownY, KnownX, 5)",
        vec![
            (
                "KnownY",
                FormulaValue::List(vec![
                    FormulaValue::Number(3.0),
                    FormulaValue::Number(5.0),
                    FormulaValue::Number(7.0),
                    FormulaValue::Number(9.0),
                ]),
            ),
            (
                "KnownX",
                FormulaValue::List(vec![
                    FormulaValue::Number(1.0),
                    FormulaValue::Number(2.0),
                    FormulaValue::Number(3.0),
                    FormulaValue::Number(4.0),
                ]),
            ),
        ],
    ));
    assert!((result - 11.0).abs() < 1e-9);
}

#[test]
fn growth_linear_regression_list_new_x() {
    let result = ev(
        "GROWTH(KnownY, KnownX, NewX)",
        vec![
            (
                "KnownY",
                FormulaValue::List(vec![
                    FormulaValue::Number(3.0),
                    FormulaValue::Number(5.0),
                    FormulaValue::Number(7.0),
                    FormulaValue::Number(9.0),
                ]),
            ),
            (
                "KnownX",
                FormulaValue::List(vec![
                    FormulaValue::Number(1.0),
                    FormulaValue::Number(2.0),
                    FormulaValue::Number(3.0),
                    FormulaValue::Number(4.0),
                ]),
            ),
            (
                "NewX",
                FormulaValue::List(vec![
                    FormulaValue::Number(5.0),
                    FormulaValue::Number(6.0),
                ]),
            ),
        ],
    );
    match result {
        FormulaValue::List(values) => {
            assert_eq!(values, vec![FormulaValue::Number(11.0), FormulaValue::Number(13.0)]);
        }
        other => panic!("expected list result, got {:?}", other),
    }
}

#[test]
fn growth_requires_non_zero_known_x_variance() {
    assert!(evaluate_formula(
        "GROWTH(KnownY, KnownX, 10)",
        ctx(vec![
            (
                "KnownY",
                FormulaValue::List(vec![
                    FormulaValue::Number(1.0),
                    FormulaValue::Number(2.0),
                    FormulaValue::Number(3.0),
                ]),
            ),
            (
                "KnownX",
                FormulaValue::List(vec![
                    FormulaValue::Number(5.0),
                    FormulaValue::Number(5.0),
                    FormulaValue::Number(5.0),
                ]),
            ),
        ]),
    )
    .is_err());
}

#[test]
fn concatenate() {
    let result = as_text(ev("CONCATENATE(\"Hello\", \" \", \"World\")", vec![]));
    assert_eq!(result, "Hello World");
}

#[test]
fn upper() {
    assert_eq!(as_text(ev("UPPER(\"hello\")", vec![])), "HELLO");
}

#[test]
fn lower() {
    assert_eq!(as_text(ev("LOWER(\"HELLO\")", vec![])), "hello");
}

#[test]
fn trim() {
    assert_eq!(as_text(ev("TRIM(\"  hello  \")", vec![])), "hello");
}

#[test]
fn left() {
    assert_eq!(as_text(ev("LEFT(\"abcdef\", 3)", vec![])), "abc");
}

#[test]
fn right() {
    assert_eq!(as_text(ev("RIGHT(\"abcdef\", 3)", vec![])), "def");
}

#[test]
fn len_function() {
    assert_eq!(as_number(ev("LEN(\"hello\")", vec![])), 5.0);
}

#[test]
fn concatenate_with_variable() {
    let result = as_text(ev(
        "CONCATENATE(\"Hello, \", Name)",
        vec![("Name", FormulaValue::Text("Alice".to_string()))],
    ));
    assert_eq!(result, "Hello, Alice");
}

#[test]
fn mid_extracts_substring() {
    let result = as_text(ev("MID(\"Dynaplan\", 2, 4)", vec![]));
    assert_eq!(result, "ynap");
}

#[test]
fn find_returns_one_based_index() {
    let result = as_number(ev("FIND(\"plan\", \"Dynaplan\")", vec![]));
    assert_eq!(result, 5.0);
}

#[test]
fn find_returns_zero_when_missing() {
    let result = as_number(ev("FIND(\"xyz\", \"Dynaplan\")", vec![]));
    assert_eq!(result, 0.0);
}

#[test]
fn substitute_replaces_all_occurrences() {
    let result = as_text(ev(
        "SUBSTITUTE(\"A-B-B\", \"B\", \"X\")",
        vec![],
    ));
    assert_eq!(result, "A-X-X");
}

#[test]
fn text_formats_decimal_pattern() {
    let result = as_text(ev("TEXT(1234.567, \"0.00\")", vec![]));
    assert_eq!(result, "1234.57");
}

#[test]
fn text_formats_percent_pattern() {
    let result = as_text(ev("TEXT(0.125, \"0.0%\")", vec![]));
    assert_eq!(result, "12.5%");
}

#[test]
fn value_parses_numeric_text() {
    let result = as_number(ev("VALUE(\"1,234.50\")", vec![]));
    assert_eq!(result, 1234.5);
}

#[test]
fn value_parses_percent_text() {
    let result = as_number(ev("VALUE(\"12.5%\")", vec![]));
    assert_eq!(result, 0.125);
}

#[test]
fn textlist_prefers_member_name() {
    let result = as_text(ev(
        "TEXTLIST(Member)",
        vec![(
            "Member",
            FormulaValue::Map(map(vec![("id", "p1".into()), ("name", "Widget".into())])),
        )],
    ));
    assert_eq!(result, "Widget");
}

#[test]
fn maketext_supports_numbered_placeholders() {
    let result = as_text(ev("MAKETEXT(\"{0}-{1}\", \"Plan\", 2026)", vec![]));
    assert_eq!(result, "Plan-2026");
}

#[test]
fn maketext_supports_sequential_placeholders() {
    let result = as_text(ev("MAKETEXT(\"{} {}\", \"Hello\", \"World\")", vec![]));
    assert_eq!(result, "Hello World");
}

#[test]
fn yeartodate_uses_current_period() {
    let result = as_text(ev(
        "YEARTODATE()",
        vec![("CURRENT_PERIOD", FormulaValue::Text("2025-11".to_string()))],
    ));
    assert_eq!(result, "YTD 2025");
}

#[test]
fn monthtodate_with_explicit_period() {
    let result = as_text(ev("MONTHTODATE(\"2026-03\")", vec![]));
    assert_eq!(result, "MTD 2026-03");
}

#[test]
fn date_function_builds_iso_date() {
    let result = as_text(ev("DATE(2026, 3, 2)", vec![]));
    assert_eq!(result, "2026-03-02");
}

#[test]
fn datevalue_normalizes_datetime_text() {
    let result = as_text(ev(
        "DATEVALUE(\"2026-03-02T15:30:00Z\")",
        vec![],
    ));
    assert_eq!(result, "2026-03-02");
}

#[test]
fn today_returns_iso_date_text() {
    let result = as_text(ev("TODAY()", vec![]));
    assert_eq!(result.len(), 10);
    assert_eq!(result.chars().nth(4), Some('-'));
    assert_eq!(result.chars().nth(7), Some('-'));
}

#[test]
fn ceiling_floor_mod_sign() {
    assert_eq!(as_number(ev("CEILING(1.2)", vec![])), 2.0);
    assert_eq!(as_number(ev("FLOOR(1.8)", vec![])), 1.0);
    assert_eq!(as_number(ev("MOD(10, 3)", vec![])), 1.0);
    assert_eq!(as_number(ev("SIGN(-3)", vec![])), -1.0);
}

#[test]
fn mod_zero_divisor_raises() {
    assert!(evaluate_formula("MOD(5, 0)", HashMap::new()).is_err());
}

#[test]
fn validate_formula_valid_returns_empty_list() {
    assert!(validate_formula("Revenue * 0.15").is_empty());
}

#[test]
fn validate_formula_empty_returns_error() {
    assert!(!validate_formula("").is_empty());
}

#[test]
fn validate_formula_whitespace_only_returns_error() {
    assert!(!validate_formula("   ").is_empty());
}

#[test]
fn validate_formula_mismatched_paren_returns_error() {
    assert!(!validate_formula("(2 + 3").is_empty());
}

#[test]
fn validate_formula_unknown_char_returns_error() {
    assert!(!validate_formula("@Revenue").is_empty());
}

#[test]
fn validate_formula_valid_function_returns_empty() {
    assert!(validate_formula("IF(Revenue > 0, Revenue * 0.1, 0)").is_empty());
}

#[test]
fn get_references_single_variable() {
    assert_eq!(get_references("Revenue * 0.15"), refs(&["Revenue"]));
}

#[test]
fn get_references_multiple_variables() {
    assert_eq!(
        get_references("Price * Quantity - Discount"),
        refs(&["Price", "Quantity", "Discount"])
    );
}

#[test]
fn get_references_function_name_excluded() {
    let values = get_references("SUM(Sales, Returns)");
    assert!(!values.contains("SUM"));
    assert!(values.contains("Sales"));
    assert!(values.contains("Returns"));
}

#[test]
fn get_references_literals_not_included() {
    assert!(get_references("2 + 3").is_empty());
}

#[test]
fn get_references_nested_formula() {
    assert_eq!(
        get_references("IF(Revenue > 1000, Revenue * Rate, MinFee)"),
        refs(&["Revenue", "Rate", "MinFee"])
    );
}

#[test]
fn get_references_dotted_reference() {
    let values = get_references("Product.Price * Quantity");
    assert!(values.contains("Product.Price"));
}

#[test]
fn get_references_invalid_formula_returns_empty_set() {
    assert!(get_references("@@@invalid@@@").is_empty());
}

#[test]
fn deeply_nested_expression() {
    let result = as_number(ev("((2 + 3) * (4 - 1)) / 5", vec![]));
    assert_eq!(result, 3.0);
}

#[test]
fn nested_if() {
    let result = as_number(ev("IF(x > 10, IF(x > 20, 3, 2), 1)", vec![("x", 15.0.into())]));
    assert_eq!(result, 2.0);
}

#[test]
fn boolean_literal_in_expression() {
    let result = as_number(ev(
        "IF(Active, Revenue, 0)",
        vec![
            ("Active", FormulaValue::Bool(true)),
            ("Revenue", FormulaValue::Number(500.0)),
        ],
    ));
    assert_eq!(result, 500.0);
}

#[test]
fn string_comparison() {
    let result = as_bool(ev(
        "Status = \"Active\"",
        vec![("Status", FormulaValue::Text("Active".to_string()))],
    ));
    assert!(result);
}

#[test]
fn chained_and_or() {
    let result = as_bool(ev(
        "AND(x > 0, OR(y > 5, z > 5))",
        vec![("x", 1.0.into()), ("y", 10.0.into()), ("z", 0.0.into())],
    ));
    assert!(result);
}

#[test]
fn not_with_comparison() {
    let result = as_bool(ev("NOT(x = 0)", vec![("x", 5.0.into())]));
    assert!(result);
}

#[test]
fn power_with_variable() {
    let result = as_number(ev("x ^ 2", vec![("x", 5.0.into())]));
    assert_eq!(result, 25.0);
}

#[test]
fn syntax_error_in_evaluate_formula_raises() {
    assert!(evaluate_formula("(2 + 3", HashMap::new()).is_err());
}

#[test]
fn if_lazy_no_div_by_zero_in_dead_branch() {
    let result = as_number(ev("IF(TRUE, 99, 1 / 0)", vec![]));
    assert_eq!(result, 99.0);
}

#[test]
fn yearvalue_uses_current_period_when_target_omitted() {
    let result = as_number(ev(
        "YEARVALUE(Sales)",
        vec![
            (
                "Sales",
                FormulaValue::List(vec![
                    FormulaValue::Number(5.0),
                    FormulaValue::Number(10.0),
                    FormulaValue::Number(20.0),
                ]),
            ),
            (
                "TIME_PERIODS",
                FormulaValue::List(vec![
                    FormulaValue::Text("2023-12".to_string()),
                    FormulaValue::Text("2024-01".to_string()),
                    FormulaValue::Text("2024-02".to_string()),
                ]),
            ),
            ("CURRENT_PERIOD", FormulaValue::Text("2024-02".to_string())),
        ],
    ));
    assert_eq!(result, 30.0);
}

#[test]
fn monthvalue_with_target_month() {
    let result = as_number(ev(
        "MONTHVALUE(Sales, 2)",
        vec![
            (
                "Sales",
                FormulaValue::List(vec![
                    FormulaValue::Number(10.0),
                    FormulaValue::Number(20.0),
                    FormulaValue::Number(30.0),
                ]),
            ),
            (
                "TIME_PERIODS",
                FormulaValue::List(vec![
                    FormulaValue::Text("2024-01".to_string()),
                    FormulaValue::Text("2024-02".to_string()),
                    FormulaValue::Text("2024-02".to_string()),
                ]),
            ),
        ],
    ));
    assert_eq!(result, 50.0);
}

#[test]
fn quartervalue_with_target_quarter() {
    let result = as_number(ev(
        "QUARTERVALUE(Sales, 2)",
        vec![
            (
                "Sales",
                FormulaValue::List(vec![
                    FormulaValue::Number(10.0),
                    FormulaValue::Number(20.0),
                    FormulaValue::Number(30.0),
                    FormulaValue::Number(40.0),
                ]),
            ),
            (
                "TIME_PERIODS",
                FormulaValue::List(vec![
                    FormulaValue::Text("FY2024-Q1".to_string()),
                    FormulaValue::Text("FY2024-Q2".to_string()),
                    FormulaValue::Text("FY2024-Q2".to_string()),
                    FormulaValue::Text("FY2024-Q3".to_string()),
                ]),
            ),
        ],
    ));
    assert_eq!(result, 50.0);
}

#[test]
fn current_period_start_from_context() {
    let result = as_text(ev(
        "CURRENTPERIODSTART()",
        vec![("CURRENT_PERIOD", FormulaValue::Text("2024-03".to_string()))],
    ));
    assert_eq!(result, "2024-03-01");
}

#[test]
fn current_period_end_with_argument() {
    let result = as_text(ev("CURRENTPERIODEND(\"FY2024-Q1\")", vec![]));
    assert_eq!(result, "2024-03-31");
}

#[test]
fn timesum_with_range() {
    let result = as_number(ev(
        "TIMESUM(Sales, \"2024-02\", \"2024-03\")",
        vec![
            (
                "Sales",
                FormulaValue::List(vec![
                    FormulaValue::Number(10.0),
                    FormulaValue::Number(20.0),
                    FormulaValue::Number(30.0),
                    FormulaValue::Number(40.0),
                ]),
            ),
            (
                "TIME_PERIODS",
                FormulaValue::List(vec![
                    FormulaValue::Text("2024-01".to_string()),
                    FormulaValue::Text("2024-02".to_string()),
                    FormulaValue::Text("2024-03".to_string()),
                    FormulaValue::Text("2024-04".to_string()),
                ]),
            ),
        ],
    ));
    assert_eq!(result, 50.0);
}

#[test]
fn timeaverage_with_range() {
    let result = as_number(ev(
        "TIMEAVERAGE(Sales, \"2024-02\", \"2024-03\")",
        vec![
            (
                "Sales",
                FormulaValue::List(vec![
                    FormulaValue::Number(10.0),
                    FormulaValue::Number(20.0),
                    FormulaValue::Number(30.0),
                    FormulaValue::Number(40.0),
                ]),
            ),
            (
                "TIME_PERIODS",
                FormulaValue::List(vec![
                    FormulaValue::Text("2024-01".to_string()),
                    FormulaValue::Text("2024-02".to_string()),
                    FormulaValue::Text("2024-03".to_string()),
                    FormulaValue::Text("2024-04".to_string()),
                ]),
            ),
        ],
    ));
    assert_eq!(result, 25.0);
}

#[test]
fn lag_uses_current_index() {
    let result = as_number(ev(
        "LAG(Sales, 1)",
        vec![
            (
                "Sales",
                FormulaValue::List(vec![
                    FormulaValue::Number(10.0),
                    FormulaValue::Number(20.0),
                    FormulaValue::Number(30.0),
                ]),
            ),
            ("CURRENT_INDEX", FormulaValue::Number(2.0)),
        ],
    ));
    assert_eq!(result, 20.0);
}

#[test]
fn lead_uses_current_index() {
    let result = as_number(ev(
        "LEAD(Sales, 1)",
        vec![
            (
                "Sales",
                FormulaValue::List(vec![
                    FormulaValue::Number(10.0),
                    FormulaValue::Number(20.0),
                    FormulaValue::Number(30.0),
                ]),
            ),
            ("CURRENT_INDEX", FormulaValue::Number(0.0)),
        ],
    ));
    assert_eq!(result, 20.0);
}

#[test]
fn moving_sum_window() {
    let result = as_number(ev(
        "MOVINGSUM(Sales, 3)",
        vec![
            (
                "Sales",
                FormulaValue::List(vec![
                    FormulaValue::Number(1.0),
                    FormulaValue::Number(2.0),
                    FormulaValue::Number(3.0),
                    FormulaValue::Number(4.0),
                ]),
            ),
            ("CURRENT_INDEX", FormulaValue::Number(3.0)),
        ],
    ));
    assert_eq!(result, 9.0);
}

#[test]
fn moving_average_window() {
    let result = as_number(ev(
        "MOVINGAVERAGE(Sales, 2)",
        vec![
            (
                "Sales",
                FormulaValue::List(vec![
                    FormulaValue::Number(1.0),
                    FormulaValue::Number(2.0),
                    FormulaValue::Number(3.0),
                    FormulaValue::Number(4.0),
                ]),
            ),
            ("CURRENT_INDEX", FormulaValue::Number(3.0)),
        ],
    ));
    assert_eq!(result, 3.5);
}

#[test]
fn cumulate_to_current_index() {
    let result = as_number(ev(
        "CUMULATE(Sales)",
        vec![
            (
                "Sales",
                FormulaValue::List(vec![
                    FormulaValue::Number(1.0),
                    FormulaValue::Number(2.0),
                    FormulaValue::Number(3.0),
                    FormulaValue::Number(4.0),
                ]),
            ),
            ("CURRENT_INDEX", FormulaValue::Number(2.0)),
        ],
    ));
    assert_eq!(result, 6.0);
}

#[test]
fn inperiod_true() {
    assert!(as_bool(ev(
        "INPERIOD(\"2024-03-15\", \"FY2024-Q1\")",
        vec![],
    )));
}

#[test]
fn finditem_from_member_list() {
    let result = ev(
        "FINDITEM(Products, \"Gadget\")",
        vec![(
            "Products",
            FormulaValue::List(vec![
                FormulaValue::Map(map(vec![("id", "p1".into()), ("name", "Widget".into())])),
                FormulaValue::Map(map(vec![("id", "p2".into()), ("name", "Gadget".into())])),
            ]),
        )],
    );
    match result {
        FormulaValue::Map(member) => {
            assert_eq!(member.get("id"), Some(&FormulaValue::Text("p2".to_string())));
        }
        other => panic!("expected map result, got {:?}", other),
    }
}

#[test]
fn item_uses_current_items_context() {
    let result = ev(
        "ITEM(Products)",
        vec![
            (
                "Products",
                FormulaValue::List(vec![
                    FormulaValue::Map(map(vec![("id", "p1".into())])),
                    FormulaValue::Map(map(vec![("id", "p2".into())])),
                ]),
            ),
            (
                "CURRENT_ITEMS",
                FormulaValue::Map(map(vec![(
                    "Products",
                    FormulaValue::Map(map(vec![("id", "p2".into()), ("name", "Gadget".into())])),
                )])),
            ),
        ],
    );
    match result {
        FormulaValue::Map(member) => {
            assert_eq!(member.get("id"), Some(&FormulaValue::Text("p2".to_string())));
        }
        other => panic!("expected map result, got {:?}", other),
    }
}

#[test]
fn isancestor_true_from_parent_map() {
    let result = as_bool(ev(
        "ISANCESTOR(\"root\", \"leaf\")",
        vec![(
            "PARENT_MAP",
            FormulaValue::Map(map(vec![
                ("leaf", "mid".into()),
                ("mid", "root".into()),
            ])),
        )],
    ));
    assert!(result);
}

#[test]
fn lookup_legacy_key_mapping() {
    let result = as_text(ev(
        "LOOKUP(Product, ProductToCode)",
        vec![
            ("Product", "Widget".into()),
            (
                "ProductToCode",
                FormulaValue::Map(map(vec![
                    ("Widget", "W01".into()),
                    ("Gadget", "G02".into()),
                ])),
            ),
        ],
    ));
    assert_eq!(result, "W01");
}

#[test]
fn lookup_source_map_with_dimension_mapping() {
    let result = as_number(ev(
        "LOOKUP(SalesByIntersection, Mapping)",
        vec![
            (
                "SalesByIntersection",
                FormulaValue::Map(map(vec![
                    ("North|Widget", 100.0.into()),
                    ("South|Widget", 50.0.into()),
                ])),
            ),
            (
                "Mapping",
                FormulaValue::Map(map(vec![
                    ("Region", "North".into()),
                    ("Product", "Widget".into()),
                ])),
            ),
        ],
    ));
    assert_eq!(result, 100.0);
}

#[test]
fn sum_source_map_with_partial_mapping() {
    let result = as_number(ev(
        "SUM(SalesByIntersection, Mapping)",
        vec![
            (
                "SalesByIntersection",
                FormulaValue::Map(map(vec![
                    ("North|Widget", 100.0.into()),
                    ("South|Widget", 50.0.into()),
                    ("North|Gadget", 20.0.into()),
                ])),
            ),
            (
                "Mapping",
                FormulaValue::Map(map(vec![("Region", "North".into())])),
            ),
        ],
    ));
    assert_eq!(result, 120.0);
}

#[test]
fn ranklist_with_dimension_labels() {
    let result = ev(
        "RANKLIST(Scores, Teams, 2)",
        vec![
            (
                "Scores",
                FormulaValue::List(vec![15.0.into(), 25.0.into(), 20.0.into()]),
            ),
            (
                "Teams",
                FormulaValue::List(vec!["A".into(), "B".into(), "C".into()]),
            ),
        ],
    );
    assert_eq!(
        result,
        FormulaValue::List(vec!["B".into(), "C".into()])
    );
}

#[test]
fn collect_values_by_dimension_order() {
    let result = ev(
        "COLLECT(SalesByProduct, Products)",
        vec![
            (
                "SalesByProduct",
                FormulaValue::Map(map(vec![("p1", 100.0.into()), ("p2", 200.0.into())])),
            ),
            (
                "Products",
                FormulaValue::List(vec!["p2".into(), "p1".into()]),
            ),
        ],
    );
    assert_eq!(
        result,
        FormulaValue::List(vec![200.0.into(), 100.0.into()])
    );
}

#[test]
fn post_returns_value() {
    let result = as_number(ev("POST(\"TargetLineItem\", 42)", vec![]));
    assert_eq!(result, 42.0);
}
