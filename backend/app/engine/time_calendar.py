"""
Pure Python (no DB) time calendar engine.

Provides:
- TimePeriodType enum
- FiscalCalendar configuration class
- generate_time_periods() — build hierarchical time period dicts
- get_period_for_date() — find which period a date falls in
- spread_value() — distribute a value across periods
"""

import enum
from datetime import date, timedelta
from typing import Any, Dict, List, Optional


class WeekPattern(str, enum.Enum):
    iso = "iso"
    custom = "custom"


class RetailCalendarPattern(str, enum.Enum):
    standard = "standard"
    four_four_five = "4-4-5"
    four_five_four = "4-5-4"
    five_four_four = "5-4-4"


class TimePeriodType(str, enum.Enum):
    week = "week"
    month = "month"
    quarter = "quarter"
    half_year = "half_year"
    year = "year"


class FiscalCalendar:
    """Configures fiscal year behaviour.

    Args:
        fiscal_year_start_month: 1-12 (1 = January, 7 = July, etc.)
        week_start_day: 0=Monday … 6=Sunday
        week_pattern: "iso" (full ISO weeks) or "custom" (week_start_day based)
        retail_pattern: "standard", "4-4-5", "4-5-4", or "5-4-4"
    """

    def __init__(
        self,
        fiscal_year_start_month: int = 1,
        week_start_day: int = 0,
        week_pattern: WeekPattern = WeekPattern.iso,
        retail_pattern: RetailCalendarPattern = RetailCalendarPattern.standard,
    ) -> None:
        if not 1 <= fiscal_year_start_month <= 12:
            raise ValueError("fiscal_year_start_month must be 1-12")
        if not 0 <= week_start_day <= 6:
            raise ValueError("week_start_day must be 0-6")
        try:
            normalized_week_pattern = WeekPattern(week_pattern)
        except ValueError as exc:
            raise ValueError("week_pattern must be 'iso' or 'custom'") from exc
        try:
            normalized_retail_pattern = RetailCalendarPattern(retail_pattern)
        except ValueError as exc:
            raise ValueError(
                "retail_pattern must be one of: standard, 4-4-5, 4-5-4, 5-4-4"
            ) from exc
        self.fiscal_year_start_month = fiscal_year_start_month
        self.week_start_day = week_start_day
        self.week_pattern = normalized_week_pattern
        self.retail_pattern = normalized_retail_pattern


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fiscal_year_label(calendar_year: int, fiscal_year_start_month: int) -> str:
    """Return the fiscal year label for a given calendar year.

    If the fiscal year starts in January the fiscal year equals the calendar
    year.  Otherwise the fiscal year is labelled by the year in which it
    *ends* (e.g. a fiscal year starting July 2023 ends in June 2024, so it
    is labelled FY2024).
    """
    if fiscal_year_start_month == 1:
        return f"FY{calendar_year}"
    return f"FY{calendar_year + 1}"


def _month_name(month: int) -> str:
    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    return months[month - 1]


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return (date(year + 1, 1, 1) - date(year, 12, 1)).days
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _month_end(year: int, month: int) -> date:
    return date(year, month, _days_in_month(year, month))


def _fiscal_month_sequence(fiscal_year_start_month: int) -> List[tuple]:
    """Return ordered list of (calendar_year_offset, month) for a fiscal year.

    fiscal_year_start_month=1  → [(0,1),(0,2),…,(0,12)]
    fiscal_year_start_month=7  → [(0,7),(0,8),…,(0,12),(1,1),…,(1,6)]

    year_offset is added to the *start* calendar year to get the actual year.
    """
    seq: List[tuple] = []
    for i in range(12):
        m = (fiscal_year_start_month - 1 + i) % 12 + 1
        offset = (fiscal_year_start_month - 1 + i) // 12
        seq.append((offset, m))
    return seq


def _retail_month_week_pattern(
    retail_pattern: RetailCalendarPattern,
) -> Optional[List[int]]:
    if retail_pattern == RetailCalendarPattern.four_four_five:
        return [4, 4, 5] * 4
    if retail_pattern == RetailCalendarPattern.four_five_four:
        return [4, 5, 4] * 4
    if retail_pattern == RetailCalendarPattern.five_four_four:
        return [5, 4, 4] * 4
    return None


# ---------------------------------------------------------------------------
# Period generation
# ---------------------------------------------------------------------------

def generate_time_periods(
    start_year: int,
    end_year: int,
    granularity: TimePeriodType,
    fiscal_calendar: Optional[FiscalCalendar] = None,
) -> List[Dict[str, Any]]:
    """Generate time period dicts for the given range and granularity.

    Returns a flat list of dicts ordered from coarsest (year) to finest
    (week / month).  Each dict contains:
        id            – unique string identifier  e.g. "FY2024", "2024-Q1"
        name          – human-readable label
        code          – short code (same as id)
        start_date    – ISO date string
        end_date      – ISO date string
        parent_code   – code of the parent period, or None for top-level
        period_type   – TimePeriodType value (string)

    The hierarchy for granularity=month  is  year > half > quarter > month
    The hierarchy for granularity=quarter is year > half > quarter
    The hierarchy for granularity=half_year is year > half_year
    The hierarchy for granularity=year is year
    The hierarchy for granularity=week  is  year > half > quarter > month > week
    """
    if fiscal_calendar is None:
        fiscal_calendar = FiscalCalendar()

    if fiscal_calendar.retail_pattern != RetailCalendarPattern.standard:
        return _generate_retail_time_periods(
            start_year=start_year,
            end_year=end_year,
            granularity=granularity,
            fiscal_calendar=fiscal_calendar,
        )

    periods: List[Dict[str, Any]] = []
    seen_codes: set = set()

    def _add(p: Dict[str, Any]) -> None:
        if p["code"] not in seen_codes:
            seen_codes.add(p["code"])
            periods.append(p)

    for cal_year in range(start_year, end_year + 1):
        fy_label = _fiscal_year_label(cal_year, fiscal_calendar.fiscal_year_start_month)
        fy_code = fy_label

        seq = _fiscal_month_sequence(fiscal_calendar.fiscal_year_start_month)
        # seq[i] = (year_offset, month)
        months_cal = [(cal_year + offset, month) for offset, month in seq]
        fy_start = _month_start(months_cal[0][0], months_cal[0][1])
        fy_end = _month_end(months_cal[11][0], months_cal[11][1])
        month_meta: List[Dict[str, Any]] = []

        # --- Year ---
        year_period: Dict[str, Any] = {
            "id": fy_code,
            "name": fy_label,
            "code": fy_code,
            "start_date": fy_start.isoformat(),
            "end_date": fy_end.isoformat(),
            "parent_code": None,
            "period_type": TimePeriodType.year,
        }
        _add(year_period)

        if granularity == TimePeriodType.year:
            continue

        # --- Halves (H1 = months 0-5, H2 = months 6-11 of fiscal year) ---
        for h_idx in range(2):
            h_months = months_cal[h_idx * 6:(h_idx + 1) * 6]
            h_start = _month_start(h_months[0][0], h_months[0][1])
            h_end = _month_end(h_months[5][0], h_months[5][1])
            h_code = f"{fy_code}-H{h_idx + 1}"
            h_name = f"{fy_label} H{h_idx + 1}"
            half_period: Dict[str, Any] = {
                "id": h_code,
                "name": h_name,
                "code": h_code,
                "start_date": h_start.isoformat(),
                "end_date": h_end.isoformat(),
                "parent_code": fy_code,
                "period_type": TimePeriodType.half_year,
            }
            _add(half_period)

            if granularity == TimePeriodType.half_year:
                continue

            # --- Quarters (Q1-Q4 within fiscal year) ---
            for q_offset in range(2):
                q_idx = h_idx * 2 + q_offset  # 0-3
                q_months = months_cal[q_idx * 3:(q_idx + 1) * 3]
                q_start = _month_start(q_months[0][0], q_months[0][1])
                q_end = _month_end(q_months[2][0], q_months[2][1])
                q_code = f"{fy_code}-Q{q_idx + 1}"
                q_name = f"{fy_label} Q{q_idx + 1}"
                quarter_period: Dict[str, Any] = {
                    "id": q_code,
                    "name": q_name,
                    "code": q_code,
                    "start_date": q_start.isoformat(),
                    "end_date": q_end.isoformat(),
                    "parent_code": h_code,
                    "period_type": TimePeriodType.quarter,
                }
                _add(quarter_period)

                if granularity == TimePeriodType.quarter:
                    continue

                # --- Months ---
                for m_offset in range(3):
                    m_idx = q_idx * 3 + m_offset
                    m_year, m_month = months_cal[m_idx]
                    m_start = _month_start(m_year, m_month)
                    m_end = _month_end(m_year, m_month)
                    m_code = f"{m_year}-{m_month:02d}"
                    m_name = f"{_month_name(m_month)} {m_year}"
                    month_period: Dict[str, Any] = {
                        "id": m_code,
                        "name": m_name,
                        "code": m_code,
                        "start_date": m_start.isoformat(),
                        "end_date": m_end.isoformat(),
                        "parent_code": q_code,
                        "period_type": TimePeriodType.month,
                    }
                    _add(month_period)
                    month_meta.append(
                        {
                            "year": m_year,
                            "month": m_month,
                            "code": m_code,
                            "name": m_name,
                        }
                    )

        if granularity == TimePeriodType.month:
            continue

        # --- Weeks ---
        if fiscal_calendar.week_pattern == WeekPattern.iso:
            month_codes = {m["code"] for m in month_meta}
            for w_start, w_end in _iso_weeks_in_fiscal_year(fy_start, fy_end):
                iso_year, iso_week, _ = w_start.isocalendar()
                w_code = f"{iso_year}-W{iso_week:02d}"
                if w_code in seen_codes:
                    continue
                parent_hint = max(w_start, fy_start)
                if parent_hint > fy_end:
                    parent_hint = fy_end
                parent_code = f"{parent_hint.year}-{parent_hint.month:02d}"
                if parent_code not in month_codes and len(month_meta) > 0:
                    parent_code = month_meta[0]["code"]
                week_period: Dict[str, Any] = {
                    "id": w_code,
                    "name": f"Week {iso_week} {iso_year}",
                    "code": w_code,
                    "start_date": w_start.isoformat(),
                    "end_date": w_end.isoformat(),
                    "parent_code": parent_code,
                    "period_type": TimePeriodType.week,
                }
                _add(week_period)
        else:
            for month in month_meta:
                m_year = int(month["year"])
                m_month = int(month["month"])
                m_code = str(month["code"])
                m_name = str(month["name"])
                weeks = _weeks_in_month(m_year, m_month, fiscal_calendar.week_start_day)
                for w_num, (w_start, w_end) in enumerate(weeks, start=1):
                    iso_week = w_start.isocalendar()[1]
                    w_code = f"{w_start.year}-W{iso_week:02d}"
                    if w_code in seen_codes:
                        w_code = f"{m_code}-W{w_num}"
                    w_name = f"Week {iso_week} {w_start.year}"
                    if w_code.count("-W") > 1:
                        w_name = f"{m_name} Wk{w_num}"
                    week_period: Dict[str, Any] = {
                        "id": w_code,
                        "name": w_name,
                        "code": w_code,
                        "start_date": w_start.isoformat(),
                        "end_date": w_end.isoformat(),
                        "parent_code": m_code,
                        "period_type": TimePeriodType.week,
                    }
                    _add(week_period)

    return periods


def _generate_retail_time_periods(
    start_year: int,
    end_year: int,
    granularity: TimePeriodType,
    fiscal_calendar: FiscalCalendar,
) -> List[Dict[str, Any]]:
    periods: List[Dict[str, Any]] = []
    seen_codes: set = set()

    def _add(p: Dict[str, Any]) -> None:
        if p["code"] not in seen_codes:
            seen_codes.add(p["code"])
            periods.append(p)

    month_weeks = _retail_month_week_pattern(fiscal_calendar.retail_pattern)
    if month_weeks is None:
        return periods

    for cal_year in range(start_year, end_year + 1):
        fy_label = _fiscal_year_label(cal_year, fiscal_calendar.fiscal_year_start_month)
        fy_code = fy_label
        fy_start = date(cal_year, fiscal_calendar.fiscal_year_start_month, 1)

        month_periods: List[Dict[str, Any]] = []
        cursor = fy_start
        for idx, weeks in enumerate(month_weeks, start=1):
            period_start = cursor
            period_end = period_start + timedelta(days=(weeks * 7) - 1)
            quarter_number = ((idx - 1) // 3) + 1
            month_periods.append(
                {
                    "index": idx,
                    "code": f"{fy_code}-P{idx:02d}",
                    "name": f"{fy_label} P{idx:02d}",
                    "start": period_start,
                    "end": period_end,
                    "quarter": quarter_number,
                    "weeks": weeks,
                }
            )
            cursor = period_end + timedelta(days=1)

        fy_end = month_periods[-1]["end"]

        year_period: Dict[str, Any] = {
            "id": fy_code,
            "name": fy_label,
            "code": fy_code,
            "start_date": fy_start.isoformat(),
            "end_date": fy_end.isoformat(),
            "parent_code": None,
            "period_type": TimePeriodType.year,
        }
        _add(year_period)
        if granularity == TimePeriodType.year:
            continue

        halves = [(1, month_periods[:6]), (2, month_periods[6:])]
        for half_number, half_months in halves:
            half_code = f"{fy_code}-H{half_number}"
            half_period: Dict[str, Any] = {
                "id": half_code,
                "name": f"{fy_label} H{half_number}",
                "code": half_code,
                "start_date": half_months[0]["start"].isoformat(),
                "end_date": half_months[-1]["end"].isoformat(),
                "parent_code": fy_code,
                "period_type": TimePeriodType.half_year,
            }
            _add(half_period)

        if granularity == TimePeriodType.half_year:
            continue

        quarter_to_half = {1: 1, 2: 1, 3: 2, 4: 2}
        quarter_periods: Dict[int, Dict[str, Any]] = {}
        for q_number in range(1, 5):
            q_months = month_periods[(q_number - 1) * 3:q_number * 3]
            q_code = f"{fy_code}-Q{q_number}"
            q_period: Dict[str, Any] = {
                "id": q_code,
                "name": f"{fy_label} Q{q_number}",
                "code": q_code,
                "start_date": q_months[0]["start"].isoformat(),
                "end_date": q_months[-1]["end"].isoformat(),
                "parent_code": f"{fy_code}-H{quarter_to_half[q_number]}",
                "period_type": TimePeriodType.quarter,
            }
            quarter_periods[q_number] = q_period
            _add(q_period)

        if granularity == TimePeriodType.quarter:
            continue

        for month in month_periods:
            m_period: Dict[str, Any] = {
                "id": month["code"],
                "name": month["name"],
                "code": month["code"],
                "start_date": month["start"].isoformat(),
                "end_date": month["end"].isoformat(),
                "parent_code": quarter_periods[int(month["quarter"])]["code"],
                "period_type": TimePeriodType.month,
            }
            _add(m_period)

        if granularity == TimePeriodType.month:
            continue

        week_number = 1
        for month in month_periods:
            for week_offset in range(int(month["weeks"])):
                week_start = month["start"] + timedelta(days=week_offset * 7)
                week_end = week_start + timedelta(days=6)
                week_code = f"{fy_code}-W{week_number:02d}"
                week_period: Dict[str, Any] = {
                    "id": week_code,
                    "name": f"{fy_label} W{week_number:02d}",
                    "code": week_code,
                    "start_date": week_start.isoformat(),
                    "end_date": week_end.isoformat(),
                    "parent_code": month["code"],
                    "period_type": TimePeriodType.week,
                }
                _add(week_period)
                week_number += 1

    return periods


def _iso_weeks_in_fiscal_year(
    fiscal_year_start: date,
    fiscal_year_end: date,
) -> List[tuple]:
    weeks: List[tuple] = []
    current = fiscal_year_start - timedelta(days=fiscal_year_start.weekday())
    while current <= fiscal_year_end:
        week_end = current + timedelta(days=6)
        if week_end >= fiscal_year_start:
            weeks.append((current, week_end))
        current = current + timedelta(days=7)
    return weeks


def _weeks_in_month(
    year: int,
    month: int,
    week_start_day: int,
) -> List[tuple]:
    """Return list of (start_date, end_date) for each week that starts in month."""
    weeks: List[tuple] = []
    d = _month_start(year, month)
    month_end = _month_end(year, month)

    # Advance to the first occurrence of week_start_day on or after d
    days_ahead = (week_start_day - d.weekday()) % 7
    if days_ahead > 0:
        # There's a partial first week — include it starting from month start
        partial_end = d + timedelta(days=days_ahead - 1)
        weeks.append((d, partial_end))
        d = d + timedelta(days=days_ahead)

    while d <= month_end:
        w_end = d + timedelta(days=6)
        if w_end > month_end:
            w_end = month_end
        weeks.append((d, w_end))
        d = d + timedelta(days=7)

    return weeks


# ---------------------------------------------------------------------------
# Period lookup
# ---------------------------------------------------------------------------

def get_period_for_date(
    target_date: date,
    granularity: TimePeriodType,
    fiscal_calendar: Optional[FiscalCalendar] = None,
) -> Optional[Dict[str, Any]]:
    """Return the period dict that contains target_date for the given granularity.

    Searches one year back and forward around target_date.
    """
    if fiscal_calendar is None:
        fiscal_calendar = FiscalCalendar()

    search_year = target_date.year
    periods = generate_time_periods(
        search_year - 1, search_year + 1, granularity, fiscal_calendar
    )
    for p in periods:
        if p["period_type"] != granularity:
            continue
        p_start = date.fromisoformat(p["start_date"])
        p_end = date.fromisoformat(p["end_date"])
        if p_start <= target_date <= p_end:
            return p
    return None


# ---------------------------------------------------------------------------
# Value spreading
# ---------------------------------------------------------------------------

def spread_value(
    total: float,
    periods: List[Dict[str, Any]],
    method: str = "even",
) -> List[float]:
    """Spread *total* across periods.

    Args:
        total: The aggregate value to distribute.
        periods: List of period dicts (must have start_date / end_date for
                 proportional_to_days method).
        method: "even" or "proportional_to_days"

    Returns:
        List of floats, one per period, summing to total.
    """
    n = len(periods)
    if n == 0:
        return []

    if method == "even":
        base = total / n
        values = [base] * n
        # Distribute rounding remainder to last period
        remainder = total - sum(values[:-1])
        values[-1] = remainder
        return values

    if method == "proportional_to_days":
        day_counts: List[int] = []
        for p in periods:
            p_start = date.fromisoformat(p["start_date"])
            p_end = date.fromisoformat(p["end_date"])
            day_counts.append((p_end - p_start).days + 1)
        total_days = sum(day_counts)
        if total_days == 0:
            return [0.0] * n
        values = [total * (dc / total_days) for dc in day_counts]
        # Adjust last to fix floating-point drift
        values[-1] = total - sum(values[:-1])
        return values

    raise ValueError(f"Unknown spread method: {method!r}. Use 'even' or 'proportional_to_days'.")
