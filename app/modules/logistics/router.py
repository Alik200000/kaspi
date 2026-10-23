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


class CreateManifestPayload(BaseModel):
    courier_service: str = "Kaspi Доставка"
    courier_name: str = "Касымов Арман"
    vehicle_number: str = "777 ABC 02"
    order_ids: List[str] = ["KSP-1094821", "KSP-1094822", "KSP-1094825"]


@router.get("/manifests")
async def list_manifests(db: AsyncSession = Depends(get_db)):
    """
    Returns list of courier handover manifests and dispatch registers.
    """
    return await LogisticsTrackerService.get_manifests(db)


@router.post("/manifests/create")
async def create_manifest(
    payload: CreateManifestPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new courier handover manifest with order items and barcodes.
    """
    mnf = await LogisticsTrackerService.create_manifest(
        courier_service=payload.courier_service,
        courier_name=payload.courier_name,
        vehicle_number=payload.vehicle_number,
        order_ids=payload.order_ids,
        db=db
    )
    return {
        "status": "success",
        "manifest": mnf,
        "print_url": f"/api/v1/logistics/manifests/{mnf['id']}/act-html"
    }


@router.get("/manifests/{manifest_id}/act-html")
async def get_manifest_act_html(manifest_id: str):
    """
    Generates printable legal courier handover act with signatures and package checklist.
    """
    from fastapi.responses import HTMLResponse
    html = LogisticsTrackerService.generate_manifest_act_html(manifest_id)
    return HTMLResponse(content=html)

