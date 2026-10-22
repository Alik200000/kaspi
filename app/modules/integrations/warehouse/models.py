import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class WarehouseIntegration(Base):
    """
    Configuration for external warehouse ERP/accounting systems:
    - МойСклад (REST API 1.2)
    - 1С:Предприятие (CommerceML 2.0 exchange protocol)
    """
    __tablename__ = "warehouse_integrations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    system_type: Mapped[str] = mapped_column(String(50), default="moysklad") # 'moysklad', 'onec'
    name: Mapped[str] = mapped_column(String(255), default="Основной склад")
    
    # Credentials & Connection
    api_token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True) # MoySklad Bearer token or login:password
    api_url: Mapped[Optional[str]] = mapped_column(String(500), default="https://api.moysklad.ru/api/remap/1.2")
    warehouse_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # MoySklad warehouse UUID
    warehouse_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Synchronization flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_sync_stock: Mapped[bool] = mapped_column(Boolean, default=True) # Import stock into MasterProducts
    auto_push_orders: Mapped[bool] = mapped_column(Boolean, default=True) # Push Kaspi orders into MoySklad/1C
    
    # 1C CommerceML specific settings
    cml_username: Mapped[Optional[str]] = mapped_column(String(100), default="kaspi_1c")
    cml_password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Audit & Status
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[Optional[str]] = mapped_column(String(50), default="IDLE") # SUCCESS, ERROR, IDLE
    last_sync_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_sync_items_count: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
