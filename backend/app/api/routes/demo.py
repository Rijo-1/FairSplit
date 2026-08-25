from fastapi import APIRouter

from app.services.demo import get_demo_bill

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.get("/bill")
async def get_demo_bill_endpoint():
    return {"bill": get_demo_bill()}
