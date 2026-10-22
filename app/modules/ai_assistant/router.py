import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.modules.ai_assistant.models import CustomerReview
from app.modules.ai_assistant.service import AIAssistantService
from app.modules.notifications.service import NotificationService
from app.modules.integrations.kaspi.models import KaspiShop

router = APIRouter(prefix="/ai", tags=["AI Assistant & Reviews (Kaspi AI)"])


class GenerateReplyPayload(BaseModel):
    review_id: str


class AutoReplyAllPayload(BaseModel):
    min_rating: int = 4 # Auto-reply to 4 and 5 stars, flag 1-3 for manual/SOS review


class GenerateSEOPayload(BaseModel):
    title: str
    brand: Optional[str] = None
    category: Optional[str] = None
    features: Optional[List[str]] = None


@router.get("/reviews")
async def list_reviews(
    sentiment: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns list of customer reviews with AI sentiment and replies.
    """
    stmt = select(CustomerReview).order_by(desc(CustomerReview.created_at))
    if sentiment:
        stmt = stmt.where(CustomerReview.ai_sentiment == sentiment)
    if status:
        stmt = stmt.where(CustomerReview.reply_status == status)

    result = await db.execute(stmt)
    reviews = result.scalars().all()

    # If empty, automatically seed demo reviews for rich UX
    if not reviews and not sentiment and not status:
        await seed_demo_reviews_internal(db)
        result = await db.execute(select(CustomerReview).order_by(desc(CustomerReview.created_at)))
        reviews = result.scalars().all()

    sos_count = sum(1 for r in reviews if r.ai_sentiment == "CRITICAL_SOS")
    avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 2) if reviews else 5.0

    return {
        "total": len(reviews),
        "average_rating": avg_rating,
        "sos_incidents_count": sos_count,
        "reviews": [
            {
                "id": str(r.id),
                "external_review_id": r.external_review_id,
                "customer_name": r.customer_name,
                "product_name": r.product_name,
                "product_sku": r.product_sku,
                "rating": r.rating,
                "review_text": r.review_text,
                "ai_sentiment": r.ai_sentiment,
                "reply_text": r.reply_text,
                "reply_status": r.reply_status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "replied_at": r.replied_at.isoformat() if r.replied_at else None,
            }
            for r in reviews
        ]
    }


@router.post("/reviews/generate-reply")
async def generate_single_reply(
    payload: GenerateReplyPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Generates an empathetic AI reply for a specific review and saves it.
    """
    try:
        r_id = uuid.UUID(payload.review_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid review UUID")

    stmt = select(CustomerReview).where(CustomerReview.id == r_id)
    review = (await db.execute(stmt)).scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    reply = AIAssistantService.generate_smart_reply(
        customer_name=review.customer_name,
        product_name=review.product_name,
        rating=review.rating,
        review_text=review.review_text
    )

    review.reply_text = reply
    review.reply_status = "REPLIED"
    review.replied_at = datetime.utcnow()
    await db.commit()

    return {
        "status": "success",
        "review_id": str(review.id),
        "reply_text": reply
    }


@router.post("/reviews/auto-reply-all")
async def auto_reply_all(
    payload: AutoReplyAllPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Batch auto-replies to all pending 4-star and 5-star reviews with personalized AI answers.
    Escalates 1-star and 2-star negative reviews directly to the merchant via Telegram SOS alerts.
    """
    stmt = select(CustomerReview).where(CustomerReview.reply_status == "PENDING")
    reviews = (await db.execute(stmt)).scalars().all()

    replied_count = 0
    sos_escalated_count = 0

    for r in reviews:
        if r.rating >= payload.min_rating:
            reply = AIAssistantService.generate_smart_reply(
                customer_name=r.customer_name,
                product_name=r.product_name,
                rating=r.rating,
                review_text=r.review_text
            )
            r.reply_text = reply
            r.reply_status = "REPLIED"
            r.replied_at = datetime.utcnow()
            replied_count += 1
        elif r.rating <= 2:
            r.reply_status = "ESCALATED_SOS"
            sos_escalated_count += 1
            # Send Telegram alert for negative review
            try:
                await NotificationService.send_alert(
                    title=f"🚨 SOS: Негативный отзыв {r.rating}★ в Kaspi",
                    message=f"Клиент: {r.customer_name}\nТовар: {r.product_name}\nОтзыв: «{r.review_text}»\nТребуется срочная связь с клиентом!",
                    alert_type="SOS_REVIEW"
                )
            except Exception:
                pass

    await db.commit()

    return {
        "status": "success",
        "replied_count": replied_count,
        "sos_escalated_count": sos_escalated_count,
        "message": f"Автоматически отвечено на {replied_count} отзывов, эскалировано {sos_escalated_count} SOS инцидентов"
    }


@router.post("/generate-description")
async def generate_seo_description(payload: GenerateSEOPayload):
    """
    Generates Kaspi-optimized SEO product descriptions and bullet points.
    """
    result = AIAssistantService.generate_seo_card_description(
        title=payload.title,
        brand=payload.brand,
        category=payload.category,
        key_features=payload.features
    )
    return result


class CopilotChatPayload(BaseModel):
    query: str


@router.post("/copilot/chat")
async def copilot_chat(
    payload: CopilotChatPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Interactive AI Sales Copilot & Director with live business context.
    """
    from app.modules.ai_assistant.copilot import AICopilotService
    return await AICopilotService.chat(payload.query, db)


async def seed_demo_reviews_internal(db: AsyncSession):
    demo_data = [
        {
            "customer": "Айдар К.",
            "product": "Смартфон Apple iPhone 15 128GB Black",
            "sku": "IPH-15-128",
            "rating": 5,
            "text": "Отличный оригинальный телефон! Доставили день в день через Kaspi Почтомат. Упакован супер, коробка целая, активировался без проблем. Продавца рекомендую!",
            "sentiment": "EXCELLENT"
        },
        {
            "customer": "Дана М.",
            "product": "Беспроводные наушники Apple AirPods Pro 2",
            "sku": "APP-2-WHT",
            "rating": 5,
            "text": "Звук просто бомба, шумоподавление работает отлично. Пробился на сайте Apple. Спасибо за быструю отправку!",
            "sentiment": "EXCELLENT"
        },
        {
            "customer": "Ерлан С.",
            "product": "Фитнес-браслет Xiaomi Smart Band 8 Black",
            "sku": "XM-SB8-BLK",
            "rating": 4,
            "text": "Хороший браслет за свои деньги, батарею держит долго. Единственное — коробка была слегка примята, но сам девайс в идеале.",
            "sentiment": "POSITIVE"
        },
        {
            "customer": "Алибек Т.",
            "product": "Планшет Samsung Galaxy Tab S9 FE 128GB Gray",
            "sku": "SAM-TAB9-GRY",
            "rating": 1,
            "text": "Ужас! Пришел не тот цвет, а в коробке нет стилуса S-Pen! Срочно решите вопрос или верните деньги!",
            "sentiment": "CRITICAL_SOS"
        }
    ]

    for item in demo_data:
        external_id = f"REV-{uuid.uuid4().hex[:8].upper()}"
        rev = CustomerReview(
            external_review_id=external_id,
            customer_name=item["customer"],
            product_name=item["product"],
            product_sku=item["sku"],
            rating=item["rating"],
            review_text=item["text"],
            ai_sentiment=item["sentiment"],
            reply_status="PENDING"
        )
        db.add(rev)

    await db.commit()
