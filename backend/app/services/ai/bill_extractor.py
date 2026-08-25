"""Groq AI bill extraction service."""

import base64
import json
import logging
import re
from typing import Any, Optional

from groq import Groq
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.bill import (
    AdjustmentType,
    BillAdjustmentSchema,
    BillItemSchema,
    ExtractedBillSchema,
    ItemCategory,
)
from app.services.ai.prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT, RETRY_PROMPT
from app.services.calculation.engine import validate_bill_totals

logger = logging.getLogger(__name__)


class BillExtractionError(Exception):
    def __init__(self, message: str, code: str = "BILL_EXTRACTION_FAILED"):
        self.message = message
        self.code = code
        super().__init__(message)


def _generate_item_id(index: int) -> str:
    return f"item_{index + 1}"


def _generate_adj_id(index: int, adj_type: str) -> str:
    return f"{adj_type}_{index + 1}"


class BillExtractor:
    def __init__(self):
        settings = get_settings()
        self.client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None
        self.model = settings.groq_vision_model
        self.max_retries = 2

    async def extract_from_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> ExtractedBillSchema:
        if not self.client:
            raise BillExtractionError(
                "AI service is not configured. Please set GROQ_API_KEY.",
                code="AI_NOT_CONFIGURED",
            )

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{b64}"

        last_error: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            try:
                prompt = EXTRACTION_USER_PROMPT if attempt == 0 else RETRY_PROMPT.format(error=last_error)
                raw = await self._call_groq(data_uri, prompt)
                bill = self._parse_and_validate(raw)
                validation = validate_bill_totals(bill)
                if not validation.is_valid:
                    bill.needs_review = True
                    bill.warnings.append(validation.message or "Bill totals don't reconcile.")
                return bill
            except (ValidationError, json.JSONDecodeError, BillExtractionError) as e:
                last_error = str(e)
                logger.warning("Extraction attempt %d failed: %s", attempt + 1, last_error)
                if attempt == self.max_retries:
                    raise BillExtractionError(
                        "We couldn't read this bill clearly. Please try again with a clearer photo.",
                    ) from e

        raise BillExtractionError("We couldn't read this bill clearly.")

    async def _call_groq(self, data_uri: str, user_prompt: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4096,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def _parse_and_validate(self, raw: dict) -> ExtractedBillSchema:
        bill_data = raw.get("bill", raw)
        warnings = raw.get("warnings", [])
        needs_review = raw.get("needs_review", False)

        items: list[BillItemSchema] = []
        for i, item in enumerate(bill_data.get("items", [])):
            category_str = item.get("category", "other")
            try:
                category = ItemCategory(category_str)
            except ValueError:
                category = ItemCategory.OTHER
                needs_review = True
                warnings.append(f"Unknown category for '{item.get('name', 'item')}'")

            items.append(BillItemSchema(
                id=item.get("id") or _generate_item_id(i),
                name=item.get("name") or item.get("original_name", "Unknown Item"),
                original_name=item.get("original_name") or item.get("name"),
                normalized_name=item.get("normalized_name"),
                quantity=item.get("quantity", 1),
                unit_price=item.get("unit_price", 0),
                line_total=item.get("line_total", 0),
                category=category,
                subcategory=item.get("subcategory"),
                taxable=item.get("taxable", True),
                is_shared_candidate=item.get("is_shared_candidate", False),
                confidence=item.get("confidence", 0.8),
            ))

        adjustments: list[BillAdjustmentSchema] = []
        for key, adj_type in [
            ("charges", AdjustmentType.SERVICE_CHARGE),
            ("discounts", AdjustmentType.DISCOUNT),
            ("taxes", AdjustmentType.TAX),
            ("coupons", AdjustmentType.COUPON),
        ]:
            for i, adj in enumerate(bill_data.get(key, [])):
                try:
                    type_val = AdjustmentType(adj.get("type", adj_type.value))
                except ValueError:
                    type_val = adj_type
                adjustments.append(BillAdjustmentSchema(
                    id=adj.get("id") or _generate_adj_id(i, type_val.value),
                    type=type_val,
                    name=adj.get("name", type_val.value),
                    amount=adj.get("amount", 0),
                    percentage=adj.get("percentage"),
                    scope=adj.get("scope", "all"),
                ))

        # Also parse unified adjustments array
        for i, adj in enumerate(bill_data.get("adjustments", [])):
            try:
                type_val = AdjustmentType(adj.get("type", "other"))
            except ValueError:
                continue
            adjustments.append(BillAdjustmentSchema(
                id=adj.get("id") or _generate_adj_id(i + 100, type_val.value),
                type=type_val,
                name=adj.get("name", type_val.value),
                amount=adj.get("amount", 0),
                percentage=adj.get("percentage"),
                scope=adj.get("scope", "all"),
            ))

        return ExtractedBillSchema(
            restaurant_name=bill_data.get("restaurant_name") or bill_data.get("restaurant", {}).get("name"),
            currency=bill_data.get("currency", "INR"),
            items=items,
            adjustments=adjustments,
            subtotal=bill_data.get("subtotal", 0),
            total=bill_data.get("total", 0),
            confidence=bill_data.get("confidence", raw.get("confidence", 0.8)),
            needs_review=needs_review or raw.get("needs_review", False),
            warnings=list(warnings) + list(raw.get("warnings", [])),
        )
