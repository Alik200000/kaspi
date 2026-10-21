from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional, Tuple


class KaspiRepricerEngine:
    """
    Automated dumping & smart pricing engine for Kaspi.kz product cards.
    Aims to secure Top-1 position on Kaspi while strictly respecting floor price limits.
    """

    @classmethod
    def calculate_floor_price(
        cls,
        cost_price: Decimal,
        min_margin_percent: Decimal = Decimal("5.0"),
        kaspi_commission_percent: Decimal = Decimal("10.0"),
        fixed_delivery_cost: Decimal = Decimal("2500.0")
    ) -> Decimal:
        """
        Calculates absolute floor price below which product cannot be sold:
        Revenue - (Cost + Margin + Commission + Delivery) >= 0
        Price * (1 - Commission/100) >= Cost * (1 + Margin/100) + Delivery
        Price >= (Cost * (1 + Margin/100) + Delivery) / (1 - Commission/100)
        """
        margin_mult = Decimal("1") + (min_margin_percent / Decimal("100"))
        net_needed = (cost_price * margin_mult) + fixed_delivery_cost
        kaspi_keep_factor = Decimal("1") - (kaspi_commission_percent / Decimal("100"))
        
        floor = net_needed / kaspi_keep_factor
        return floor.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    @classmethod
    def evaluate_target_price(
        cls,
        current_our_price: Decimal,
        competitors: List[Dict[str, Any]], # e.g. [{"merchant": "Technodom", "price": 395000}]
        floor_price: Decimal,
        ceiling_price: Optional[Decimal] = None,
        strategy: str = "competitor_minus_1"
    ) -> Tuple[Decimal, str, Optional[Dict[str, Any]]]:
        """
        Calculates optimal target price based on competitor landscape.
        Returns: (target_price, action_reason, top_competitor)
        """
        if not competitors or strategy == "disabled":
            return (current_our_price, "no_competitors_or_disabled", None)

        # Sort competitors by price ascending
        valid_competitors = sorted(
            [c for c in competitors if c.get("price") and Decimal(str(c["price"])) > 0],
            key=lambda c: Decimal(str(c["price"]))
        )

        if not valid_competitors:
            return (current_our_price, "no_valid_competitors", None)

        top_competitor = valid_competitors[0]
        top_comp_price = Decimal(str(top_competitor["price"]))

        if strategy == "competitor_minus_1":
            # Undercut competitor by 1 KZT (or 10 KZT) to win Top-1 position
            target = top_comp_price - Decimal("10")

            # Check if competitor is severely dumping below our floor price
            if target < floor_price:
                # Fall back to floor price to prevent selling at a loss
                return (floor_price, "floor_price_guard_activated", top_competitor)

            # Check price ceiling if configured
            if ceiling_price and target > ceiling_price:
                target = ceiling_price

            # If our current price is already lower and competitor #2 is far higher,
            # we can optimize upwards while still beating top competitor:
            if current_our_price < target:
                return (target, "undercut_competitor_to_win_top_1", top_competitor)
            elif current_our_price == target:
                return (target, "holding_top_1_position", top_competitor)
            else:
                return (target, "undercut_competitor_to_win_top_1", top_competitor)

        elif strategy == "match_min":
            target = max(top_comp_price, floor_price)
            return (target, "match_competitor_price", top_competitor)

        return (current_our_price, "strategy_default", top_competitor)
