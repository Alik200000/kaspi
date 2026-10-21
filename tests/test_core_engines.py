import io
import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from decimal import Decimal

from unittest.mock import MagicMock

from app.modules.pricing.engine import PricingEngine
from app.modules.pricing.models import PricingRule
from app.modules.catalog.models import MasterProduct
from app.modules.suppliers.models import SupplierOffer, Supplier
from app.modules.suppliers.parser import SupplierFeedParser
from app.modules.integrations.kaspi.feed_generator import KaspiFeedGenerator
from app.modules.integrations.kaspi.models import KaspiShop, KaspiProduct


def test_pricing_engine():
    print("Testing PricingEngine...")
    
    # Setup offers
    offer_supplier1 = SupplierOffer(
        supplier_sku="SUP1-A",
        raw_title="Samsung Galaxy S24",
        cost_price=350000.0,
        stock_quantity=5,
        is_available=True
    )
    # Supplier 2 has cheaper price
    offer_supplier2 = SupplierOffer(
        supplier_sku="SUP2-A",
        raw_title="Samsung Galaxy S24",
        cost_price=340000.0,
        stock_quantity=2,
        is_available=True
    )
    # Supplier 3 is out of stock (should be ignored)
    offer_supplier3 = SupplierOffer(
        supplier_sku="SUP3-A",
        raw_title="Samsung Galaxy S24",
        cost_price=320000.0,
        stock_quantity=0,
        is_available=True
    )

    best_offer = PricingEngine.select_optimal_offer([offer_supplier1, offer_supplier2, offer_supplier3])
    assert best_offer is not None, "Failed: Best offer should not be None"
    assert best_offer.supplier_sku == "SUP2-A", f"Expected SUP2-A, got {best_offer.supplier_sku}"
    print("  [OK] Optimal supplier selection passed (cheapest in-stock supplier chosen)")

    # Test markup calculations
    prod = MasterProduct(
        sku_internal="SAM-S24",
        title="Samsung Galaxy S24 256GB",
        brand="Samsung",
        category="Smartphones"
    )

    # Rule: 10% markup + 1000 KZT fixed for Samsung brand
    rule = PricingRule(
        name="Samsung Rule",
        brand="Samsung",
        markup_percent=10.0,
        markup_fixed=1000.0,
        min_margin_percent=5.0,
        priority=10
    )

    # Cost 340,000 -> 340,000 * 1.10 = 374,000 + 1,000 = 375,000
    final_price = PricingEngine.calculate_final_price(prod, Decimal("340000"), [rule])
    assert final_price == Decimal("375000"), f"Expected 375000, got {final_price}"
    print("  [OK] Pricing markup calculation passed (340,000 -> 375,000 KZT)")


def test_feed_parser():
    print("Testing SupplierFeedParser...")
    sample_csv = (
        "Артикул;Наименование;Бренд;Штрихкод;Цена;Остаток\n"
        "ART-001;Наушники Sony WH-1000XM5;Sony;4548736132580;165 000 ₸;12\n"
        "ART-002;Мышь Logitech MX Master 3S;Logitech;5099206103726;48000;> 20\n"
    )
    
    stream = io.StringIO(sample_csv)
    rows = list(SupplierFeedParser.parse_csv_stream(stream, delimiter=";"))
    assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
    assert rows[0]["supplier_sku"] == "ART-001"
    assert rows[0]["cost_price"] == Decimal("165000")
    assert rows[0]["stock_quantity"] == 12
    assert rows[1]["cost_price"] == Decimal("48000")
    assert rows[1]["stock_quantity"] == 20
    print("  [OK] Streaming CSV parsing with currency cleanup passed")


def test_kaspi_xml_feed():
    print("Testing Kaspi XML Feed generator...")
    shop = KaspiShop(
        name="Techno Hub KZ",
        merchant_id="MERCHANT_9988",
        feed_slug="technohub",
        default_store_id="PP1"
    )
    
    master = MasterProduct(
        sku_internal="SONY-WH5",
        title="Sony WH-1000XM5 Black",
        brand="Sony"
    )
    
    kaspi_prod = KaspiProduct(
        kaspi_sku="KASPI-SONY-01",
        current_sale_price=189990.0,
        current_stock=8,
        is_available=True,
        master_product=master
    )

    xml_snippet = KaspiFeedGenerator.format_offer_xml(kaspi_prod, shop.default_store_id)
    assert '<offer sku="KASPI-SONY-01">' in xml_snippet
    assert '<brand>Sony</brand>' in xml_snippet
    assert '<availability available="yes" storeId="PP1"/>' in xml_snippet
    assert '<price>189990</price>' in xml_snippet
    print("  [OK] Kaspi XML format compliant with Kaspi merchant catalog specifications")


if __name__ == "__main__":
    test_pricing_engine()
    test_feed_parser()
    test_kaspi_xml_feed()
    print("\nALL ARCHITECTURE TESTS PASSED SUCCESSFULLY!")
