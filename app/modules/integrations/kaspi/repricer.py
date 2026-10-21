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
        strategy: str = "competitor_minus_1",
        blacklisted_merchants: Optional[List[str]] = None,
        night_mode_enabled: bool = False,
        night_markup_percent: Decimal = Decimal("3.0")
    ) -> Tuple[Decimal, str, Optional[Dict[str, Any]]]:
        """
        Calculates optimal target price based on competitor landscape.
        Supports:
        - Floor Price Guard (prevents loss)
        - Competitor undercutting (-10 KZT)
        - Upward price pull (steps up if competitor raises price or goes OOS)
        - Blacklist filter (ignores rogue/fake dumping merchants)
        - Night Mode (boosts margin during low-activity night hours)
        """
        if strategy == "disabled":
            return (current_our_price, "strategy_disabled", None)

        # 1. Filter out blacklisted merchants (fake dumpers)
        blacklist = set(m.lower().strip() for m in (blacklisted_merchants or []))
        filtered_comps = [
            c for c in competitors
            if c.get("price") and Decimal(str(c["price"])) > 0
            and c.get("merchant", "").lower().strip() not in blacklist
        ]

        if not filtered_comps:
            # If no valid competitors remain, pull price up to ceiling or keep current
            target = ceiling_price if ceiling_price else current_our_price
            return (target, "no_valid_competitors_ceiling_applied", None)

        # Sort competitors by price ascending
        valid_competitors = sorted(
            filtered_comps,
            key=lambda c: Decimal(str(c["price"]))
        )

        top_competitor = valid_competitors[0]
        top_comp_price = Decimal(str(top_competitor["price"]))

        if strategy == "competitor_minus_1":
            # Undercut competitor by 10 KZT to capture Top-1 position
            target = top_comp_price - Decimal("10")

            # Check if competitor is dumping below our floor price
            if target < floor_price:
                return (floor_price, "floor_price_guard_activated", top_competitor)

            # Check price ceiling if configured
            if ceiling_price and target > ceiling_price:
                target = ceiling_price

            # Night Mode: during night hours, boost margin slightly (+3%)
            if night_mode_enabled:
                night_target = target * (Decimal("1") + (night_markup_percent / Decimal("100")))
                if ceiling_price:
                    night_target = min(night_target, ceiling_price)
                return (night_target.quantize(Decimal("1"), rounding=ROUND_HALF_UP), "night_mode_margin_boost", top_competitor)

            # Upward recovery: if our current price was dumped lower but competitor raised price,
            # we pull our price up to target
            if current_our_price < target:
                return (target, "pulled_price_upward_to_maximize_profit", top_competitor)
            elif current_our_price == target:
                return (target, "holding_top_1_position", top_competitor)
            else:
                return (target, "undercut_competitor_to_win_top_1", top_competitor)

        elif strategy == "match_min":
            target = max(top_comp_price, floor_price)
            return (target, "match_competitor_price", top_competitor)

        return (current_our_price, "strategy_default", top_competitor)
