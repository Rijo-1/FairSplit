"""Demo bill data for testing without AI."""

from decimal import Decimal

from app.schemas.bill import (
    AdjustmentType,
    BillAdjustmentSchema,
    BillItemSchema,
    ExtractedBillSchema,
    ItemCategory,
)


def get_demo_bill() -> ExtractedBillSchema:
    return ExtractedBillSchema(
        restaurant_name="Demo Restaurant",
        currency="INR",
        items=[
            BillItemSchema(
                id="demo_1", name="Paneer Tikka", original_name="Paneer Tikka",
                quantity=Decimal("1"), unit_price=Decimal("320"), line_total=Decimal("320"),
                category=ItemCategory.VEG_FOOD, subcategory="starter", is_shared_candidate=True, confidence=1.0,
            ),
            BillItemSchema(
                id="demo_2", name="Chicken Biryani", original_name="Chicken Biryani",
                quantity=Decimal("1"), unit_price=Decimal("450"), line_total=Decimal("450"),
                category=ItemCategory.NON_VEG_FOOD, subcategory="main_course", confidence=1.0,
            ),
            BillItemSchema(
                id="demo_3", name="French Fries", original_name="French Fries",
                quantity=Decimal("1"), unit_price=Decimal("240"), line_total=Decimal("240"),
                category=ItemCategory.SHARED_FOOD, subcategory="side", is_shared_candidate=True, confidence=1.0,
            ),
            BillItemSchema(
                id="demo_4", name="Kingfisher", original_name="KF Ultra 650ml",
                normalized_name="Kingfisher Ultra", quantity=Decimal("1"), unit_price=Decimal("300"),
                line_total=Decimal("300"), category=ItemCategory.ALCOHOL, subcategory="beer", confidence=1.0,
            ),
            BillItemSchema(
                id="demo_5", name="Coke", original_name="Coke",
                quantity=Decimal("1"), unit_price=Decimal("120"), line_total=Decimal("120"),
                category=ItemCategory.NON_ALCOHOLIC_DRINK, subcategory="soft_drink", confidence=1.0,
            ),
            BillItemSchema(
                id="demo_6", name="Gulab Jamun", original_name="Gulab Jamun",
                quantity=Decimal("1"), unit_price=Decimal("180"), line_total=Decimal("180"),
                category=ItemCategory.DESSERT, subcategory="dessert", is_shared_candidate=True, confidence=1.0,
            ),
        ],
        adjustments=[
            BillAdjustmentSchema(id="demo_d1", type=AdjustmentType.DISCOUNT, name="Discount", amount=Decimal("200")),
            BillAdjustmentSchema(id="demo_t1", type=AdjustmentType.TAX, name="GST", amount=Decimal("253")),
        ],
        subtotal=Decimal("1610"),
        total=Decimal("1663"),
        confidence=1.0,
        needs_review=False,
    )
