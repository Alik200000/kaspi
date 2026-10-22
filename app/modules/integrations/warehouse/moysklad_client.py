import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)


class MoySkladClient:
    """
    Asynchronous client for MoySklad (МойСклад) JSON API v1.2.
    Handles:
    - Stock quantities sync (импорт физических остатков)
    - Pushing Kaspi marketplace orders to MoySklad (экспорт заказов покупателя)
    """

    DEFAULT_BASE_URL = "https://api.moysklad.ru/api/remap/1.2"

    def __init__(self, api_token: str, base_url: Optional[str] = None):
        self.api_token = api_token.strip()
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        
        # MoySklad supports Bearer token or Basic auth
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "KaspiSaaSPlatform/2.0"
        }
        if ":" in self.api_token and not self.api_token.startswith("Bearer "):
            import base64
            encoded = base64.b64encode(self.api_token.encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {encoded}"
        else:
            token = self.api_token if self.api_token.startswith("Bearer ") else f"Bearer {self.api_token}"
            headers["Authorization"] = token

        self.headers = headers

    async def test_connection(self) -> Dict[str, Any]:
        """
        Tests API token and fetches available warehouses/stores.
        """
        url = f"{self.base_url}/entity/store"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    stores = [
                        {"id": s.get("id"), "name": s.get("name"), "pathName": s.get("pathName", "")}
                        for s in data.get("rows", [])
                    ]
                    return {
                        "valid": True,
                        "status_code": 200,
                        "message": "Подключение к МойСклад успешно установлено!",
                        "stores": stores
                    }
                elif resp.status_code in (401, 403):
                    return {
                        "valid": False,
                        "status_code": resp.status_code,
                        "message": "Ошибка авторизации: неверный токен доступа МойСклад."
                    }
                else:
                    return {
                        "valid": False,
                        "status_code": resp.status_code,
                        "message": f"МойСклад ответил кодом {resp.status_code}: {resp.text[:150]}"
                    }
            except Exception as e:
                return {
                    "valid": False,
                    "status_code": 500,
                    "message": f"Ошибка сети при подключении к МойСклад: {str(e)}"
                }

    async def get_stock_report(self, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches current stock levels from MoySklad stock report (/report/stock/all).
        Returns list of items with SKU/article, stock quantity, inTransit, reserve.
        """
        url = f"{self.base_url}/report/stock/all"
        params = {"limit": 100}
        if store_id:
            params["filter"] = f"store=https://api.moysklad.ru/api/remap/1.2/entity/store/{store_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for item in data.get("rows", []):
                results.append({
                    "name": item.get("name"),
                    "article": item.get("article"),
                    "code": item.get("code"),
                    "barcode": item.get("barcodes", [{}])[0].get("ean13") if item.get("barcodes") else None,
                    "stock": float(item.get("stock", 0)),
                    "reserve": float(item.get("reserve", 0)),
                    "available": float(item.get("quantity", item.get("stock", 0)) - item.get("reserve", 0))
                })
            return results

    async def create_customer_order(
        self,
        external_order_id: str,
        customer_name: Optional[str],
        customer_phone: Optional[str],
        items: List[Dict[str, Any]],
        organization_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a 'customerorder' (Заказ покупателя) in MoySklad for physical order fulfillment.
        """
        url = f"{self.base_url}/entity/customerorder"
        
        order_positions = []
        for it in items:
            order_positions.append({
                "quantity": it.get("quantity", 1),
                "price": float(it.get("price", 0)) * 100, # MoySklad stores currency in kopecks/tiyn
                "assortment": {
                    "meta": {
                        "href": it.get("assortment_href"),
                        "type": "product",
                        "mediaType": "application/json"
                    }
                }
            })

        payload: Dict[str, Any] = {
            "name": f"Kaspi-{external_order_id}",
            "description": f"Заказ с Kaspi.kz № {external_order_id}. Клиент: {customer_name or '—'}, Телефон: {customer_phone or '—'}",
            "externalCode": external_order_id,
            "applicable": True
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()
