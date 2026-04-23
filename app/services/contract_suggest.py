"""
AI Contract Suggestion Service.

Uses the existing Kimi AI (via HuggingFace Router) to generate
improved legal text for specific contract clauses.
"""

import logging
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)

# System prompt for contract clause generation
CONTRACT_SUGGEST_PROMPT = """Ты — опытный корпоративный юрист, специализирующийся на праве Республики Казахстан.
Твоя задача: предложить профессиональный юридический текст для указанного раздела договора.

ПРАВИЛА:
- Пиши на русском языке
- Используй терминологию законодательства РК (ГК РК, ТК РК)
- Текст должен быть готов к включению в договор — формальный, точный
- Не добавляй заголовков разделов, только текст пунктов
- Используй нумерацию пунктов (X.1, X.2, ...)
- Не используй markdown-форматирование
- Отвечай ТОЛЬКО текстом для договора, без пояснений"""

# Field descriptions for better AI context
FIELD_DESCRIPTIONS = {
    "conditions": "условия и предмет договора",
    "penalties": "штрафные санкции и неустойки",
    "deadlines": "сроки исполнения обязательств",
    "liability": "ответственность сторон",
    "termination": "условия расторжения договора",
    "payment_terms": "порядок и условия оплаты",
    "custom": "пользовательский раздел",
}

CONTRACT_TYPE_NAMES = {
    "sale": "договор купли-продажи",
    "labor": "трудовой договор",
}


async def suggest_contract_text(
    contract_type: str,
    field: str,
    prompt: str,
    context: Optional[dict] = None,
) -> str:
    """
    Generate AI suggestion for a contract clause.

    Args:
        contract_type: Type of contract (sale or labor)
        field: Which contract field to generate text for
        prompt: User's description of desired text
        context: Optional contract data for personalization

    Returns:
        Generated text for the contract clause
    """
    field_desc = FIELD_DESCRIPTIONS.get(field, field)
    contract_name = CONTRACT_TYPE_NAMES.get(contract_type, "договор")

    # Build context string from contract data if available
    context_str = ""
    if context:
        context_parts = [f"- {k}: {v}" for k, v in context.items() if v]
        if context_parts:
            context_str = f"\n\nДанные договора:\n" + "\n".join(context_parts)

    user_message = (
        f"Тип договора: {contract_name}\n"
        f"Раздел: {field_desc}\n"
        f"Запрос пользователя: {prompt}"
        f"{context_str}\n\n"
        f"Напиши юридический текст для включения в {contract_name}, раздел «{field_desc}»."
    )

    # Try real AI
    if settings.hf_token:
        try:
            return await _call_ai(user_message)
        except Exception as e:
            logger.warning(f"⚠️ AI API недоступен, используется шаблон: {e}")
            return _get_fallback_text(contract_type, field, prompt)
    else:
        logger.info("ℹ️ HF_TOKEN не задан — используется шаблонный текст")
        return _get_fallback_text(contract_type, field, prompt)


async def _call_ai(user_message: str) -> str:
    """Call Kimi AI via HuggingFace Router."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=settings.hf_token,
    )

    logger.info(f"🤖 Запрос к Kimi для генерации текста договора")

    response = await client.chat.completions.create(
        model=settings.kimi_model,
        messages=[
            {"role": "system", "content": CONTRACT_SUGGEST_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    result = response.choices[0].message.content.strip()
    logger.info(f"✅ Текст от AI получен: {len(result)} символов")
    return result


def _get_fallback_text(contract_type: str, field: str, prompt: str) -> str:
    """
    Return template-based fallback text when AI is unavailable.
    Provides meaningful defaults for each field type.
    """
    fallbacks = {
        "sale": {
            "conditions": (
                "X.1. Продавец обязуется передать в собственность Покупателя, "
                "а Покупатель обязуется принять и оплатить товар в соответствии "
                "с условиями настоящего Договора.\n"
                "X.2. Качество товара должно соответствовать стандартам, "
                "установленным законодательством Республики Казахстан."
            ),
            "penalties": (
                "X.1. За нарушение сроков оплаты Покупатель уплачивает Продавцу "
                "неустойку в размере 0,1% от суммы задолженности за каждый день просрочки, "
                "но не более 10% от общей суммы Договора (ст. 293 ГК РК).\n"
                "X.2. За нарушение сроков поставки Продавец уплачивает Покупателю "
                "неустойку в размере 0,1% от стоимости недопоставленного товара "
                "за каждый день просрочки."
            ),
            "deadlines": (
                "X.1. Товар передаётся Покупателю в течение 10 (десяти) рабочих дней "
                "с момента подписания настоящего Договора.\n"
                "X.2. Приёмка товара осуществляется в течение 3 (трёх) рабочих дней "
                "с момента доставки."
            ),
            "liability": (
                "X.1. Стороны несут ответственность за неисполнение или ненадлежащее "
                "исполнение обязательств по настоящему Договору в соответствии "
                "с законодательством Республики Казахстан.\n"
                "X.2. Возмещению подлежат прямые убытки, подтверждённые документально."
            ),
            "termination": (
                "X.1. Настоящий Договор может быть расторгнут по соглашению Сторон.\n"
                "X.2. Каждая из Сторон вправе расторгнуть Договор в одностороннем порядке, "
                "уведомив другую Сторону в письменной форме не менее чем за 30 (тридцать) "
                "календарных дней до даты расторжения (ст. 404 ГК РК)."
            ),
            "payment_terms": (
                "X.1. Оплата производится в безналичном порядке путём перечисления "
                "денежных средств на расчётный счёт Продавца.\n"
                "X.2. Оплата осуществляется в следующем порядке: предоплата в размере "
                "50% — в течение 5 рабочих дней с момента подписания Договора; "
                "окончательный расчёт — в течение 5 рабочих дней после приёмки товара."
            ),
        },
        "labor": {
            "conditions": (
                "X.1. Работодатель принимает Работника на должность согласно "
                "штатному расписанию.\n"
                "X.2. Место работы: по юридическому адресу Работодателя.\n"
                "X.3. Характер работы: основная работа, полная занятость."
            ),
            "penalties": (
                "X.1. За нарушение трудовой дисциплины к Работнику могут применяться "
                "дисциплинарные взыскания в соответствии со ст. 64 Трудового кодекса РК:\n"
                "а) замечание;\nб) выговор;\nв) строгий выговор;\n"
                "г) расторжение трудового договора по инициативе работодателя."
            ),
            "deadlines": (
                "X.1. Испытательный срок устанавливается продолжительностью 3 (три) месяца.\n"
                "X.2. Рабочее время: с 09:00 до 18:00, обеденный перерыв с 13:00 до 14:00.\n"
                "X.3. Ежегодный оплачиваемый трудовой отпуск — 24 календарных дня."
            ),
            "liability": (
                "X.1. Работник несёт материальную ответственность за ущерб, "
                "причинённый Работодателю, в порядке и пределах, установленных "
                "Трудовым кодексом РК (Глава 14).\n"
                "X.2. Работодатель несёт ответственность за обеспечение безопасных "
                "условий труда (ст. 23 ТК РК)."
            ),
            "termination": (
                "X.1. Трудовой договор может быть прекращён по основаниям, "
                "предусмотренным ст. 49 Трудового кодекса РК.\n"
                "X.2. Работник вправе расторгнуть Договор, предупредив Работодателя "
                "не менее чем за 1 (один) месяц (ст. 56 ТК РК)."
            ),
            "payment_terms": (
                "X.1. Заработная плата выплачивается не реже одного раза в месяц, "
                "не позднее 10-го числа месяца, следующего за расчётным.\n"
                "X.2. Оплата производится в безналичном порядке на банковский счёт Работника.\n"
                "X.3. За сверхурочную работу начисляется оплата в полуторном размере (ст. 108 ТК РК)."
            ),
        },
    }

    # Get field-specific fallback or generic one
    contract_fallbacks = fallbacks.get(contract_type, fallbacks["sale"])
    text = contract_fallbacks.get(field)

    if text:
        return text

    # Generic custom fallback
    return (
        f"X.1. [Текст по запросу: {prompt}]\n\n"
        f"⚠️ ДЕМО-РЕЖИМ: Для генерации текста с помощью AI добавьте HF_TOKEN в файл .env.\n"
        f"Получить токен: https://huggingface.co/settings/tokens"
    )
