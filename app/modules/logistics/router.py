from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.modules.logistics.service import LogisticsTrackerService

router = APIRouter(prefix="/logistics", tags=["Logistics & Kaspi Delivery SLA Tracker"])


class ProcessReturnPayload(BaseModel):
    order_id: str
    reason: str = "Клиент отказался в отделении / не подошел цвет"
    restock_items: bool = True


@router.get("/status")
async def get_logistics_status(db: AsyncSession = Depends(get_db)):
    """
    Returns live delivery SLA alerts, courier delays and stuck Postomat packages.
    """
    alerts = await LogisticsTrackerService.get_sla_alerts(db)
    return alerts


@router.get("/sla-alerts")
async def get_sla_alerts(db: AsyncSession = Depends(get_db)):
    return await LogisticsTrackerService.get_sla_alerts(db)


@router.post("/process-return")
async def process_return(
    payload: ProcessReturnPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Handles order returns, restores warehouse inventory, and calculates return fees.
    """
    try:
        result = await LogisticsTrackerService.process_order_return(
            order_id=payload.order_id,
            reason=payload.reason,
            restock_items=payload.restock_items,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
