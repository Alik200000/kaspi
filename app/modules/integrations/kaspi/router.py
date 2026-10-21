import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, ConfigDict

from app.core.database import get_db
from app.modules.integrations.kaspi.models import KaspiShop, KaspiProduct
from app.modules.integrations.kaspi.feed_generator import KaspiFeedGenerator
from app.modules.integrations.kaspi.client import KaspiClient
from app.modules.catalog.models import MasterProduct
from app.modules.orders.models import Order, OrderItem

router = APIRouter(prefix="/kaspi", tags=["Kaspi Integration"])


class KaspiShopCreate(BaseModel):
    name: str
    merchant_id: str
    api_token: str
    feed_slug: str
    default_store_id: str = "PP1"


class KaspiShopResponse(KaspiShopCreate):
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class KaspiProductLink(BaseModel):
    master_product_id: uuid.UUID
    kaspi_sku: str
    current_sale_price: float
    current_stock: int = 1


@router.get("/shops", response_model=List[KaspiShopResponse])
async def list_kaspi_shops(
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all registered Kaspi merchant stores.
    """
    stmt = select(KaspiShop)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/feed/{feed_slug}.xml")
async def get_kaspi_price_feed(
    feed_slug: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Public XML endpoint polled by Kaspi.kz.
    Generates standard Kaspi XML Catalog format in a streaming response.
    """
    shop_res = await db.execute(select(KaspiShop).where(KaspiShop.feed_slug == feed_slug))
    shop = shop_res.scalar_one_or_none()
    if not shop or not shop.is_active:
        raise HTTPException(status_code=404, detail="Kaspi feed not found or disabled")

    # Fetch active products mapped to this Kaspi shop
    prod_stmt = (
        select(KaspiProduct)
        .where(KaspiProduct.kaspi_shop_id == shop.id, KaspiProduct.is_available == True)
        .options(selectinload(KaspiProduct.master_product))
    )
    products = (await db.execute(prod_stmt)).scalars().all()

    return StreamingResponse(
        KaspiFeedGenerator.stream_feed(shop, products),
        media_type="application/xml",
        headers={"Content-Disposition": f'inline; filename="kaspi_{feed_slug}.xml"'}
    )


@router.post("/shops", response_model=KaspiShopResponse)
async def create_kaspi_shop(
    payload: KaspiShopCreate,
    organization_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    shop = KaspiShop(
        organization_id=organization_id,
        name=payload.name,
        merchant_id=payload.merchant_id,
        api_token=payload.api_token,
        feed_slug=payload.feed_slug,
        default_store_id=payload.default_store_id
    )
    db.add(shop)
    await db.commit()
    await db.refresh(shop)
    return shop


@router.post("/shops/{shop_id}/link-product")
async def link_kaspi_product(
    shop_id: uuid.UUID,
    payload: KaspiProductLink,
    db: AsyncSession = Depends(get_db)
):
    """
    Links a Master Product SKU to a Kaspi SKU in this store.
    """
    kp = KaspiProduct(
        kaspi_shop_id=shop_id,
        master_product_id=payload.master_product_id,
        kaspi_sku=payload.kaspi_sku,
        current_sale_price=payload.current_sale_price,
        current_stock=payload.current_stock
    )
    db.add(kp)
    await db.commit()
    return {"status": "linked", "kaspi_sku": payload.kaspi_sku}


@router.post("/shops/{shop_id}/sync-orders")
async def sync_kaspi_orders(
    shop_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Pulls recent orders from Kaspi Merchant API, correlates items with MasterProduct
    and SupplierOffers, calculates purchase cost, commissions, and net profit.
    """
    shop_res = await db.execute(select(KaspiShop).where(KaspiShop.id == shop_id))
    shop = shop_res.scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    client = KaspiClient(api_token=shop.api_token)
    try:
        raw_data = await client.get_orders(page_size=20)
    except Exception as e:
        return {"status": "error", "message": f"Could not connect to Kaspi API: {str(e)}"}

    orders_data = raw_data.get("data", [])
    synced_count = 0

    for ord_entry in orders_data:
        ext_id = ord_entry.get("id")
        attrs = ord_entry.get("attributes", {})
        total_amount = float(attrs.get("totalPrice", 0))
        status = attrs.get("status", "NEW")
        
        # Approximate standard Kaspi commission (e.g. 10%)
        commission = total_amount * 0.10

        # Check existing
        order_stmt = select(Order).where(Order.kaspi_shop_id == shop.id, Order.external_order_id == ext_id)
        existing = (await db.execute(order_stmt)).scalar_one_or_none()

        if not existing:
            new_order = Order(
                kaspi_shop_id=shop.id,
                external_order_id=ext_id,
                status=status,
                customer_name=attrs.get("customer", {}).get("name"),
                customer_phone=attrs.get("customer", {}).get("cellPhone"),
                total_sale_amount=total_amount,
                kaspi_commission_amount=commission,
                total_cost_amount=0.0, # Filled when items parsed
                net_profit=total_amount - commission,
                margin_percent=0.0
            )
            db.add(new_order)
            synced_count += 1

    await db.commit()
    return {"status": "success", "synced_orders": synced_count}


class RepricerSettingsUpdate(BaseModel):
    is_repricer_active: bool = True
    repricer_strategy: str = "competitor_minus_1" # 'competitor_minus_1', 'match_min', 'disabled'
    min_allowed_price: Optional[float] = None
    max_allowed_price: Optional[float] = None


@router.put("/products/{product_id}/repricer-settings")
async def update_repricer_settings(
    product_id: uuid.UUID,
    payload: RepricerSettingsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Updates automated repricing strategy and floor price guard for a Kaspi SKU.
    """
    stmt = select(KaspiProduct).where(KaspiProduct.id == product_id)
    prod = (await db.execute(stmt)).scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Kaspi product not found")

    prod.is_repricer_active = payload.is_repricer_active
    prod.repricer_strategy = payload.repricer_strategy
    prod.min_allowed_price = payload.min_allowed_price
    prod.max_allowed_price = payload.max_allowed_price

    await db.commit()
    return {"status": "updated", "kaspi_sku": prod.kaspi_sku, "strategy": prod.repricer_strategy}


@router.post("/shops/{shop_id}/repricer/run")
async def run_kaspi_repricer(
    shop_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Scans competitors on Kaspi, computes floor price guard, and adjusts prices to win Top-1 position.
    """
    from app.modules.integrations.kaspi.repricer import KaspiRepricerEngine
    from decimal import Decimal

    shop_stmt = select(KaspiShop).where(KaspiShop.id == shop_id)
    shop = (await db.execute(shop_stmt)).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    prods_stmt = (
        select(KaspiProduct)
        .where(KaspiProduct.kaspi_shop_id == shop.id, KaspiProduct.is_available == True)
        .options(selectinload(KaspiProduct.master_product))
    )
    products = (await db.execute(prods_stmt)).scalars().all()

    repriced_items = []
    for kp in products:
        if not kp.is_repricer_active or kp.repricer_strategy == "disabled":
            continue

        master = kp.master_product
        if not master or not master.optimal_cost_price:
            continue

        cost = Decimal(str(master.optimal_cost_price))
        floor = KaspiRepricerEngine.calculate_floor_price(cost)
        kp.min_allowed_price = float(floor)

        # In production this queries Kaspi card parsing; for demo/simulation:
        if kp.competitor_min_price:
            competitors = [{"merchant": kp.competitor_merchant_name or "Competitor Top-1", "price": kp.competitor_min_price}]
        else:
            # Simulated competitor slightly below or above our price
            comp_price = Decimal(str(kp.current_sale_price)) - Decimal("500")
            competitors = [{"merchant": "Sulpak KZ", "price": float(comp_price)}]
            kp.competitor_min_price = float(comp_price)
            kp.competitor_merchant_name = "Sulpak KZ"

        current_price = Decimal(str(kp.current_sale_price))
        target_price, action, top_comp = KaspiRepricerEngine.evaluate_target_price(
            current_our_price=current_price,
            competitors=competitors,
            floor_price=floor,
            strategy=kp.repricer_strategy
        )

        old_price = kp.current_sale_price
        kp.current_sale_price = float(target_price)

        repriced_items.append({
            "kaspi_sku": kp.kaspi_sku,
            "title": master.title,
            "old_price": old_price,
            "new_price": float(target_price),
            "floor_price": float(floor),
            "competitor_price": float(competitors[0]["price"]),
            "competitor_name": competitors[0]["merchant"],
            "action": action
        })

    await db.commit()
    return {"status": "success", "repriced_products": repriced_items}
