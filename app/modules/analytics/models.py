import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Numeric, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class PurchaseOrder(Base):
    """
    Supplier Purchase Order generated automatically by AI Smart Restock engine.
    """
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT") # DRAFT, ORDERED, RECEIVED, CANCELLED
    
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0.00)
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # JSON payload with list of items [{sku, title, qty, unit_cost, subtotal}]
    items_json: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
