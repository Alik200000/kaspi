from fastapi import APIRouter
from app.modules.notifications.service import notifications

router = APIRouter(prefix="/notifications", tags=["Notifications & Telegram Alerts"])


@router.get("/recent")
async def get_recent_notifications():
    """
    Returns the latest high-priority system alerts:
    - Out of Stock events
    - Supplier Price Surges (> 10%)
    - New Kaspi Orders with unit economics
    """
    return notifications.recent_alerts


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
