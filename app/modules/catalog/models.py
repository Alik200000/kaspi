import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Numeric, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Organization(Base):
    """Multi-tenant organization entity."""
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    users: Mapped[List["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    master_products: Mapped[List["MasterProduct"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    """User account with RBAC."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="manager") # owner, admin, manager, viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="users")


class MasterProduct(Base):
    """
    Canonical core product representing a single SKU across the whole platform.
    Can aggregate multiple supplier offers and map to multiple marketplace stores.
    """
    __tablename__ = "master_products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    sku_internal: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Pre-calculated pricing cache (updated by pricing engine)
    optimal_cost_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    calculated_sale_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    total_stock: Mapped[int] = mapped_column(default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "sku_internal", name="uq_org_internal_sku"),
    )

    organization: Mapped["Organization"] = relationship(back_populates="master_products")
    supplier_offers: Mapped[List["SupplierOffer"]] = relationship("SupplierOffer", back_populates="master_product")
    price_history: Mapped[List["PriceHistory"]] = relationship("PriceHistory", back_populates="master_product", cascade="all, delete-orphan")


class PriceHistory(Base):
    """
    Audit log tracking cost and retail price shifts, stock movements,
    and repricing triggers over time.
    """
    __tablename__ = "price_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    master_product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("master_products.id", ondelete="CASCADE"), nullable=False)
    
    old_cost_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    new_cost_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    
    old_sale_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    new_sale_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    
    old_stock: Mapped[Optional[int]] = mapped_column(default=0)
    new_stock: Mapped[Optional[int]] = mapped_column(default=0)
    
    change_reason: Mapped[str] = mapped_column(String(255), default="automatic_reprice") # 'supplier_feed_update', 'automatic_reprice', 'manual_override'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    master_product: Mapped["MasterProduct"] = relationship(back_populates="price_history")
