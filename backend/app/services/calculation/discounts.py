"""Discount allocation logic."""

from decimal import Decimal
from typing import Dict, List

from app.schemas.bill import AdjustmentType, BillAdjustmentSchema, BillItemSchema, ItemCategory
from app.services.calculation.allocations import FOOD_CATEGORIES, is_consumable_item
from app.services.calculation.rounding import ZERO, proportional_split, to_decimal


def get_discount_total(adjustments: List[BillAdjustmentSchema]) -> Decimal:
    total = ZERO
    for adj in adjustments:
        if adj.type in {AdjustmentType.DISCOUNT, AdjustmentType.COUPON}:
            total += to_decimal(adj.amount)
    return total


def allocate_discounts(
    discount_total: Decimal,
    participant_subtotals: Dict[str, Decimal],
    adjustments: List[BillAdjustmentSchema],
    items: List[BillItemSchema],
    allocations_item_ids: Dict[str, set],
) -> Dict[str, Decimal]:
    """Allocate discount proportionally based on eligible item subtotals."""
    if discount_total <= ZERO:
        return {pid: ZERO for pid in participant_subtotals}

    eligible_subtotals = _eligible_subtotals(
        participant_subtotals, adjustments, items, allocations_item_ids
    )
    return proportional_split(discount_total, eligible_subtotals)


def _eligible_subtotals(
    participant_subtotals: Dict[str, Decimal],
    adjustments: List[BillAdjustmentSchema],
    items: List[BillItemSchema],
    allocations_item_ids: Dict[str, set],
) -> Dict[str, Decimal]:
    """Determine eligible subtotals for discount. Default: proportional to all consumables."""
    scoped_adjustments = [a for a in adjustments if a.type in {AdjustmentType.DISCOUNT, AdjustmentType.COUPON}]

    if not scoped_adjustments or all(a.scope == "all" for a in scoped_adjustments):
        return {pid: sub for pid, sub in participant_subtotals.items() if sub > ZERO}

    # Scope-specific: only items matching scope participate
    eligible_categories = set()
    for adj in scoped_adjustments:
        if adj.scope == "food":
            eligible_categories.update(FOOD_CATEGORIES)
        elif adj.scope == "alcohol":
            eligible_categories.add(ItemCategory.ALCOHOL)

    if not eligible_categories:
        return {pid: sub for pid, sub in participant_subtotals.items() if sub > ZERO}

    item_category_map = {i.id: i.category for i in items if is_consumable_item(i)}
    eligible = {pid: ZERO for pid in participant_subtotals}

    for pid, item_ids in allocations_item_ids.items():
        for item_id in item_ids:
            cat = item_category_map.get(item_id)
            if cat in eligible_categories:
                # Re-derive from subtotals proportionally is complex; use full subtotal if any eligible
                eligible[pid] = participant_subtotals.get(pid, ZERO)
                break

    if sum(eligible.values(), ZERO) == ZERO:
        return {pid: sub for pid, sub in participant_subtotals.items() if sub > ZERO}

    return eligible
