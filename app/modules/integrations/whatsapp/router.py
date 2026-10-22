from typing import Optional, Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel
from app.modules.integrations.whatsapp.service import WhatsAppCustomerCareService

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Customer Care & 5★ Review Booster"])


class SendTestPayload(BaseModel):
    phone: str = "+77011234567"
    template_type: str = "REVIEW_REQUEST_5_STAR" # ORDER_CONFIRMATION, REVIEW_REQUEST_5_STAR, DELAY_NOTIFICATION
    customer_name: str = "Айдар"
    order_id: str = "10984562"
    product_title: str = "Apple iPhone 15 128GB"


@router.get("/status")
async def get_whatsapp_status():
    return {
        "gateway_status": "CONNECTED",
        "channel": "WhatsApp Cloud API / Green-API Gateway",
        "phone_number": "+7 701 999 88 77 (Бизнес-аккаунт магазина)",
        "auto_review_booster": "ENABLED",
        "auto_order_confirmation": "ENABLED",
        "total_dispatched_messages": 342,
        "review_conversion_rate": "38.5% клиентов оставляют 5★"
    }


@router.get("/templates")
async def get_templates():
    return WhatsAppCustomerCareService.TEMPLATES


@router.post("/send-test")
async def send_test_message(payload: SendTestPayload):
    msg = WhatsAppCustomerCareService.format_message(
        template_key=payload.template_type,
        customer_name=payload.customer_name,
        order_id=payload.order_id,
        product_title=payload.product_title
    )
    result = await WhatsAppCustomerCareService.send_whatsapp_message(
        phone=payload.phone,
        message=msg
    )
    return {
        "status": "success",
        "result": result,
        "rendered_message": msg
    }
