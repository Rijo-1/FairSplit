"""Main calculation engine orchestrating all split logic."""

from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Set

from app.schemas.bill import (
    BillValidationResult,
    ExtractedBillSchema,
    ParticipantBreakdown,
    ServiceChargeMode,
    SplitRequestSchema,
    SplitResultSchema,
)
from app.services.calculation.allocations import allocate_items, is_consumable_item
from app.services.calculation.credits import allocate_credits
from app.services.calculation.discounts import allocate_discounts, get_discount_total
from app.services.calculation.rounding import ZERO, distribute_remainder, round_money, to_decimal
from app.services.calculation.service_charge import allocate_service_charge, get_service_charge_total
from app.services.calculation.taxes import allocate_taxes, get_tax_total


def validate_bill_totals(bill: ExtractedBillSchema, tolerance: Decimal = Decimal("1.00")) -> BillValidationResult:
    items_subtotal = sum(
        (to_decimal(i.line_total) for i in bill.items if is_consumable_item(i)),
        ZERO,
    )

    service_charge = get_service_charge_total(bill.adjustments)
    tax_total = get_tax_total(bill.adjustments)
    discount_total = get_discount_total(bill.adjustments)
    credit_total = sum((to_decimal(c.amount) for c in bill.payment_credits), ZERO)

    expected = items_subtotal + service_charge + tax_total - discount_total - credit_total
    extracted = to_decimal(bill.total)
    difference = abs(expected - extracted)

    is_valid = difference <= tolerance
    message = None
    if not is_valid:
        message = (
            f"Some numbers on this bill don't add up. "
            f"Expected ~{round_money(expected)}, found {round_money(extracted)} "
            f"(difference: {round_money(difference)})."
        )

    return BillValidationResult(
        is_valid=is_valid,
        expected_total=round_money(expected),
        extracted_total=round_money(extracted),
        difference=round_money(difference),
        tolerance=tolerance,
        message=message,
    )


def calculate_split(request: SplitRequestSchema) -> SplitResultSchema:
    bill = request.bill
    participants = request.participants
    allocations = request.allocations
    warnings: List[str] = []

    # Build allocation lookup
    allocations_by_participant: Dict[str, Set[str]] = defaultdict(set)
    for alloc in allocations:
        allocations_by_participant[alloc.participant_id].add(alloc.bill_item_id)

    participant_subtotals, item_details, taxable_subtotals = allocate_items(
        bill.items, participants, allocations
    )

    discount_total = get_discount_total(bill.adjustments)
    discount_shares = allocate_discounts(
        discount_total,
        participant_subtotals,
        bill.adjustments,
        bill.items,
        {pid: ids for pid, ids in allocations_by_participant.items()},
    )

    tax_total = get_tax_total(bill.adjustments)
    tax_shares = allocate_taxes(tax_total, taxable_subtotals)

    service_charge_total = get_service_charge_total(bill.adjustments)
    service_shares = allocate_service_charge(
        service_charge_total,
        participant_subtotals,
        request.service_charge_mode,
    )

    pre_credit_totals: Dict[str, Decimal] = {}
    for p in participants:
        pid = p.id
        pre_credit = (
            participant_subtotals.get(pid, ZERO)
            - discount_shares.get(pid, ZERO)
            + tax_shares.get(pid, ZERO)
            + service_shares.get(pid, ZERO)
        )
        pre_credit_totals[pid] = max(pre_credit, ZERO)

    all_credits = list(bill.payment_credits) + list(request.payment_credits)
    credit_benefits = allocate_credits(all_credits, pre_credit_totals)
    total_credit_amount = sum((to_decimal(c.amount) for c in all_credits), ZERO)

    raw_finals: Dict[str, Decimal] = {}
    rounding_adjustments: Dict[str, Decimal] = {p.id: ZERO for p in participants}

    for p in participants:
        pid = p.id
        raw = pre_credit_totals.get(pid, ZERO) - credit_benefits.get(pid, ZERO)
        raw_finals[pid] = max(raw, ZERO)

    # Net amount the group must settle in cash after external credits applied
    target_total = max(to_decimal(bill.total) - total_credit_amount, ZERO)
    final_amounts = distribute_remainder(raw_finals, target_total)

    # Compute rounding adjustments
    for pid in final_amounts:
        rounded_raw = round_money(raw_finals.get(pid, ZERO))
        rounding_adjustments[pid] = final_amounts[pid] - rounded_raw

    participant_map = {p.id: p.name for p in participants}
    breakdowns: List[ParticipantBreakdown] = []

    for p in participants:
        pid = p.id
        breakdowns.append(ParticipantBreakdown(
            participant_id=pid,
            participant_name=participant_map[pid],
            items_subtotal=round_money(participant_subtotals.get(pid, ZERO)),
            discount_share=round_money(discount_shares.get(pid, ZERO)),
            tax_share=round_money(tax_shares.get(pid, ZERO)),
            service_charge_share=round_money(service_shares.get(pid, ZERO)),
            credit_share=round_money(credit_benefits.get(pid, ZERO)),
            rounding_adjustment=round_money(rounding_adjustments.get(pid, ZERO)),
            final_amount=final_amounts[pid],
            item_details=item_details.get(pid, []),
        ))

    computed_total = sum((b.final_amount for b in breakdowns), ZERO)
    if computed_total != target_total:
        warnings.append(f"Settlement total mismatch: {computed_total} vs {target_total}")

    return SplitResultSchema(
        grand_total=target_total,
        participants=breakdowns,
        summary={
            "items_subtotal": float(sum(participant_subtotals.values(), ZERO)),
            "discount_total": float(discount_total),
            "tax_total": float(tax_total),
            "service_charge_total": float(service_charge_total),
            "credit_total": float(total_credit_amount),
            "bill_total": float(to_decimal(bill.total)),
            "participant_count": len(participants),
            "item_count": len([i for i in bill.items if is_consumable_item(i)]),
        },
        warnings=warnings,
    )
