import asyncio
import sys
from pathlib import Path
from decimal import Decimal

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal, engine, Base
from app.core.security import get_password_hash
from app.modules.catalog.models import Organization, User, MasterProduct
from app.modules.suppliers.models import Supplier, SupplierOffer
from app.modules.pricing.models import PricingRule
from app.modules.pricing.engine import PricingEngine
from app.modules.integrations.kaspi.models import KaspiShop, KaspiProduct
from app.modules.orders.models import Order, OrderItem
from tabulate import tabulate


async def seed():
    print("==================================================================")
    print("   Starting E-Commerce & Kaspi SaaS Platform Demo Data Seeder     ")
    print("==================================================================")

    # 1. Initialize Tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Check if already seeded
        existing_org = await db.execute(select(Organization).where(Organization.name == "TechTrade Kazakhstan"))
        if existing_org.scalar_one_or_none():
            print("\n[INFO] Demo organization already exists. Skipping duplicate seeding.")
            return

        # 2. Create Organization & Owner User
        org = Organization(name="TechTrade Kazakhstan")
        db.add(org)
        await db.flush()

        user = User(
            organization_id=org.id,
            email="admin@techtrade.kz",
            hashed_password=get_password_hash("admin123"),
            full_name="Olzhas Baimuratov",
            role="owner"
        )
        db.add(user)
        print(f"[OK] Created Organization '{org.name}' and Owner User: admin@techtrade.kz (pass: admin123)")

        # 3. Create Suppliers
        supplier_marvel = Supplier(
            organization_id=org.id,
            name="Marvel Kazakhstan Distribution",
            code="MARVEL_KZ",
            delivery_days=1,
            priority=2
        )
        supplier_alser = Supplier(
            organization_id=org.id,
            name="Alser B2B Wholesale",
            code="ALSER_B2B",
            delivery_days=2,
            priority=1
        )
        db.add_all([supplier_marvel, supplier_alser])
        await db.flush()
        print(f"[OK] Registered 2 Competing Suppliers: '{supplier_marvel.name}' and '{supplier_alser.name}'")

        # 4. Create Master Products (Canonical SKU)
        products_data = [
            {
                "sku_internal": "APL-IPH15-128-BLK",
                "title": "Apple iPhone 15 128GB Black",
                "brand": "Apple",
                "barcode": "0195949038234",
                "category": "Smartphones"
            },
            {
                "sku_internal": "SAM-S24U-256-GRY",
                "title": "Samsung Galaxy S24 Ultra 256GB Titanium Gray",
                "brand": "Samsung",
                "barcode": "8806095304892",
                "category": "Smartphones"
            },
            {
                "sku_internal": "SNY-WH1000XM5-BLK",
                "title": "Беспроводные наушники Sony WH-1000XM5 Black",
                "brand": "Sony",
                "barcode": "4548736132580",
                "category": "Audio"
            },
            {
                "sku_internal": "DYS-V15-ABS",
                "title": "Пылесос Dyson V15 Detect Absolute Gold",
                "brand": "Dyson",
                "barcode": "5025155057841",
                "category": "Home Appliances"
            },
            {
                "sku_internal": "XMI-ROB-X10P",
                "title": "Робот-пылесос Xiaomi Robot Vacuum X10+ White",
                "brand": "Xiaomi",
                "barcode": "6934177789456",
                "category": "Home Appliances"
            }
        ]

        master_products = []
        for p in products_data:
            mp = MasterProduct(
                organization_id=org.id,
                sku_internal=p["sku_internal"],
                title=p["title"],
                brand=p["brand"],
                barcode=p["barcode"],
                category=p["category"]
            )
            master_products.append(mp)
            db.add(mp)
        await db.flush()
        print(f"[OK] Added {len(master_products)} Master SKU products to canonical catalog")

        # 5. Populate Competing Supplier Offers (with varying prices and stock)
        offers_data = [
            # iPhone 15: Alser is cheaper (365,000 vs 372,000)
            (supplier_marvel.id, master_products[0].id, "MRV-IPH15", "Apple iPhone 15 128 Black", 372000.0, 10),
            (supplier_alser.id, master_products[0].id, "ALS-IPH15", "iPhone 15 128GB Black A3090", 365000.0, 4),

            # Samsung S24 Ultra: Marvel is cheaper (540,000 vs 552,000)
            (supplier_marvel.id, master_products[1].id, "MRV-S24U", "Samsung Galaxy S24 Ultra Gray", 540000.0, 6),
            (supplier_alser.id, master_products[1].id, "ALS-S24U", "Galaxy S24 Ultra 256 Titanium", 552000.0, 5),

            # Sony WH-1000XM5: Equal price (150,000), but Marvel has higher priority
            (supplier_marvel.id, master_products[2].id, "MRV-SNYXM5", "Наушники Sony WH-1000XM5", 150000.0, 7),
            (supplier_alser.id, master_products[2].id, "ALS-SNYXM5", "Sony WH-1000XM5 ANC Black", 150000.0, 12),

            # Dyson V15: Marvel is out of stock (390,000, 0 qty), Alser has stock (405,000, 3 qty)
            (supplier_marvel.id, master_products[3].id, "MRV-DYS15", "Dyson V15 Absolute Gold", 390000.0, 0),
            (supplier_alser.id, master_products[3].id, "ALS-DYS15", "Dyson V15 Detect Absolute", 405000.0, 3),

            # Xiaomi Robot Vacuum: Only Alser offers it
            (supplier_alser.id, master_products[4].id, "ALS-X10P", "Xiaomi Robot Vacuum X10+ RU", 270000.0, 8),
        ]

        for s_id, m_id, s_sku, r_title, cost, stock in offers_data:
            offer = SupplierOffer(
                supplier_id=s_id,
                master_product_id=m_id,
                supplier_sku=s_sku,
                raw_title=r_title,
                cost_price=cost,
                stock_quantity=stock,
                is_available=True
            )
            db.add(offer)
        await db.flush()
        print(f"[OK] Loaded {len(offers_data)} multi-supplier offers with live stock and pricing")

        # 6. Create Tiered Pricing Rules
        rules = [
            PricingRule(
                organization_id=org.id,
                name="Apple Flagship Rule",
                brand="Apple",
                markup_percent=8.0,
                markup_fixed=2000.0,
                min_margin_percent=5.0,
                priority=10
            ),
            PricingRule(
                organization_id=org.id,
                name="Samsung Flagship Rule",
                brand="Samsung",
                markup_percent=10.0,
                markup_fixed=1000.0,
                min_margin_percent=6.0,
                priority=10
            ),
            PricingRule(
                organization_id=org.id,
                name="Premium Audio Rule",
                category="Audio",
                markup_percent=14.0,
                markup_fixed=1500.0,
                min_margin_percent=8.0,
                priority=8
            ),
            PricingRule(
                organization_id=org.id,
                name="General Default Markup",
                markup_percent=12.0,
                markup_fixed=1000.0,
                min_margin_percent=5.0,
                priority=1
            )
        ]
        db.add_all(rules)
        await db.flush()
        print(f"[OK] Configured {len(rules)} Smart Pricing Rules (tiered markups & minimum margin safeguards)")

        # 7. Execute Automated Repricing
        # Fetch products and recalculate
        from sqlalchemy.orm import selectinload
        prod_res = await db.execute(
            select(MasterProduct).where(MasterProduct.organization_id == org.id).options(selectinload(MasterProduct.supplier_offers))
        )
        loaded_prods = prod_res.scalars().all()

        repricing_table = []
        for p in loaded_prods:
            best_offer = PricingEngine.select_optimal_offer(p.supplier_offers)
            if best_offer:
                cost = Decimal(str(best_offer.cost_price))
                sale_price = PricingEngine.calculate_final_price(p, cost, rules)
                p.optimal_cost_price = float(cost)
                p.calculated_sale_price = float(sale_price)
                p.total_stock = sum(o.stock_quantity for o in p.supplier_offers if o.is_available)
                
                margin_kzt = float(sale_price) - float(cost)
                margin_pct = round((margin_kzt / float(sale_price)) * 100, 1)

                repricing_table.append([
                    p.title[:35],
                    best_offer.supplier_sku,
                    f"{cost:,.0f} KZT",
                    f"{float(sale_price):,.0f} KZT",
                    f"{margin_kzt:,.0f} KZT ({margin_pct}%)",
                    f"{p.total_stock} шт."
                ])

        # 8. Create Kaspi Store & Link Products
        kaspi_shop = KaspiShop(
            organization_id=org.id,
            name="TechTrade Kaspi Flagship Store",
            merchant_id="MERCHANT_KZ_7749",
            api_token="kaspi-demo-token-99887766",
            feed_slug="techtrade-almaty",
            default_store_id="PP1"
        )
        db.add(kaspi_shop)
        await db.flush()

        for p in loaded_prods:
            kp = KaspiProduct(
                kaspi_shop_id=kaspi_shop.id,
                master_product_id=p.id,
                kaspi_sku=p.sku_internal,
                current_sale_price=p.calculated_sale_price or 100000.0,
                current_stock=p.total_stock,
                is_available=True
            )
            db.add(kp)
        await db.flush()
        print(f"[OK] Connected Kaspi Shop '{kaspi_shop.name}' (Feed: /api/v1/kaspi/feed/{kaspi_shop.feed_slug}.xml)")

        # 9. Create Sample Orders & Unit Economics
        sample_orders_data = [
            ("KASPI-ORD-9001", master_products[0], 1, 396200.0, 365000.0, "Азамат Сериков", "+77015551122"),
            ("KASPI-ORD-9002", master_products[1], 1, 595000.0, 540000.0, "Динара Касымова", "+77773334455"),
            ("KASPI-ORD-9003", master_products[2], 2, 345000.0, 300000.0, "Руслан Алиев", "+77058889900"),
        ]

        for ext_id, prod, qty, sale_tot, cost_tot, c_name, c_phone in sample_orders_data:
            # 10% Kaspi commission, 2,500 delivery
            commission = sale_tot * 0.10
            delivery = 2500.0
            net_prof = sale_tot - cost_tot - commission - delivery
            margin_pct = (net_prof / sale_tot) * 100 if sale_tot > 0 else 0

            order = Order(
                kaspi_shop_id=kaspi_shop.id,
                external_order_id=ext_id,
                status="ACCEPTED",
                customer_name=c_name,
                customer_phone=c_phone,
                total_sale_amount=sale_tot,
                total_cost_amount=cost_tot,
                kaspi_commission_amount=commission,
                delivery_cost=delivery,
                net_profit=net_prof,
                margin_percent=margin_pct
            )
            db.add(order)
            await db.flush()

            order_item = OrderItem(
                order_id=order.id,
                master_product_id=prod.id,
                kaspi_sku=prod.sku_internal,
                title=prod.title,
                quantity=qty,
                sale_price=sale_tot / qty,
                purchase_cost=cost_tot / qty,
                item_margin=sale_tot - cost_tot
            )
            db.add(order_item)

        await db.commit()
        print(f"[OK] Recorded 3 sample Kaspi orders with calculated unit economics")

        # 10. Display Summary Table
        print("\n=== REPRICED CATALOG OVERVIEW (Optimal Supplier & Final Price) ===")
        print(tabulate(
            repricing_table,
            headers=["Master SKU / Название", "Оффер", "Закупка (Cost)", "Цена продажи (Sale)", "Маржа", "Остаток"],
            tablefmt="grid"
        ))

        print("\n==================================================================")
        print("  DEMO SEED COMPLETED SUCCESSFULLY!                              ")
        print("==================================================================")
        print("  Swagger UI:      http://127.0.0.1:8000/docs                    ")
        print("  Kaspi XML Feed:  http://127.0.0.1:8000/api/v1/kaspi/feed/techtrade-almaty.xml")
        print("  Login:           admin@techtrade.kz                            ")
        print("  Password:        admin123                                      ")
        print("==================================================================\n")


if __name__ == "__main__":
    asyncio.run(seed())
