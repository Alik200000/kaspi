from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.modules.finance.service import KazakhstanFinanceTaxService

router = APIRouter(prefix="/finance", tags=["Kazakhstan Tax 910 & Financial P&L"])


@router.get("/pnl-summary")
async def get_pnl_summary(db: AsyncSession = Depends(get_db)):
    """
    Returns full unit economics P&L: Turnover, COGS, Kaspi commission, delivery, 3% tax and Net Cash.
    """
    return await KazakhstanFinanceTaxService.get_financial_summary(db)


@router.get("/tax-910")
async def get_tax_910_report(db: AsyncSession = Depends(get_db)):
    """
    Returns Form 910.00 Simplified Tax calculations for individual entrepreneurs in Kazakhstan.
    """
    summary = await KazakhstanFinanceTaxService.get_financial_summary(db)
    return summary["tax_910"]
