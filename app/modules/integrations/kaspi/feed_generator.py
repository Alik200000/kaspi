import html
from datetime import datetime
from typing import AsyncGenerator, Sequence
from app.modules.integrations.kaspi.models import KaspiProduct, KaspiShop


class KaspiFeedGenerator:
    """
    Generates compliant Kaspi XML catalog feeds.
    Format adheres to Kaspi Merchant specifications:
    <kaspi_catalog date="..." xmlns="kaspi_catalog" xmlns:xsi="...">
        <company>...</company>
        <merchantid>...</merchantid>
        <offers>
            <offer sku="...">
                <model>...</model>
                <brand>...</brand>
                <availabilities>
                    <availability available="yes|no" storeId="..."/>
                </availabilities>
                <price>...</price>
            </offer>
        </offers>
    </kaspi_catalog>
    """

    @classmethod
    def generate_feed_header(cls, shop: KaspiShop) -> str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        company_escaped = html.escape(shop.name)
        merchant_escaped = html.escape(shop.merchant_id)
        
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<kaspi_catalog date="{date_str}" '
            'xmlns="kaspi_catalog" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:schemaLocation="kaspi_catalog kaspi_catalog.xsd">\n'
            f'  <company>{company_escaped}</company>\n'
            f'  <merchantid>{merchant_escaped}</merchantid>\n'
            '  <offers>\n'
        )

    @classmethod
    def generate_feed_footer(cls) -> str:
        return '  </offers>\n</kaspi_catalog>\n'

    @classmethod
    def format_offer_xml(cls, item: KaspiProduct, store_ids: Sequence[str]) -> str:
        sku = html.escape(item.kaspi_sku)
        master = item.master_product
        model = html.escape(master.title if master else item.kaspi_sku)
        brand = html.escape(master.brand or "") if master and master.brand else ""
        brand_tag = f"      <brand>{brand}</brand>\n" if brand else ""
        
        # Availability is "yes" only if in stock and enabled
        is_available = "yes" if (item.is_available and (item.current_stock or 0) > 0) else "no"
        price_int = int(item.current_sale_price)

        availabilities_xml = "".join(
            f'        <availability available="{is_available}" storeId="{sid}"/>\n'
            for sid in store_ids
        )

        return (
            f'    <offer sku="{sku}">\n'
            f'      <model>{model}</model>\n'
            f'{brand_tag}'
            f'      <availabilities>\n'
            f'{availabilities_xml}'
            f'      </availabilities>\n'
            f'      <price>{price_int}</price>\n'
            f'    </offer>\n'
        )

    @classmethod
    async def stream_feed(
        cls,
        shop: KaspiShop,
        products: Sequence[KaspiProduct]
    ) -> AsyncGenerator[str, None]:
        """
        Yields the feed line by line or chunk by chunk to prevent loading large catalogs into memory.
        """
        yield cls.generate_feed_header(shop)
        
        # Support multi-city points of presence (PP1: Almaty, PP2: Astana, PP3: Shymkent)
        store_ids = ["PP1", "PP2", "PP3"]
        if shop.default_store_id and shop.default_store_id not in store_ids:
            store_ids.insert(0, shop.default_store_id)

        for prod in products:
            yield cls.format_offer_xml(prod, store_ids)
            
        yield cls.generate_feed_footer()
