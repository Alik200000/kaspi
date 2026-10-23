from decimal import Decimal
from typing import Optional, List, Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel

from app.modules.pricing.advanced_repricer import AdvancedRepricerService

router = APIRouter(prefix="/pricing/advanced", tags=["Advanced Repricer & Anti-Dumping 2.0"])


class BaitTrapPayload(BaseModel):
    product_title: str
    current_price: float
    competitor_price: float
    our_cost: float
    our_floor_price: float


class PromoGuardPayload(BaseModel):
    cost_price: float
    standard_retail_price: float
    promo_type: str = "KASPI_ZHUMA" # KASPI_ZHUMA, KASPI_RED
    min_margin_percent: float = 5.0
    fixed_delivery_cost: float = 2500.0


class CartelDuoPayload(BaseModel):
    shop1_name: str = "Магазин 1 (ИП Асыл)"
    shop2_name: str = "Магазин 2 (ТОО Олимп)"
    target_first_price: float
    price_step: float = 5.0


@router.get("/status")
async def get_advanced_repricer_status():
    return {
        "bait_trap_engine": "ACTIVE",
        "promo_guard_engine": "ACTIVE",
        "cartel_duo_engine": "ACTIVE",
        "supported_promos": ["KASPI_ZHUMA", "KASPI_RED", "STANDARD"],
        "strategies": [
            {"id": "bait_trap", "name": "Ловушка для ботов-демпингеров", "desc": "Выявляет ботов, фиксирует их на минимуме и поднимает нашу цену"},
            {"id": "promo_guard", "name": "Защита маржи Kaspi Жұма / Red", "desc": "Пересчет комиссий 12-15% для исключения торговли в убыток"},
            {"id": "cartel_duo", "name": "Картельный режим (Топ 1 и Топ 2)", "desc": "Координация 2-х магазинов одного владельца для 100% захвата витрины"}
        ]
    }


@router.post("/bait-trap")
async def trigger_bait_trap(payload: BaitTrapPayload):
    result = AdvancedRepricerService.run_bait_trap(
        product_title=payload.product_title,
        current_price=Decimal(str(payload.current_price)),
        competitor_price=Decimal(str(payload.competitor_price)),
        our_cost=Decimal(str(payload.our_cost)),
        our_floor_price=Decimal(str(payload.our_floor_price))
    )
    return result


@router.post("/promo-guard")
async def evaluate_promo_guard(payload: PromoGuardPayload):
    result = AdvancedRepricerService.calculate_promo_guard(
        cost_price=Decimal(str(payload.cost_price)),
        standard_retail_price=Decimal(str(payload.standard_retail_price)),
        promo_type=payload.promo_type,
        min_margin_percent=Decimal(str(payload.min_margin_percent)),
        fixed_delivery_cost=Decimal(str(payload.fixed_delivery_cost))
    )
    return result


@router.post("/cartel-duo")
async def calculate_cartel_duo(payload: CartelDuoPayload):
    result = AdvancedRepricerService.calculate_cartel_duo(
        shop1_name=payload.shop1_name,
        shop2_name=payload.shop2_name,
        target_first_price=Decimal(str(payload.target_first_price)),
        price_step=Decimal(str(payload.price_step))
    )
    return result


class CheckPriceSurgePayload(BaseModel):
    sku: str
    product_title: str
    supplier_name: str
    old_cost: float
    new_cost: float
    threshold_pct: float = 15.0


@router.get("/circuit-breaker/status")
async def get_circuit_breaker_status():
    """
    Returns live status of the Supplier Price Surge Circuit Breaker.
    """
    from app.modules.pricing.circuit_breaker import SupplierPriceSurgeCircuitBreaker
    return SupplierPriceSurgeCircuitBreaker.get_status()


@router.post("/circuit-breaker/check")
async def evaluate_price_surge(payload: CheckPriceSurgePayload):
    """
    Checks incoming supplier cost change and auto-blocks SKU if surge exceeds threshold.
    """
    from app.modules.pricing.circuit_breaker import SupplierPriceSurgeCircuitBreaker
    return SupplierPriceSurgeCircuitBreaker.evaluate_price_change(
        sku=payload.sku,
        product_title=payload.product_title,
        supplier_name=payload.supplier_name,
        old_cost=payload.old_cost,
        new_cost=payload.new_cost,
        threshold_pct=payload.threshold_pct
    )


@router.post("/circuit-breaker/{sku}/unlock")
async def unlock_circuit_breaker_sku(sku: str):
    """
    Unlocks a paused SKU after seller confirms new supplier pricing.
    """
    from app.modules.pricing.circuit_breaker import SupplierPriceSurgeCircuitBreaker
    res = SupplierPriceSurgeCircuitBreaker.unlock_sku(sku)
    if not res:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="SKU не найден в списке заблокированных")
    return res

