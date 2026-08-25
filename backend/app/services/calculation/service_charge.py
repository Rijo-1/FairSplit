"""Service charge allocation logic."""

from decimal import Decimal
from typing import Dict, List

from app.schemas.bill import AdjustmentType, BillAdjustmentSchema, ServiceChargeMode
from app.services.calculation.rounding import ZERO, equal_split, proportional_split, to_decimal


def get_service_charge_total(adjustments: List[BillAdjustmentSchema]) -> Decimal:
    total = ZERO
    for adj in adjustments:
        if adj.type == AdjustmentType.SERVICE_CHARGE:
            total += to_decimal(adj.amount)
    return total


def allocate_service_charge(
    service_charge_total: Decimal,
    participant_subtotals: Dict[str, Decimal],
    mode: ServiceChargeMode = ServiceChargeMode.PROPORTIONAL,
) -> Dict[str, Decimal]:
    if service_charge_total <= ZERO:
        return {pid: ZERO for pid in participant_subtotals}

    active = [pid for pid, sub in participant_subtotals.items() if sub > ZERO]
    if not active:
        active = list(participant_subtotals.keys())

    if mode == ServiceChargeMode.EQUAL:
        return equal_split(service_charge_total, active)

    weights = {pid: participant_subtotals.get(pid, ZERO) for pid in active}
    return proportional_split(service_charge_total, weights)
