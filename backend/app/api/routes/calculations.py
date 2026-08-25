import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.bill import SplitRequestSchema, SplitResultSchema
from app.services.calculation.engine import calculate_split

router = APIRouter(prefix="/api/splits", tags=["splits"])


@router.post("/calculate", response_model=SplitResultSchema)
async def calculate_split_endpoint(request: SplitRequestSchema):
    request_id = str(uuid.uuid4())
    try:
        if not request.participants:
            raise ValueError("At least one participant is required.")
        if not request.allocations:
            raise ValueError("At least one item allocation is required.")
        return calculate_split(request)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "CALCULATION_FAILED",
                    "message": str(e),
                    "request_id": request_id,
                }
            },
        ) from e
