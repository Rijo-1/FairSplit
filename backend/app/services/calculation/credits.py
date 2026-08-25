"""Payment credit allocation logic."""

from decimal import Decimal
from typing import Dict, List, Optional

from app.schemas.bill import CreditAllocationMode, PaymentCreditSchema
from app.services.calculation.rounding import ZERO, equal_split, proportional_split, to_decimal


def allocate_credits(
    credits: List[PaymentCreditSchema],
    participant_pre_credit_totals: Dict[str, Decimal],
    custom_credit_allocations: Optional[Dict[str, Dict[str, Decimal]]] = None,
) -> Dict[str, Decimal]:
    """
    Returns credit benefit per participant (positive = reduces what they pay).
    Credits reduce the bill; owner_only mode reduces only owner's share.
    """
    credit_benefits: Dict[str, Decimal] = {pid: ZERO for pid in participant_pre_credit_totals}

    for credit in credits:
        amount = to_decimal(credit.amount)
        mode = credit.allocation_mode
        owner_id = credit.owner_participant_id
        participants = list(participant_pre_credit_totals.keys())

        if mode == CreditAllocationMode.OWNER_ONLY:
            if owner_id in credit_benefits:
                credit_benefits[owner_id] += amount
            continue

        if mode == CreditAllocationMode.EQUAL:
            shares = equal_split(amount, participants)
            for pid, share in shares.items():
                credit_benefits[pid] = credit_benefits.get(pid, ZERO) + share
            continue

        if mode == CreditAllocationMode.CUSTOM and credit.custom_allocations:
            custom = {k: to_decimal(v) for k, v in credit.custom_allocations.items()}
            distributed = proportional_split(amount, custom)
            for pid, share in distributed.items():
                credit_benefits[pid] = credit_benefits.get(pid, ZERO) + share
            continue

        # Proportional (default fallback)
        weights = {pid: max(participant_pre_credit_totals.get(pid, ZERO), ZERO) for pid in participants}
        shares = proportional_split(amount, weights)
        for pid, share in shares.items():
            credit_benefits[pid] = credit_benefits.get(pid, ZERO) + share

    return credit_benefits
