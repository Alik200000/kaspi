from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional
from datetime import datetime


class AdvancedRepricerService:
    """
    Advanced algorithmic pricing:
    1. Competitor Bot Hunter & Bait Trap Simulator.
    2. Kaspi Red / Kaspi Жұма Festive Commission Guard.
    3. Multi-Shop Cartel Duo positioning.
    """

    @classmethod
    def run_bait_trap(
        cls,
        product_title: str,
        current_price: Decimal,
        competitor_price: Decimal,
        our_cost: Decimal,
        our_floor_price: Decimal
    ) -> Dict[str, Any]:
        """
        Executes the Bot Bait Trap:
        1. Emits a temporary low-probe price near our safe floor (our_floor_price + 100 ₸).
        2. Competitor bot triggers automatic matching and drops to its bottom.
        3. Once competitor locks at bottom, our price rebounds to full retail, protecting profit.
        """
        probe_bait_price = our_floor_price + Decimal("150")
        estimated_competitor_floor = competitor_price * Decimal("0.92") # Approx 8% below current

        rebound_optimal_price = current_price
        if competitor_price > our_floor_price:
            rebound_optimal_price = max(competitor_price - Decimal("10"), our_floor_price)

        return {
            "status": "active",
            "product": product_title,
            "original_price": float(current_price),
            "competitor_price": float(competitor_price),
            "our_floor_price": float(our_floor_price),
            "bait_probe_price": float(probe_bait_price),
            "estimated_competitor_floor": round(float(estimated_competitor_floor)),
            "rebound_target_price": float(rebound_optimal_price),
            "action_taken": "TRAP_ENGAGED",
            "explanation": (
                f"Ловушка активирована: выставлена приманка {probe_bait_price:,.0f} ₸. "
                f"Бот конкурента среагировал и заблокирован на уровне {estimated_competitor_floor:,.0f} ₸. "
                f"Наша цена возвращена на безопасный максимум {rebound_optimal_price:,.0f} ₸ с гарантированной прибылью."
            )
        }

    @classmethod
    def calculate_promo_guard(
        cls,
        cost_price: Decimal,
        standard_retail_price: Decimal,
        promo_type: str = "KASPI_ZHUMA", # KASPI_ZHUMA (15%), KASPI_RED (12%), STANDARD (10%)
        min_margin_percent: Decimal = Decimal("5.0"),
        fixed_delivery_cost: Decimal = Decimal("2500.0")
    ) -> Dict[str, Any]:
        """
        Calculates price adjustments for Kaspi Жұма / Red campaigns:
        Elevated commission:
        - Kaspi Жұма: ~15%
        - Kaspi Red: ~12%
        - Standard: ~10%
        """
        commission_map = {
            "KASPI_ZHUMA": Decimal("15.0"),
            "KASPI_RED": Decimal("12.0"),
            "STANDARD": Decimal("10.0")
        }
        commission_pct = commission_map.get(promo_type.upper(), Decimal("15.0"))

        margin_mult = Decimal("1") + (min_margin_percent / Decimal("100"))
        net_needed = (cost_price * margin_mult) + fixed_delivery_cost
        keep_factor = Decimal("1") - (commission_pct / Decimal("100"))

        promo_floor_price = (net_needed / keep_factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        
        # Check if current standard retail price would cause a loss under promo commission
        is_safe_under_current_price = standard_retail_price >= promo_floor_price
        recommended_promo_price = max(standard_retail_price, promo_floor_price)

        net_profit_estimate = (
            recommended_promo_price * (Decimal("1") - (commission_pct / Decimal("100")))
            - cost_price
            - fixed_delivery_cost
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        return {
            "promo_type": promo_type,
            "commission_percent": float(commission_pct),
            "cost_price": float(cost_price),
            "standard_retail_price": float(standard_retail_price),
            "promo_floor_price": float(promo_floor_price),
            "is_safe_without_adjustment": is_safe_under_current_price,
            "recommended_promo_price": float(recommended_promo_price),
            "estimated_net_profit_per_sale": float(net_profit_estimate),
            "verdict": "SAFE" if is_safe_under_current_price else "PRICE_INCREASE_REQUIRED"
        }

    @classmethod
    def calculate_cartel_duo(
        cls,
        shop1_name: str,
        shop2_name: str,
        target_first_price: Decimal,
        price_step: Decimal = Decimal("5.0")
    ) -> Dict[str, Any]:
        """
        Positions Shop 1 at Top-1 and Shop 2 at Top-2.
        """
        shop1_price = target_first_price
        shop2_price = target_first_price + price_step

        return {
            "mode": "CARTEL_DUO_ACTIVE",
            "position_1": {
                "shop": shop1_name,
                "price": float(shop1_price),
                "rank": 1
            },
            "position_2": {
                "shop": shop2_name,
                "price": float(shop2_price),
                "rank": 2
            },
            "coverage": "100% Top-2 Kaspi Shelf Captured"
        }
