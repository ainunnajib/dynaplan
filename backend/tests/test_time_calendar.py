"""
Pure Python tests for app.engine.time_calendar (F009).
No database required — all tests run against the engine only.
At least 20 test cases as required by the spec.
"""

from datetime import date

import pytest

from app.engine.time_calendar import (
    FiscalCalendar,
    TimePeriodType,
    generate_time_periods,
    get_period_for_date,
    spread_value,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def periods_of_type(periods, ptype):
    return [p for p in periods if p["period_type"] == ptype]


# ---------------------------------------------------------------------------
# FiscalCalendar construction
# ---------------------------------------------------------------------------

def test_fiscal_calendar_defaults():
    cal = FiscalCalendar()
    assert cal.fiscal_year_start_month == 1
    assert cal.week_start_day == 0


def test_fiscal_calendar_custom():
    cal = FiscalCalendar(fiscal_year_start_month=7, week_start_day=6)
    assert cal.fiscal_year_start_month == 7
    assert cal.week_start_day == 6


def test_fiscal_calendar_invalid_month():
    with pytest.raises(ValueError):
        FiscalCalendar(fiscal_year_start_month=13)


def test_fiscal_calendar_invalid_week_day():
    with pytest.raises(ValueError):
        FiscalCalendar(week_start_day=7)


# ---------------------------------------------------------------------------
# Year granularity
# ---------------------------------------------------------------------------

def test_generate_year_single():
    periods = generate_time_periods(2024, 2024, TimePeriodType.year)
    years = periods_of_type(periods, TimePeriodType.year)
    assert len(years) == 1
    assert years[0]["code"] == "FY2024"
    assert years[0]["start_date"] == "2024-01-01"
    assert years[0]["end_date"] == "2024-12-31"
    assert years[0]["parent_code"] is None


def test_generate_year_multiple():
    periods = generate_time_periods(2022, 2025, TimePeriodType.year)
    years = periods_of_type(periods, TimePeriodType.year)
    assert len(years) == 4
    codes = [y["code"] for y in years]
    assert "FY2022" in codes
    assert "FY2025" in codes


def test_year_granularity_no_sub_periods():
    periods = generate_time_periods(2024, 2024, TimePeriodType.year)
    assert all(p["period_type"] == TimePeriodType.year for p in periods)


# ---------------------------------------------------------------------------
# Month granularity
# ---------------------------------------------------------------------------

def test_generate_months_count():
    periods = generate_time_periods(2024, 2024, TimePeriodType.month)
    months = periods_of_type(periods, TimePeriodType.month)
    assert len(months) == 12


def test_generate_months_coverage():
    periods = generate_time_periods(2024, 2024, TimePeriodType.month)
    months = periods_of_type(periods, TimePeriodType.month)
    month_codes = sorted(m["code"] for m in months)
    expected = [f"2024-{m:02d}" for m in range(1, 13)]
    assert month_codes == expected


def test_month_has_correct_dates():
    periods = generate_time_periods(2024, 2024, TimePeriodType.month)
    months = periods_of_type(periods, TimePeriodType.month)
    feb = next(m for m in months if m["code"] == "2024-02")
    assert feb["start_date"] == "2024-02-01"
    assert feb["end_date"] == "2024-02-29"  # 2024 is a leap year


def test_generate_months_hierarchy_contains_all_levels():
    periods = generate_time_periods(2024, 2024, TimePeriodType.month)
    types = {p["period_type"] for p in periods}
    assert TimePeriodType.year in types
    assert TimePeriodType.half_year in types
    assert TimePeriodType.quarter in types
    assert TimePeriodType.month in types
    # Weeks should NOT be present for month granularity
    assert TimePeriodType.week not in types


# ---------------------------------------------------------------------------
# Quarter granularity
# ---------------------------------------------------------------------------

def test_generate_quarters_count():
    periods = generate_time_periods(2024, 2024, TimePeriodType.quarter)
    quarters = periods_of_type(periods, TimePeriodType.quarter)
    assert len(quarters) == 4


def test_quarter_codes():
    periods = generate_time_periods(2024, 2024, TimePeriodType.quarter)
    quarters = periods_of_type(periods, TimePeriodType.quarter)
    codes = sorted(q["code"] for q in quarters)
    assert codes == ["FY2024-Q1", "FY2024-Q2", "FY2024-Q3", "FY2024-Q4"]


def test_quarter_parent_is_half():
    periods = generate_time_periods(2024, 2024, TimePeriodType.quarter)
    quarters = periods_of_type(periods, TimePeriodType.quarter)
    q1 = next(q for q in quarters if q["code"] == "FY2024-Q1")
    assert q1["parent_code"] == "FY2024-H1"
    q3 = next(q for q in quarters if q["code"] == "FY2024-Q3")
    assert q3["parent_code"] == "FY2024-H2"


def test_quarter_date_ranges():
    periods = generate_time_periods(2024, 2024, TimePeriodType.quarter)
    quarters = periods_of_type(periods, TimePeriodType.quarter)
    q1 = next(q for q in quarters if q["code"] == "FY2024-Q1")
    assert q1["start_date"] == "2024-01-01"
    assert q1["end_date"] == "2024-03-31"
    q4 = next(q for q in quarters if q["code"] == "FY2024-Q4")
    assert q4["start_date"] == "2024-10-01"
    assert q4["end_date"] == "2024-12-31"


# ---------------------------------------------------------------------------
# Half-year granularity
# ---------------------------------------------------------------------------

def test_half_year_count():
    periods = generate_time_periods(2024, 2024, TimePeriodType.half_year)
    halves = periods_of_type(periods, TimePeriodType.half_year)
    assert len(halves) == 2


def test_half_year_parent_is_year():
    periods = generate_time_periods(2024, 2024, TimePeriodType.half_year)
    halves = periods_of_type(periods, TimePeriodType.half_year)
    for h in halves:
        assert h["parent_code"] == "FY2024"


# ---------------------------------------------------------------------------
# Hierarchy: year > quarter > month
# ---------------------------------------------------------------------------

def test_hierarchy_year_contains_halves():
    periods = generate_time_periods(2024, 2024, TimePeriodType.month)
    halves = periods_of_type(periods, TimePeriodType.half_year)
    assert len(halves) == 2
    for h in halves:
        assert h["parent_code"] == "FY2024"


def test_hierarchy_quarters_under_correct_half():
    periods = generate_time_periods(2024, 2024, TimePeriodType.month)
    quarters = periods_of_type(periods, TimePeriodType.quarter)
    h1_quarters = [q for q in quarters if q["parent_code"] == "FY2024-H1"]
    h2_quarters = [q for q in quarters if q["parent_code"] == "FY2024-H2"]
    assert len(h1_quarters) == 2
    assert len(h2_quarters) == 2


def test_hierarchy_months_under_quarters():
    periods = generate_time_periods(2024, 2024, TimePeriodType.month)
    months = periods_of_type(periods, TimePeriodType.month)
    q1_months = [m for m in months if m["parent_code"] == "FY2024-Q1"]
    assert len(q1_months) == 3
    month_codes = sorted(m["code"] for m in q1_months)
    assert month_codes == ["2024-01", "2024-02", "2024-03"]


# ---------------------------------------------------------------------------
# Fiscal year starting in July
# ---------------------------------------------------------------------------

def test_fiscal_year_july_label():
    cal = FiscalCalendar(fiscal_year_start_month=7)
    periods = generate_time_periods(2023, 2023, TimePeriodType.year, cal)
    years = periods_of_type(periods, TimePeriodType.year)
    # FY starting July 2023 ends June 2024, so labelled FY2024
    assert any(y["code"] == "FY2024" for y in years)


def test_fiscal_year_july_start_date():
    cal = FiscalCalendar(fiscal_year_start_month=7)
    periods = generate_time_periods(2023, 2023, TimePeriodType.year, cal)
    years = periods_of_type(periods, TimePeriodType.year)
    fy = next(y for y in years if y["code"] == "FY2024")
    assert fy["start_date"] == "2023-07-01"
    assert fy["end_date"] == "2024-06-30"


def test_fiscal_year_july_quarters():
    cal = FiscalCalendar(fiscal_year_start_month=7)
    periods = generate_time_periods(2023, 2023, TimePeriodType.quarter, cal)
    quarters = periods_of_type(periods, TimePeriodType.quarter)
    fy_quarters = [q for q in quarters if q["code"].startswith("FY2024")]
    assert len(fy_quarters) == 4
    q1 = next(q for q in fy_quarters if q["code"] == "FY2024-Q1")
    # Q1 of a July-start FY covers Jul-Sep
    assert q1["start_date"] == "2023-07-01"
    assert q1["end_date"] == "2023-09-30"


def test_fiscal_year_july_months_twelve():
    cal = FiscalCalendar(fiscal_year_start_month=7)
    periods = generate_time_periods(2023, 2023, TimePeriodType.month, cal)
    months = periods_of_type(periods, TimePeriodType.month)
    # Fiscal year 2024 (Jul 2023 - Jun 2024): 12 months
    fy_months = [m for m in months if m["parent_code"] and m["parent_code"].startswith("FY2024")]
    assert len(fy_months) == 12


# ---------------------------------------------------------------------------
# Week generation
# ---------------------------------------------------------------------------

def test_weeks_are_generated_for_week_granularity():
    periods = generate_time_periods(2024, 2024, TimePeriodType.week)
    weeks = periods_of_type(periods, TimePeriodType.week)
    # There are at least 52 weeks in a year
    assert len(weeks) >= 52


def test_week_parent_is_month():
    periods = generate_time_periods(2024, 2024, TimePeriodType.week)
    weeks = periods_of_type(periods, TimePeriodType.week)
    months_codes = {p["code"] for p in periods_of_type(periods, TimePeriodType.month)}
    for w in weeks:
        assert w["parent_code"] in months_codes, (
            f"Week {w['code']} has parent {w['parent_code']} which is not a month"
        )


def test_week_dates_within_year():
    periods = generate_time_periods(2024, 2024, TimePeriodType.week)
    weeks = periods_of_type(periods, TimePeriodType.week)
    for w in weeks:
        ws = date.fromisoformat(w["start_date"])
        we = date.fromisoformat(w["end_date"])
        assert ws <= we
        assert ws.year in (2023, 2024, 2025)  # weeks can slightly overflow


# ---------------------------------------------------------------------------
# spread_value — even
# ---------------------------------------------------------------------------

def test_spread_even_twelve_months():
    months = generate_time_periods(2024, 2024, TimePeriodType.month)
    months_only = periods_of_type(months, TimePeriodType.month)
    values = spread_value(1200.0, months_only, method="even")
    assert len(values) == 12
    assert all(v == pytest.approx(100.0) for v in values)
    assert sum(values) == pytest.approx(1200.0)


def test_spread_even_exact_sum():
    periods_list = [{"start_date": "2024-01-01", "end_date": "2024-01-31"}] * 7
    values = spread_value(100.0, periods_list, method="even")
    assert sum(values) == pytest.approx(100.0)


def test_spread_even_single_period():
    p = [{"start_date": "2024-01-01", "end_date": "2024-01-31"}]
    values = spread_value(42.5, p, method="even")
    assert values == [pytest.approx(42.5)]


def test_spread_even_empty():
    values = spread_value(1000.0, [], method="even")
    assert values == []


# ---------------------------------------------------------------------------
# spread_value — proportional_to_days
# ---------------------------------------------------------------------------

def test_spread_proportional_sum():
    months = generate_time_periods(2024, 2024, TimePeriodType.month)
    months_only = periods_of_type(months, TimePeriodType.month)
    values = spread_value(1200.0, months_only, method="proportional_to_days")
    assert sum(values) == pytest.approx(1200.0)


def test_spread_proportional_feb_less_than_jan():
    months = generate_time_periods(2024, 2024, TimePeriodType.month)
    months_only = periods_of_type(months, TimePeriodType.month)
    values = spread_value(1200.0, months_only, method="proportional_to_days")
    # Jan has 31 days, Feb has 29 (2024 is leap year) — Jan should get more
    jan_val = values[0]
    feb_val = values[1]
    assert jan_val > feb_val


def test_spread_proportional_equal_length_months():
    """Two 31-day months should get equal shares."""
    p = [
        {"start_date": "2024-01-01", "end_date": "2024-01-31"},  # 31 days
        {"start_date": "2024-03-01", "end_date": "2024-03-31"},  # 31 days
    ]
    values = spread_value(620.0, p, method="proportional_to_days")
    assert values[0] == pytest.approx(310.0)
    assert values[1] == pytest.approx(310.0)


def test_spread_unknown_method_raises():
    p = [{"start_date": "2024-01-01", "end_date": "2024-01-31"}]
    with pytest.raises(ValueError, match="Unknown spread method"):
        spread_value(100.0, p, method="zigzag")


# ---------------------------------------------------------------------------
# get_period_for_date
# ---------------------------------------------------------------------------

def test_get_period_for_date_month():
    result = get_period_for_date(date(2024, 3, 15), TimePeriodType.month)
    assert result is not None
    assert result["code"] == "2024-03"


def test_get_period_for_date_quarter():
    result = get_period_for_date(date(2024, 5, 1), TimePeriodType.quarter)
    assert result is not None
    assert result["code"] == "FY2024-Q2"


def test_get_period_for_date_year():
    result = get_period_for_date(date(2024, 12, 31), TimePeriodType.year)
    assert result is not None
    assert result["code"] == "FY2024"


def test_get_period_for_date_fiscal_july():
    cal = FiscalCalendar(fiscal_year_start_month=7)
    result = get_period_for_date(date(2023, 8, 15), TimePeriodType.year, cal)
    assert result is not None
    # Aug 2023 falls in FY2024 (Jul 2023 - Jun 2024)
    assert result["code"] == "FY2024"


def test_get_period_for_date_half_year():
    result = get_period_for_date(date(2024, 9, 1), TimePeriodType.half_year)
    assert result is not None
    assert result["code"] == "FY2024-H2"


def test_get_period_for_date_week():
    result = get_period_for_date(date(2024, 1, 15), TimePeriodType.week)
    assert result is not None
    assert result["period_type"] == TimePeriodType.week
    start = date.fromisoformat(result["start_date"])
    end = date.fromisoformat(result["end_date"])
    assert start <= date(2024, 1, 15) <= end


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_no_duplicate_codes():
    periods = generate_time_periods(2022, 2024, TimePeriodType.month)
    codes = [p["code"] for p in periods]
    assert len(codes) == len(set(codes)), "Duplicate period codes found"


def test_period_start_before_end():
    periods = generate_time_periods(2024, 2024, TimePeriodType.week)
    for p in periods:
        assert p["start_date"] <= p["end_date"], (
            f"Period {p['code']}: start {p['start_date']} > end {p['end_date']}"
        )


def test_multi_year_month_count():
    periods = generate_time_periods(2023, 2025, TimePeriodType.month)
    months = periods_of_type(periods, TimePeriodType.month)
    assert len(months) == 36  # 3 years * 12 months
