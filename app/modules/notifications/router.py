from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
from app.modules.notifications.service import notifications

router = APIRouter(prefix="/notifications", tags=["Notifications & Telegram Alerts"])


class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str


@router.get("/recent")
async def get_recent_notifications():
    """
    Returns the latest high-priority system alerts:
    - Out of Stock events
    - Supplier Price Surges (> 10%)
    - New Kaspi Orders with unit economics
    """
    return notifications.recent_alerts


@router.get("/telegram/config")
async def get_telegram_config():
    """
    Returns whether Telegram bot is configured and the masked chat ID.
    """
    is_configured = bool(notifications.telegram_bot_token and notifications.telegram_chat_id)
    masked_chat = notifications.telegram_chat_id if notifications.telegram_chat_id else None
    return {
        "is_configured": is_configured,
        "chat_id": masked_chat,
        "has_token": bool(notifications.telegram_bot_token)
    }


@router.post("/telegram/config")
async def set_telegram_config(payload: TelegramConfig):
    """
    Configures real Telegram Bot API credentials for instant phone push notifications.
    """
    notifications.configure_telegram(payload.bot_token, payload.chat_id)
    return {
        "status": "success",
        "message": "Параметры Telegram успешно сохранены",
        "chat_id": payload.chat_id
    }


@router.post("/telegram/test")
async def test_telegram_alert(payload: Optional[TelegramConfig] = None):
    """
    Sends a test push notification to verify the Telegram bot credentials.
    """
    token = payload.bot_token if payload and payload.bot_token else notifications.telegram_bot_token
    chat_id = payload.chat_id if payload and payload.chat_id else notifications.telegram_chat_id

    if not token or not chat_id:
        raise HTTPException(status_code=400, detail="Telegram Bot Token и Chat ID не настроены")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    text = (
        "🚀 *Kaspi & Supplier SaaS Platform*\n\n"
        "✅ *Тестовое уведомление успешно доставлено!*\n"
        "Ваш Telegram-бот активен и будет присылать:\n"
        "• Обнуление остатков поставщиков (Out-of-Stock)\n"
        "• Резкие скачки цен закупки (> 10%)\n"
        "• Новые заказы с расчетом чистой прибыли"
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
            if resp.status_code == 200:
                # If valid and payload was passed, store it permanently
                if payload:
                    notifications.configure_telegram(payload.bot_token, payload.chat_id)
                return {"status": "success", "message": "Сообщение успешно отправлено в Telegram!"}
            else:
                data = resp.json()
                return {"status": "error", "message": data.get("description", "Ошибка Telegram API")}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка соединения с Telegram: {str(e)}")


@router.post("/simulate-alert")
async def simulate_alert(alert_type: str = "out_of_stock"):
    """
    Simulates a critical event for demonstration and testing:
    - 'out_of_stock'
    - 'price_surge'
    - 'new_order'
    """
    if alert_type == "out_of_stock":
        await notifications.alert_out_of_stock("Apple iPhone 15 128GB Black", "APL-IPH15-128-BLK")
    elif alert_type == "price_surge":
        await notifications.alert_price_surge("Samsung Galaxy S24 Ultra", "SAM-S24U-256-GRY", 540000.0, 610000.0)
    elif alert_type == "new_order":
        await notifications.alert_new_order("KASPI-ORD-9988", 396200.0, 31200.0)
    return {"status": "emitted", "alert_type": alert_type}
