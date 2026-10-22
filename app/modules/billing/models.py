import uuid
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Integer, Boolean, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class SubscriptionTier:
    START = "START"
    BUSINESS = "BUSINESS"
    ENTERPRISE = "ENTERPRISE"


class UserSubscription(Base):
    """
    SaaS Tenant Subscription record with tier limits and expiration dates.
    """
    __tablename__ = "user_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    
    tier: Mapped[str] = mapped_column(String(50), default=SubscriptionTier.BUSINESS)
    plan_name: Mapped[str] = mapped_column(String(100), default="Тариф «Бизнес»")
    price_kzt: Mapped[float] = mapped_column(Numeric(12, 2), default=19900.00)
    
    # Limits
    max_skus: Mapped[int] = mapped_column(Integer, default=1000)
    max_shops: Mapped[int] = mapped_column(Integer, default=3)
    has_ai_reviews: Mapped[bool] = mapped_column(Boolean, default=True)
    has_smart_restock: Mapped[bool] = mapped_column(Boolean, default=True)
    has_bait_trap: Mapped[bool] = mapped_column(Boolean, default=True)
    has_warehouse_erp: Mapped[bool] = mapped_column(Boolean, default=True)
    has_multichannel: Mapped[bool] = mapped_column(Boolean, default=True)

    status: Mapped[str] = mapped_column(String(50), default="ACTIVE") # ACTIVE, EXPIRED, CANCELLED
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow() + timedelta(days=30)
    )
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PaymentInvoice(Base):
    """
    Invoices generated for subscription renewals via Kaspi Pay QR or Card.
    """
    __tablename__ = "payment_invoices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(50), nullable=False)
    amount_kzt: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    
    payment_method: Mapped[str] = mapped_column(String(50), default="KASPI_PAY_QR") # KASPI_PAY_QR, CARD, INVOICE
    status: Mapped[str] = mapped_column(String(50), default="PAID") # PENDING, PAID, FAILED
    
    kaspi_payment_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
