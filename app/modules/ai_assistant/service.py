import re
from typing import Dict, Any, Optional, List
from datetime import datetime


class AIAssistantService:
    """
    AI Service powering Kaspi Seller super-tools:
    1. Sentiment analysis and auto-reply generator for Kaspi reviews.
    2. SOS Incident detector (1-2 star alerts).
    3. Kaspi SEO product card description generator.
    """

    CRITICAL_KEYWORDS = [
        "брак", "сломан", "не работает", "подделка", "фальшивка", "обман",
        "мошенник", "дефект", "ужасно", "царапины", "вскрыта", "не тот товар",
        "верните деньги", "разочарован", "отвратительно"
    ]

    @classmethod
    def analyze_sentiment(cls, rating: int, text: str) -> str:
        text_lower = text.lower()
        if rating <= 2 or any(k in text_lower for k in cls.CRITICAL_KEYWORDS):
            return "CRITICAL_SOS" if rating <= 2 else "NEGATIVE"
        elif rating == 3:
            return "NEUTRAL"
        elif rating == 4:
            return "POSITIVE"
        else:
            return "EXCELLENT"

    @classmethod
    def is_sos_incident(cls, rating: int, text: str) -> bool:
        if rating <= 2:
            return True
        text_lower = text.lower()
        return any(k in text_lower for k in cls.CRITICAL_KEYWORDS)

    @classmethod
    def generate_smart_reply(
        cls,
        customer_name: str,
        product_name: str,
        rating: int,
        review_text: str,
        shop_name: str = "Наш магазин"
    ) -> str:
        """
        Generates contextual, empathetic, and conversion-oriented replies.
        """
        name_clean = customer_name.strip() if customer_name else "Уважаемый покупатель"
        sentiment = cls.analyze_sentiment(rating, review_text)

        if sentiment == "CRITICAL_SOS":
            return (
                f"Здравствуйте, {name_clean}! Приносим искренние извинения за возникшие сложности с «{product_name}». "
                f"Для нас крайне важно качество каждого отправленного заказа. Пожалуйста, напишите нам в чат Kaspi Pay или свяжитесь со службой заботы о клиентах — мы немедленно организуем бесплатную замену или полный возврат средств. "
                f"Мы ценим ваше доверие и решим вопрос в течение 1 часа! С уважением, команда «{shop_name}»."
            )
        elif sentiment == "NEGATIVE" or rating == 3:
            return (
                f"Здравствуйте, {name_clean}! Благодарим вас за обратную связь о товаре «{product_name}». "
                f"Нам очень жаль, что покупка не оправдала ожидания на 100%. Мы уже передали ваши замечания в отдел контроля качества. "
                f"Если вам потребуется консультация по эксплуатации или настройке, мы всегда на связи и рады помочь. "
                f"С уважением и заботой, «{shop_name}»."
            )
        elif rating == 4:
            return (
                f"Здравствуйте, {name_clean}! Спасибо за высокую оценку и выбор нашего магазина! "
                f"Мы рады, что «{product_name}» вам понравился. Постоянно работаем над тем, чтобы наш сервис заслуживал только 5 звезд. "
                f"Будем счастливы видеть вас снова среди наших постоянных покупателей! Приятного использования!"
            )
        else: # 5 stars / EXCELLENT
            return (
                f"Здравствуйте, {name_clean}! Огромное спасибо за великолепный отзыв и высшую оценку! 🌟 "
                f"Мы очень рады, что «{product_name}» радует вас качеством. Наша цель — доставлять только оригинальную и проверенную продукцию. "
                f"Добавляйте магазин «{shop_name}» в избранное на Kaspi, чтобы первыми узнавать о скидках и новинках. Отличного настроения и приятных покупок!"
            )

    @classmethod
    def generate_seo_card_description(
        cls,
        title: str,
        brand: Optional[str] = None,
        category: Optional[str] = None,
        key_features: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generates high-converting SEO content for Kaspi Product Cards.
        Includes title, marketing hook, bullet points, and warranty badges.
        """
        b = brand.strip() if brand else "Оригинал"
        c = category.strip() if category else "Товары для дома и жизни"
        features_list = key_features or [
            "100% официальная гарантия и сертификат подлинности",
            "Быстрая отправка через Kaspi Доставку день в день",
            "Качественные материалы премиум-уровня с долгим сроком службы",
            "Надежная многослойная упаковка перед передачей курьеру"
        ]

        bullets_formatted = "\n".join([f"• {f}" for f in features_list])

        description_html = f"""
<h3>{title} — Оригинальное качество от {b}</h3>
<p><strong>{title}</strong> в категории <em>{c}</em> — это идеальный баланс надежности, функциональности и передовых технологий. Товар проходит обязательный тройной контроль качества перед передачей в службу доставки Kaspi.</p>

<h4>Главные преимущества модели:</h4>
{bullets_formatted}

<h4>Комплектация и гарантия:</h4>
<p>В комплекте: фирменная упаковка, товарная накладная, инструкция на русском/казахском языках. Официальная гарантия производителя с обслуживанием в сертифицированных сервисных центрах Казахстана.</p>
        """.strip()

        return {
            "seo_title": f"{title} {b} — купить в рассрочку 0-0-12 на Kaspi",
            "short_hook": f"Лучший выбор в категории {c}. Официальная гарантия, быстрая Kaspi Доставка!",
            "description_html": description_html,
            "bullet_points": features_list,
            "tags": [b.lower(), (category or "kaspi").lower(), "доставка kaspi", "в рассрочку", "гарантия"]
        }
