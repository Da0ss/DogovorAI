"""
AI Service — Интеграция с Kimi AI для анализа юридических рисков в договорах.
Использует OpenAI-совместимый API через HuggingFace Router.
"""

import json
import logging
from typing import Optional

from config.settings import settings
from app.models.document import AnalysisResult, RiskItem, RiskLevel

logger = logging.getLogger(__name__)

AI_UNAVAILABLE_PREFIX = "AI_SERVICE_UNAVAILABLE"

# Системный промпт для анализа договоров
SYSTEM_PROMPT = """Ты — опытный юрист-аналитик AI-сервиса DogovorAI, специализирующийся на праве Республики Казахстан (РК).
Твоя задача: проанализировать текст договора и выявить юридические риски, основываясь на Гражданском кодексе РК, Трудовом кодексе РК и других нормативных актах Казахстана.

ФОРМАТ ОТВЕТА (строго JSON):
{
  "document_type": "тип договора (подряда/аренды/трудовой/купли-продажи/иной)",
  "summary": "краткое резюме договора (2-3 предложения)",
  "risks": [
    {
      "category": "категория риска (оплата/расторжение/ответственность/сроки/конфиденциальность/иное)",
      "description": "описание риска на русском языке с указанием на нарушение норм законодательства РК",
      "risk_level": "high/medium/low",
      "original_clause": "исходный текст пункта договора (если найден)",
      "recommendation": "конкретная рекомендация по устранению риска согласно праву РК"
    }
  ],
  "recommendations": ["общая рекомендация 1", "общая рекомендация 2"]
}

ПРАВИЛА:
- Используй терминологию и нормы Республики Казахстан (тенге, НДС РК, ГК РК, ТК РК)
- Находи РЕАЛЬНЫЕ риски, не выдумывай
- risk_level: high — критический риск (может привести к значительным убыткам), medium — умеренный, low — незначительный
- Если рисков нет — верни пустой массив risks
- Язык ответа: ТОЛЬКО русский (или казахский, если текст на казахском)
- Не добавляй пояснений вне JSON структуры"""


def _parse_ai_response(raw_response: str) -> AnalysisResult:
    """
    Парсит JSON-ответ от AI и преобразует в AnalysisResult.

    Args:
        raw_response: Строка JSON от AI

    Returns:
        AnalysisResult: Структурированный результат анализа
    """
    try:
        # Очистка от возможных markdown обёрток
        clean_response = raw_response.strip()
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        if clean_response.startswith("```"):
            clean_response = clean_response[3:]
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]
        clean_response = clean_response.strip()

        data = json.loads(clean_response)

        # Парсим риски
        risks = []
        for risk_data in data.get("risks", []):
            try:
                risk_level_str = risk_data.get("risk_level", "medium").lower()
                risk_level = RiskLevel(risk_level_str) if risk_level_str in ["high", "medium", "low"] else RiskLevel.MEDIUM

                risk = RiskItem(
                    category=risk_data.get("category", "Прочее"),
                    description=risk_data.get("description", ""),
                    risk_level=risk_level,
                    original_clause=risk_data.get("original_clause"),
                    recommendation=risk_data.get("recommendation"),
                )
                risks.append(risk)
            except Exception as e:
                logger.warning(f"⚠️ Пропуск риска из-за ошибки парсинга: {e}")
                continue

        high_count = sum(1 for r in risks if r.risk_level == RiskLevel.HIGH)
        medium_count = sum(1 for r in risks if r.risk_level == RiskLevel.MEDIUM)

        # Определяем общий уровень риска
        if high_count > 0:
            overall_level = RiskLevel.HIGH
        elif medium_count > 0:
            overall_level = RiskLevel.MEDIUM
        else:
            overall_level = RiskLevel.LOW

        return AnalysisResult(
            document_type=data.get("document_type", "Неопределён"),
            summary=data.get("summary", ""),
            risks=risks,
            total_risks=len(risks),
            high_risk_count=high_count,
            medium_risk_count=medium_count,
            overall_risk_level=overall_level,
            recommendations=data.get("recommendations", []),
            analysis_success=True
        )

    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка парсинга JSON от AI: {e}\nОтвет: {raw_response[:500]}")
        return AnalysisResult(
            analysis_success=False,
            error_message=f"AI вернул некорректный JSON: {str(e)}"
        )


def _ai_unavailable(message: str) -> AnalysisResult:
    """Build a production-safe AI unavailable result."""
    return AnalysisResult(
        analysis_success=False,
        error_message=f"{AI_UNAVAILABLE_PREFIX}: {message}",
    )


def is_ai_unavailable(result: AnalysisResult) -> bool:
    """Return True when an AnalysisResult represents upstream AI unavailability."""
    return bool(
        result.error_message
        and result.error_message.startswith(AI_UNAVAILABLE_PREFIX)
    )


def public_ai_error_message(result: AnalysisResult) -> str:
    """Return an error message safe for API responses."""
    if not result.error_message:
        return "AI service unavailable"
    return result.error_message.replace(f"{AI_UNAVAILABLE_PREFIX}: ", "", 1)


async def analyze_contract_text(contract_text: str) -> AnalysisResult:
    """
    Анализирует текст договора с помощью Kimi AI и возвращает структурированные риски.

    Args:
        contract_text: Извлечённый текст договора

    Returns:
        AnalysisResult: Найденные риски, резюме и рекомендации

    Raises:
        Не вызывает исключений — ошибки возвращаются внутри AnalysisResult.analysis_success=False
    """
    if not contract_text or len(contract_text.strip()) < 50:
        return AnalysisResult(
            analysis_success=False,
            error_message="Текст договора слишком короткий для анализа (менее 50 символов)"
        )

    # Ограничиваем текст для API (первые 15000 символов)
    text_to_analyze = contract_text[:15000]
    if len(contract_text) > 15000:
        logger.warning(f"⚠️ Текст договора обрезан с {len(contract_text)} до 15000 символов")
        text_to_analyze += "\n\n[... текст договора продолжается ...]"

    # Проверяем наличие HF токена
    if not settings.hf_token:
        if settings.is_production:
            logger.error("HF_TOKEN is not configured in production")
            return _ai_unavailable("AI анализ временно недоступен: HF_TOKEN не настроен.")
        logger.warning("⚠️ HF_TOKEN не задан — используем демо-анализ только для разработки")
        return _get_demo_analysis(contract_text)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=settings.hf_token,
        )

        logger.info(f"🤖 Отправка запроса к Kimi ({settings.kimi_model}), {len(text_to_analyze)} символов")

        response = await client.chat.completions.create(
            model=settings.kimi_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Проанализируй этот договор:\n\n{text_to_analyze}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Низкая температура для стабильных ответов
            max_tokens=4000,
        )

        raw_content = response.choices[0].message.content
        logger.info(f"✅ Ответ от Kimi получен: {len(raw_content)} символов")

        return _parse_ai_response(raw_content)

    except Exception as e:
        logger.error(f"❌ Ошибка при запросе к Kimi API: {str(e)}")
        return _get_api_error_fallback(contract_text, e)


def _get_api_error_fallback(contract_text: str, err: Exception) -> AnalysisResult:
    """
    Если HF / Router недоступен (квота, токен, сеть) — отдаём демо-результат,
    чтобы UI не ломался и пользователь видел причину.
    """
    if settings.is_production:
        err_short = str(err)[:300]
        logger.error(f"AI API unavailable in production: {err_short}")
        return _ai_unavailable("AI анализ временно недоступен. Попробуйте позже.")

    base = _get_demo_analysis(contract_text)
    err_short = str(err)[:400]
    logger.warning(f"⚠️ AI API недоступен, демо-фолбэк: {err_short}")
    return base.model_copy(
        update={
            "document_type": "Демо",
            "summary": (
                "Запрос к AI не выполнен, "
                "закончилась квота. "
                f"Ниже — пример результата, он не основан на вашем файле."
            ),
            "recommendations": [
                "Проверьте HF_TOKEN и лимиты: https://huggingface.co/settings/tokens",
                err_short,
            ]
            + list(base.recommendations),
        }
    )


def _get_demo_analysis(contract_text: str) -> AnalysisResult:
    """
    Возвращает демо-результат анализа при отсутствии токена API.
    Используется для тестирования без реального AI.

    Args:
        contract_text: Текст договора

    Returns:
        AnalysisResult: Демонстрационный результат
    """
    logger.info("ℹ️ Используется демо-анализ (HF_TOKEN не задан)")

    demo_risks = [
        RiskItem(
            category="Оплата",
            description="В договоре не указан чёткий срок оплаты — 'оплата по требованию' без конкретных дат создаёт риск задержек согласно ст. 277 ГК РК",
            risk_level=RiskLevel.HIGH,
            recommendation="Добавить конкретный срок оплаты (например, 'в течение 5 рабочих дней с момента подписания акта')",
        ),
        RiskItem(
            category="Расторжение",
            description="Одностороннее расторжение можно применить без уведомления другой стороны — риск нарушения баланса интересов (ст. 401 ГК РК)",
            risk_level=RiskLevel.MEDIUM,
            recommendation="Добавить условие: 'Уведомить другую сторону не менее чем за 30 дней до расторжения'",
        ),
        RiskItem(
            category="Ответственность",
            description="Штрафные санкции могут быть признаны несоразмерными судом согласно ст. 297 ГК РК",
            risk_level=RiskLevel.HIGH,
            recommendation="Привести размер неустойки в соответствие с практикой (обычно не более 0.1-0.5% в день)",
        ),
    ]

    return AnalysisResult(
        document_type="Демо (HF_TOKEN не задан)",
        summary=(
            "ДЕМО-РЕЖИМ: Добавьте HF_TOKEN в .env для реального анализа. "
            f"Текст содержит {len(contract_text)} символов."
        ),
        risks=demo_risks,
        total_risks=len(demo_risks),
        high_risk_count=2,
        medium_risk_count=1,
        overall_risk_level=RiskLevel.HIGH,
        recommendations=[
            "Добавьте HF_TOKEN в файл .env для активации AI-анализа",
            "Получить токен: https://huggingface.co/settings/tokens",
        ],
        analysis_success=True
    )
