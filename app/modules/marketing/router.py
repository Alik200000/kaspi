from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.modules.marketing.service import KaspiAdsAutoBidderService

router = APIRouter(prefix="/marketing", tags=["Kaspi Ads Auto-Bidder & DRR Optimizer"])


class CreateCampaignPayload(BaseModel):
    name: str
    master_sku: str
    daily_budget: float
    target_drr_pct: float = 7.0
    max_cpc: float = 80.0


@router.get("/campaigns")
async def list_campaigns():
    """
    Returns list of all Kaspi marketing campaigns, metrics, CPC, and DRR.
    """
    return {
        "campaigns": KaspiAdsAutoBidderService.get_campaigns(),
        "summary": KaspiAdsAutoBidderService.get_summary()
    }


@router.post("/campaigns/create")
async def create_campaign(payload: CreateCampaignPayload):
    """
    Creates a new auto-managed Kaspi Ads campaign.
    """
    cmp = KaspiAdsAutoBidderService.create_campaign(
        name=payload.name,
        master_sku=payload.master_sku,
        daily_budget=payload.daily_budget,
        target_drr_pct=payload.target_drr_pct,
        max_cpc=payload.max_cpc
    )
    return {"status": "success", "campaign": cmp}


@router.post("/auto-bidder/run")
async def run_auto_bidder():
    """
    Triggers the automated Kaspi Ads bidding and DRR optimization cycle.
    """
    result = KaspiAdsAutoBidderService.optimize_bids()
    return result


@router.post("/campaigns/{campaign_id}/toggle")
async def toggle_campaign_status(campaign_id: str):
    """
    Toggles campaign between ACTIVE and PAUSED.
    """
    cmp = KaspiAdsAutoBidderService.toggle_campaign(campaign_id)
    if not cmp:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    return {"status": "success", "campaign": cmp}
