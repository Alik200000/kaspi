import logging
from typing import Dict, Any, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class KaspiClient:
    """
    Async client for Kaspi.kz Merchant API.
    Handles order fetching, order status transitions, and rate limiting.
    """

    def __init__(self, api_token: str, base_url: Optional[str] = None):
        self.api_token = api_token
        self.base_url = (base_url or settings.KASPI_API_BASE_URL).rstrip("/")
        self.headers = {
            "Content-Type": "application/vnd.api+json",
            "X-Auth-Token": self.api_token,
            "User-Agent": "KaspiSaaSPlatform/1.0"
        }

    async def get_orders(
        self,
        state: Optional[str] = None, # e.g. "NEW", "SIGN_REQUIRED", "PICKUP", "DELIVERY", "COMPLETED"
        start_date_ms: Optional[int] = None,
        page_number: int = 0,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Polls orders from Kaspi Merchant API matching state and date criteria.
        """
        url = f"{self.base_url}/orders"
        params: Dict[str, Any] = {
            "page[number]": page_number,
            "page[size]": page_size
        }

        if state:
            params["filter[orders][state]"] = state
        if start_date_ms:
            params["filter[orders][creationDate][$ge]"] = start_date_ms

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                logger.error(f"Kaspi API error {exc.response.status_code}: {exc.response.text}")
                raise
            except Exception as e:
                logger.error(f"Failed to fetch Kaspi orders: {str(e)}")
                raise

    async def get_order_entries(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Fetches specific product entries for an order.
        """
        url = f"{self.base_url}/orders/{order_id}/entries"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    async def accept_order(self, order_id: str) -> bool:
        """
        Accept order for processing (transitions state from NEW to ACCEPTED_BY_MERCHANT).
        """
        url = f"{self.base_url}/orders"
        payload = {
            "data": {
                "type": "orders",
                "id": order_id,
                "attributes": {
                    "status": "ACCEPTED_BY_MERCHANT"
                }
            }
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.status_code in (200, 204)
