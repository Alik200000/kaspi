from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.modules.integrations.multichannel.service import MultichannelSyncService

router = APIRouter(prefix="/multichannel", tags=["Unified Multi-Marketplace Stock (Kaspi + WB + Ozon)"])


@router.get("/status")
async def get_multichannel_status(db: AsyncSession = Depends(get_db)):
    """
    Returns synchronization status across Kaspi, Wildberries, Ozon and Halyk Market.
    """
    return await MultichannelSyncService.get_multichannel_status(db)


@router.post("/sync-all")
async def broadcast_multichannel_stocks(db: AsyncSession = Depends(get_db)):
    """
    Simultaneously broadcasts physical warehouse stock to all connected marketplaces.
    """
    return await MultichannelSyncService.broadcast_stock_sync(db)
