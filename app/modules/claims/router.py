import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.modules.claims.models import VendorClaim
from app.modules.claims.service import VendorClaimsService

router = APIRouter(prefix="/claims", tags=["Vendor Defect Claims & RMA Manager"])


class CreateClaimPayload(BaseModel):
    supplier_name: str
    product_title: str
    sku: str
    defect_type: str = "FACTORY_DEFECT"
    defect_description: str
    claim_amount: float
    external_order_id: Optional[str] = None
    serial_number: Optional[str] = None


@router.get("")
async def list_claims(db: AsyncSession = Depends(get_db)):
    """
    Returns list of RMA defect claims against suppliers.
    """
    return await VendorClaimsService.get_claims(db)


@router.post("/create")
async def create_claim(
    payload: CreateClaimPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new defect claim for supplier compensation.
    """
    claim = await VendorClaimsService.create_claim(
        supplier_name=payload.supplier_name,
        product_title=payload.product_title,
        sku=payload.sku,
        defect_type=payload.defect_type,
        defect_description=payload.defect_description,
        claim_amount=payload.claim_amount,
        external_order_id=payload.external_order_id,
        serial_number=payload.serial_number,
        db=db
    )
    return {
        "status": "success",
        "claim_number": claim.claim_number,
        "product_title": claim.product_title,
        "claim_amount": float(claim.claim_amount),
        "act_url": f"/api/v1/claims/{claim.id}/act-html"
    }


@router.get("/{claim_id}/act-html", response_class=HTMLResponse)
async def get_claim_act_html(
    claim_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Generates printable legal Claim Act (Акт рекламации) ready to send to the distributor.
    """
    try:
        c_uuid = uuid.UUID(claim_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid claim UUID")

    stmt = select(VendorClaim).where(VendorClaim.id == c_uuid)
    claim = (await db.execute(stmt)).scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    html = VendorClaimsService.generate_claim_act_html(claim)
    return HTMLResponse(content=html)
