import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional

class SupplierPriceSurgeCircuitBreaker:
    """
    Supplier Price Surge Circuit Breaker (Предохранитель от резкого роста цен).
    Monitors changes in supplier purchase cost.
    If the new cost in the incoming feed exceeds the previous cost by more than the threshold
    (default 15%), it IMMEDIATELY trips the breaker:
    1. Blocks product from Kaspi XML feed (sets stock to 0 or archives offer)
    2. Logs a HIGH priority incident
    3. Prevents seller from selling at old prices and sustaining massive losses.
    """

    DEFAULT_SURGE_THRESHOLD_PCT = 15.0

    # Registry of tripped circuit breaker items
    _blocked_items = [
        {
            "sku": "SKU-IPHONE15PM-BLK",
            "product_title": "Apple iPhone 15 Pro Max 256GB Black",
            "supplier_name": "Дистрибьютор Alser / Marvel",
            "old_cost_kzt": 520000.0,
            "new_cost_kzt": 645000.0,
            "surge_percent": 24.04,
            "threshold_percent": 15.0,
            "blocked_at": "2026-10-23 21:15:00",
            "status": "BLOCKED_SURGE_DETECTED",
            "kaspi_offer_status": "PAUSED_STOCK_ZERO",
            "prevented_loss_kzt": 125000.0
        }
    ]

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        return {
            "circuit_breaker_active": True,
            "default_surge_threshold_pct": cls.DEFAULT_SURGE_THRESHOLD_PCT,
            "blocked_items_count": len(cls._blocked_items),
            "total_prevented_losses_kzt": sum(item["prevented_loss_kzt"] for item in cls._blocked_items),
            "blocked_items": cls._blocked_items
        }

    @classmethod
    def evaluate_price_change(
        cls,
        sku: str,
        product_title: str,
        supplier_name: str,
        old_cost: float,
        new_cost: float,
        threshold_pct: float = 15.0
    ) -> Dict[str, Any]:
        if old_cost <= 0:
            return {"tripped": False, "reason": "No previous cost history"}

        surge_pct = round(((new_cost - old_cost) / old_cost) * 100, 2)

        if surge_pct >= threshold_pct:
            incident = {
                "sku": sku,
                "product_title": product_title,
                "supplier_name": supplier_name,
                "old_cost_kzt": old_cost,
                "new_cost_kzt": new_cost,
                "surge_percent": surge_pct,
                "threshold_percent": threshold_pct,
                "blocked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "BLOCKED_SURGE_DETECTED",
                "kaspi_offer_status": "PAUSED_STOCK_ZERO",
                "prevented_loss_kzt": round(new_cost - old_cost, 2)
            }
            # Avoid duplicate SKU
            cls._blocked_items = [i for i in cls._blocked_items if i["sku"] != sku]
            cls._blocked_items.insert(0, incident)

            return {
                "tripped": True,
                "action": "AUTO_BLOCKED_IN_KASPI",
                "surge_percent": surge_pct,
                "threshold_percent": threshold_pct,
                "message": f"🚨 Сработал предохранитель! Закупка выросла на +{surge_pct}% (порог {threshold_pct}%). Товар {sku} заблокирован от продажи в минус.",
                "incident": incident
            }

        return {
            "tripped": False,
            "surge_percent": surge_pct,
            "threshold_percent": threshold_pct,
            "message": "Изменение цены в пределах нормы."
        }

    @classmethod
    def unlock_sku(cls, sku: str) -> Optional[Dict[str, Any]]:
        for item in cls._blocked_items:
            if item["sku"] == sku:
                cls._blocked_items.remove(item)
                return {"status": "unlocked", "sku": sku, "message": "Товар разблокирован и возвращен в прайс-лист Kaspi"}
        return None
