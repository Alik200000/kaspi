import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Real-time alert dispatcher for critical marketplace and supplier events.
    Supports Telegram Bot API, webhooks, and an in-app event log.
    """

    def __init__(self):
        # In-memory circular buffer of the most recent alerts for the UI
        self.recent_alerts: List[Dict[str, Any]] = []
        self.telegram_bot_token: Optional[str] = None
        self.telegram_chat_id: Optional[str] = None

    def configure_telegram(self, bot_token: str, chat_id: str):
        self.telegram_bot_token = bot_token
        self.telegram_chat_id = chat_id

    async def _send_telegram_message(self, text: str):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.info(f"[TELEGRAM ALERT SIMULATED]\n{text}")
            return

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                res = await client.post(url, json=payload)
                res.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {str(e)}")

    async def emit_alert(
        self,
        event_type: str, # 'OUT_OF_STOCK', 'PRICE_SURGE', 'NEW_ORDER'
        title: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        alert_record = {
            "id": len(self.recent_alerts) + 1,
            "event_type": event_type,
            "title": title,
            "message": message,
            "details": details or {},
            "timestamp": datetime.utcnow().strftime("%H:%M:%S")
        }
        self.recent_alerts.insert(0, alert_record)
        if len(self.recent_alerts) > 50:
            self.recent_alerts.pop()

        # Format Telegram text
        icon = "🔴" if event_type == "OUT_OF_STOCK" else ("🟡" if event_type == "PRICE_SURGE" else "🟢")
        tg_text = (
            f"{icon} *{title}*\n"
            f"{message}\n"
            f"_Время: {alert_record['timestamp']}_"
        )
        await self._send_telegram_message(tg_text)

    async def alert_out_of_stock(self, product_title: str, sku: str):
        await self.emit_alert(
            event_type="OUT_OF_STOCK",
            title=f"Товар закончился у всех поставщиков!",
            message=f"Товар *{product_title}* (SKU: `{sku}`) обнулен на Kaspi во избежание штрафа за отмену заказа.",
            details={"sku": sku}
        )

    async def alert_price_surge(self, product_title: str, sku: str, old_cost: float, new_cost: float):
        pct = round(((new_cost - old_cost) / old_cost) * 100, 1)
        await self.emit_alert(
            event_type="PRICE_SURGE",
            title=f"Скачок цены закупки +{pct}%",
            message=f"Поставщик поднял цену на *{product_title}* c {old_cost:,.0f} до {new_cost:,.0f} ₸. Розничная цена Kaspi пересчитана.",
            details={"sku": sku, "old_cost": old_cost, "new_cost": new_cost, "pct": pct}
        )

    async def alert_new_order(self, order_id: str, total_amount: float, net_profit: float):
        await self.emit_alert(
            event_type="NEW_ORDER",
            title=f"Новый заказ Kaspi #{order_id}",
            message=f"Сумма заказа: *{total_amount:,.0f} ₸*\nРасчетная чистая прибыль: *{net_profit:,.0f} ₸*",
            details={"order_id": order_id, "amount": total_amount, "profit": net_profit}
        )


# Global singleton
notifications = NotificationService()
