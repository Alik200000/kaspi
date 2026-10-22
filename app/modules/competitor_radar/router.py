from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.modules.competitor_radar.service import CompetitorRadarService

router = APIRouter(prefix="/radar", tags=["Kaspi Live Competitor Radar"])


@router.get("/overview")
async def get_radar_overview(db: AsyncSession = Depends(get_db)):
    """
    Returns live competitor positions, rankings, prices, and price war history.
    """
    return await CompetitorRadarService.get_radar_overview(db)
