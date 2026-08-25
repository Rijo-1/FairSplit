"""Tax allocation logic."""

from decimal import Decimal
from typing import Dict, List

from app.schemas.bill import AdjustmentType, BillAdjustmentSchema
from app.services.calculation.rounding import ZERO, proportional_split, to_decimal


def get_tax_total(adjustments: List[BillAdjustmentSchema]) -> Decimal:
    total = ZERO
    for adj in adjustments:
        if adj.type == AdjustmentType.TAX:
            total += to_decimal(adj.amount)
    return total


def allocate_taxes(
    tax_total: Decimal,
    taxable_subtotals: Dict[str, Decimal],
) -> Dict[str, Decimal]:
    """Allocate tax proportionally based on each participant's taxable item share."""
    if tax_total <= ZERO:
        return {pid: ZERO for pid in taxable_subtotals}

    weights = {pid: sub for pid, sub in taxable_subtotals.items() if sub > ZERO}
    if not weights:
        return {pid: ZERO for pid in taxable_subtotals}

    return proportional_split(tax_total, weights)
