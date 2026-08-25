"""Item-level allocation logic."""

from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Tuple

from app.schemas.bill import (
    AllocationType,
    BillItemSchema,
    ItemAllocationSchema,
    ItemCategory,
    ParticipantSchema,
)
from app.services.calculation.rounding import ZERO, distribute_remainder, proportional_split, round_money, to_decimal


FOOD_CATEGORIES = {
    ItemCategory.VEG_FOOD,
    ItemCategory.NON_VEG_FOOD,
    ItemCategory.VEGAN_FOOD,
    ItemCategory.DESSERT,
    ItemCategory.SIDE,
    ItemCategory.STARTER,
    ItemCategory.MAIN_COURSE,
    ItemCategory.SHARED_FOOD,
    ItemCategory.OTHER,
}


def is_consumable_item(item: BillItemSchema) -> bool:
    return item.category not in {
        ItemCategory.TAX,
        ItemCategory.SERVICE_CHARGE,
        ItemCategory.DISCOUNT,
        ItemCategory.COUPON,
        ItemCategory.PAYMENT_CREDIT,
    }


def allocate_items(
    items: List[BillItemSchema],
    participants: List[ParticipantSchema],
    allocations: List[ItemAllocationSchema],
) -> Tuple[Dict[str, Decimal], Dict[str, List[dict]], Dict[str, Decimal]]:
    """
    Returns:
        participant_subtotals: per-participant item cost
        item_details: per-participant breakdown of items
        taxable_subtotals: per-participant taxable amount for tax allocation
    """
    participant_ids = {p.id for p in participants}
    participant_names = {p.id: p.name for p in participants}
    consumable_items = [i for i in items if is_consumable_item(i)]

    subtotals: Dict[str, Decimal] = {p.id: ZERO for p in participants}
    taxable_subtotals: Dict[str, Decimal] = {p.id: ZERO for p in participants}
    item_details: Dict[str, List[dict]] = {p.id: [] for p in participants}

    allocations_by_item: Dict[str, List[ItemAllocationSchema]] = defaultdict(list)
    for alloc in allocations:
        allocations_by_item[alloc.bill_item_id].append(alloc)

    for item in consumable_items:
        item_allocs = allocations_by_item.get(item.id, [])
        if not item_allocs:
            continue

        item_total = to_decimal(item.line_total)
        shares = _compute_item_shares(item, item_allocs, participant_ids)

        for pid, share in shares.items():
            if share <= ZERO:
                continue
            subtotals[pid] = subtotals.get(pid, ZERO) + share
            if item.taxable:
                taxable_subtotals[pid] = taxable_subtotals.get(pid, ZERO) + share
            item_details[pid].append({
                "item_id": item.id,
                "name": item.name,
                "category": item.category.value,
                "amount": float(round_money(share)),
            })

    return subtotals, item_details, taxable_subtotals


def _compute_item_shares(
    item: BillItemSchema,
    allocations: List[ItemAllocationSchema],
    valid_participant_ids: set,
) -> Dict[str, Decimal]:
    item_total = to_decimal(item.line_total)
    filtered = [a for a in allocations if a.participant_id in valid_participant_ids]

    if not filtered:
        return {}

    alloc_type = filtered[0].allocation_type

    if alloc_type == AllocationType.PERCENTAGE:
        weights = {a.participant_id: to_decimal(a.percentage or ZERO) for a in filtered}
        pct_sum = sum(weights.values(), ZERO)
        if pct_sum == ZERO:
            return equal_item_split(item_total, [a.participant_id for a in filtered])
        return proportional_split(item_total, weights)

    if alloc_type == AllocationType.QUANTITY:
        quantities = {a.participant_id: to_decimal(a.quantity or ZERO) for a in filtered}
        qty_sum = sum(quantities.values(), ZERO)
        if qty_sum == ZERO:
            return equal_item_split(item_total, [a.participant_id for a in filtered])
        return proportional_split(item_total, quantities)

    return equal_item_split(item_total, [a.participant_id for a in filtered])


def equal_item_split(total: Decimal, participant_ids: List[str]) -> Dict[str, Decimal]:
    if not participant_ids:
        return {}
    share = total / len(participant_ids)
    raw = {pid: share for pid in participant_ids}
    return distribute_remainder(raw, total)


def get_alcohol_participant_ids(
    items: List[BillItemSchema],
    allocations: List[ItemAllocationSchema],
) -> set:
    alcohol_item_ids = {i.id for i in items if i.category == ItemCategory.ALCOHOL}
    return {a.participant_id for a in allocations if a.bill_item_id in alcohol_item_ids}
