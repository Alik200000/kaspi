import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict


class MasterProductBase(BaseModel):
    sku_internal: str
    title: str
    brand: Optional[str] = None
    barcode: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None


class MasterProductCreate(MasterProductBase):
    pass


class MasterProductResponse(MasterProductBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    optimal_cost_price: Optional[float] = None
    calculated_sale_price: Optional[float] = None
    total_stock: int = 0

    model_config = ConfigDict(from_attributes=True)
