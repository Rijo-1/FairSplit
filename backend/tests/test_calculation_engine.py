"""Comprehensive calculation engine tests."""

from decimal import Decimal

import pytest

from app.schemas.bill import (
    AdjustmentType,
    AllocationType,
    BillAdjustmentSchema,
    BillItemSchema,
    CreditAllocationMode,
    ExtractedBillSchema,
    ItemAllocationSchema,
    ItemCategory,
    ParticipantSchema,
    PaymentCreditSchema,
    ServiceChargeMode,
    SplitMode,
    SplitRequestSchema,
)
from app.services.calculation.engine import calculate_split, validate_bill_totals


def _item(id: str, name: str, total: float, category: ItemCategory = ItemCategory.OTHER, qty: float = 1) -> BillItemSchema:
    return BillItemSchema(
        id=id,
        name=name,
        original_name=name,
        quantity=Decimal(str(qty)),
        unit_price=Decimal(str(total / qty)),
        line_total=Decimal(str(total)),
        category=category,
    )


def _participant(id: str, name: str) -> ParticipantSchema:
    return ParticipantSchema(id=id, name=name)


def _equal_alloc(item_id: str, participant_ids: list[str]) -> list[ItemAllocationSchema]:
    return [
        ItemAllocationSchema(bill_item_id=item_id, participant_id=pid, allocation_type=AllocationType.EQUAL)
        for pid in participant_ids
    ]


def _assert_total_invariant(result, expected_total: Decimal):
    computed = sum((p.final_amount for p in result.participants), Decimal("0"))
    assert computed == expected_total, f"Sum {computed} != {expected_total}"


class TestBasicSplit:
    def test_equal_split_two_people(self):
        bill = ExtractedBillSchema(
            items=[_item("1", "Pizza", 1000)],
            subtotal=Decimal("1000"),
            total=Decimal("1000"),
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "Alice"), _participant("b", "Bob")],
            allocations=_equal_alloc("1", ["a", "b"]),
        )
        result = calculate_split(request)
        assert result.participants[0].final_amount == Decimal("500.00")
        assert result.participants[1].final_amount == Decimal("500.00")
        _assert_total_invariant(result, Decimal("1000"))

    def test_different_items(self):
        bill = ExtractedBillSchema(
            items=[
                _item("1", "Salad", 300),
                _item("2", "Steak", 700),
            ],
            subtotal=Decimal("1000"),
            total=Decimal("1000"),
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "Alice"), _participant("b", "Bob")],
            allocations=[
                ItemAllocationSchema(bill_item_id="1", participant_id="a"),
                ItemAllocationSchema(bill_item_id="2", participant_id="b"),
            ],
        )
        result = calculate_split(request)
        by_name = {p.participant_name: p.final_amount for p in result.participants}
        assert by_name["Alice"] == Decimal("300.00")
        assert by_name["Bob"] == Decimal("700.00")
        _assert_total_invariant(result, Decimal("1000"))


class TestSharedItems:
    def test_shared_by_three(self):
        bill = ExtractedBillSchema(
            items=[_item("1", "Fries", 300, ItemCategory.SHARED_FOOD)],
            subtotal=Decimal("300"),
            total=Decimal("300"),
        )
        bill.items[0].is_shared_candidate = True
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "A"), _participant("b", "B"), _participant("c", "C")],
            allocations=_equal_alloc("1", ["a", "b", "c"]),
        )
        result = calculate_split(request)
        for p in result.participants:
            assert p.final_amount == Decimal("100.00")
        _assert_total_invariant(result, Decimal("300"))


class TestQuantity:
    def test_beer_quantity_split(self):
        bill = ExtractedBillSchema(
            items=[_item("1", "Beer", 900, ItemCategory.ALCOHOL, qty=3)],
            subtotal=Decimal("900"),
            total=Decimal("900"),
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "John"), _participant("b", "Alex")],
            allocations=[
                ItemAllocationSchema(bill_item_id="1", participant_id="a", allocation_type=AllocationType.QUANTITY, quantity=Decimal("2")),
                ItemAllocationSchema(bill_item_id="1", participant_id="b", allocation_type=AllocationType.QUANTITY, quantity=Decimal("1")),
            ],
        )
        result = calculate_split(request)
        by_name = {p.participant_name: p.final_amount for p in result.participants}
        assert by_name["John"] == Decimal("600.00")
        assert by_name["Alex"] == Decimal("300.00")
        _assert_total_invariant(result, Decimal("900"))


class TestDiscounts:
    def test_percentage_discount_proportional(self):
        bill = ExtractedBillSchema(
            items=[
                _item("1", "Item A", 1000),
                _item("2", "Item B", 3000),
            ],
            adjustments=[
                BillAdjustmentSchema(id="d1", type=AdjustmentType.DISCOUNT, name="20% off", amount=Decimal("800"), percentage=Decimal("20")),
            ],
            subtotal=Decimal("4000"),
            total=Decimal("3200"),
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "A"), _participant("b", "B")],
            allocations=[
                ItemAllocationSchema(bill_item_id="1", participant_id="a"),
                ItemAllocationSchema(bill_item_id="2", participant_id="b"),
            ],
        )
        result = calculate_split(request)
        by_name = {p.participant_name: p for p in result.participants}
        assert by_name["A"].discount_share == Decimal("200.00")
        assert by_name["B"].discount_share == Decimal("600.00")
        assert by_name["A"].final_amount == Decimal("800.00")
        assert by_name["B"].final_amount == Decimal("2400.00")
        _assert_total_invariant(result, Decimal("3200"))

    def test_fixed_discount(self):
        bill = ExtractedBillSchema(
            items=[
                _item("1", "A", 1000),
                _item("2", "B", 4000),
            ],
            adjustments=[
                BillAdjustmentSchema(id="d1", type=AdjustmentType.DISCOUNT, name="Flat", amount=Decimal("500")),
            ],
            subtotal=Decimal("5000"),
            total=Decimal("4500"),
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "A"), _participant("b", "B")],
            allocations=[
                ItemAllocationSchema(bill_item_id="1", participant_id="a"),
                ItemAllocationSchema(bill_item_id="2", participant_id="b"),
            ],
        )
        result = calculate_split(request)
        _assert_total_invariant(result, Decimal("4500"))


class TestTax:
    def test_tax_proportional(self):
        bill = ExtractedBillSchema(
            items=[
                _item("1", "A", 500),
                _item("2", "B", 1500),
            ],
            adjustments=[
                BillAdjustmentSchema(id="t1", type=AdjustmentType.TAX, name="GST", amount=Decimal("180")),
            ],
            subtotal=Decimal("2000"),
            total=Decimal("2180"),
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "A"), _participant("b", "B")],
            allocations=[
                ItemAllocationSchema(bill_item_id="1", participant_id="a"),
                ItemAllocationSchema(bill_item_id="2", participant_id="b"),
            ],
        )
        result = calculate_split(request)
        by_name = {p.participant_name: p for p in result.participants}
        assert by_name["A"].tax_share == Decimal("45.00")
        assert by_name["B"].tax_share == Decimal("135.00")
        _assert_total_invariant(result, Decimal("2180"))


class TestServiceCharge:
    def test_service_charge_proportional(self):
        bill = ExtractedBillSchema(
            items=[_item("1", "Food", 1000), _item("2", "Drink", 1000)],
            adjustments=[
                BillAdjustmentSchema(id="s1", type=AdjustmentType.SERVICE_CHARGE, name="SC", amount=Decimal("100")),
            ],
            subtotal=Decimal("2000"),
            total=Decimal("2100"),
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "A"), _participant("b", "B")],
            allocations=[
                ItemAllocationSchema(bill_item_id="1", participant_id="a"),
                ItemAllocationSchema(bill_item_id="2", participant_id="b"),
            ],
            service_charge_mode=ServiceChargeMode.PROPORTIONAL,
        )
        result = calculate_split(request)
        for p in result.participants:
            assert p.service_charge_share == Decimal("50.00")
        _assert_total_invariant(result, Decimal("2100"))

    def test_service_charge_equal(self):
        bill = ExtractedBillSchema(
            items=[_item("1", "Food", 1000), _item("2", "Drink", 3000)],
            adjustments=[
                BillAdjustmentSchema(id="s1", type=AdjustmentType.SERVICE_CHARGE, name="SC", amount=Decimal("100")),
            ],
            subtotal=Decimal("4000"),
            total=Decimal("4100"),
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "A"), _participant("b", "B")],
            allocations=[
                ItemAllocationSchema(bill_item_id="1", participant_id="a"),
                ItemAllocationSchema(bill_item_id="2", participant_id="b"),
            ],
            service_charge_mode=ServiceChargeMode.EQUAL,
        )
        result = calculate_split(request)
        for p in result.participants:
            assert p.service_charge_share == Decimal("50.00")
        _assert_total_invariant(result, Decimal("4100"))


class TestAlcohol:
    def test_only_drinkers_pay_alcohol(self):
        bill = ExtractedBillSchema(
            items=[
                _item("1", "Paneer", 320, ItemCategory.VEG_FOOD),
                _item("2", "Beer", 300, ItemCategory.ALCOHOL),
            ],
            subtotal=Decimal("620"),
            total=Decimal("620"),
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[
                _participant("a", "Rijo"),
                _participant("b", "John"),
                _participant("c", "Sarah"),
            ],
            allocations=[
                *_equal_alloc("1", ["a", "c"]),
                ItemAllocationSchema(bill_item_id="2", participant_id="b"),
            ],
        )
        result = calculate_split(request)
        by_name = {p.participant_name: p.final_amount for p in result.participants}
        assert by_name["John"] == Decimal("300.00")
        assert by_name["Rijo"] == Decimal("160.00")
        assert by_name["Sarah"] == Decimal("160.00")
        _assert_total_invariant(result, Decimal("620"))


class TestPaymentCredits:
    def test_credit_owner_only(self):
        bill = ExtractedBillSchema(
            items=[_item("1", "Food", 1000)],
            subtotal=Decimal("1000"),
            total=Decimal("1000"),
            payment_credits=[
                PaymentCreditSchema(
                    id="c1",
                    provider="Swiggy Dine Coins",
                    amount=Decimal("500"),
                    owner_participant_id="a",
                    allocation_mode=CreditAllocationMode.OWNER_ONLY,
                ),
            ],
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "Rijo"), _participant("b", "Alex")],
            allocations=_equal_alloc("1", ["a", "b"]),
        )
        result = calculate_split(request)
        by_name = {p.participant_name: p for p in result.participants}
        assert by_name["Rijo"].credit_share == Decimal("500.00")
        assert by_name["Rijo"].final_amount == Decimal("0.00")
        assert by_name["Alex"].final_amount == Decimal("500.00")
        _assert_total_invariant(result, Decimal("500"))

    def test_credit_shared_equally(self):
        bill = ExtractedBillSchema(
            items=[_item("1", "Food", 1000)],
            subtotal=Decimal("1000"),
            total=Decimal("1000"),
            payment_credits=[
                PaymentCreditSchema(
                    id="c1",
                    provider="Coins",
                    amount=Decimal("200"),
                    owner_participant_id="a",
                    allocation_mode=CreditAllocationMode.EQUAL,
                ),
            ],
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "A"), _participant("b", "B")],
            allocations=_equal_alloc("1", ["a", "b"]),
        )
        result = calculate_split(request)
        for p in result.participants:
            assert p.credit_share == Decimal("100.00")
        _assert_total_invariant(result, Decimal("800"))


class TestDemoBill:
    """Demo bill from spec: subtotal 1610, discount 200, GST 253, total 1663."""

    def test_demo_bill_split(self):
        bill = ExtractedBillSchema(
            restaurant_name="Demo Restaurant",
            currency="INR",
            items=[
                _item("1", "Paneer Tikka", 320, ItemCategory.VEG_FOOD),
                _item("2", "Chicken Biryani", 450, ItemCategory.NON_VEG_FOOD),
                _item("3", "French Fries", 240, ItemCategory.SHARED_FOOD),
                _item("4", "Kingfisher", 300, ItemCategory.ALCOHOL),
                _item("5", "Coke", 120, ItemCategory.NON_ALCOHOLIC_DRINK),
                _item("6", "Gulab Jamun", 180, ItemCategory.DESSERT),
            ],
            adjustments=[
                BillAdjustmentSchema(id="d1", type=AdjustmentType.DISCOUNT, name="Discount", amount=Decimal("200")),
                BillAdjustmentSchema(id="t1", type=AdjustmentType.TAX, name="GST", amount=Decimal("253")),
            ],
            subtotal=Decimal("1610"),
            total=Decimal("1663"),
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[
                _participant("r", "Rijo"),
                _participant("a", "Alex"),
                _participant("s", "Sarah"),
                _participant("j", "John"),
                _participant("h", "Rahul"),
            ],
            allocations=[
                *_equal_alloc("1", ["r", "s"]),
                ItemAllocationSchema(bill_item_id="2", participant_id="a"),
                *_equal_alloc("3", ["r", "a", "s", "j"]),
                ItemAllocationSchema(bill_item_id="4", participant_id="j"),
                ItemAllocationSchema(bill_item_id="4", participant_id="h"),
                ItemAllocationSchema(bill_item_id="5", participant_id="s"),
                *_equal_alloc("6", ["r", "s"]),
            ],
        )
        result = calculate_split(request)
        _assert_total_invariant(result, Decimal("1663"))
        assert len(result.participants) == 5
        assert all(p.final_amount >= Decimal("0") for p in result.participants)


class TestBillValidation:
    def test_valid_bill(self):
        bill = ExtractedBillSchema(
            items=[_item("1", "Food", 1000)],
            subtotal=Decimal("1000"),
            total=Decimal("1000"),
        )
        result = validate_bill_totals(bill)
        assert result.is_valid

    def test_mismatch_bill(self):
        bill = ExtractedBillSchema(
            items=[_item("1", "Food", 1000)],
            subtotal=Decimal("1000"),
            total=Decimal("900"),
        )
        result = validate_bill_totals(bill)
        assert not result.is_valid


class TestLargeGroup:
    def test_ten_participants(self):
        items = [_item(str(i), f"Item {i}", 100) for i in range(10)]
        bill = ExtractedBillSchema(
            items=items,
            subtotal=Decimal("1000"),
            total=Decimal("1000"),
        )
        participants = [_participant(str(i), f"P{i}") for i in range(10)]
        allocations = [ItemAllocationSchema(bill_item_id=str(i), participant_id=str(i)) for i in range(10)]
        request = SplitRequestSchema(bill=bill, participants=participants, allocations=allocations)
        result = calculate_split(request)
        _assert_total_invariant(result, Decimal("1000"))


class TestMixedScenario:
    def test_discount_tax_service_charge(self):
        bill = ExtractedBillSchema(
            items=[
                _item("1", "A", 2000),
                _item("2", "B", 2000),
            ],
            adjustments=[
                BillAdjustmentSchema(id="d1", type=AdjustmentType.DISCOUNT, name="Disc", amount=Decimal("400")),
                BillAdjustmentSchema(id="t1", type=AdjustmentType.TAX, name="GST", amount=Decimal("576")),
                BillAdjustmentSchema(id="s1", type=AdjustmentType.SERVICE_CHARGE, name="SC", amount=Decimal("200")),
            ],
            subtotal=Decimal("4000"),
            total=Decimal("4376"),
        )
        request = SplitRequestSchema(
            bill=bill,
            participants=[_participant("a", "A"), _participant("b", "B")],
            allocations=[
                ItemAllocationSchema(bill_item_id="1", participant_id="a"),
                ItemAllocationSchema(bill_item_id="2", participant_id="b"),
            ],
        )
        result = calculate_split(request)
        _assert_total_invariant(result, Decimal("4376"))
