import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.orders.models import Order, OrderItem
from app.modules.catalog.models import MasterProduct


class WarehouseScannerService:
    """
    Mobile Warehouse & Order Fulfillment Scanner:
    Prevents shipping mistakes by matching scanned barcode/SKU with active orders.
    """

    @classmethod
    async def verify_barcode(
        cls,
        scanned_code: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Scans barcode/SKU and matches with an active Kaspi order waiting for assembly.
        """
        code_clean = scanned_code.strip()
        
        # 1. First look up MasterProduct by barcode or SKU
        mp_stmt = select(MasterProduct).where(
            (MasterProduct.barcode == code_clean) |
            (MasterProduct.sku.ilike(code_clean))
        )
        product = (await db.execute(mp_stmt)).scalars().first()

        # 2. Look up orders waiting for packing (NEW or ACCEPTED)
        orders_stmt = select(Order).options(selectinload(Order.items)).where(
            Order.status.in_(["NEW", "ACCEPTED"])
        ).order_by(Order.created_at.asc())
        active_orders = (await db.execute(orders_stmt)).scalars().all()

        for o in active_orders:
            for it in o.items:
                # Check SKU or title or product id match
                matched = False
                if product and it.master_product_id == product.id:
                    matched = True
                elif it.kaspi_sku.lower() == code_clean.lower():
                    matched = True
                elif product and product.sku.lower() in it.title.lower():
                    matched = True

                if matched:
                    return {
                        "verified": True,
                        "status": "MATCH",
                        "order_id": str(o.id),
                        "external_order_id": o.external_order_id,
                        "customer_name": o.customer_name or "Клиент Kaspi",
                        "product_title": it.title,
                        "sku": it.kaspi_sku,
                        "quantity": it.quantity,
                        "delivery_address": o.delivery_address or "Kaspi Доставка",
                        "audio_cue": "SUCCESS_BEEP",
                        "message": f"✓ Товар проверен! Заказ #{o.external_order_id} готов к упаковке."
                    }

        # If product was found in catalog but no order needs it:
        if product:
            return {
                "verified": False,
                "status": "MISMATCH_NO_ORDER",
                "scanned_code": code_clean,
                "product_found": product.title,
                "audio_cue": "ERROR_BUZZER",
                "message": f"⚠️ Товар «{product.title}» есть на складе, но нет активных заказов Kaspi, ожидающих сборку!"
            }

        # Unknown barcode
        return {
            "verified": False,
            "status": "UNKNOWN_BARCODE",
            "scanned_code": code_clean,
            "audio_cue": "ERROR_BUZZER",
            "message": f"❌ Штрихкод {code_clean} не найден в каталоге магазина!"
        }

    @classmethod
    async def complete_assembly(
        cls,
        order_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Advances order to ASSEMBLED status and provides label print link.
        """
        try:
            o_uuid = uuid.UUID(order_id)
        except ValueError:
            raise ValueError("Invalid order UUID")

        stmt = select(Order).where(Order.id == o_uuid)
        order = (await db.execute(stmt)).scalar_one_or_none()
        if not order:
            raise ValueError("Order not found")

        order.status = "ASSEMBLED"
        order.synced_at = datetime.utcnow()
        await db.commit()

        return {
            "status": "success",
            "order_id": str(order.id),
            "external_order_id": order.external_order_id,
            "new_status": "ASSEMBLED",
            "label_url": f"/api/v1/orders/{order.id}/shipping-label-html?format=58x40&autoprint=true",
            "message": f"Заказ #{order.external_order_id} собран! Термоэтикетка отправлена на печать."
        }
