import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.core.database import get_db
from app.modules.orders.models import Order
from app.modules.integrations.kaspi.models import KaspiShop

router = APIRouter(prefix="/orders", tags=["Orders & Analytics"])


class OrderResponse(BaseModel):
    id: uuid.UUID
    external_order_id: str
    status: str
    customer_name: Optional[str] = None
    total_sale_amount: float
    total_cost_amount: float
    kaspi_commission_amount: float
    net_profit: float
    margin_percent: float
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AnalyticsSummary(BaseModel):
    total_orders: int
    gross_revenue: float
    total_cost_of_goods: float
    total_kaspi_commission: float
    net_profit: float
    average_margin_percent: float


@router.get("", response_model=List[OrderResponse])
async def list_orders(
    shop_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Order).order_by(Order.created_at.desc())
    if shop_id:
        stmt = stmt.where(Order.kaspi_shop_id == shop_id)
    if status:
        stmt = stmt.where(Order.status == status)
    
    orders = (await db.execute(stmt)).scalars().all()
    return orders


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    shop_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns unit economics and profitability dashboard metrics.
    """
    stmt = select(
        func.count(Order.id).label("total_orders"),
        func.coalesce(func.sum(Order.total_sale_amount), 0).label("gross_revenue"),
        func.coalesce(func.sum(Order.total_cost_amount), 0).label("total_cogs"),
        func.coalesce(func.sum(Order.kaspi_commission_amount), 0).label("total_commission"),
        func.coalesce(func.sum(Order.net_profit), 0).label("net_profit")
    )
    if shop_id:
        stmt = stmt.where(Order.kaspi_shop_id == shop_id)

    res = (await db.execute(stmt)).one()
    
    total_orders = res.total_orders or 0
    revenue = float(res.gross_revenue)
    cogs = float(res.total_cogs)
    commission = float(res.total_commission)
    profit = float(res.net_profit)
    
    avg_margin = (profit / revenue * 100) if revenue > 0 else 0.0

    return AnalyticsSummary(
        total_orders=total_orders,
        gross_revenue=revenue,
        total_cost_of_goods=cogs,
        total_kaspi_commission=commission,
        net_profit=profit,
        average_margin_percent=round(avg_margin, 2)
    )


@router.get("/export/excel")
async def export_orders_to_excel(
    shop_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Exports orders and unit economics report as an Excel (.xlsx) spreadsheet.
    """
    import io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from fastapi.responses import Response

    stmt = select(Order).order_by(Order.created_at.desc())
    if shop_id:
        stmt = stmt.where(Order.kaspi_shop_id == shop_id)
    orders = (await db.execute(stmt)).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Реестр заказов Kaspi"

    # Header styling
    headers = [
        "№ Заказа Kaspi", "Дата", "Статус", "Покупатель", "Телефон",
        "Сумма продажи (₸)", "Себестоимость (₸)", "Комиссия Kaspi (₸)",
        "Доставка (₸)", "Чистая прибыль (₸)", "Рентабельность (%)"
    ]

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")

    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    for ord in orders:
        date_str = ord.created_at.strftime("%d.%m.%Y %H:%M") if ord.created_at else ""
        row = [
            ord.external_order_id,
            date_str,
            ord.status,
            ord.customer_name or "—",
            ord.customer_phone or "—",
            float(ord.total_sale_amount),
            float(ord.total_cost_amount),
            float(ord.kaspi_commission_amount),
            float(ord.delivery_cost),
            float(ord.net_profit),
            float(ord.margin_percent)
        ]
        ws.append(row)
        current_row = ws.max_row
        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(row=current_row, column=col_idx)
            c.border = thin_border
            if col_idx in [6, 7, 8, 9, 10]:
                c.number_format = '#,##0 "₸"'
                c.alignment = right_align
            elif col_idx == 11:
                c.number_format = '0.0"%"'
                c.alignment = right_align

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"kaspi_orders_report_{uuid.uuid4().hex[:8]}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{order_id}/shipping-label-html")
async def get_shipping_label_html(
    order_id: uuid.UUID,
    format: str = Query("58x40", description="Label format: '58x40' or '75x120'"),
    db: AsyncSession = Depends(get_db)
):
    """
    Renders a standard Kaspi Delivery thermal shipping label (58x40 mm or 75x120 mm)
    with barcode Code128, order ID, delivery details, and auto-print trigger.
    """
    from fastapi.responses import HTMLResponse
    stmt = select(Order).where(Order.id == order_id)
    ord = (await db.execute(stmt)).scalar_one_or_none()
    if not ord:
        # Fallback to external_order_id lookup if string was passed
        stmt_ext = select(Order).where(Order.external_order_id == str(order_id))
        ord = (await db.execute(stmt_ext)).scalar_one_or_none()
        if not ord:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Order not found")

    date_str = ord.created_at.strftime("%d.%m.%Y %H:%M") if ord.created_at else datetime.utcnow().strftime("%d.%m.%Y %H:%M")
    is_large = format == "75x120"
    width_mm = "75mm" if is_large else "58mm"
    height_mm = "120mm" if is_large else "40mm"

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Этикетка Kaspi Доставка - {ord.external_order_id}</title>
  <!-- JsBarcode library for barcode rendering -->
  <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
  <style>
    @page {{
      size: {width_mm} {height_mm};
      margin: 0;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }}
    body {{
      width: {width_mm};
      height: {height_mm};
      padding: 2.5mm;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      color: #000;
      background: #fff;
      overflow: hidden;
    }}
    .header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1.5px solid #000;
      padding-bottom: 1.5mm;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 1.5mm;
    }}
    .logo-badge {{
      background: #000;
      color: #fff;
      font-weight: 900;
      font-size: 11pt;
      width: 5mm;
      height: 5mm;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 1mm;
    }}
    .brand-title {{
      font-size: 8.5pt;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.2px;
    }}
    .order-type {{
      font-size: 7pt;
      font-weight: 700;
      border: 1px solid #000;
      padding: 0.5mm 1.5mm;
      border-radius: 1mm;
      text-transform: uppercase;
    }}
    .order-num {{
      font-size: 10.5pt;
      font-weight: 900;
      letter-spacing: 0.3px;
      margin-top: 1mm;
    }}
    .customer-info {{
      font-size: 7.5pt;
      line-height: 1.25;
      margin-top: 1mm;
      border-bottom: 1px dashed #000;
      padding-bottom: 1.5mm;
    }}
    .barcode-wrap {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      margin: 1mm 0;
    }}
    svg#barcode {{
      max-width: 95%;
      height: {"24mm" if is_large else "15mm"};
    }}
    .footer {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 6.5pt;
      border-top: 1px solid #000;
      padding-top: 1mm;
    }}
    @media print {{
      .no-print {{ display: none !important; }}
    }}
  </style>
</head>
<body onload="initBarcode()">

  <div>
    <div class="header">
      <div class="brand">
        <div class="logo-badge">K</div>
        <div class="brand-title">Kaspi Доставка</div>
      </div>
      <div class="order-type">ЭКСПРЕСС</div>
    </div>

    <div class="order-num">№ {ord.external_order_id}</div>

    <div class="customer-info">
      <div><strong>Получатель:</strong> {ord.customer_name or "Клиент Kaspi"}</div>
      <div><strong>Телефон:</strong> {ord.customer_phone or "+7 (7xx) xxx-xx-xx"}</div>
      <div><strong>Сумма:</strong> {ord.total_sale_amount:,.0f} ₸ (Оплачено)</div>
    </div>
  </div>

  <div class="barcode-wrap">
    <svg id="barcode"></svg>
  </div>

  <div class="footer">
    <span>Дата: {date_str}</span>
    <span>Мест: 1/1</span>
    <span>{format}</span>
  </div>

  <script>
    function initBarcode() {{
      JsBarcode("#barcode", "{ord.external_order_id}", {{
        format: "CODE128",
        lineColor: "#000",
        width: 1.8,
        height: 45,
        displayValue: true,
        fontSize: 10,
        margin: 0
      }});
      // Auto-trigger print dialog if requested
      if (window.location.search.includes("autoprint=true")) {{
        setTimeout(() => window.print(), 350);
      }}
    }}
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
