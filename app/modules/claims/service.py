import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.claims.models import VendorClaim


class VendorClaimsService:
    """
    RMA & Supplier Defect Claim Management.
    """

    @classmethod
    async def create_claim(
        cls,
        supplier_name: str,
        product_title: str,
        sku: str,
        defect_type: str,
        defect_description: str,
        claim_amount: float,
        external_order_id: Optional[str],
        serial_number: Optional[str],
        db: AsyncSession
    ) -> VendorClaim:
        claim_num = f"RMA-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:5].upper()}"
        claim = VendorClaim(
            claim_number=claim_num,
            supplier_name=supplier_name,
            product_title=product_title,
            sku=sku,
            defect_type=defect_type,
            defect_description=defect_description,
            claim_amount=claim_amount,
            external_order_id=external_order_id,
            serial_number=serial_number or "N/A",
            status="SUBMITTED"
        )
        db.add(claim)
        await db.commit()
        await db.refresh(claim)
        return claim

    @classmethod
    async def get_claims(cls, db: AsyncSession) -> List[Dict[str, Any]]:
        stmt = select(VendorClaim).order_by(desc(VendorClaim.created_at))
        claims = (await db.execute(stmt)).scalars().all()

        if not claims:
            # Seed initial demo claim
            c = await cls.create_claim(
                supplier_name="Официальный Дистрибьютор Алматы",
                product_title="Apple AirPods Pro 2",
                sku="APP-2-WHT",
                defect_type="FACTORY_DEFECT",
                defect_description="Заводской дефект: левый наушник не заряжается в кейсе. Клиент вернул заказ через Kaspi Доставку.",
                claim_amount=85000.0,
                external_order_id="10984562",
                serial_number="H7Y9823KL1",
                db=db
            )
            claims = [c]

        return [
            {
                "id": str(c.id),
                "claim_number": c.claim_number,
                "supplier_name": c.supplier_name,
                "product_title": c.product_title,
                "sku": c.sku,
                "defect_type": c.defect_type,
                "defect_description": c.defect_description,
                "claim_amount": float(c.claim_amount),
                "status": c.status,
                "external_order_id": c.external_order_id,
                "serial_number": c.serial_number,
                "created_at": c.created_at.strftime("%d.%m.%Y") if c.created_at else None
            }
            for c in claims
        ]

    @classmethod
    def generate_claim_act_html(cls, claim: VendorClaim) -> str:
        date_str = claim.created_at.strftime("%d.%m.%Y") if claim.created_at else datetime.utcnow().strftime("%d.%m.%Y")
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Акт рекламации {claim.claim_number}</title>
  <style>
    body {{ font-family: 'Times New Roman', serif; padding: 40px; color: #111; max-width: 800px; margin: auto; }}
    h2, h3 {{ text-align: center; margin-bottom: 5px; }}
    .header {{ display: flex; justify-content: space-between; margin-bottom: 25px; font-size: 14px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
    th, td {{ border: 1px solid #333; padding: 8px 12px; text-align: left; font-size: 13px; }}
    th {{ background: #f0f0f0; }}
    .signatures {{ margin-top: 50px; display: flex; justify-content: space-between; }}
    .sign-line {{ border-top: 1px solid #333; width: 220px; text-align: center; padding-top: 5px; font-size: 12px; }}
    @media print {{ body {{ padding: 0; }} }}
  </style>
</head>
<body onload="window.print()">
  <div class="header">
    <div><strong>Покупатель (Продавец Kaspi):</strong><br>ИП Сейдалиев А.<br>БИН/ИИН: 920412350881<br>г. Алматы, пр. Абая 150</div>
    <div><strong>Поставщик:</strong><br>{claim.supplier_name}<br>г. Алматы, Складской комплекс</div>
  </div>

  <h2>АКТ РЕКЛАМАЦИИ О ВЫЯВЛЕННОМ БРАКЕ № {claim.claim_number}</h2>
  <div style="text-align: center; font-size: 13px; margin-bottom: 20px;">от {date_str} г.</div>

  <p style="font-size: 14px; line-height: 1.6;">
    Настоящий Акт составлен комиссией в составе представителя Покупателя и подтверждает выявление несоответствия качества / дефекта товара, поставленного по накладной в рамках договора поставки. Товар был возвращен розничным клиентом маркетплейса Kaspi.kz по заказу <strong>#{claim.external_order_id or 'Б/Н'}</strong>.
  </p>

  <table>
    <thead>
      <tr>
        <th>Наименование товара</th>
        <th>Артикул (SKU)</th>
        <th>Серийный номер</th>
        <th>Характер дефекта</th>
        <th>Сумма компенсации</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>{claim.product_title}</strong></td>
        <td>{claim.sku}</td>
        <td>{claim.serial_number or 'N/A'}</td>
        <td>{claim.defect_description}</td>
        <td><strong>{claim.claim_amount:,.0f} ₸</strong></td>
      </tr>
    </tbody>
  </table>

  <p style="font-size: 13px;">
    <strong>Требование:</strong> На основании Закона РК «О защите прав потребителей» и условий договора поставки, просим произвести замену бракованного изделия либо зачесть сумму претензии <strong>{claim.claim_amount:,.0f} ₸</strong> в счет будущих поставок товаров.
  </p>

  <div class="signatures">
    <div>
      <div>Претензию предъявил:</div>
      <br><br>
      <div class="sign-line">ИП Сейдалиев А. (Подпись / М.П.)</div>
    </div>
    <div>
      <div>Представитель Поставщика:</div>
      <br><br>
      <div class="sign-line">Принято к рассмотрению (Подпись)</div>
    </div>
  </div>
</body>
</html>"""
