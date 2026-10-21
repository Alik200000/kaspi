import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Numeric, Integer, JSON, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Supplier(Base):
    """External supplier definition."""
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    integration_type: Mapped[str] = mapped_column(String(50), default="file") # 'file', 'api', 'ftp', 'url'
    
    # JSON configuration for file column mapping, update schedules, delivery days
    feed_config: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    delivery_days: Mapped[int] = mapped_column(Integer, default=1)
    priority: Mapped[int] = mapped_column(Integer, default=1) # higher priority preferred if costs are equal
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_org_supplier_code"),
    )

    offers: Mapped[list["SupplierOffer"]] = relationship(back_populates="supplier", cascade="all, delete-orphan")


class SupplierOffer(Base):
    """
    Live offer from a supplier. Multiple supplier offers can link to one MasterProduct.
    """
    __tablename__ = "supplier_offers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    master_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("master_products.id", ondelete="SET NULL"), nullable=True)
    
    supplier_sku: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    raw_title: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    
    cost_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Matching metadata
    match_confidence: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0) # 0.00 to 1.00
    match_type: Mapped[str] = mapped_column(String(50), default="none") # 'barcode', 'sku', 'fuzzy_auto', 'manual'
    match_status: Mapped[str] = mapped_column(String(50), default="unmatched") # 'confirmed', 'pending_review', 'unmatched'

    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("supplier_id", "supplier_sku", name="uq_supplier_sku"),
    )

    supplier: Mapped["Supplier"] = relationship(back_populates="offers")
    master_product: Mapped[Optional["MasterProduct"]] = relationship("MasterProduct", back_populates="supplier_offers")
