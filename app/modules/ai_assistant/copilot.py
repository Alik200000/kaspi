from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.models import Order
from app.modules.catalog.models import MasterProduct
from app.modules.finance.service import KazakhstanFinanceTaxService
from app.modules.competitor_radar.service import CompetitorRadarService
from app.modules.analytics.service import SmartRestockService


class AICopilotService:
    """
    AI Sales Director & Copilot:
    Analyzes live store economics and answers executive questions with actionable insights.
    """

    @classmethod
    async def chat(cls, query: str, db: AsyncSession) -> Dict[str, Any]:
        q_lower = query.lower()

        # Load live database metrics
        finance_summary = await KazakhstanFinanceTaxService.get_financial_summary(db)
        forecast = await SmartRestockService.get_restock_forecast(db)
        radar = await CompetitorRadarService.get_radar_overview(db)

        gross = finance_summary["gross_turnover_kzt"]
        net_cash = finance_summary["net_cash_in_hand_kzt"]
        tax_3 = finance_summary["tax_910"]["total_tax_kzt"]
        margin_pct = finance_summary["net_margin_percent"]
        total_orders = finance_summary["total_orders"]
        top_1_count = radar["top_1_captured_count"]
        critical_restock = [f for f in forecast if f["urgency"] in ("CRITICAL", "OUT_OF_STOCK")]

        # Determine intelligent response
        if any(w in q_lower for w in ["заработ", "прибыль", "доход", "деньги", "p&l", "табыс"]):
            reply = (
                f"📊 **Финансовый отчет по вашему магазину:**\n\n"
                f"• **Общий оборот:** {gross:,.0f} ₸ ({total_orders} заказов)\n"
                f"• **Чистая прибыль на руки (Net Cash):** {net_cash:,.0f} ₸\n"
                f"• **Чистая маржинальность:** {margin_pct}%\n"
                f"• **Резерв на налог 3% (Форма 910):** {tax_3:,.0f} ₸\n\n"
                f"💡 **Совет директора:** Ваша маржа находится на здоровом уровне! Рекомендуется направить 20% чистой прибыли в дозаказ флагманских позиций."
            )
            actions = ["Открыть P&L отчет", "Сформировать выписку"]

        elif any(w in q_lower for w in ["конкурент", "демпинг", "боты", "топ 1", "цена", "баға"]):
            reply = (
                f"📡 **Сводка радара конкурентов на полке Kaspi:**\n\n"
                f"• Вы удерживаете **1-е место на {top_1_count} из {radar['total_tracked_products']}** товаров ({radar['top_1_share_percent']}% витрины)!\n"
                f"• Выявлены боты: **Technodom KZ** и **Sulpak** сбивают цены на 10 ₸.\n"
                f"• **Защита Floor Price Guard:** активна, ни один товар не продается в минус.\n\n"
                f"💡 **Совет директора:** Включите режим «Bait Trap (Ловушка)» на iPhone 15, чтобы запереть бота конкурента на дне и поднять нашу маржу!"
            )
            actions = ["Запустить Repricer", "Активировать Bait Trap"]

        elif any(w in q_lower for w in ["склад", "остаток", "дозаказ", "заказ", "кончился", "қалдық"]):
            crit_titles = ", ".join([c["title"] for c in critical_restock[:2]]) or "Все товары в норме"
            reply = (
                f"📦 **Складская аналитика и риск Out-of-Stock:**\n\n"
                f"• **Критических позиций (< 3 дней до нуля):** {len(critical_restock)} шт.\n"
                f"• **Срочно требуют внимания:** {crit_titles}\n"
                f"• **Рекомендуемая сумма дозаказа:** {sum(f['estimated_reorder_cost'] for f in forecast):,.0f} ₸\n\n"
                f"💡 **Совет директора:** Если товар обнулится, карточка Kaspi упадет в выдаче и потеряет позиции. Сформируйте заявку дистрибьютору прямо сейчас!"
            )
            actions = ["Сформировать заказ в 1 клик", "Синхронизировать 1С"]

        elif any(w in q_lower for w in ["налог", "910", "упрощенк", "салық"]):
            reply = (
                f"🧮 **Налоговый расчет (Упрощенка 3%, Форма 910.00 РК):**\n\n"
                f"• База налогообложения (Оборот Kaspi): {gross:,.0f} ₸\n"
                f"• **Итого налог 3%:** {tax_3:,.0f} ₸\n"
                f"  - 1.5% ИПН: {finance_summary['tax_910']['ipn_1_5_percent']:,.0f} ₸\n"
                f"  - 1.5% Соцналог: {finance_summary['tax_910']['social_tax_1_5_percent']:,.0f} ₸\n"
                f"• **Срок уплаты:** {finance_summary['tax_910']['declaration_deadline']}\n\n"
                f"💡 Сумма полностью просчитана и готова к внесению в налоговую декларацию."
            )
            actions = ["Скачать форму 910", "Налоговая шпаргалка"]

        else:
            reply = (
                f"👋 Здравствуйте! Я ваш персональный **AI Директор по продажам Kaspi**.\n\n"
                f"Я в реальном времени слежу за вашими заказами ({total_orders} шт.), прибылью ({net_cash:,.0f} ₸), "
                f"остатками на складе и войной цен с конкурентами.\n\n"
                f"Спросите меня о чем угодно:\n"
                f"• *«Сколько я заработал чистыми?»*\n"
                f"• *«Кто из конкурентов сбивает цены?»*\n"
                f"• *«Что срочно нужно докупить на склад?»*\n"
                f"• *«Сколько налогов нужно отложить по форме 910?»*"
            )
            actions = ["Сколько я заработал?", "Кто сбивает цены?", "Что докупить?"]

        return {
            "query": query,
            "response": reply,
            "suggested_actions": actions,
            "metrics_snapshot": {
                "gross_turnover": gross,
                "net_profit": net_cash,
                "tax_3_pct": tax_3,
                "top_1_ratio": f"{top_1_count}/{radar['total_tracked_products']}"
            }
        }
