"""
Pure Python (no DB) time calendar engine for F009.

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
        week_start_day: 0=Monday … 6=Sunday (ISO default: 0)
    """

    def __init__(
        self,
        fiscal_year_start_month: int = 1,
        week_start_day: int = 0,
    ) -> None:
        if not 1 <= fiscal_year_start_month <= 12:
            raise ValueError("fiscal_year_start_month must be 1-12")
        if not 0 <= week_start_day <= 6:
            raise ValueError("week_start_day must be 0-6")
        self.fiscal_year_start_month = fiscal_year_start_month
        self.week_start_day = week_start_day


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

                    if granularity == TimePeriodType.month:
                        continue

                    # --- Weeks ---
                    weeks = _weeks_in_month(m_year, m_month, fiscal_calendar.week_start_day)
                    for w_num, (w_start, w_end) in enumerate(weeks, start=1):
                        # ISO week number of the week that contains w_start
                        iso_week = w_start.isocalendar()[1]
                        w_code = f"{m_year}-W{iso_week:02d}"
                        # avoid duplicate codes when a week spans two months
                        # use a unique code if already seen
                        if w_code in seen_codes:
                            w_code = f"{m_code}-W{w_num}"
                        w_name = f"Week {iso_week} {m_year}"
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
