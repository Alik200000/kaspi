import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Numeric, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class VendorClaim(Base):
    """
    Supplier Defect & Warranty Claim record (RMA).
    Generates legal claim acts against suppliers to recover losses from returns.
    """
    __tablename__ = "vendor_claims"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    external_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_title: Mapped[str] = mapped_column(String(500), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    defect_type: Mapped[str] = mapped_column(String(100), default="FACTORY_DEFECT") # FACTORY_DEFECT, PHYSICAL_DAMAGE, MISSING_PARTS
    defect_description: Mapped[str] = mapped_column(Text, nullable=False)
    claim_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), default="SUBMITTED") # SUBMITTED, ACCEPTED, COMPENSATED, REJECTED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
