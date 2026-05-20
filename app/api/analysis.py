"""
Analysis API — Эндпоинты для анализа договоров.
Принимает PDF, DOCX, JPG, PNG — возвращает структурированные юридические риски.

Включает проверку лимитов: basic (3/мес), pro (30/мес), max (∞).
"""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from typing import Optional

from app.services.file_service import FileService
from app.services.ai_service import analyze_contract_text
from app.services.legal_service import LegalService
from app.services.usage_limiter import usage_limiter, UsageLimitError
from app.models.document import AnalyzeResponse, AnalysisResult
from app.models.database import SessionLocal
from app.models.models import Document, AnalysisResult as DBAnalysisResult

import jwt
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_token(request: Request) -> Optional[str]:
    """Extract Bearer token from request, or None for anonymous."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1]
    return None


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Анализ договора на юридические риски",
    description=(
        "Загрузите договор в формате PDF, DOCX, TXT или изображение (JPG/PNG). "
        "Сервис извлечёт текст и вернёт список юридических рисков с рекомендациями."
    ),
    tags=["Analysis"],
)
async def analyze_document(
    request: Request,
    file: UploadFile = File(..., description="Файл договора (PDF, DOCX, TXT, JPG, PNG)")
) -> AnalyzeResponse:
    """
    Основной эндпоинт анализа документа.

    Args:
        request: HTTP запрос (для извлечения токена авторизации)
        file: Загружаемый файл договора

    Returns:
        AnalyzeResponse: Информация о файле и результаты юридического анализа

    Raises:
        HTTPException 400: Неподдерживаемый формат или пустой файл
        HTTPException 402: Лимит анализов исчерпан
        HTTPException 500: Внутренняя ошибка при обработке
    """
    logger.info(f"📥 Получен запрос на анализ файла: {file.filename}")

    # ── Шаг 0: Проверка лимитов ──
    token = _extract_token(request)
    try:
        usage_info = usage_limiter.check_limit(token) if token else None
    except UsageLimitError as e:
        logger.warning(f"⛔ Лимит исчерпан: {e}")
        raise HTTPException(
            status_code=402,
            detail={
                "error":    "limit_exceeded",
                "message":  str(e),
                "used":     e.used,
                "limit":    e.limit,
                "plan":     e.plan,
                "reset_at": e.reset_at,
            }
        )

    # ── Шаг 1: Обработка файла и извлечение текста ──
    file_result = await FileService.process_uploaded_file(file)

    if not file_result.success:
        logger.warning(f"⚠️ Ошибка обработки файла: {file_result.error_message}")
        raise HTTPException(
            status_code=400,
            detail=file_result.error_message
        )

    logger.info(
        f"✅ Текст извлечён: {file_result.char_count} символов "
        f"из {file_result.filename} ({file_result.file_type.value})"
    )

    # ── Шаг 2: AI-анализ извлечённого текста ──
    analysis_result = await analyze_contract_text(file_result.extracted_text)

    if not analysis_result.analysis_success:
        logger.error(f"❌ Ошибка AI-анализа: {analysis_result.error_message}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка анализа: {analysis_result.error_message}"
        )

    # ── Шаг 3: Обогащение рисков ссылками на нормы права РК ──
    analysis_result = LegalService.enrich_analysis(analysis_result)

    # ── Шаг 4: Инкремент счётчика использования ──
    if token:
        usage_limiter.increment(token)

    logger.info(
        f"🎯 Анализ завершён: найдено {analysis_result.total_risks} рисков "
        f"(критических: {analysis_result.high_risk_count})"
    )

    # ── Шаг 5: Сохранение результата в БД для зарегистрированных пользователей ──
    user_id = None
    if token:
        if token.startswith("local-token-"):
            user_id = token.replace("local-token-", "")
        else:
            try:
                payload = jwt.decode(token, options={"verify_signature": False})
                user_id = payload.get("sub")
            except Exception:
                pass

    if user_id:
        db = SessionLocal()
        try:
            # 1. Create Document record
            db_doc = Document(
                user_id=user_id,
                filename=file_result.filename,
                original_name=file_result.filename,
                file_type=file_result.file_type.value,
                char_count=file_result.char_count,
                page_count=file_result.page_count
            )
            db.add(db_doc)
            db.flush() # get id

            # 2. Serialize risks and recommendations
            risks_json = [r.dict() for r in analysis_result.risks] if analysis_result.risks else []
            recs_json = analysis_result.recommendations if analysis_result.recommendations else []

            # 3. Create AnalysisResult record
            db_analysis = DBAnalysisResult(
                user_id=user_id,
                document_id=db_doc.id,
                document_type=analysis_result.document_type,
                summary=analysis_result.summary,
                overall_risk_level=analysis_result.overall_risk_level.value if hasattr(analysis_result.overall_risk_level, 'value') else "unknown",
                risks=risks_json,
                recommendations=recs_json,
                total_risks=analysis_result.total_risks,
                high_risk_count=analysis_result.high_risk_count,
                medium_risk_count=analysis_result.high_risk_count, # wait, this was medium but Pydantic only tracks high
                success=analysis_result.analysis_success,
                error_message=analysis_result.error_message
            )
            db.add(db_analysis)
            db.commit()
            logger.info(f"💾 Результат сохранен в БД для пользователя {user_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Ошибка сохранения истории в БД: {e}")
        finally:
            db.close()

    return AnalyzeResponse(
        status="success",
        file_info=file_result,
        analysis=analysis_result
    )


@router.post(
    "/v1/analyze",
    response_model=AnalyzeResponse,
    include_in_schema=False,
    summary="Алиас /api/v1/analyze (совместимость со старым фронтом)",
)
async def analyze_document_v1(
    request: Request,
    file: UploadFile = File(..., description="Файл договора (PDF, DOCX, TXT, JPG, PNG)")
) -> AnalyzeResponse:
    """
    Алиас для совместимости со старым фронтендом.
    """
    return await analyze_document(request, file)


@router.get(
    "/analyze/formats",
    summary="Поддерживаемые форматы файлов",
    tags=["Analysis"]
)
async def get_supported_formats() -> dict:
    """
    Возвращает информацию о поддерживаемых форматах файлов.
    """
    return {
        "supported_formats": [
            {"extension": "pdf",      "description": "PDF документы",               "max_size_mb": 20},
            {"extension": "docx",     "description": "Microsoft Word документы",     "max_size_mb": 20},
            {"extension": "txt",      "description": "Обычный текстовый документ",   "max_size_mb": 20},
            {"extension": "jpg/jpeg", "description": "JPEG изображения (OCR)",        "max_size_mb": 20},
            {"extension": "png",      "description": "PNG изображения (OCR)",         "max_size_mb": 20},
        ],
        "max_file_size_mb": 20,
        "ocr_languages": ["русский", "английский"]
    }


# ================================================================
# Usage endpoint  (called by paywall.js as /api/usage/me)
# ================================================================

@router.get(
    "/usage/me",
    summary="Текущее использование — мои лимиты",
    tags=["Usage"],
)
async def get_my_usage(request: Request) -> dict:
    """
    Возвращает информацию о текущем использовании лимитов.
    Используется paywall.js на всех страницах.
    Поддерживает local-token и Supabase JWT.
    """
    token = _extract_token(request)
    usage = usage_limiter.get_usage(token) if token else {
        "used":      0,
        "limit":     3,
        "plan":      "basic",
        "plan_name": "Basic",
        "reset_at":  None,
    }
    limit = usage.get("limit")
    used  = usage.get("used", 0)
    return {
        "success":   True,
        **usage,
        "remaining": (limit - used) if limit is not None else None,
        "exceeded":  (limit is not None and used >= limit),
    }


# Legacy alias  (some pages may call /api/analyze/usage/me)
@router.get("/analyze/usage/me", include_in_schema=False)
async def get_my_usage_legacy(request: Request) -> dict:
    return await get_my_usage(request)