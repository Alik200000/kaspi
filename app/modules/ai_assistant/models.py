import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CustomerReview(Base):
    """
    Stores customer reviews and questions from Kaspi marketplace
    for AI-driven auto-replies, sentiment monitoring and SOS alerting.
    """
    __tablename__ = "customer_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kaspi_shop_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("kaspi_shops.id", ondelete="CASCADE"), nullable=True)
    
    external_review_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), default="Покупатель Kaspi")
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    product_sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    rating: Mapped[int] = mapped_column(Integer, nullable=False) # 1 to 5
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # AI Sentiment: POSITIVE, NEUTRAL, NEGATIVE, CRITICAL_SOS
    ai_sentiment: Mapped[str] = mapped_column(String(50), default="POSITIVE")
    
    reply_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reply_status: Mapped[str] = mapped_column(String(50), default="PENDING") # PENDING, REPLIED, ESCALATED_SOS
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
