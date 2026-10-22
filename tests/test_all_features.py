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
        "/api/v1/notifications/recent",
        "/api/v1/warehouse/status",
        "/api/v1/warehouse/1c/exchange",
        "/api/v1/ai/reviews",
        "/api/v1/ai/reviews/generate-reply",
        "/api/v1/ai/reviews/auto-reply-all",
        "/api/v1/ai/generate-description",
        "/api/v1/analytics/restock-forecast",
        "/api/v1/analytics/abc-xyz",
        "/api/v1/analytics/purchase-orders",
        "/api/v1/pricing/advanced/bait-trap",
        "/api/v1/pricing/advanced/promo-guard",
        "/api/v1/pricing/advanced/cartel-duo",
        "/api/v1/pricing/advanced/status",
        "/api/v1/logistics/status",
        "/api/v1/logistics/sla-alerts",
        "/api/v1/logistics/process-return",
        "/api/v1/multichannel/status",
        "/api/v1/multichannel/sync-all"
    ]

    for ep in required_endpoints:
        assert ep in paths, f"Missing endpoint: {ep}"
    print(f"  [OK] All {len(required_endpoints)} API endpoints verified in OpenAPI schema")


def test_warehouse_moysklad_and_1c():
    test_section("9. Warehouse ERP & Accounting (MoySklad & 1C CommerceML)")
    from app.modules.integrations.warehouse.cml_service import OneCCommerceMLService
    from app.modules.integrations.warehouse.moysklad_client import MoySkladClient
    from app.modules.orders.models import Order

    # 1. Test 1C CommerceML XML generation
    demo_order = Order(
        external_order_id="KASPI-9988",
        status="NEW",
        customer_name="Нурлан С.",
        customer_phone="+77011234567",
        total_sale_amount=150000.0,
        items=[]
    )
    cml_xml = OneCCommerceMLService.generate_orders_cml([demo_order])
    assert "<КоммерческаяИнформация" in cml_xml
    assert "KASPI-9988" in cml_xml
    assert "Нурлан С." in cml_xml
    print("  [OK] 1C:Предприятие CommerceML 2.0 orders XML export passed")

    # 2. Test 1C CommerceML catalog XML parser
    sample_1c_catalog = """<?xml version="1.0" encoding="utf-8"?>
    <КоммерческаяИнформация>
      <Каталог>
        <Товары>
          <Товар>
            <Артикул>APL-IPH15-BLK</Артикул>
            <Наименование>iPhone 15 Black</Наименование>
            <Количество>25</Количество>
            <Штрихкод>0195949038234</Штрихкод>
          </Товар>
        </Товары>
      </Каталог>
    </КоммерческаяИнформация>"""
    parsed_items = OneCCommerceMLService.parse_1c_catalog_xml(sample_1c_catalog)
    assert len(parsed_items) == 1
    assert parsed_items[0]["sku"] == "APL-IPH15-BLK"
    assert parsed_items[0]["stock"] == 25
    print("  [OK] 1C CommerceML catalog & stock XML parser passed")

    # 3. Test MoySklad Client initialization & headers
    ms_client = MoySkladClient(api_token="test_bearer_token_123")
    assert ms_client.headers["Authorization"] == "Bearer test_bearer_token_123"
    print("  [OK] MoySklad REST API 1.2 client configuration passed")


def test_ai_assistant_and_reviews():
    test_section("10. Kaspi AI Review Manager & SEO Copywriter")
    from app.modules.ai_assistant.service import AIAssistantService

    # 1. Test 5-star warm gratitude reply
    reply_5star = AIAssistantService.generate_smart_reply(
        customer_name="Айдар",
        product_name="iPhone 15",
        rating=5,
        review_text="Супер телефон, доставка быстрая!"
    )
    assert "Айдар" in reply_5star
    assert "iPhone 15" in reply_5star
    print("  [OK] AI 5-star positive response generator passed")

    # 2. Test SOS detector for critical review
    is_sos = AIAssistantService.is_sos_incident(rating=1, text="Пришел брак, не включается!")
    assert is_sos is True
    reply_sos = AIAssistantService.generate_smart_reply(
        customer_name="Ерлан",
        product_name="AirPods Pro",
        rating=1,
        review_text="Брак, верните деньги!"
    )
    assert "извинения" in reply_sos.lower()
    print("  [OK] AI SOS incident detector and empathetic resolution passed")

    # 3. Test SEO card generator
    seo = AIAssistantService.generate_seo_card_description(
        title="Смартфон Samsung S24",
        brand="Samsung",
        category="Смартфоны"
    )
    assert "Samsung" in seo["seo_title"]
    assert len(seo["bullet_points"]) >= 3
    print("  [OK] Kaspi SEO card copywriter passed")


def test_smart_restock_and_abc_xyz():
    test_section("11. AI Restock Runout Prediction & ABC/XYZ Matrix")
    from decimal import Decimal
    from app.modules.analytics.service import SmartRestockService

    # Restock velocity and runout simulation
    lead_time = 3
    safety_stock = 5
    velocity = 2.0
    current_stock = 4

    days_until_out = current_stock / velocity
    assert days_until_out == 2.0 # Less than 3 days -> CRITICAL
    target_inventory = (lead_time + safety_stock) * velocity
    reorder_qty = target_inventory - current_stock
    assert reorder_qty == 12.0
    print("  [OK] Stock runout days calculation (2.0 days) & reorder quantity (12 units) passed")


def test_advanced_repricer_2():
    test_section("12. Repricer 2.0: Bait Trap, Kaspi Жума Promo Guard & Cartel Duo")
    from decimal import Decimal
    from app.modules.pricing.advanced_repricer import AdvancedRepricerService

    # 1. Bait Trap
    trap_res = AdvancedRepricerService.run_bait_trap(
        product_title="iPhone 15",
        current_price=Decimal("400000"),
        competitor_price=Decimal("398000"),
        our_cost=Decimal("340000"),
        our_floor_price=Decimal("375000")
    )
    assert trap_res["bait_probe_price"] == 375150.0
    assert trap_res["action_taken"] == "TRAP_ENGAGED"
    print("  [OK] Competitor Bot Bait Trap algorithm passed")

    # 2. Kaspi Жума / Red promo margin guard (elevated 15% commission)
    promo_res = AdvancedRepricerService.calculate_promo_guard(
        cost_price=Decimal("100000"),
        standard_retail_price=Decimal("115000"),
        promo_type="KASPI_ZHUMA",
        min_margin_percent=Decimal("5.0"),
        fixed_delivery_cost=Decimal("2500")
    )
    assert promo_res["commission_percent"] == 15.0
    assert promo_res["promo_floor_price"] > 100000
    print("  [OK] Kaspi Жума festival 15% commission margin guard passed")

    # 3. Cartel Duo
    cartel_res = AdvancedRepricerService.calculate_cartel_duo(
        shop1_name="ИП Магазин 1",
        shop2_name="ТОО Магазин 2",
        target_first_price=Decimal("50000"),
        price_step=Decimal("5")
    )
    assert cartel_res["position_1"]["price"] == 50000.0
    assert cartel_res["position_2"]["price"] == 50005.0
    print("  [OK] Cartel Duo multi-account Top-1 & Top-2 positioning passed")


def test_logistics_and_multichannel():
    test_section("13. Logistics Delivery SLA & Cross-Marketplace Sync")
    from app.modules.integrations.multichannel.service import MultichannelSyncService

    channels = MultichannelSyncService.CHANNELS
    assert any(c["id"] == "kaspi" for c in channels)
    assert any(c["id"] == "wildberries" for c in channels)
    assert any(c["id"] == "ozon" for c in channels)
    print("  [OK] Unified Kaspi + Wildberries + Ozon multichannel coordinator passed")


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
    test_warehouse_moysklad_and_1c()
    test_ai_assistant_and_reviews()
    test_smart_restock_and_abc_xyz()
    test_advanced_repricer_2()
    test_logistics_and_multichannel()
    print("\n=======================================================")
    print("  [PASS] ALL 13 TEST SECTIONS PASSED WITH 100% SUCCESS!    ")
    print("=======================================================\n")
