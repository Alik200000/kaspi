from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.modules.billing.models import PaymentInvoice
from app.modules.billing.service import BillingService

router = APIRouter(prefix="/billing", tags=["SaaS Billing & Subscriptions"])


class ActivatePlanPayload(BaseModel):
    tier: str # START, BUSINESS, ENTERPRISE
    payment_method: str = "KASPI_PAY_QR" # KASPI_PAY_QR, CARD


@router.get("/plans")
async def get_plans_catalog():
    """
    Returns available SaaS pricing plans.
    """
    return BillingService.PLANS


@router.get("/subscription")
async def get_subscription(db: AsyncSession = Depends(get_db)):
    """
    Returns current active subscription status and feature permissions.
    """
    return await BillingService.get_current_subscription(db)


@router.post("/activate-plan")
async def activate_plan(
    payload: ActivatePlanPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Upgrades or renews subscription tier with instant activation.
    """
    result = await BillingService.create_invoice_and_activate(
        tier=payload.tier,
        payment_method=payload.payment_method,
        db=db
    )
    return result


@router.get("/invoices")
async def list_invoices(db: AsyncSession = Depends(get_db)):
    """
    Returns history of payment receipts and Kaspi Pay invoices.
    """
    stmt = select(PaymentInvoice).order_by(desc(PaymentInvoice.created_at))
    invoices = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(i.id),
            "invoice_number": i.invoice_number,
            "tier": i.tier,
            "amount_kzt": float(i.amount_kzt),
            "payment_method": i.payment_method,
            "status": i.status,
            "kaspi_payment_link": i.kaspi_payment_link,
            "created_at": i.created_at.strftime("%d.%m.%Y %H:%M") if i.created_at else None
        }
        for i in invoices
    ]
