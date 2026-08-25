"""Decimal rounding utilities for financial calculations."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Tuple


TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


def to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_money(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def distribute_remainder(
    amounts: Dict[str, Decimal],
    target_total: Decimal,
) -> Dict[str, Decimal]:
    """Distribute rounding remainder deterministically to largest fractional parts."""
    rounded = {k: round_money(v) for k, v in amounts.items()}
    current_total = sum(rounded.values(), ZERO)
    remainder = round_money(target_total - current_total)

    if remainder == ZERO or not rounded:
        return rounded

    # Sort by fractional part descending, then by key for determinism
    fractional_parts = sorted(
        rounded.keys(),
        key=lambda k: (amounts[k] - rounded[k], k),
        reverse=True,
    )

    step = Decimal("0.01") if remainder > ZERO else Decimal("-0.01")
    steps_needed = int(abs(remainder / step))
    for i in range(steps_needed):
        key = fractional_parts[i % len(fractional_parts)]
        rounded[key] = round_money(rounded[key] + step)

    return rounded


def proportional_split(
    total: Decimal,
    weights: Dict[str, Decimal],
) -> Dict[str, Decimal]:
    """Split total proportionally by weights. Returns zero for zero-weight keys."""
    weight_sum = sum(weights.values(), ZERO)
    if weight_sum == ZERO:
        if not weights:
            return {}
        equal_share = total / len(weights)
        return distribute_remainder({k: equal_share for k in weights}, total)

    raw = {k: (total * w / weight_sum) for k, w in weights.items()}
    return distribute_remainder(raw, total)


def equal_split(total: Decimal, keys: List[str]) -> Dict[str, Decimal]:
    if not keys:
        return {}
    share = total / len(keys)
    return distribute_remainder({k: share for k in keys}, total)
