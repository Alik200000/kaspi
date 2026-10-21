import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.modules.catalog.models import MasterProduct, Organization
from app.modules.catalog.schemas import MasterProductCreate, MasterProductResponse
from app.modules.pricing.models import PricingRule
from app.modules.pricing.engine import PricingEngine
from decimal import Decimal

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get("/products", response_model=List[MasterProductResponse])
async def list_products(
    organization_id: Optional[uuid.UUID] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns canonical Master SKU catalog with current best cost, calculated sales price and total stock.
    """
    stmt = select(MasterProduct).order_by(MasterProduct.created_at.desc())
    if organization_id:
        stmt = stmt.where(MasterProduct.organization_id == organization_id)
    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(
            (MasterProduct.title.ilike(search_filter)) |
            (MasterProduct.sku_internal.ilike(search_filter)) |
            (MasterProduct.barcode.ilike(search_filter))
        )
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/products", response_model=MasterProductResponse)
async def create_product(
    payload: MasterProductCreate,
    organization_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new Master Product SKU.
    """
    prod = MasterProduct(
        organization_id=organization_id,
        sku_internal=payload.sku_internal,
        title=payload.title,
        brand=payload.brand,
        barcode=payload.barcode,
        category=payload.category,
        description=payload.description
    )
    db.add(prod)
    await db.commit()
    await db.refresh(prod)
    return prod


@router.post("/reprice")
async def trigger_catalog_repricing(
    organization_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Recalculates best supplier offer and final selling price for all products in an organization.
    """
    # Fetch all products with their supplier offers
    prod_stmt = (
        select(MasterProduct)
        .where(MasterProduct.organization_id == organization_id)
        .options(selectinload(MasterProduct.supplier_offers))
    )
    products_res = await db.execute(prod_stmt)
    products = products_res.scalars().all()

    # Fetch active pricing rules
    rule_stmt = select(PricingRule).where(
        PricingRule.organization_id == organization_id,
        PricingRule.is_active == True
    )
    rules_res = await db.execute(rule_stmt)
    rules = rules_res.scalars().all()

    updated_count = 0
    for prod in products:
        best_offer = PricingEngine.select_optimal_offer(prod.supplier_offers)
        if best_offer:
            cost = Decimal(str(best_offer.cost_price))
            sale_price = PricingEngine.calculate_final_price(prod, cost, rules)
            prod.optimal_cost_price = float(cost)
            prod.calculated_sale_price = float(sale_price)
            prod.total_stock = sum(o.stock_quantity for o in prod.supplier_offers if o.is_available)
        else:
            prod.total_stock = 0
        updated_count += 1

    await db.commit()
    return {"status": "ok", "products_repriced": updated_count}


@router.get("/products/{product_id}/history")
async def get_product_price_history(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns time-series history of cost and sales price changes,
    stock fluctuations, and repricing triggers for a Master SKU.
    """
    from app.modules.catalog.models import PriceHistory
    stmt = (
        select(PriceHistory)
        .where(PriceHistory.master_product_id == product_id)
        .order_by(PriceHistory.created_at.desc())
    )
    records = (await db.execute(stmt)).scalars().all()
    return records
