import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Numeric, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class PricingRule(Base):
    """
    Pricing and markup rules per organization, optionally scoped by brand, category, or price range.
    """
    __tablename__ = "pricing_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    min_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    max_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    
    markup_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00) # e.g. 15.00 for 15%
    markup_fixed: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00)   # e.g. 500 KZT
    min_margin_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=5.00) # protection against low margin
    
    priority: Mapped[int] = mapped_column(Integer, default=0) # highest priority rule applied first
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
