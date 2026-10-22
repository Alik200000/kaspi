import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import UserSubscription, PaymentInvoice, SubscriptionTier


class BillingService:
    """
    SaaS multi-tenant subscription and Kaspi Pay QR billing engine.
    """

    PLANS = [
        {
            "tier": SubscriptionTier.START,
            "name": "Старт (Тестовый)",
            "price_kzt": 0,
            "period": "Бессрочно",
            "max_skus": 50,
            "max_shops": 1,
            "features": [
                "До 50 товаров в каталоге",
                "1 магазин Kaspi",
                "Синхронизация прайсов (CSV/Excel)",
                "Базовый репрайсинг",
                "Поддержка в Telegram"
            ],
            "popular": False
        },
        {
            "tier": SubscriptionTier.BUSINESS,
            "name": "Бизнес (Оптимальный)",
            "price_kzt": 19900,
            "period": "в месяц",
            "max_skus": 1000,
            "max_shops": 3,
            "features": [
                "До 1 000 товаров в каталоге",
                "До 3 магазинов Kaspi (мульти-аккаунты)",
                "Kaspi Smart Repricer (авто-перебив на 10 ₸)",
                "Floor Price Guard (защита от демпинга)",
                "Печать термоэтикеток 58x40 и 100x150",
                "Telegram-бот мгновенных уведомлений",
                "Kaspi AI: Автоответчик на отзывы и SOS-перехват"
            ],
            "popular": True
        },
        {
            "tier": SubscriptionTier.ENTERPRISE,
            "name": "Магнат / Pro",
            "price_kzt": 39900,
            "period": "в месяц",
            "max_skus": 999999,
            "max_shops": 10,
            "features": [
                "Неограниченно товаров и магазинов",
                "Полная интеграция 1С:Предприятие & МойСклад",
                "Bait Trap (ловушка для ботов-демпингеров)",
                "Кросс-маркетплейс: Kaspi + WB + Ozon + Halyk",
                "AI Smart Restock и ABC/XYZ матрица",
                "Мобильный сканер кладовщика (/scanner)",
                "Приоритетный сервер и личный менеджер 24/7"
            ],
            "popular": False
        }
    ]

    @classmethod
    async def get_current_subscription(cls, db: AsyncSession) -> Dict[str, Any]:
        stmt = select(UserSubscription).order_by(desc(UserSubscription.created_at))
        sub = (await db.execute(stmt)).scalars().first()

        if not sub:
            # Create default Business plan
            sub = UserSubscription(
                tier=SubscriptionTier.BUSINESS,
                plan_name="Тариф «Бизнес»",
                price_kzt=19900.00,
                max_skus=1000,
                max_shops=3,
                status="ACTIVE",
                expires_at=datetime.utcnow() + timedelta(days=28)
            )
            db.add(sub)
            await db.commit()
            await db.refresh(sub)

        now = datetime.utcnow()
        days_left = max(0, (sub.expires_at - now).days) if sub.expires_at else 30

        return {
            "tier": sub.tier,
            "plan_name": sub.plan_name,
            "price_kzt": float(sub.price_kzt),
            "status": sub.status,
            "max_skus": sub.max_skus,
            "max_shops": sub.max_shops,
            "days_left": days_left,
            "expires_at": sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else "30 дней",
            "has_ai_reviews": sub.has_ai_reviews,
            "has_smart_restock": sub.has_smart_restock,
            "has_bait_trap": sub.has_bait_trap,
            "has_warehouse_erp": sub.has_warehouse_erp,
            "has_multichannel": sub.has_multichannel
        }

    @classmethod
    async def create_invoice_and_activate(
        cls,
        tier: str,
        payment_method: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        plan = next((p for p in cls.PLANS if p["tier"] == tier.upper()), cls.PLANS[1])
        inv_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        inv = PaymentInvoice(
            invoice_number=inv_number,
            tier=plan["tier"],
            amount_kzt=plan["price_kzt"],
            payment_method=payment_method,
            status="PAID",
            kaspi_payment_link=f"https://kaspi.kz/pay?service_id=kaspi_saas&invoice={inv_number}"
        )
        db.add(inv)

        # Update or create subscription
        stmt = select(UserSubscription).order_by(desc(UserSubscription.created_at))
        sub = (await db.execute(stmt)).scalars().first()
        if not sub:
            sub = UserSubscription()
            db.add(sub)

        sub.tier = plan["tier"]
        sub.plan_name = plan["name"]
        sub.price_kzt = plan["price_kzt"]
        sub.max_skus = plan["max_skus"]
        sub.max_shops = plan["max_shops"]
        sub.status = "ACTIVE"
        sub.expires_at = datetime.utcnow() + timedelta(days=30)

        await db.commit()

        return {
            "status": "success",
            "invoice_number": inv_number,
            "activated_plan": plan["name"],
            "amount_paid_kzt": plan["price_kzt"],
            "payment_method": payment_method,
            "valid_until": sub.expires_at.strftime("%d.%m.%Y"),
            "message": f"Тариф «{plan['name']}» успешно активирован на 30 дней!"
        }
