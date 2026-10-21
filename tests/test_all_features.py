import io
import sys
import os
from pathlib import Path
from decimal import Decimal

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules.pricing.engine import PricingEngine
from app.modules.pricing.models import PricingRule
from app.modules.catalog.models import MasterProduct
from app.modules.suppliers.models import SupplierOffer, Supplier
from app.modules.suppliers.parser import SupplierFeedParser
from app.modules.catalog.matching import SKUMatchingEngine
from app.modules.integrations.kaspi.repricer import KaspiRepricerEngine
from app.modules.integrations.kaspi.feed_generator import KaspiFeedGenerator
from app.modules.integrations.kaspi.models import KaspiShop, KaspiProduct
from app.modules.notifications.service import notifications
from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token
from app.main import app


def test_section(name):
    print(f"\n==================================================")
    print(f"  TESTING: {name}")
    print(f"==================================================")


def test_auth_and_security():
    test_section("1. Auth, Bcrypt & JWT Security")
    
    # 1. Password hashing
    raw_pass = "superSecretPassword123!"
    hashed = get_password_hash(raw_pass)
    assert verify_password(raw_pass, hashed) is True, "Password verification failed"
    assert verify_password("wrongPassword", hashed) is False, "Password should not match wrong string"
    print("  [OK] Bcrypt password hashing & verification passed")

    # 2. JWT Generation & Decoding
    payload = {"sub": "user-uuid-123", "org_id": "org-uuid-456", "role": "owner"}
    token = create_access_token(payload)
    decoded = decode_access_token(token)
    assert decoded is not None, "JWT decoding failed"
    assert decoded["sub"] == "user-uuid-123"
    assert decoded["role"] == "owner"
    print("  [OK] JWT token generation and decoding passed")


def test_cascade_matching_engine():
    test_section("2. SKU Cascade Matching Engine (Barcode -> SKU -> Fuzzy)")

    candidates = [
        MasterProduct(
            sku_internal="APL-IPH15-BLK",
            title="Apple iPhone 15 128GB Black",
            brand="Apple",
            barcode="0195949038234"
        ),
        MasterProduct(
            sku_internal="SAM-S24-GRY",
            title="Samsung Galaxy S24 Ultra 256GB Gray",
            brand="Samsung",
            barcode="8806095304892"
        ),
        MasterProduct(
            sku_internal="SNY-WH1000XM5",
            title="Sony WH-1000XM5 ANC Black",
            brand="Sony",
            barcode="4548736132580"
        )
    ]

    # Test 1: Exact Barcode
    m1, conf1, t1, s1 = SKUMatchingEngine.match_offer(
        offer_title="Любое название товара без упоминания модели",
        offer_barcode="0195949038234",
        offer_sku="SUP-111",
        offer_brand="Apple",
        candidates=candidates
    )
    assert m1 is not None and m1.sku_internal == "APL-IPH15-BLK"
    assert conf1 == 1.0 and t1 == "barcode" and s1 == "confirmed"
    print("  [OK] Stage 1: Exact Barcode matching passed (100% confidence)")

    # Test 2: Normalized Internal SKU
    m2, conf2, t2, s2 = SKUMatchingEngine.match_offer(
        offer_title="Незнакомое название",
        offer_barcode=None,
        offer_sku="SAM - S24 - GRY", # messy spaces
        offer_brand="Samsung",
        candidates=candidates
    )
    assert m2 is not None and m2.sku_internal == "SAM-S24-GRY"
    assert conf2 == 0.95 and t2 == "sku" and s2 == "confirmed"
    print("  [OK] Stage 2: Normalized SKU matching passed (95% confidence)")

    # Test 3: Fuzzy Token Similarity
    m3, conf3, t3, s3 = SKUMatchingEngine.match_offer(
        offer_title="Наушники беспроводные Sony WH 1000XM5 черный оригинал",
        offer_barcode=None,
        offer_sku="SOME-RANDOM-CODE",
        offer_brand="Sony",
        candidates=candidates
    )
    assert m3 is not None and m3.sku_internal == "SNY-WH1000XM5"
    assert conf3 >= 0.70
    print(f"  [OK] Stage 3: Fuzzy token similarity passed (Score: {conf3*100:.1f}%, Type: {t3})")


def test_supplier_streaming_parser():
    test_section("3. Supplier Feed Streaming Parser (O(1) Memory)")

    csv_data = (
        "Артикул;Наименование;Бренд;Штрихкод;Цена;Остаток\n"
        "ART-001;Смартфон Apple iPhone 15;Apple;0195949038234;365 000 ₸;> 10\n"
        "ART-002;Samsung Galaxy S24;Samsung;8806095304892;540000 тг;5\n"
    )
    stream = io.StringIO(csv_data)
    rows = list(SupplierFeedParser.parse_csv_stream(stream, delimiter=";"))
    assert len(rows) == 2
    assert rows[0]["cost_price"] == Decimal("365000")
    assert rows[0]["stock_quantity"] == 10
    assert rows[1]["cost_price"] == Decimal("540000")
    assert rows[1]["stock_quantity"] == 5
    print("  [OK] Streaming CSV parser with currency & symbol sanitization passed")


def test_pricing_and_repricing():
    test_section("4. Optimal Supplier Selection & Rule-based Markups")

    offer_cheap_instock = SupplierOffer(
        supplier_sku="CHEAP",
        cost_price=100000.0,
        stock_quantity=4,
        is_available=True
    )
    offer_cheapest_out_of_stock = SupplierOffer(
        supplier_sku="OUT_OF_STOCK",
        cost_price=90000.0,
        stock_quantity=0,
        is_available=True
    )
    offer_expensive = SupplierOffer(
        supplier_sku="EXPENSIVE",
        cost_price=110000.0,
        stock_quantity=10,
        is_available=True
    )

    best = PricingEngine.select_optimal_offer([offer_cheapest_out_of_stock, offer_cheap_instock, offer_expensive])
    assert best is not None and best.supplier_sku == "CHEAP", "Should choose cheapest IN-STOCK offer"
    print("  [OK] Optimal supplier selection passed (ignores zero stock, picks lowest price)")

    # Markup test
    prod = MasterProduct(sku_internal="TEST", title="Test SKU", brand="Apple")
    rule = PricingRule(
        name="Apple Rule",
        brand="Apple",
        markup_percent=10.0,
        markup_fixed=500.0,
        min_margin_percent=5.0,
        priority=10
    )
    # 100,000 * 1.10 = 110,000 + 500 = 110,500
    final_price = PricingEngine.calculate_final_price(prod, Decimal("100000"), [rule])
    assert final_price == Decimal("110500")
    print("  [OK] Rule-based markup calculation passed (100,000 -> 110,500 KZT)")


def test_kaspi_bot_repricer():
    test_section("5. Kaspi Bot Repricer (Top-1 Undercutting & Floor Price Guard)")

    cost = Decimal("100000")
    # Floor price: Cost 100,000 + 5% min margin + 2500 delivery / (1 - 0.10 Kaspi commission)
    floor = KaspiRepricerEngine.calculate_floor_price(
        cost_price=cost,
        min_margin_percent=Decimal("5.0"),
        kaspi_commission_percent=Decimal("10.0"),
        fixed_delivery_cost=Decimal("2500.0")
    )
    assert floor > Decimal("115000"), f"Floor price {floor} should cover cost, margin, and commissions"
    print(f"  [OK] Floor Price Guard calculated: {floor:,.0f} KZT")

    # Case A: Competitor is above floor price (e.g. 130,000). Target: 130,000 - 10 = 129,990
    target_a, action_a, _ = KaspiRepricerEngine.evaluate_target_price(
        current_our_price=Decimal("135000"),
        competitors=[{"merchant": "Sulpak", "price": 130000}],
        floor_price=floor,
        strategy="competitor_minus_1"
    )
    assert target_a == Decimal("129990")
    assert action_a == "undercut_competitor_to_win_top_1"
    print("  [OK] Case A: Competitor undercut by 10 KZT to capture Top-1 position passed")

    # Case B: Competitor severely dumps below floor price (e.g. 110,000 < floor 119,444).
    # Target MUST be clamped to floor price to prevent selling at a loss!
    target_b, action_b, _ = KaspiRepricerEngine.evaluate_target_price(
        current_our_price=Decimal("135000"),
        competitors=[{"merchant": "DumpingStore", "price": 110000}],
        floor_price=floor,
        strategy="competitor_minus_1"
    )
    assert target_b == floor, f"Target {target_b} should be clamped to floor {floor}"
    assert action_b == "floor_price_guard_activated"
    print("  [OK] Case B: Floor Price Guard activated, prevented selling at a loss passed")


def test_kaspi_multi_city_xml():
    test_section("6. Kaspi Multi-City XML Feed Generator")

    shop = KaspiShop(
        name="TechTrade Kaspi Store",
        merchant_id="MERCHANT_KZ_99",
        feed_slug="test-feed",
        default_store_id="PP1"
    )
    master = MasterProduct(sku_internal="APL-IPH15", title="Apple iPhone 15", brand="Apple")
    kprod = KaspiProduct(
        kaspi_sku="APL-IPH15",
        current_sale_price=396200.0,
        current_stock=10,
        is_available=True,
        master_product=master
    )

    xml_snippet = KaspiFeedGenerator.format_offer_xml(kprod, ["PP1", "PP2", "PP3"])
    assert 'sku="APL-IPH15"' in xml_snippet
    assert '<price>396200</price>' in xml_snippet
    assert '<availability available="yes" storeId="PP1"/>' in xml_snippet
    assert '<availability available="yes" storeId="PP2"/>' in xml_snippet
    assert '<availability available="yes" storeId="PP3"/>' in xml_snippet
    print("  [OK] Multi-city XML generation (Almaty PP1, Astana PP2, Shymkent PP3) passed")


def test_notifications_service():
    test_section("7. Real-time Notification & Alerting Service")

    notifications.recent_alerts.clear()
    
    import asyncio
    asyncio.run(notifications.alert_out_of_stock("Apple iPhone 15", "APL-IPH15"))
    asyncio.run(notifications.alert_price_surge("Samsung S24 Ultra", "SAM-S24", 500000.0, 580000.0))
    asyncio.run(notifications.alert_new_order("KASPI-ORD-1111", 396200.0, 31200.0))

    assert len(notifications.recent_alerts) == 3
    assert notifications.recent_alerts[0]["event_type"] == "NEW_ORDER"
    assert notifications.recent_alerts[1]["event_type"] == "PRICE_SURGE"
    assert notifications.recent_alerts[2]["event_type"] == "OUT_OF_STOCK"
    print("  [OK] Out-of-Stock, Price Surge and New Order alert dispatches passed")


def test_fastapi_openapi_contract():
    test_section("8. FastAPI OpenAPI Contract & Route Verification")

    schema = app.openapi()
    paths = schema.get("paths", {})

    required_endpoints = [
        "/health",
        "/ui",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/catalog/products",
        "/api/v1/catalog/reprice",
        "/api/v1/catalog/products/{product_id}/history",
        "/api/v1/suppliers",
        "/api/v1/suppliers/{supplier_id}/upload-feed",
        "/api/v1/suppliers/matching/pending-review",
        "/api/v1/suppliers/matching/{offer_id}/confirm",
        "/api/v1/kaspi/shops",
        "/api/v1/kaspi/feed/{feed_slug}.xml",
        "/api/v1/kaspi/shops/{shop_id}/repricer/run",
        "/api/v1/orders",
        "/api/v1/orders/analytics/summary",
        "/api/v1/orders/export/excel",
        "/api/v1/tasks/status",
        "/api/v1/tasks/run/{task_name}",
        "/api/v1/notifications/recent"
    ]

    for ep in required_endpoints:
        assert ep in paths, f"Missing endpoint: {ep}"
    print(f"  [OK] All {len(required_endpoints)} API endpoints verified in OpenAPI schema")


if __name__ == "__main__":
    print("\n=======================================================")
    print("  STARTING FULL SUITE AUTOMATED VERIFICATION          ")
    print("=======================================================")
    test_auth_and_security()
    test_cascade_matching_engine()
    test_supplier_streaming_parser()
    test_pricing_and_repricing()
    test_kaspi_bot_repricer()
    test_kaspi_multi_city_xml()
    test_notifications_service()
    test_fastapi_openapi_contract()
    print("\n=======================================================")
    print("  [PASS] ALL 8 TEST SECTIONS PASSED WITH 100% SUCCESS!     ")
    print("=======================================================\n")
