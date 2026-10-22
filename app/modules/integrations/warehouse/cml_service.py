import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Tuple
from app.modules.orders.models import Order
from app.modules.catalog.models import MasterProduct

logger = logging.getLogger(__name__)


class OneCCommerceMLService:
    """
    Implements standard 1С:Предприятие CommerceML 2.0 / 2.08 exchange protocol.
    Standard modes:
    - checkauth: Authenticates 1C connection
    - init: Exchanges file size & zip parameters
    - file / import: Receives XML catalog & stocks from 1C
    - query: Exports Kaspi marketplace orders to 1C in CommerceML format
    """

    @classmethod
    def generate_orders_cml(cls, orders: List[Order]) -> str:
        """
        Builds CommerceML 2.0 XML representation of Kaspi orders for 1C import.
        """
        root = ET.Element("КоммерческаяИнформация", {
            "ВерсияСхемы": "2.08",
            "ДатаФормирования": datetime.utcnow().strftime("%Y-%m-%d"),
            "Формат": "CommerceML 2.0"
        })

        for o in orders:
            doc = ET.SubElement(root, "Документ")
            ET.SubElement(doc, "Ид").text = str(o.id)
            ET.SubElement(doc, "Номер").text = o.external_order_id
            ET.SubElement(doc, "Дата").text = o.created_at.strftime("%Y-%m-%d") if o.created_at else ""
            ET.SubElement(doc, "Время").text = o.created_at.strftime("%H:%M:%S") if o.created_at else ""
            ET.SubElement(doc, "ХозОперация").text = "Заказ товара"
            ET.SubElement(doc, "Роль").text = "Продавец"
            ET.SubElement(doc, "Валюта").text = "KZT"
            ET.SubElement(doc, "Курс").text = "1"
            ET.SubElement(doc, "Сумма").text = str(o.total_sale_amount)

            # Контрагент / Покупатель Kaspi
            contractor = ET.SubElement(doc, "Контрагенты")
            c = ET.SubElement(contractor, "Контрагент")
            ET.SubElement(c, "Ид").text = f"kaspi_client_{o.external_order_id}"
            ET.SubElement(c, "Наименование").text = o.customer_name or "Клиент Kaspi.kz"
            ET.SubElement(c, "ПолноеНаименование").text = o.customer_name or "Клиент Kaspi.kz"
            ET.SubElement(c, "Роль").text = "Покупатель"
            
            contacts = ET.SubElement(c, "Контакты")
            phone = ET.SubElement(contacts, "Контакт")
            ET.SubElement(phone, "Тип").text = "ТелефонРабочий"
            ET.SubElement(phone, "Значение").text = o.customer_phone or ""

            # Товары заказа
            goods = ET.SubElement(doc, "Товары")
            for item in o.items:
                good = ET.SubElement(goods, "Товар")
                ET.SubElement(good, "Ид").text = str(item.master_product_id or item.kaspi_sku)
                ET.SubElement(good, "Артикул").text = item.kaspi_sku
                ET.SubElement(good, "Наименование").text = item.title
                ET.SubElement(good, "Количество").text = str(item.quantity)
                ET.SubElement(good, "ЦенаЗаЕдиницу").text = str(item.price if hasattr(item, 'price') else 0)
                ET.SubElement(good, "Сумма").text = str((item.price if hasattr(item, 'price') else 0) * item.quantity)

            # Статус
            status_elem = ET.SubElement(doc, "ЗначенияРеквизитов")
            r1 = ET.SubElement(status_elem, "ЗначениеРеквизита")
            ET.SubElement(r1, "Наименование").text = "Статус заказа"
            ET.SubElement(r1, "Значение").text = o.status

        xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        return xml_bytes.decode("utf-8")

    @classmethod
    def parse_1c_catalog_xml(cls, xml_text: str) -> List[Dict[str, Any]]:
        """
        Parses incoming CommerceML catalog XML from 1C and extracts stock and prices.
        """
        parsed_items = []
        try:
            root = ET.fromstring(xml_text)
            # Find all products
            for prod in root.iter("Товар"):
                sku = prod.findtext("Артикул") or prod.findtext("Ид")
                title = prod.findtext("Наименование") or ""
                barcode = prod.findtext("Штрихкод") or ""
                stock = float(prod.findtext("Количество") or prod.findtext("Остаток") or 0)
                
                parsed_items.append({
                    "sku": sku.strip() if sku else None,
                    "title": title.strip(),
                    "barcode": barcode.strip(),
                    "stock": stock
                })
        except Exception as e:
            logger.error(f"Error parsing 1C CommerceML XML: {str(e)}")

        return parsed_items
