import datetime
from typing import List, Dict, Any, Optional

class KaspiAdsAutoBidderService:
    """
    Kaspi Marketing Auto-Bidder & CPC Optimizer.
    Automatically manages internal Kaspi.kz product advertising campaigns,
    targets optimal DRR (Ad Spend / Revenue ratio), prevents overspending on low-margin products,
    and applies automated hourly dayparting.
    """

    # In-memory mock store for campaigns with realistic defaults
    _campaigns = [
        {
            "id": "ad-cmp-001",
            "name": "Apple iPhone 15 Pro Max 256GB Черный — Топ Поиск",
            "master_sku": "SKU-IPHONE15PM-BLK",
            "status": "ACTIVE",
            "daily_budget": 15000.0,
            "spent_today": 8450.0,
            "cpc": 45.0,
            "max_cpc": 70.0,
            "target_drr_pct": 6.0,  # 6% ad spend target
            "current_drr_pct": 5.4,
            "impressions": 14200,
            "clicks": 312,
            "ctr_pct": 2.2,
            "orders_count": 8,
            "ad_revenue": 1560000.0,
            "stock_units": 14,
            "margin_pct": 14.8,
            "dayparting_active": True,
            "last_optimized_at": "2026-10-23 22:30:00"
        },
        {
            "id": "ad-cmp-002",
            "name": "Samsung Galaxy S24 Ultra 512GB Серый — Главная категория",
            "master_sku": "SKU-SAMS24U-GRY",
            "status": "ACTIVE",
            "daily_budget": 12000.0,
            "spent_today": 7100.0,
            "cpc": 52.0,
            "max_cpc": 80.0,
            "target_drr_pct": 7.0,
            "current_drr_pct": 6.8,
            "impressions": 9800,
            "clicks": 215,
            "ctr_pct": 2.19,
            "orders_count": 5,
            "ad_revenue": 1045000.0,
            "stock_units": 9,
            "margin_pct": 15.2,
            "dayparting_active": True,
            "last_optimized_at": "2026-10-23 22:30:00"
        },
        {
            "id": "ad-cmp-003",
            "name": "Dyson V15 Detect Absolute — Авто-продвижение",
            "master_sku": "SKU-DYSONV15-ABS",
            "status": "PAUSED_STOCKOUT_RISK",
            "daily_budget": 8000.0,
            "spent_today": 3200.0,
            "cpc": 38.0,
            "max_cpc": 65.0,
            "target_drr_pct": 8.0,
            "current_drr_pct": 7.2,
            "impressions": 4300,
            "clicks": 95,
            "ctr_pct": 2.21,
            "orders_count": 2,
            "ad_revenue": 444000.0,
            "stock_units": 1,  # Stock <= 1 triggers auto-pause
            "margin_pct": 16.5,
            "dayparting_active": False,
            "last_optimized_at": "2026-10-23 21:00:00"
        }
    ]

    @classmethod
    def get_campaigns(cls) -> List[Dict[str, Any]]:
        return cls._campaigns

    @classmethod
    def get_summary(cls) -> Dict[str, Any]:
        total_spent = sum(c["spent_today"] for c in cls._campaigns)
        total_revenue = sum(c["ad_revenue"] for c in cls._campaigns)
        total_orders = sum(c["orders_count"] for c in cls._campaigns)
        total_clicks = sum(c["clicks"] for c in cls._campaigns)
        overall_drr = round((total_spent / total_revenue * 100), 2) if total_revenue > 0 else 0.0
        roas = round((total_revenue / total_spent), 1) if total_spent > 0 else 0.0

        return {
            "total_campaigns": len(cls._campaigns),
            "active_campaigns": sum(1 for c in cls._campaigns if c["status"] == "ACTIVE"),
            "total_spent_today": total_spent,
            "total_ad_revenue": total_revenue,
            "total_orders": total_orders,
            "total_clicks": total_clicks,
            "overall_drr_pct": overall_drr,
            "roas_multiplier": roas,
            "estimated_savings_kzt": 48500.0  # Money saved by auto-stopping wasteful bids
        }

    @classmethod
    def create_campaign(
        cls,
        name: str,
        master_sku: str,
        daily_budget: float,
        target_drr_pct: float = 7.0,
        max_cpc: float = 80.0
    ) -> Dict[str, Any]:
        campaign_id = f"ad-cmp-{len(cls._campaigns) + 1:03d}"
        new_cmp = {
            "id": campaign_id,
            "name": name,
            "master_sku": master_sku,
            "status": "ACTIVE",
            "daily_budget": daily_budget,
            "spent_today": 0.0,
            "cpc": min(35.0, max_cpc),
            "max_cpc": max_cpc,
            "target_drr_pct": target_drr_pct,
            "current_drr_pct": 0.0,
            "impressions": 0,
            "clicks": 0,
            "ctr_pct": 0.0,
            "orders_count": 0,
            "ad_revenue": 0.0,
            "stock_units": 10,
            "margin_pct": 15.0,
            "dayparting_active": True,
            "last_optimized_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        cls._campaigns.append(new_cmp)
        return new_cmp

    @classmethod
    def optimize_bids(cls) -> Dict[str, Any]:
        """
        Executes automated bid optimization algorithm across all campaigns:
        1. Guard: Stock < 2 units -> PAUSED_STOCKOUT_RISK
        2. Guard: Margin < 10% -> PAUSED_LOW_MARGIN
        3. Target DRR control:
           - If current DRR > target DRR: decrease CPC by 10%
           - If current DRR < target DRR: increase CPC by 5% to capture top ad rank
        4. Dayparting: 18:00 - 23:00 is Kazakhstan prime time shopping -> +10% bid boost
        """
        now = datetime.datetime.now()
        is_prime_time = 18 <= now.hour <= 23
        actions_taken = []

        for cmp in cls._campaigns:
            old_cpc = cmp["cpc"]

            # Stock check
            if cmp["stock_units"] < 2:
                cmp["status"] = "PAUSED_STOCKOUT_RISK"
                actions_taken.append({
                    "campaign_id": cmp["id"],
                    "action": "AUTO_PAUSED",
                    "reason": f"Остаток {cmp['stock_units']} шт < 2 шт (защита бюджета)"
                })
                continue

            # Margin check
            if cmp["margin_pct"] < 10.0:
                cmp["status"] = "PAUSED_LOW_MARGIN"
                actions_taken.append({
                    "campaign_id": cmp["id"],
                    "action": "AUTO_PAUSED",
                    "reason": f"Маржа {cmp['margin_pct']}% < 10% (убыточная реклама)"
                })
                continue

            # DRR adjustment
            if cmp["current_drr_pct"] > cmp["target_drr_pct"] and cmp["clicks"] > 30:
                # Spend is too high relative to sales, reduce CPC
                new_cpc = max(20.0, round(cmp["cpc"] * 0.90, 1))
                cmp["cpc"] = new_cpc
                cmp["status"] = "ACTIVE"
                actions_taken.append({
                    "campaign_id": cmp["id"],
                    "action": "CPC_DECREASED",
                    "from_cpc": old_cpc,
                    "to_cpc": new_cpc,
                    "reason": f"ДРР {cmp['current_drr_pct']}% выше целевого {cmp['target_drr_pct']}%"
                })
            elif cmp["current_drr_pct"] < cmp["target_drr_pct"] and cmp["current_drr_pct"] > 0:
                # We have headroom to get more volume
                boost = 1.10 if is_prime_time else 1.05
                new_cpc = min(cmp["max_cpc"], round(cmp["cpc"] * boost, 1))
                cmp["cpc"] = new_cpc
                cmp["status"] = "ACTIVE"
                actions_taken.append({
                    "campaign_id": cmp["id"],
                    "action": "CPC_INCREASED",
                    "from_cpc": old_cpc,
                    "to_cpc": new_cpc,
                    "reason": f"ДРР {cmp['current_drr_pct']}% ниже целевого ({cmp['target_drr_pct']}%) {'(Прайм-тайм РК)' if is_prime_time else ''}"
                })

            cmp["last_optimized_at"] = now.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "status": "success",
            "optimized_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "is_prime_time": is_prime_time,
            "actions_count": len(actions_taken),
            "actions": actions_taken
        }

    @classmethod
    def toggle_campaign(cls, campaign_id: str) -> Optional[Dict[str, Any]]:
        for cmp in cls._campaigns:
            if cmp["id"] == campaign_id:
                cmp["status"] = "PAUSED" if cmp["status"] == "ACTIVE" else "ACTIVE"
                return cmp
        return None
