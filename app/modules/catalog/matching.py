import re
from typing import List, Tuple, Optional
from app.modules.catalog.models import MasterProduct


class SKUMatchingEngine:
    """
    Intelligent cascade matching engine for supplier offers:
    1. Exact Barcode Match (100% confidence)
    2. Normalized Internal SKU Match (95% confidence)
    3. Token Set Fuzzy Similarity Match (50-90% confidence)
    """

    NOISE_WORDS = {
        "смартфон", "телефон", "наушники", "пылесос", "робот-пылесос", "беспроводные",
        "ru", "kz", "eu", "global", "оригинал", "новый", "новинка", "акция",
        "черный", "black", "белый", "white", "серый", "gray", "grey"
    }

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Removes special characters and lowercases string."""
        if not text:
            return ""
        clean = re.sub(r"[^\w\s]", " ", text.lower())
        return " ".join(clean.split())

    @classmethod
    def tokenize(cls, text: str) -> set:
        """Splits normalized text into unique meaningful tokens, stripping common noise."""
        normalized = cls.normalize_text(text)
        tokens = set(normalized.split())
        return tokens - cls.NOISE_WORDS

    @classmethod
    def calculate_similarity_score(cls, title_a: str, title_b: str) -> float:
        """
        Calculates Jaccard / Overlap similarity score between token sets [0.0 ... 1.0].
        """
        tokens_a = cls.tokenize(title_a)
        tokens_b = cls.tokenize(title_b)

        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a.intersection(tokens_b)
        union = tokens_a.union(tokens_b)

        # Weighted score: overlap coefficient + Jaccard index
        overlap = len(intersection) / min(len(tokens_a), len(tokens_b))
        jaccard = len(intersection) / len(union)

        score = (overlap * 0.6) + (jaccard * 0.4)
        return round(score, 3)

    @classmethod
    def match_offer(
        cls,
        offer_title: str,
        offer_barcode: Optional[str],
        offer_sku: Optional[str],
        offer_brand: Optional[str],
        candidates: List[MasterProduct]
    ) -> Tuple[Optional[MasterProduct], float, str, str]:
        """
        Runs multi-stage cascade matching against candidate MasterProducts.
        Returns: (matched_product, confidence_score, match_type, match_status)
        """
        clean_offer_barcode = offer_barcode.strip() if offer_barcode else None
        clean_offer_sku = cls.normalize_text(offer_sku).replace(" ", "") if offer_sku else ""

        # 1. Exact Barcode Match
        if clean_offer_barcode:
            for prod in candidates:
                if prod.barcode and prod.barcode.strip() == clean_offer_barcode:
                    return (prod, 1.0, "barcode", "confirmed")

        # 2. Exact Normalized SKU Match
        if clean_offer_sku:
            for prod in candidates:
                clean_prod_sku = cls.normalize_text(prod.sku_internal).replace(" ", "")
                if clean_prod_sku and clean_prod_sku == clean_offer_sku:
                    return (prod, 0.95, "sku", "confirmed")

        # 3. Fuzzy Token Matching
        best_candidate: Optional[MasterProduct] = None
        highest_score: float = 0.0

        for prod in candidates:
            # If both have brands, ensure brand compatibility
            if offer_brand and prod.brand:
                if offer_brand.lower().strip() not in prod.brand.lower() and prod.brand.lower().strip() not in offer_brand.lower():
                    continue

            score = cls.calculate_similarity_score(offer_title, prod.title)
            if score > highest_score:
                highest_score = score
                best_candidate = prod

        # Determine confidence threshold
        if highest_score >= 0.75:
            return (best_candidate, highest_score, "fuzzy_auto", "confirmed")
        elif highest_score >= 0.45:
            return (best_candidate, highest_score, "fuzzy_candidate", "pending_review")
        else:
            return (None, 0.0, "none", "unmatched")
