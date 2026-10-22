import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.modules.analytics.models import PurchaseOrder
from app.modules.analytics.service import SmartRestockService

router = APIRouter(prefix="/analytics", tags=["AI Restock & ABC/XYZ Analytics"])


class PurchaseOrderItemPayload(BaseModel):
    sku: str
    title: str
    quantity: int
    unit_cost: float


class CreatePurchaseOrderPayload(BaseModel):
    supplier_name: str
    items: List[PurchaseOrderItemPayload]
    notes: Optional[str] = None


@router.get("/restock-forecast")
async def get_restock_forecast(db: AsyncSession = Depends(get_db)):
    """
    Returns AI restock velocity, stock runout predictions and reorder recommendations.
    """
    forecast = await SmartRestockService.get_restock_forecast(db)
    critical_count = sum(1 for f in forecast if f["urgency"] in ("CRITICAL", "OUT_OF_STOCK"))
    total_reorder_sum = sum(f["estimated_reorder_cost"] for f in forecast)

    return {
        "critical_items_count": critical_count,
        "total_reorder_estimate": total_reorder_sum,
        "forecast": forecast
    }


@router.get("/abc-xyz")
async def get_abc_xyz_analysis(db: AsyncSession = Depends(get_db)):
    """
    Returns 9-quadrant ABC/XYZ profit and stability matrix with strategic recommendations.
    """
    matrix = await SmartRestockService.get_abc_xyz_matrix(db)
    return matrix


@router.post("/purchase-orders")
async def create_purchase_order(
    payload: CreatePurchaseOrderPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a formalized purchase order for distributors/suppliers.
    """
    items_dicts = [item.model_dump() for item in payload.items]
    po = await SmartRestockService.create_purchase_order(
        supplier_name=payload.supplier_name,
        items=items_dicts,
        notes=payload.notes,
        db=db
    )
    return {
        "status": "success",
        "order_number": po.order_number,
        "supplier_name": po.supplier_name,
        "total_amount": float(po.total_amount),
        "items_count": po.items_count,
        "created_at": po.created_at.isoformat()
    }


@router.get("/purchase-orders")
async def list_purchase_orders(db: AsyncSession = Depends(get_db)):
    """
    Lists created purchase orders.
    """
    stmt = select(PurchaseOrder).order_by(desc(PurchaseOrder.created_at))
    orders = (await db.execute(stmt)).scalars().all()

    return [
        {
            "id": str(o.id),
            "order_number": o.order_number,
            "supplier_name": o.supplier_name,
            "status": o.status,
            "total_amount": float(o.total_amount),
            "items_count": o.items_count,
            "items": json.loads(o.items_json) if o.items_json else [],
            "notes": o.notes,
            "created_at": o.created_at.isoformat()
        }
        for o in orders
    ]
