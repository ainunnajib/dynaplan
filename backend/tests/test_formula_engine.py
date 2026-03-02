"""
Comprehensive tests for the F006 formula engine.

All tests are self-contained — no database, no HTTP client, no fixtures.
Run with:  cd backend && pytest tests/test_formula_engine.py -v
"""

import math
from datetime import date
import pytest

from app.engine.tokenizer import tokenize, Token, TokenType, TokenizerError
from app.engine.parser import (
    parse,
    ParseError,
    NumberLiteral,
    StringLiteral,
    BooleanLiteral,
    Identifier,
    BinaryOp,
    UnaryOp,
    FunctionCall,
    Comparison,
)
from app.engine.evaluator import Evaluator, FormulaError
from app.engine.formula import (
    parse_formula,
    evaluate_formula,
    validate_formula,
    get_references,
)


# ===========================================================================
# Tokenizer tests
# ===========================================================================

class TestTokenizer:
    def test_tokenize_number_integer(self):
        tokens = tokenize("42")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "42"

    def test_tokenize_number_float(self):
        tokens = tokenize("3.14")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "3.14"

    def test_tokenize_string_double_quotes(self):
        tokens = tokenize('"hello"')
        assert tokens[0].type == TokenType.STRING

    def test_tokenize_boolean_true(self):
        tokens = tokenize("TRUE")
        assert tokens[0].type == TokenType.BOOLEAN
        assert tokens[0].value == "TRUE"

    def test_tokenize_boolean_false_lowercase(self):
        # Case-insensitive
        tokens = tokenize("false")
        assert tokens[0].type == TokenType.BOOLEAN
        assert tokens[0].value == "FALSE"

    def test_tokenize_logical_and(self):
        tokens = tokenize("AND")
        assert tokens[0].type == TokenType.LOGICAL

    def test_tokenize_comparison_neq(self):
        tokens = tokenize("<>")
        assert tokens[0].type == TokenType.COMPARISON
        assert tokens[0].value == "<>"

    def test_tokenize_dotted_identifier(self):
        tokens = tokenize("Product.Price")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "Product.Price"

    def test_tokenize_arithmetic_expression(self):
        tokens = tokenize("Revenue * 0.15")
        types = [t.type for t in tokens]
        assert types == [TokenType.IDENTIFIER, TokenType.OPERATOR, TokenType.NUMBER]

    def test_tokenize_unknown_character_raises(self):
        with pytest.raises(TokenizerError):
            tokenize("@Revenue")

    def test_tokenize_whitespace_ignored(self):
        tokens = tokenize("  1  +  2  ")
        assert len(tokens) == 3


# ===========================================================================
# Parser / AST tests
# ===========================================================================

class TestParser:
    def test_parse_number_literal(self):
        node = parse("42")
        assert isinstance(node, NumberLiteral)
        assert node.value == 42.0

    def test_parse_string_literal(self):
        node = parse('"hello"')
        assert isinstance(node, StringLiteral)
        assert node.value == "hello"

    def test_parse_boolean_literal(self):
        node = parse("TRUE")
        assert isinstance(node, BooleanLiteral)
        assert node.value is True

    def test_parse_identifier(self):
        node = parse("Revenue")
        assert isinstance(node, Identifier)
        assert node.name == "Revenue"

    def test_parse_binary_add(self):
        node = parse("2 + 3")
        assert isinstance(node, BinaryOp)
        assert node.op == "+"

    def test_parse_function_call(self):
        node = parse("SUM(1, 2, 3)")
        assert isinstance(node, FunctionCall)
        assert node.name == "SUM"
        assert len(node.args) == 3

    def test_parse_unary_minus(self):
        node = parse("-5")
        assert isinstance(node, UnaryOp)
        assert node.op == "-"

    def test_parse_comparison(self):
        node = parse("Revenue > 1000")
        assert isinstance(node, Comparison)
        assert node.op == ">"

    def test_parse_nested_function(self):
        node = parse("IF(Revenue > 0, Revenue * 0.1, 0)")
        assert isinstance(node, FunctionCall)
        assert node.name == "IF"
        assert len(node.args) == 3

    def test_parse_mismatched_paren_raises(self):
        with pytest.raises(ParseError):
            parse("(2 + 3")

    def test_parse_extra_token_raises(self):
        with pytest.raises(ParseError):
            parse("2 + 3 )")

    def test_parse_empty_string_raises(self):
        with pytest.raises(Exception):
            parse("")


# ===========================================================================
# Evaluator — arithmetic
# ===========================================================================

class TestArithmetic:
    def _ev(self, expr: str, ctx: dict = None) -> object:
        return evaluate_formula(expr, ctx or {})

    def test_addition(self):
        assert self._ev("2 + 3") == 5.0

    def test_subtraction(self):
        assert self._ev("10 - 4") == 6.0

    def test_multiplication(self):
        assert self._ev("3 * 4") == 12.0

    def test_division(self):
        assert self._ev("10 / 4") == 2.5

    def test_power(self):
        assert self._ev("2 ^ 3") == 8.0

    def test_operator_precedence_mul_over_add(self):
        # 2 + 3 * 4 = 14, not 20
        assert self._ev("2 + 3 * 4") == 14.0

    def test_parentheses_override_precedence(self):
        assert self._ev("10 * (5 - 2)") == 30.0

    def test_unary_minus(self):
        assert self._ev("-5 + 10") == 5.0

    def test_nested_arithmetic(self):
        assert self._ev("(2 + 3) * (4 - 1)") == 15.0

    def test_division_by_zero_raises(self):
        with pytest.raises(FormulaError, match="Division by zero"):
            self._ev("10 / 0")

    def test_float_arithmetic(self):
        result = self._ev("0.1 + 0.2")
        assert abs(result - 0.3) < 1e-9


# ===========================================================================
# Evaluator — variables
# ===========================================================================

class TestVariables:
    def test_single_variable(self):
        result = evaluate_formula("Revenue * 0.15", {"Revenue": 1000})
        assert result == 150.0

    def test_multiple_variables(self):
        result = evaluate_formula("Price * Quantity", {"Price": 25.0, "Quantity": 4})
        assert result == 100.0

    def test_undefined_variable_raises(self):
        with pytest.raises(FormulaError, match="Undefined variable"):
            evaluate_formula("Revenue", {})

    def test_variable_in_condition(self):
        result = evaluate_formula("Active", {"Active": True})
        assert result is True

    def test_dotted_variable(self):
        result = evaluate_formula("Product.Price * 2", {"Product.Price": 50.0})
        assert result == 100.0


# ===========================================================================
# Evaluator — comparisons
# ===========================================================================

class TestComparisons:
    def test_greater_than_true(self):
        assert evaluate_formula("5 > 3") is True

    def test_greater_than_false(self):
        assert evaluate_formula("3 > 5") is False

    def test_less_than(self):
        assert evaluate_formula("2 < 10") is True

    def test_equal(self):
        assert evaluate_formula("5 = 5") is True

    def test_not_equal(self):
        result = evaluate_formula("Revenue <> 0", {"Revenue": 100})
        assert result is True

    def test_less_than_or_equal(self):
        assert evaluate_formula("5 <= 5") is True

    def test_greater_than_or_equal(self):
        assert evaluate_formula("6 >= 5") is True


# ===========================================================================
# Evaluator — logical / IF
# ===========================================================================

class TestLogical:
    def test_if_true_branch(self):
        assert evaluate_formula("IF(TRUE, 1, 0)") == 1.0

    def test_if_false_branch(self):
        assert evaluate_formula("IF(FALSE, 1, 0)") == 0.0

    def test_if_with_comparison(self):
        result = evaluate_formula(
            "IF(Revenue > 1000, Revenue * 0.1, Revenue * 0.05)",
            {"Revenue": 2000},
        )
        assert result == 200.0

    def test_if_with_comparison_false_branch(self):
        result = evaluate_formula(
            "IF(Revenue > 1000, Revenue * 0.1, Revenue * 0.05)",
            {"Revenue": 500},
        )
        assert result == 25.0

    def test_and_both_true(self):
        assert evaluate_formula("AND(TRUE, TRUE)") is True

    def test_and_one_false(self):
        assert evaluate_formula("AND(TRUE, FALSE)") is False

    def test_or_one_true(self):
        assert evaluate_formula("OR(FALSE, TRUE)") is True

    def test_not_true(self):
        assert evaluate_formula("NOT(TRUE)") is False

    def test_not_false(self):
        assert evaluate_formula("NOT(FALSE)") is True

    def test_isblank_zero(self):
        assert evaluate_formula("ISBLANK(0)") is True

    def test_isblank_nonzero(self):
        assert evaluate_formula("ISBLANK(1)") is False

    def test_if_wrong_arity_raises(self):
        with pytest.raises(FormulaError):
            evaluate_formula("IF(TRUE, 1)")


# ===========================================================================
# Evaluator — math functions
# ===========================================================================

class TestMathFunctions:
    def test_abs_negative(self):
        assert evaluate_formula("ABS(-5)") == 5.0

    def test_abs_positive(self):
        assert evaluate_formula("ABS(3)") == 3.0

    def test_round(self):
        assert evaluate_formula("ROUND(3.14159, 2)") == 3.14

    def test_round_to_zero(self):
        assert evaluate_formula("ROUND(3.7, 0)") == 4.0

    def test_min(self):
        assert evaluate_formula("MIN(3, 1, 2)") == 1.0

    def test_max(self):
        assert evaluate_formula("MAX(3, 1, 2)") == 3.0

    def test_power(self):
        assert evaluate_formula("POWER(2, 10)") == 1024.0

    def test_sqrt(self):
        assert evaluate_formula("SQRT(9)") == 3.0

    def test_sqrt_negative_raises(self):
        with pytest.raises(FormulaError, match="SQRT of negative"):
            evaluate_formula("SQRT(-1)")

    def test_log_base10(self):
        assert abs(evaluate_formula("LOG(100)") - 2.0) < 1e-9

    def test_log_custom_base(self):
        result = evaluate_formula("LOG(8, 2)")
        assert abs(result - 3.0) < 1e-9


# ===========================================================================
# Evaluator — aggregation functions
# ===========================================================================

class TestAggregation:
    def test_sum_literals(self):
        assert evaluate_formula("SUM(1, 2, 3)") == 6.0

    def test_average(self):
        assert evaluate_formula("AVERAGE(1, 2, 3)") == 2.0

    def test_count(self):
        assert evaluate_formula("COUNT(1, 2, 3)") == 3.0

    def test_itemcount(self):
        result = evaluate_formula("ITEMCOUNT(Items)", {"Items": [10, 20, 30]})
        assert result == 3.0

    def test_itemcount_empty_list(self):
        result = evaluate_formula("ITEMCOUNT(Items)", {"Items": []})
        assert result == 0.0

    def test_itemcount_requires_list(self):
        with pytest.raises(FormulaError, match="ITEMCOUNT requires a list argument"):
            evaluate_formula("ITEMCOUNT(Revenue)", {"Revenue": 100})

    def test_sum_with_variable_list(self):
        result = evaluate_formula("SUM(Items)", {"Items": [10, 20, 30]})
        assert result == 60.0

    def test_average_with_variable_list(self):
        result = evaluate_formula("AVERAGE(Scores)", {"Scores": [80, 90, 100]})
        assert abs(result - 90.0) < 1e-9


# ===========================================================================
# Evaluator — time functions (F051)
# ===========================================================================

class TestTimeFunctions:
    def test_yearvalue_uses_current_period_when_target_omitted(self):
        result = evaluate_formula(
            "YEARVALUE(Sales)",
            {
                "Sales": [5, 10, 20],
                "TIME_PERIODS": ["2023-12", "2024-01", "2024-02"],
                "CURRENT_PERIOD": "2024-02",
            },
        )
        assert result == 30.0

    def test_yearvalue_with_explicit_target(self):
        result = evaluate_formula(
            "YEARVALUE(Sales, 2024)",
            {
                "Sales": {"2023-12": 5, "2024-01": 10, "2024-02": 20},
            },
        )
        assert result == 30.0

    def test_monthvalue_with_target_month(self):
        result = evaluate_formula(
            "MONTHVALUE(Sales, 2)",
            {
                "Sales": [10, 20, 30],
                "TIME_PERIODS": ["2024-01", "2024-02", "2024-02"],
            },
        )
        assert result == 50.0

    def test_quartervalue_with_target_quarter(self):
        result = evaluate_formula(
            "QUARTERVALUE(Sales, 2)",
            {
                "Sales": [10, 20, 30, 40],
                "TIME_PERIODS": ["FY2024-Q1", "FY2024-Q2", "FY2024-Q2", "FY2024-Q3"],
            },
        )
        assert result == 50.0

    def test_weekvalue_with_target_week(self):
        result = evaluate_formula(
            "WEEKVALUE(Sales, 2)",
            {"Sales": {"2024-W01": 3, "2024-W02": 7, "2024-W03": 2}},
        )
        assert result == 7.0

    def test_halfyearvalue_with_target_half(self):
        result = evaluate_formula(
            "HALFYEARVALUE(Sales, 2)",
            {"Sales": {"FY2024-H1": 30, "FY2024-H2": 70}},
        )
        assert result == 70.0

    def test_currentperiodstart_from_context(self):
        result = evaluate_formula(
            "CURRENTPERIODSTART()",
            {"CURRENT_PERIOD": "2024-03"},
        )
        assert result == "2024-03-01"

    def test_currentperiodend_with_explicit_period(self):
        result = evaluate_formula('CURRENTPERIODEND("FY2024-Q1")')
        assert result == "2024-03-31"

    def test_periodstart_for_month(self):
        result = evaluate_formula('PERIODSTART("2024-02")')
        assert result == "2024-02-01"

    def test_periodend_for_week(self):
        result = evaluate_formula('PERIODEND("2024-W01")')
        assert result == "2024-01-07"

    def test_timesum_full_series(self):
        result = evaluate_formula(
            "TIMESUM(Sales)",
            {
                "Sales": [10, 20, 30, 40],
                "TIME_PERIODS": ["2024-01", "2024-02", "2024-03", "2024-04"],
            },
        )
        assert result == 100.0

    def test_timesum_with_range(self):
        result = evaluate_formula(
            'TIMESUM(Sales, "2024-02", "2024-03")',
            {
                "Sales": [10, 20, 30, 40],
                "TIME_PERIODS": ["2024-01", "2024-02", "2024-03", "2024-04"],
            },
        )
        assert result == 50.0

    def test_timeaverage_with_range(self):
        result = evaluate_formula(
            'TIMEAVERAGE(Sales, "2024-02", "2024-03")',
            {
                "Sales": [10, 20, 30, 40],
                "TIME_PERIODS": ["2024-01", "2024-02", "2024-03", "2024-04"],
            },
        )
        assert result == 25.0

    def test_timecount_with_range(self):
        result = evaluate_formula(
            'TIMECOUNT(Sales, "2024-02", "2024-03")',
            {
                "Sales": [10, 20, 30, 40],
                "TIME_PERIODS": ["2024-01", "2024-02", "2024-03", "2024-04"],
            },
        )
        assert result == 2.0

    def test_lag_uses_current_index(self):
        result = evaluate_formula(
            "LAG(Sales, 1)",
            {"Sales": [10, 20, 30], "CURRENT_INDEX": 2},
        )
        assert result == 20

    def test_lag_out_of_bounds_returns_default(self):
        result = evaluate_formula(
            "LAG(Sales, 5, 99)",
            {"Sales": [10, 20, 30], "CURRENT_INDEX": 2},
        )
        assert result == 99.0

    def test_lead_uses_current_index(self):
        result = evaluate_formula(
            "LEAD(Sales, 1)",
            {"Sales": [10, 20, 30], "CURRENT_INDEX": 0},
        )
        assert result == 20

    def test_offset_supports_negative_offsets(self):
        result = evaluate_formula(
            "OFFSET(Sales, -2)",
            {"Sales": [10, 20, 30], "CURRENT_INDEX": 2},
        )
        assert result == 10

    def test_movingsum_window(self):
        result = evaluate_formula(
            "MOVINGSUM(Sales, 3)",
            {"Sales": [1, 2, 3, 4], "CURRENT_INDEX": 3},
        )
        assert result == 9.0

    def test_movingaverage_window(self):
        result = evaluate_formula(
            "MOVINGAVERAGE(Sales, 2)",
            {"Sales": [1, 2, 3, 4], "CURRENT_INDEX": 3},
        )
        assert result == 3.5

    def test_cumulate_to_current_index(self):
        result = evaluate_formula(
            "CUMULATE(Sales)",
            {"Sales": [1, 2, 3, 4], "CURRENT_INDEX": 2},
        )
        assert result == 6.0

    def test_previous(self):
        result = evaluate_formula(
            "PREVIOUS(Sales)",
            {"Sales": [10, 20, 30], "CURRENT_INDEX": 2},
        )
        assert result == 20

    def test_next(self):
        result = evaluate_formula(
            "NEXT(Sales)",
            {"Sales": [10, 20, 30], "CURRENT_INDEX": 1},
        )
        assert result == 30

    def test_inperiod_true(self):
        assert evaluate_formula('INPERIOD("2024-03-15", "FY2024-Q1")') is True

    def test_inperiod_false(self):
        assert evaluate_formula(
            "INPERIOD(InputDate, Period)",
            {"InputDate": date(2024, 4, 1), "Period": "FY2024-Q1"},
        ) is False

    def test_currentperiodstart_requires_context_or_arg(self):
        with pytest.raises(FormulaError, match="CURRENTPERIODSTART"):
            evaluate_formula("CURRENTPERIODSTART()")

    def test_timeaverage_empty_range_raises(self):
        with pytest.raises(FormulaError, match="TIMEAVERAGE"):
            evaluate_formula(
                'TIMEAVERAGE(Sales, "2025-01", "2025-12")',
                {
                    "Sales": [10, 20],
                    "TIME_PERIODS": ["2024-01", "2024-02"],
                },
            )


# ===========================================================================
# Evaluator — lookup & cross-module functions (F052)
# ===========================================================================

class TestLookupCrossModuleFunctions:
    def test_finditem_from_member_list(self):
        result = evaluate_formula(
            'FINDITEM(Products, "Gadget")',
            {
                "Products": [
                    {"id": "p1", "name": "Widget", "code": "W01"},
                    {"id": "p2", "name": "Gadget", "code": "G02"},
                ]
            },
        )
        assert isinstance(result, dict)
        assert result["id"] == "p2"

    def test_finditem_from_name_map(self):
        result = evaluate_formula(
            'FINDITEM(Products, "Widget")',
            {
                "Products": {
                    "Widget": {"id": "p1", "name": "Widget"},
                    "Gadget": {"id": "p2", "name": "Gadget"},
                }
            },
        )
        assert isinstance(result, dict)
        assert result["id"] == "p1"

    def test_item_uses_current_items_context(self):
        result = evaluate_formula(
            "ITEM(Products)",
            {
                "Products": [{"id": "p1"}, {"id": "p2"}],
                "CURRENT_ITEMS": {"Products": {"id": "p2", "name": "Gadget"}},
            },
        )
        assert isinstance(result, dict)
        assert result["id"] == "p2"

    def test_item_falls_back_to_scalar_argument(self):
        result = evaluate_formula("ITEM(CurrentProduct)", {"CurrentProduct": "p1"})
        assert result == "p1"

    def test_parent_from_member_record(self):
        result = evaluate_formula(
            "PARENT(Product)",
            {"Product": {"id": "child", "parent": "root"}},
        )
        assert result == "root"

    def test_children_from_children_map(self):
        result = evaluate_formula(
            'CHILDREN("root")',
            {
                "CHILDREN_MAP": {
                    "root": [{"id": "c1"}, {"id": "c2"}],
                }
            },
        )
        assert isinstance(result, list)
        assert len(result) == 2

    def test_isleaf_true_when_no_children(self):
        result = evaluate_formula(
            'ISLEAF("c1")',
            {"CHILDREN_MAP": {"root": ["c1"]}},
        )
        assert result is True

    def test_isancestor_true_from_parent_map(self):
        result = evaluate_formula(
            'ISANCESTOR("root", "leaf")',
            {"PARENT_MAP": {"leaf": "mid", "mid": "root"}},
        )
        assert result is True

    def test_isancestor_false_when_not_related(self):
        result = evaluate_formula(
            'ISANCESTOR("left", "leaf")',
            {"PARENT_MAP": {"leaf": "mid", "mid": "root"}},
        )
        assert result is False

    def test_select_with_explicit_key_mapping(self):
        result = evaluate_formula(
            "SELECT(SalesByProduct, Mapping)",
            {
                "SalesByProduct": {"p1": 10, "p2": 20},
                "Mapping": {"key": "p2"},
            },
        )
        assert result == 20

    def test_lookup_legacy_key_mapping(self):
        result = evaluate_formula(
            "LOOKUP(Product, ProductToCode)",
            {
                "Product": "Widget",
                "ProductToCode": {"Widget": "W01", "Gadget": "G02"},
            },
        )
        assert result == "W01"

    def test_lookup_source_map_with_dimension_mapping(self):
        result = evaluate_formula(
            "LOOKUP(SalesByIntersection, Mapping)",
            {
                "SalesByIntersection": {
                    "North|Widget": 100,
                    "South|Widget": 50,
                },
                "Mapping": {"Region": "North", "Product": "Widget"},
            },
        )
        assert result == 100

    def test_sum_source_map_with_partial_mapping(self):
        result = evaluate_formula(
            "SUM(SalesByIntersection, Mapping)",
            {
                "SalesByIntersection": {
                    "North|Widget": 100,
                    "South|Widget": 50,
                    "North|Gadget": 20,
                },
                "Mapping": {"Region": "North"},
            },
        )
        assert result == 120.0

    def test_name_from_member_record(self):
        result = evaluate_formula(
            "NAME(Member)",
            {"Member": {"id": "p1", "name": "Widget"}},
        )
        assert result == "Widget"

    def test_code_from_context_member_map(self):
        result = evaluate_formula(
            "CODE(MemberId)",
            {
                "MemberId": "p2",
                "MEMBERS_BY_ID": {
                    "p2": {"id": "p2", "name": "Gadget", "code": "G02"},
                },
            },
        )
        assert result == "G02"

    def test_rank_scalar_against_dimension_values(self):
        result = evaluate_formula("RANK(20, Scores)", {"Scores": [10, 20, 30]})
        assert result == 2.0

    def test_rank_uses_current_index_for_expression_list(self):
        result = evaluate_formula(
            "RANK(Scores, Teams)",
            {
                "Scores": [30, 10, 20],
                "Teams": ["A", "B", "C"],
                "CURRENT_INDEX": 2,
            },
        )
        assert result == 2.0

    def test_ranklist_from_expression_map(self):
        result = evaluate_formula(
            "RANKLIST(SalesByProduct, Products, 2)",
            {
                "SalesByProduct": {"Widget": 100, "Gadget": 150, "Bolt": 50},
                "Products": ["Widget", "Gadget", "Bolt"],
            },
        )
        assert result == ["Gadget", "Widget"]

    def test_ranklist_with_dimension_labels(self):
        result = evaluate_formula(
            "RANKLIST(Scores, Teams, 2)",
            {"Scores": [15, 25, 20], "Teams": ["A", "B", "C"]},
        )
        assert result == ["B", "C"]

    def test_collect_values_by_dimension_order(self):
        result = evaluate_formula(
            "COLLECT(SalesByProduct, Products)",
            {
                "SalesByProduct": {"p1": 100, "p2": 200},
                "Products": ["p2", "p1"],
            },
        )
        assert result == [200, 100]

    def test_collect_scalar_replicates_across_dimension(self):
        result = evaluate_formula(
            "COLLECT(Value, Products)",
            {"Value": 5, "Products": ["p1", "p2", "p3"]},
        )
        assert result == [5, 5, 5]

    def test_post_returns_value_and_records_write(self):
        context = {"POST_WRITES": {}}
        result = evaluate_formula('POST("TargetLineItem", 42)', context)
        assert result == 42.0
        assert context["POST_WRITES"]["TargetLineItem"] == 42.0

# ===========================================================================
# Evaluator — text functions
# ===========================================================================

class TestTextFunctions:
    def test_concatenate(self):
        result = evaluate_formula('CONCATENATE("Hello", " ", "World")')
        assert result == "Hello World"

    def test_upper(self):
        assert evaluate_formula('UPPER("hello")') == "HELLO"

    def test_lower(self):
        assert evaluate_formula('LOWER("HELLO")') == "hello"

    def test_trim(self):
        assert evaluate_formula('TRIM("  hello  ")') == "hello"

    def test_left(self):
        assert evaluate_formula('LEFT("abcdef", 3)') == "abc"

    def test_right(self):
        assert evaluate_formula('RIGHT("abcdef", 3)') == "def"

    def test_len(self):
        assert evaluate_formula('LEN("hello")') == 5.0

    def test_concatenate_with_variable(self):
        result = evaluate_formula('CONCATENATE("Hello, ", Name)', {"Name": "Alice"})
        assert result == "Hello, Alice"


# ===========================================================================
# High-level API: validate_formula
# ===========================================================================

class TestValidateFormula:
    def test_valid_formula_returns_empty_list(self):
        assert validate_formula("Revenue * 0.15") == []

    def test_empty_formula_returns_error(self):
        errors = validate_formula("")
        assert len(errors) > 0

    def test_whitespace_only_returns_error(self):
        errors = validate_formula("   ")
        assert len(errors) > 0

    def test_mismatched_paren_returns_error(self):
        errors = validate_formula("(2 + 3")
        assert len(errors) > 0

    def test_unknown_char_returns_error(self):
        errors = validate_formula("@Revenue")
        assert len(errors) > 0

    def test_valid_function_returns_empty(self):
        assert validate_formula("IF(Revenue > 0, Revenue * 0.1, 0)") == []


# ===========================================================================
# High-level API: get_references
# ===========================================================================

class TestGetReferences:
    def test_single_variable(self):
        refs = get_references("Revenue * 0.15")
        assert refs == {"Revenue"}

    def test_multiple_variables(self):
        refs = get_references("Price * Quantity - Discount")
        assert refs == {"Price", "Quantity", "Discount"}

    def test_function_name_excluded(self):
        refs = get_references("SUM(Sales, Returns)")
        # SUM is a function name, not a variable
        assert "SUM" not in refs
        assert "Sales" in refs
        assert "Returns" in refs

    def test_literals_not_included(self):
        refs = get_references("2 + 3")
        assert refs == set()

    def test_nested_formula(self):
        refs = get_references("IF(Revenue > 1000, Revenue * Rate, MinFee)")
        assert refs == {"Revenue", "Rate", "MinFee"}

    def test_dotted_reference(self):
        refs = get_references("Product.Price * Quantity")
        assert "Product.Price" in refs

    def test_invalid_formula_returns_empty_set(self):
        refs = get_references("@@@invalid@@@")
        assert refs == set()


# ===========================================================================
# Edge-case / integration tests
# ===========================================================================

class TestEdgeCases:
    def test_deeply_nested_expression(self):
        result = evaluate_formula("((2 + 3) * (4 - 1)) / 5")
        assert result == 3.0

    def test_nested_if(self):
        result = evaluate_formula(
            "IF(x > 10, IF(x > 20, 3, 2), 1)",
            {"x": 15},
        )
        assert result == 2.0

    def test_boolean_literal_in_expression(self):
        result = evaluate_formula("IF(Active, Revenue, 0)", {"Active": True, "Revenue": 500})
        assert result == 500.0

    def test_string_comparison(self):
        result = evaluate_formula('Status = "Active"', {"Status": "Active"})
        assert result is True

    def test_chained_and_or(self):
        result = evaluate_formula(
            "AND(x > 0, OR(y > 5, z > 5))",
            {"x": 1, "y": 10, "z": 0},
        )
        assert result is True

    def test_not_with_comparison(self):
        result = evaluate_formula("NOT(x = 0)", {"x": 5})
        assert result is True

    def test_power_with_variable(self):
        result = evaluate_formula("x ^ 2", {"x": 5})
        assert result == 25.0

    def test_syntax_error_in_evaluate_formula_raises(self):
        with pytest.raises((ParseError, TokenizerError)):
            evaluate_formula("(2 + 3")

    def test_if_lazy_no_div_by_zero_in_dead_branch(self):
        # The false branch (1/0) should NOT be evaluated when condition is TRUE
        result = evaluate_formula("IF(TRUE, 99, 1 / 0)")
        assert result == 99.0
