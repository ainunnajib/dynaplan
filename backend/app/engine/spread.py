"""
Pure engine functions for top-down spread and bottom-up aggregation.
No database dependencies — only plain Python.
"""
import enum
from typing import List, Optional


class SpreadMethod(str, enum.Enum):
    even = "even"
    proportional = "proportional"
    manual = "manual"
    weighted = "weighted"


def spread_value(
    total: float,
    member_count: int,
    method: SpreadMethod,
    weights: Optional[List[float]] = None,
    existing_values: Optional[List[float]] = None,
) -> List[float]:
    """Distribute a total across members using the given method.

    Args:
        total: The total value to distribute.
        member_count: Number of target members to distribute to.
        method: SpreadMethod enum value.
        weights: For 'weighted' method — a list of weight values (same length as member_count).
        existing_values: For 'proportional' method — current values used as proportions.

    Returns:
        A list of distributed values with length == member_count.

    Raises:
        ValueError: On invalid inputs (wrong list lengths, etc.).
    """
    if member_count <= 0:
        return []

    if method == SpreadMethod.even:
        share = total / member_count
        return [share] * member_count

    if method == SpreadMethod.proportional:
        if existing_values is None or len(existing_values) == 0:
            # Fallback to even when no existing values provided
            share = total / member_count
            return [share] * member_count
        if len(existing_values) != member_count:
            raise ValueError(
                f"existing_values length {len(existing_values)} "
                f"does not match member_count {member_count}"
            )
        proportions = compute_proportions(existing_values)
        return [total * p for p in proportions]

    if method == SpreadMethod.manual:
        # Return existing values as-is; no auto-spread
        if existing_values is None:
            return [0.0] * member_count
        if len(existing_values) != member_count:
            raise ValueError(
                f"existing_values length {len(existing_values)} "
                f"does not match member_count {member_count}"
            )
        return list(existing_values)

    if method == SpreadMethod.weighted:
        if weights is None or len(weights) == 0:
            # Fallback to even when no weights provided
            share = total / member_count
            return [share] * member_count
        if len(weights) != member_count:
            raise ValueError(
                f"weights length {len(weights)} "
                f"does not match member_count {member_count}"
            )
        weight_total = sum(weights)
        if weight_total == 0:
            # All weights zero — fallback to even
            share = total / member_count
            return [share] * member_count
        return [total * (w / weight_total) for w in weights]

    raise ValueError(f"Unknown spread method: {method}")


def aggregate_values(values: List[float], method: str) -> float:
    """Aggregate a list of numeric values using the given method.

    Args:
        values: List of numeric values to aggregate.
        method: One of 'sum', 'average', 'min', 'max', 'count', 'first', 'last'.

    Returns:
        The aggregated scalar value.

    Raises:
        ValueError: On unsupported method.
    """
    if not values:
        if method == "count":
            return 0.0
        return 0.0

    if method == "sum":
        return sum(values)
    if method == "average":
        return sum(values) / len(values)
    if method == "min":
        return min(values)
    if method == "max":
        return max(values)
    if method == "count":
        return float(len(values))
    if method == "first":
        return values[0]
    if method == "last":
        return values[-1]

    raise ValueError(f"Unknown aggregation method: {method}")


def compute_proportions(values: List[float]) -> List[float]:
    """Compute proportion of each value relative to the total.

    If total is zero (all zeros or empty), returns an even distribution.

    Args:
        values: List of numeric values.

    Returns:
        List of proportions (each in [0, 1]) that sum to 1.0.
    """
    if not values:
        return []
    total = sum(abs(v) for v in values)
    if total == 0:
        # Even distribution fallback
        even = 1.0 / len(values)
        return [even] * len(values)
    return [abs(v) / total for v in values]
