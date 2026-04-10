"""
Analysis API — Эндпоинты для анализа договоров.
Принимает PDF, DOCX, JPG, PNG — возвращает структурированные юридические риски.
"""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.file_service import FileService
from app.services.ai_service import analyze_contract_text
from app.services.legal_service import LegalService
from app.models.document import AnalyzeResponse, AnalysisResult

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Анализ договора на юридические риски",
    description=(
        "Загрузите договор в формате PDF, DOCX или изображение (JPG/PNG). "
        "Сервис извлечёт текст и вернёт список юридических рисков с рекомендациями."
    ),
    tags=["Analysis"]
)
async def analyze_document(
    file: UploadFile = File(..., description="Файл договора (PDF, DOCX, JPG, PNG)")
) -> AnalyzeResponse:
    """
    Основной эндпоинт анализа документа.

    Args:
        file: Загружаемый файл договора

    Returns:
        AnalyzeResponse: Информация о файле и результаты юридического анализа

    Raises:
        HTTPException 400: Неподдерживаемый формат или пустой файл
        HTTPException 500: Внутренняя ошибка при обработке
    """
    logger.info(f"📥 Получен запрос на анализ файла: {file.filename}")

    # Шаг 1: Обработка файла и извлечение текста
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

    # Шаг 2: AI-анализ извлечённого текста
    analysis_result = await analyze_contract_text(file_result.extracted_text)

    if not analysis_result.analysis_success:
        logger.error(f"❌ Ошибка AI-анализа: {analysis_result.error_message}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка анализа: {analysis_result.error_message}"
        )

    # Шаг 3: Обогащение рисков ссылками на нормы права РК
    analysis_result = LegalService.enrich_analysis(analysis_result)

    logger.info(
        f"🎯 Анализ завершён: найдено {analysis_result.total_risks} рисков "
        f"(критических: {analysis_result.high_risk_count})"
    )

    return AnalyzeResponse(
        status="success",
        file_info=file_result,
        analysis=analysis_result
    )


@router.get(
    "/analyze/formats",
    summary="Поддерживаемые форматы файлов",
    tags=["Analysis"]
)
async def get_supported_formats() -> dict:
    """
    Возвращает информацию о поддерживаемых форматах файлов.

    Returns:
        dict: Список поддерживаемых форматов и ограничений
    """
    return {
        "supported_formats": [
            {"extension": "pdf", "description": "PDF документы", "max_size_mb": 20},
            {"extension": "docx", "description": "Microsoft Word документы", "max_size_mb": 20},
            {"extension": "jpg/jpeg", "description": "JPEG изображения (OCR)", "max_size_mb": 20},
            {"extension": "png", "description": "PNG изображения (OCR)", "max_size_mb": 20},
        ],
        "max_file_size_mb": 20,
        "ocr_languages": ["русский", "английский"]
    }