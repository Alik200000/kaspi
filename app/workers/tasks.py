import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.modules.catalog.models import MasterProduct, Organization, PriceHistory
from app.modules.suppliers.models import Supplier, SupplierOffer
from app.modules.pricing.models import PricingRule
from app.modules.pricing.engine import PricingEngine
from app.modules.integrations.kaspi.models import KaspiShop, KaspiProduct
from app.modules.integrations.kaspi.client import KaspiClient
from app.modules.orders.models import Order, OrderItem
from app.modules.notifications.service import notifications

logger = logging.getLogger(__name__)


async def run_reprice_and_kaspi_sync_task() -> Dict[str, Any]:
    """
    Background job:
    1. Recalculates best supplier offers across all organizations.
    2. Applies active pricing rules to determine sale prices.
    3. Automatically updates Kaspi store listings with new prices & stocks.
    """
    logger.info("[TASK] Starting automated repricing and Kaspi stock synchronization...")
    start_time = datetime.utcnow()
    updated_products = 0
    updated_kaspi_items = 0

    async with AsyncSessionLocal() as db:
        # Get all organizations
        orgs = (await db.execute(select(Organization).where(Organization.is_active == True))).scalars().all()

        for org in orgs:
            # 1. Fetch products with supplier offers
            prod_stmt = (
                select(MasterProduct)
                .where(MasterProduct.organization_id == org.id)
                .options(selectinload(MasterProduct.supplier_offers).selectinload(SupplierOffer.supplier))
            )
            products = (await db.execute(prod_stmt)).scalars().all()

            # 2. Fetch pricing rules
            rules = (await db.execute(
                select(PricingRule).where(PricingRule.organization_id == org.id, PricingRule.is_active == True)
            )).scalars().all()

            prod_map: Dict[uuid.UUID, MasterProduct] = {}

            for prod in products:
                best_offer = PricingEngine.select_optimal_offer(prod.supplier_offers)
                if best_offer:
                    cost = Decimal(str(best_offer.cost_price))
                    sale_price = PricingEngine.calculate_final_price(prod, cost, rules)
                    new_cost = float(cost)
                    new_sale = float(sale_price)
                    new_stock = sum(o.stock_quantity for o in prod.supplier_offers if o.is_available)

                    # Check if price or stock changed to record audit history
                    if (prod.optimal_cost_price != new_cost or
                        prod.calculated_sale_price != new_sale or
                        prod.total_stock != new_stock):
                        
                        # Emit price surge alert if cost increased by > 10%
                        if prod.optimal_cost_price and new_cost > (prod.optimal_cost_price * 1.10):
                            await notifications.alert_price_surge(prod.title, prod.sku_internal, prod.optimal_cost_price, new_cost)

                        history_entry = PriceHistory(
                            master_product_id=prod.id,
                            old_cost_price=prod.optimal_cost_price,
                            new_cost_price=new_cost,
                            old_sale_price=prod.calculated_sale_price,
                            new_sale_price=new_sale,
                            old_stock=prod.total_stock,
                            new_stock=new_stock,
                            change_reason="automatic_reprice"
                        )
                        db.add(history_entry)

                    prod.optimal_cost_price = new_cost
                    prod.calculated_sale_price = new_sale
                    prod.total_stock = new_stock
                else:
                    if prod.total_stock != 0:
                        await notifications.alert_out_of_stock(prod.title, prod.sku_internal)
                        db.add(PriceHistory(
                            master_product_id=prod.id,
                            old_cost_price=prod.optimal_cost_price,
                            new_cost_price=None,
                            old_sale_price=prod.calculated_sale_price,
                            new_sale_price=None,
                            old_stock=prod.total_stock,
                            new_stock=0,
                            change_reason="out_of_stock_all_suppliers"
                        ))
                    prod.total_stock = 0
                prod_map[prod.id] = prod
                updated_products += 1

            # 3. Synchronize connected Kaspi Shops
            kaspi_shops = (await db.execute(
                select(KaspiShop).where(KaspiShop.organization_id == org.id, KaspiShop.is_active == True)
            )).scalars().all()

            for shop in kaspi_shops:
                kaspi_prods = (await db.execute(
                    select(KaspiProduct).where(KaspiProduct.kaspi_shop_id == shop.id)
                )).scalars().all()

                for kp in kaspi_prods:
                    master = prod_map.get(kp.master_product_id)
                    if master and master.calculated_sale_price:
                        kp.current_sale_price = master.calculated_sale_price
                        kp.current_stock = master.total_stock
                        kp.is_available = master.total_stock > 0
                        updated_kaspi_items += 1

                shop.last_feed_generated_at = datetime.utcnow()

        await db.commit()

    duration = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"[TASK] Repricing finished in {duration:.2f}s. Products: {updated_products}, Kaspi items synced: {updated_kaspi_items}")
    return {
        "status": "success",
        "duration_seconds": duration,
        "products_repriced": updated_products,
        "kaspi_items_synced": updated_kaspi_items,
        "timestamp": datetime.utcnow().isoformat()
    }


async def run_poll_kaspi_orders_task() -> Dict[str, Any]:
    """
    Background job:
    Polls connected Kaspi shops for new/updated customer orders via Kaspi Merchant API.
    """
    logger.info("[TASK] Starting Kaspi orders polling...")
    synced_orders = 0

    async with AsyncSessionLocal() as db:
        shops = (await db.execute(select(KaspiShop).where(KaspiShop.is_active == True))).scalars().all()

        for shop in shops:
            client = KaspiClient(api_token=shop.api_token)
            try:
                raw_data = await client.get_orders(page_size=20)
            except Exception as e:
                logger.warning(f"Kaspi order poll skipped for shop {shop.name} ({str(e)})")
                continue

            for ord_entry in raw_data.get("data", []):
                ext_id = ord_entry.get("id")
                attrs = ord_entry.get("attributes", {})
                total_amount = float(attrs.get("totalPrice", 0))
                status = attrs.get("status", "NEW")

                order_stmt = select(Order).where(Order.kaspi_shop_id == shop.id, Order.external_order_id == ext_id)
                existing = (await db.execute(order_stmt)).scalar_one_or_none()

                if not existing:
                    commission = total_amount * 0.10
                    profit = total_amount - commission
                    new_order = Order(
                        kaspi_shop_id=shop.id,
                        external_order_id=ext_id,
                        status=status,
                        customer_name=attrs.get("customer", {}).get("name"),
                        customer_phone=attrs.get("customer", {}).get("cellPhone"),
                        total_sale_amount=total_amount,
                        kaspi_commission_amount=commission,
                        total_cost_amount=0.0,
                        net_profit=profit,
                        margin_percent=0.0
                    )
                    db.add(new_order)
                    synced_orders += 1
                    await notifications.alert_new_order(ext_id, total_amount, profit)

        await db.commit()

    return {
        "status": "success",
        "synced_orders": synced_orders,
        "timestamp": datetime.utcnow().isoformat()
    }
