"""
Contract Generation & Analysis API Routes.

Provides endpoints for:
  - POST /contracts/create       — generate DOCX, return as direct file download
  - POST /contracts/create-json  — generate DOCX, return JSON with download URL
  - GET  /contracts/download/{filename} — download a generated DOCX file
  - POST /contracts/suggest      — AI text suggestion for contract clauses
  - POST /contracts/analyze      — upload document, get AI analysis with risks
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from typing import Optional
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.schemas.contract import (
    ContractCreateRequest,
    ContractCreateResponse,
    ContractType,
    SaleContractRequest,
    LaborContractRequest,
    SuggestRequest,
    SuggestResponse,
)
from app.services.contract_generator import (
    generate_sale_contract,
    generate_labor_contract,
    GENERATED_DIR,
)
from app.services.contract_suggest import suggest_contract_text
from app.services.file_service import FileService
from app.services.ai_service import (
    analyze_contract_text,
    is_ai_unavailable,
    public_ai_error_message,
)
from app.services.usage_limiter import usage_limiter, UsageLimitError

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_token(request: Request) -> Optional[str]:
    """Extract Bearer token from request."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1]
    return None

# Human-readable download names per contract type
_DOWNLOAD_NAMES = {
    ContractType.SALE: "dogovor_kupli_prodazhi.docx",
    ContractType.LABOR: "trudovoy_dogovor.docx",
}


def _generate_file(request: ContractCreateRequest) -> str:
    """
    Validate request data and generate DOCX file.
    Returns the absolute path to the generated file.
    """
    if request.type == ContractType.SALE:
        validated = SaleContractRequest(**request.data)
        return generate_sale_contract(validated.model_dump())

    elif request.type == ContractType.LABOR:
        validated = LaborContractRequest(**request.data)
        return generate_labor_contract(validated.model_dump())

    raise HTTPException(
        status_code=422,
        detail=f"Неизвестный тип договора: '{request.type}'. Поддерживаемые: 'sale', 'labor'.",
    )


# ------------------------------------------------------------------
# POST /contracts/create  — returns the DOCX file directly (one-click)
# ------------------------------------------------------------------
@router.post(
    "/contracts/create",
    summary="Генерация и скачивание договора (DOCX)",
    description="Генерирует DOCX и возвращает файл напрямую для немедленного скачивания.",
    responses={
        200: {
            "description": "DOCX файл договора",
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}
            },
        },
        422: {"description": "Ошибка валидации"},
    },
)
async def create_contract(request: ContractCreateRequest):
    """Generate contract and return DOCX file directly."""
    try:
        file_path = _generate_file(request)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Шаблон не найден: {e}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if not Path(file_path).exists():
        raise HTTPException(status_code=500, detail="Файл не сгенерирован")

    download_name = _DOWNLOAD_NAMES.get(request.type, "dogovor.docx")
    logger.info(f"✅ Договор сгенерирован → FileResponse: {download_name}")

    return FileResponse(
        path=file_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )


# ------------------------------------------------------------------
# POST /contracts/create-json  — returns JSON with download_url
# ------------------------------------------------------------------
@router.post(
    "/contracts/create-json",
    response_model=ContractCreateResponse,
    summary="Генерация договора (JSON-ответ)",
    description="Генерирует DOCX и возвращает JSON с URL для скачивания.",
)
async def create_contract_json(request: ContractCreateRequest):
    """Generate contract and return JSON metadata with download link."""
    try:
        file_path = _generate_file(request)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Шаблон не найден: {e}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if not Path(file_path).exists():
        raise HTTPException(status_code=500, detail="Файл не сгенерирован")

    filename = os.path.basename(file_path)
    download_name = _DOWNLOAD_NAMES.get(request.type, "dogovor.docx")
    download_url = f"/api/contracts/download/{filename}"

    logger.info(f"✅ Договор → JSON: {download_name} → {filename}")

    return ContractCreateResponse(
        success=True,
        message=f"Договор успешно сгенерирован: {download_name}",
        filename=filename,
        download_url=download_url,
    )


# ------------------------------------------------------------------
# GET /contracts/download/{filename}
# ------------------------------------------------------------------
@router.get(
    "/contracts/download/{filename}",
    summary="Скачать сгенерированный договор",
    responses={
        200: {
            "description": "DOCX файл",
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}
            },
        },
        404: {"description": "Файл не найден"},
    },
)
async def download_contract(filename: str):
    """Download a previously generated contract by filename."""
    safe_filename = os.path.basename(filename)
    if safe_filename != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Некорректное имя файла")

    file_path = GENERATED_DIR / safe_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Файл не найден: {filename}")

    return FileResponse(
        path=str(file_path),
        filename="dogovor.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": 'attachment; filename="dogovor.docx"',
        },
    )


# ------------------------------------------------------------------
# POST /contracts/suggest
# ------------------------------------------------------------------
@router.post(
    "/contracts/suggest",
    response_model=SuggestResponse,
    summary="AI-подсказка для текста договора",
)
async def suggest_text(request: SuggestRequest):
    """Generate AI-powered text suggestion for a contract clause."""
    try:
        suggested = await suggest_contract_text(
            contract_type=request.contract_type.value,
            field=request.field.value,
            prompt=request.prompt,
            context=request.context,
        )
        return SuggestResponse(
            success=True,
            field=request.field.value,
            suggested_text=suggested,
            message="Текст сгенерирован. Вы можете отредактировать его.",
        )
    except Exception as e:
        logger.error(f"Ошибка suggest: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# POST /contracts/analyze  — upload doc, get AI risk analysis
# ------------------------------------------------------------------
@router.post(
    "/contracts/analyze",
    summary="Анализ загруженного договора",
    description="Загрузите DOCX или PDF — система проанализирует документ и вернёт "
                "список рисков с рекомендациями.",
)
async def analyze_contract(
    request: Request,
    file: UploadFile = File(..., description="Файл договора (PDF, DOCX, TXT)")
):
    """
    Analyze an uploaded contract, return structured risk issues.
    Response includes issues ready for the 'create with fixes' flow.
    Checks usage limits before processing.
    """
    logger.info(f"📥 Анализ документа: {file.filename}")

    # Step 0: check usage limits
    token = _extract_token(request)
    try:
        if token:
            usage_limiter.check_limit(token)
    except UsageLimitError as e:
        logger.warning(f"⛔ Лимит исчерпан: {e}")
        raise HTTPException(
            status_code=402,
            detail={
                "error": "limit_exceeded",
                "message": str(e),
                "used": e.used,
                "limit": e.limit,
                "plan": e.plan,
            }
        )

    # Step 1: extract text
    file_result = await FileService.process_uploaded_file(file)
    if not file_result.success:
        raise HTTPException(status_code=400, detail=file_result.error_message)

    logger.info(f"✅ Текст извлечён: {file_result.char_count} символов")

    # Step 2: AI analysis
    analysis = await analyze_contract_text(file_result.extracted_text)
    if not analysis.analysis_success:
        raise HTTPException(
            status_code=503 if is_ai_unavailable(analysis) else 500,
            detail=public_ai_error_message(analysis),
        )

    # Step 3: transform into issues format for frontend
    issues = []
    for risk in analysis.risks:
        issues.append({
            "text": risk.original_clause or "",
            "risk": risk.description,
            "category": risk.category,
            "risk_level": risk.risk_level.value,
            "suggestion": risk.recommendation or "",
        })

    # Step 4: increment usage counter
    if token:
        usage_limiter.increment(token)

    logger.info(f"🎯 Анализ завершён: {len(issues)} рисков")

    return {
        "success": True,
        "document_type": analysis.document_type,
        "summary": analysis.summary,
        "issues": issues,
        "recommendations": analysis.recommendations,
        "overall_risk_level": analysis.overall_risk_level.value,
        "total_risks": analysis.total_risks,
        "high_risk_count": analysis.high_risk_count,
        "medium_risk_count": analysis.medium_risk_count,
    }
