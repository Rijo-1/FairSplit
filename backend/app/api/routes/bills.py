import logging
import uuid
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.bill import ExtractedBillSchema
from app.services.ai.bill_extractor import BillExtractionError, BillExtractor
from app.services.calculation.engine import validate_bill_totals
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bills", tags=["bills"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/extract")
async def extract_bill(file: UploadFile = File(...)):
    request_id = str(uuid.uuid4())

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_IMAGE_TYPE",
                    "message": "Please upload a JPEG, PNG, or WebP image.",
                    "request_id": request_id,
                }
            },
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": "Image is too large. Maximum size is 10MB.",
                    "request_id": request_id,
                }
            },
        )

    if len(contents) < 100:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_IMAGE",
                    "message": "This doesn't look like a valid image.",
                    "request_id": request_id,
                }
            },
        )

    extractor = BillExtractor()
    try:
        bill = await extractor.extract_from_image(contents, file.content_type or "image/jpeg")
        logger.info("Bill extracted successfully", extra={"request_id": request_id, "items": len(bill.items)})
        return {"bill": bill, "request_id": request_id}
    except BillExtractionError as e:
        logger.warning("Bill extraction failed: %s", e.message, extra={"request_id": request_id})
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "request_id": request_id,
                }
            },
        ) from e


@router.post("/validate")
async def validate_bill(bill: ExtractedBillSchema):
    settings = get_settings()
    result = validate_bill_totals(bill, tolerance=settings.rounding_tolerance)
    return result
