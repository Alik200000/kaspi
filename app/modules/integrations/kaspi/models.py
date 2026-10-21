import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Numeric, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class KaspiShop(Base):
    """
    Connected Kaspi.kz merchant account/store.
    Supports multi-store configurations per organization.
    """
    __tablename__ = "kaspi_shops"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False) # e.g. "Kaspi Almaty Store"
    merchant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    api_token: Mapped[str] = mapped_column(String(512), nullable=False)
    
    # Unique slug for public XML price feed access (e.g. /api/v1/kaspi/feed/{feed_slug}.xml)
    feed_slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    
    # Default city / point of presence ID for Kaspi delivery (e.g. "PP1")
    default_store_id: Mapped[str] = mapped_column(String(50), default="PP1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_feed_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    products: Mapped[list["KaspiProduct"]] = relationship(back_populates="shop", cascade="all, delete-orphan")


class KaspiProduct(Base):
    """
    Link between MasterProduct and a specific Kaspi Merchant store.
    """
    __tablename__ = "kaspi_products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kaspi_shop_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("kaspi_shops.id", ondelete="CASCADE"), nullable=False)
    master_product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("master_products.id", ondelete="CASCADE"), nullable=False)
    
    # Kaspi SKU / Offer identifier
    kaspi_sku: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    
    current_sale_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    current_stock: Mapped[int] = mapped_column(Integer, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_synced: Mapped[bool] = mapped_column(Boolean, default=True)

    # Kaspi Dynamic Repricer (Dumping & Top-1 automation)
    is_repricer_active: Mapped[bool] = mapped_column(Boolean, default=True)
    repricer_strategy: Mapped[str] = mapped_column(String(50), default="competitor_minus_1") # 'competitor_minus_1', 'fixed_margin', 'disabled'
    min_allowed_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True) # Floor Price Guard
    max_allowed_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True) # Price ceiling
    competitor_min_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True) # Detected lowest competitor price
    competitor_merchant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("kaspi_shop_id", "kaspi_sku", name="uq_shop_kaspi_sku"),
    )

    shop: Mapped["KaspiShop"] = relationship(back_populates="products")
    master_product: Mapped["MasterProduct"] = relationship("MasterProduct")
