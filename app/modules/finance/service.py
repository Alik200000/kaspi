from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.orders.models import Order


class KazakhstanFinanceTaxService:
    """
    Financial Management & Republic of Kazakhstan Tax Calculator:
    1. Form 910.00 Simplified Tax Declaration (3% of Gross Kaspi Turnover).
    2. Comprehensive P&L (Gross Revenue, COGS, Kaspi Fees, Logistics, 3% Tax, Net Cash in Hand).
    """

    TAX_RATE = 0.03 # 3% for Kazakhstan Simplified Tax Regime (ИП на упрощенке)

    @classmethod
    async def get_financial_summary(cls, db: AsyncSession) -> Dict[str, Any]:
        stmt = select(Order)
        orders = (await db.execute(stmt)).scalars().all()

        total_orders_count = len(orders)
        gross_turnover = sum(float(o.total_sale_amount or 0.0) for o in orders)
        total_cogs = sum(float(o.total_cost_amount or 0.0) for o in orders)
        kaspi_commissions = sum(float(o.kaspi_commission_amount or 0.0) for o in orders)
        delivery_costs = sum(float(o.delivery_cost or 0.0) for o in orders)

        # 3% Tax calculation
        tax_3_percent = round(gross_turnover * cls.TAX_RATE, 2)
        ipn_share = round(tax_3_percent / 2, 2) # 1.5% ИПН
        social_tax_share = round(tax_3_percent / 2, 2) # 1.5% Социальный налог

        # Net cash in hand after ALL deductions including 3% tax
        net_cash_in_hand = round(gross_turnover - total_cogs - kaspi_commissions - delivery_costs - tax_3_percent, 2)
        net_margin_percent = round((net_cash_in_hand / gross_turnover * 100), 2) if gross_turnover > 0 else 0.0

        return {
            "period": "Текущий отчетный период (2026)",
            "total_orders": total_orders_count,
            "gross_turnover_kzt": round(gross_turnover, 2),
            "cogs_kzt": round(total_cogs, 2),
            "kaspi_commissions_kzt": round(kaspi_commissions, 2),
            "delivery_costs_kzt": round(delivery_costs, 2),
            "tax_910": {
                "regime": "Специальный налоговый режим на основе упрощенной декларации (Форма 910.00)",
                "rate_percent": 3.0,
                "total_tax_kzt": tax_3_percent,
                "ipn_1_5_percent": ipn_share,
                "social_tax_1_5_percent": social_tax_share,
                "declaration_deadline": "До 15 числа второго месяца следующего за полугодием"
            },
            "net_cash_in_hand_kzt": net_cash_in_hand,
            "net_margin_percent": net_margin_percent,
            "recommendation": (
                f"Чистый заработок с оборота составляет {net_margin_percent}%. "
                f"Рекомендуется отложить {tax_3_percent:,.0f} ₸ на отдельный счет Kaspi Pay для уплаты налогов по форме 910.00."
            )
        }
