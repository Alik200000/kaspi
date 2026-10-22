from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.modules.warehouse_scanner.service import WarehouseScannerService

router = APIRouter(prefix="/scanner", tags=["Mobile Warehouse Barcode Scanner"])


class VerifyBarcodePayload(BaseModel):
    barcode: str


class AssembleOrderPayload(BaseModel):
    order_id: str


@router.post("/verify")
async def verify_barcode(
    payload: VerifyBarcodePayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Checks scanned barcode against pending Kaspi orders to prevent packing errors.
    """
    result = await WarehouseScannerService.verify_barcode(payload.barcode, db)
    return result


@router.post("/assemble")
async def assemble_order(
    payload: AssembleOrderPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Marks order as assembled and returns ready-to-print shipping label URL.
    """
    try:
        return await WarehouseScannerService.complete_assembly(payload.order_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
