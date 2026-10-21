import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Order(Base):
    """
    Consolidated order record from marketplaces (Kaspi).
    Tracks unit economics and margins.
    """
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kaspi_shop_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("kaspi_shops.id", ondelete="CASCADE"), nullable=False)
    
    external_order_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False) # NEW, ACCEPTED, ASSEMBLED, COMPLETED, CANCELLED
    
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    delivery_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Financials & Unit Economics
    total_sale_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    total_cost_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00)
    kaspi_commission_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00)
    delivery_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00)
    
    # Net Profit = total_sale_amount - total_cost_amount - kaspi_commission_amount - delivery_cost
    net_profit: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00)
    margin_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("kaspi_shop_id", "external_order_id", name="uq_shop_order"),
    )

    items: Mapped[List["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """
    Specific item within an order, tied to the MasterProduct and the matched SupplierOffer.
    """
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    master_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("master_products.id", ondelete="SET NULL"), nullable=True)
    supplier_offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("supplier_offers.id", ondelete="SET NULL"), nullable=True)
    
    kaspi_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    
    sale_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    purchase_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00)
    item_margin: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00)

    order: Mapped["Order"] = relationship(back_populates="items")
