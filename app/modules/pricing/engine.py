from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple
from app.modules.catalog.models import MasterProduct
from app.modules.suppliers.models import SupplierOffer
from app.modules.pricing.models import PricingRule


class PricingEngine:
    """
    Evaluates supplier offers, picks the optimal supplier,
    and applies rule-based markup calculations.
    """

    @staticmethod
    def select_optimal_offer(offers: List[SupplierOffer]) -> Optional[SupplierOffer]:
        """
        Picks the best offer from available suppliers.
        Criteria:
        1. Must be in stock (stock_quantity > 0 and is_available == True).
        2. Lowest cost_price.
        3. Tie-breaker: highest supplier priority.
        """
        valid_offers = [o for o in offers if o.is_available and (o.stock_quantity or 0) > 0]
        if not valid_offers:
            return None

        def get_offer_sort_key(o: SupplierOffer):
            cost = Decimal(str(o.cost_price))
            supplier_prio = 1
            # Safely check if supplier relationship is already loaded in memory
            if "supplier" in o.__dict__ and o.__dict__["supplier"]:
                supplier_prio = getattr(o.__dict__["supplier"], "priority", 1)
            return (cost, -supplier_prio)

        valid_offers.sort(key=get_offer_sort_key)
        return valid_offers[0]

    @staticmethod
    def find_matching_rule(
        product: MasterProduct,
        cost_price: Decimal,
        rules: List[PricingRule]
    ) -> Optional[PricingRule]:
        """
        Finds the highest priority pricing rule that matches the product attributes and cost range.
        """
        active_rules = sorted(
            [r for r in rules if getattr(r, "is_active", True) is not False],
            key=lambda r: getattr(r, "priority", 0) or 0,
            reverse=True
        )

        for rule in active_rules:
            # Check brand match if rule specifies brand
            if rule.brand and product.brand and rule.brand.lower() != product.brand.lower():
                continue
            
            # Check category match
            if rule.category and product.category and rule.category.lower() != product.category.lower():
                continue

            # Check min cost
            if rule.min_cost is not None and cost_price < Decimal(str(rule.min_cost)):
                continue

            # Check max cost
            if rule.max_cost is not None and cost_price > Decimal(str(rule.max_cost)):
                continue

            return rule

        return None

    @classmethod
    def calculate_final_price(
        cls,
        product: MasterProduct,
        cost_price: Decimal,
        rules: List[PricingRule]
    ) -> Decimal:
        """
        Calculates final selling price:
        price = (cost_price * (1 + markup_percent / 100)) + markup_fixed
        Ensures margin meets min_margin_percent.
        """
        matched_rule = cls.find_matching_rule(product, cost_price, rules)

        if matched_rule:
            pct = Decimal(str(matched_rule.markup_percent or 0)) / Decimal(100)
            fix = Decimal(str(matched_rule.markup_fixed or 0))
            calculated = (cost_price * (Decimal(1) + pct)) + fix
            
            # Verify minimum margin threshold
            min_margin_pct = Decimal(str(matched_rule.min_margin_percent or 5)) / Decimal(100)
            minimum_allowed_price = cost_price * (Decimal(1) + min_margin_pct)
            if calculated < minimum_allowed_price:
                calculated = minimum_allowed_price
        else:
            # Default fallback: 15% standard markup
            calculated = cost_price * Decimal("1.15")

        # Round to whole number (standard in KZT marketplace pricing)
        return calculated.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
