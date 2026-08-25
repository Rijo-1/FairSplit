from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ItemCategory(str, Enum):
    VEG_FOOD = "veg_food"
    NON_VEG_FOOD = "non_veg_food"
    VEGAN_FOOD = "vegan_food"
    ALCOHOL = "alcohol"
    NON_ALCOHOLIC_DRINK = "non_alcoholic_drink"
    DESSERT = "dessert"
    SIDE = "side"
    STARTER = "starter"
    MAIN_COURSE = "main_course"
    SHARED_FOOD = "shared_food"
    SERVICE_CHARGE = "service_charge"
    TAX = "tax"
    DISCOUNT = "discount"
    COUPON = "coupon"
    PAYMENT_CREDIT = "payment_credit"
    OTHER = "other"


class AdjustmentType(str, Enum):
    DISCOUNT = "discount"
    TAX = "tax"
    SERVICE_CHARGE = "service_charge"
    COUPON = "coupon"
    CREDIT = "credit"


class AllocationType(str, Enum):
    EQUAL = "equal"
    PERCENTAGE = "percentage"
    QUANTITY = "quantity"


class CreditAllocationMode(str, Enum):
    OWNER_ONLY = "owner_only"
    EQUAL = "equal"
    PROPORTIONAL = "proportional"
    CUSTOM = "custom"


class SplitMode(str, Enum):
    EXACT = "exact"
    FAIR = "fair"
    CUSTOM = "custom"


class ServiceChargeMode(str, Enum):
    PROPORTIONAL = "proportional"
    EQUAL = "equal"
    CUSTOM = "custom"


class BillItemSchema(BaseModel):
    id: str
    name: str
    original_name: Optional[str] = None
    normalized_name: Optional[str] = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(ge=0)
    line_total: Decimal = Field(ge=0)
    category: ItemCategory = ItemCategory.OTHER
    subcategory: Optional[str] = None
    taxable: bool = True
    is_shared_candidate: bool = False
    confidence: float = Field(default=1.0, ge=0, le=1)


class BillAdjustmentSchema(BaseModel):
    id: str
    type: AdjustmentType
    name: str
    amount: Decimal = Field(ge=0)
    percentage: Optional[Decimal] = Field(default=None, ge=0, le=100)
    scope: str = "all"


class PaymentCreditSchema(BaseModel):
    id: str
    provider: str
    amount: Decimal = Field(gt=0)
    owner_participant_id: str
    allocation_mode: CreditAllocationMode = CreditAllocationMode.OWNER_ONLY
    custom_allocations: Optional[dict[str, Decimal]] = None


class ParticipantSchema(BaseModel):
    id: str
    name: str
    dietary_preference: Optional[str] = None


class ItemAllocationSchema(BaseModel):
    bill_item_id: str
    participant_id: str
    allocation_type: AllocationType = AllocationType.EQUAL
    quantity: Optional[Decimal] = Field(default=None, gt=0)
    percentage: Optional[Decimal] = Field(default=None, gt=0, le=100)


class ExtractedBillSchema(BaseModel):
    restaurant_name: Optional[str] = None
    currency: str = "INR"
    items: List[BillItemSchema] = Field(default_factory=list)
    adjustments: List[BillAdjustmentSchema] = Field(default_factory=list)
    payment_credits: List[PaymentCreditSchema] = Field(default_factory=list)
    subtotal: Decimal = Field(ge=0)
    total: Decimal = Field(ge=0)
    confidence: float = Field(default=1.0, ge=0, le=1)
    needs_review: bool = False
    warnings: List[str] = Field(default_factory=list)


class BillValidationResult(BaseModel):
    is_valid: bool
    expected_total: Decimal
    extracted_total: Decimal
    difference: Decimal
    tolerance: Decimal
    message: Optional[str] = None


class SplitRequestSchema(BaseModel):
    bill: ExtractedBillSchema
    participants: List[ParticipantSchema]
    allocations: List[ItemAllocationSchema]
    split_mode: SplitMode = SplitMode.FAIR
    service_charge_mode: ServiceChargeMode = ServiceChargeMode.PROPORTIONAL
    payment_credits: List[PaymentCreditSchema] = Field(default_factory=list)


class ParticipantBreakdown(BaseModel):
    participant_id: str
    participant_name: str
    items_subtotal: Decimal
    discount_share: Decimal
    tax_share: Decimal
    service_charge_share: Decimal
    credit_share: Decimal
    rounding_adjustment: Decimal
    final_amount: Decimal
    item_details: List[dict] = Field(default_factory=list)


class SplitResultSchema(BaseModel):
    grand_total: Decimal
    participants: List[ParticipantBreakdown]
    summary: dict = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
