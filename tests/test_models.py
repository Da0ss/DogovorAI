"""
Тесты для Document моделей (Pydantic).
Проверка AnalysisResult, RiskItem, FileProcessResult.
"""

import pytest
from pydantic import ValidationError

from app.models.document import (
    FileType,
    RiskLevel,
    RiskItem,
    AnalysisResult,
    FileProcessResult,
    AnalyzeResponse,
)


# ============================================================
# Тесты: FileType enum
# ============================================================

class TestFileType:
    """Тесты перечисления FileType."""

    def test_all_types_exist(self):
        expected = {"pdf", "docx", "image", "txt", "unknown"}
        actual = {ft.value for ft in FileType}
        assert expected == actual

    def test_pdf_value(self):
        assert FileType.PDF.value == "pdf"

    def test_unknown_value(self):
        assert FileType.UNKNOWN.value == "unknown"


# ============================================================
# Тесты: RiskLevel enum
# ============================================================

class TestRiskLevel:
    """Тесты перечисления RiskLevel."""

    def test_all_levels_exist(self):
        levels = {rl.value for rl in RiskLevel}
        assert "high" in levels
        assert "medium" in levels
        assert "low" in levels

    def test_from_string(self):
        assert RiskLevel("high") == RiskLevel.HIGH
        assert RiskLevel("medium") == RiskLevel.MEDIUM
        assert RiskLevel("low") == RiskLevel.LOW

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError):
            RiskLevel("critical")


# ============================================================
# Тесты: RiskItem
# ============================================================

class TestRiskItem:
    """Тесты модели RiskItem."""

    def test_minimal_valid_risk(self):
        """Минимально валидный RiskItem с обязательными полями."""
        risk = RiskItem(
            category="Оплата",
            description="Срок оплаты не определён",
        )
        assert risk.category == "Оплата"
        assert risk.risk_level == RiskLevel.MEDIUM  # default
        assert risk.original_clause is None
        assert risk.recommendation is None

    def test_full_risk_item(self):
        """Полный RiskItem со всеми полями."""
        risk = RiskItem(
            category="Расторжение",
            description="Отсутствует порядок расторжения",
            risk_level=RiskLevel.HIGH,
            original_clause="Договор расторгается без уведомления",
            recommendation="Добавить срок уведомления 30 дней",
            law_reference="ГК РК ст. 404",
            law_description="Односторонний отказ от договора",
        )
        assert risk.risk_level == RiskLevel.HIGH
        assert risk.law_reference == "ГК РК ст. 404"

    def test_missing_category_raises(self):
        with pytest.raises(ValidationError):
            RiskItem(description="Только описание")

    def test_missing_description_raises(self):
        with pytest.raises(ValidationError):
            RiskItem(category="Оплата")

    def test_default_risk_level_is_medium(self):
        risk = RiskItem(category="Тест", description="Описание")
        assert risk.risk_level == RiskLevel.MEDIUM


# ============================================================
# Тесты: AnalysisResult
# ============================================================

class TestAnalysisResult:
    """Тесты модели AnalysisResult."""

    def test_default_values(self):
        """AnalysisResult с дефолтными значениями создаётся корректно."""
        result = AnalysisResult()
        assert result.analysis_success is True
        assert result.total_risks == 0
        assert result.risks == []
        assert result.recommendations == []
        assert result.overall_risk_level == RiskLevel.LOW

    def test_with_risks(self):
        risks = [
            RiskItem(category="Оплата", description="Срок", risk_level=RiskLevel.HIGH),
            RiskItem(category="Срок", description="Просрочка", risk_level=RiskLevel.MEDIUM),
        ]
        result = AnalysisResult(
            document_type="Договор подряда",
            summary="Договор на выполнение работ",
            risks=risks,
            total_risks=2,
            high_risk_count=1,
            medium_risk_count=1,
            overall_risk_level=RiskLevel.HIGH,
            analysis_success=True,
        )
        assert result.total_risks == 2
        assert result.high_risk_count == 1
        assert result.overall_risk_level == RiskLevel.HIGH

    def test_failed_analysis(self):
        """Провальный анализ сохраняет error_message."""
        result = AnalysisResult(
            analysis_success=False,
            error_message="AI недоступен"
        )
        assert result.analysis_success is False
        assert result.error_message == "AI недоступен"

    def test_model_copy_update(self):
        """model_copy(update=...) работает корректно."""
        base = AnalysisResult(document_type="Тест", summary="Базовый")
        updated = base.model_copy(update={"summary": "Обновлённый"})
        assert updated.summary == "Обновлённый"
        assert updated.document_type == "Тест"

    def test_recommendations_list(self):
        result = AnalysisResult(recommendations=["Рек 1", "Рек 2"])
        assert len(result.recommendations) == 2


# ============================================================
# Тесты: FileProcessResult
# ============================================================

class TestFileProcessResult:
    """Тесты модели FileProcessResult."""

    def test_valid_txt_result(self):
        result = FileProcessResult(
            filename="test.txt",
            file_type=FileType.TXT,
            extracted_text="Содержимое файла",
            char_count=16,
            page_count=1,
            success=True,
        )
        assert result.filename == "test.txt"
        assert result.char_count == 16

    def test_failed_result(self):
        result = FileProcessResult(
            filename="bad.pdf",
            file_type=FileType.PDF,
            success=False,
            error_message="Не удалось прочитать PDF",
        )
        assert result.success is False
        assert result.error_message is not None
        assert result.extracted_text == ""  # default

    def test_defaults(self):
        result = FileProcessResult(filename="f.txt", file_type=FileType.TXT)
        assert result.extracted_text == ""
        assert result.char_count == 0
        assert result.page_count == 0
        assert result.success is True
        assert result.error_message is None


# ============================================================
# Тесты: AnalyzeResponse
# ============================================================

class TestAnalyzeResponse:
    """Тесты ответа на запрос анализа."""

    def test_analyze_response_structure(self):
        file_info = FileProcessResult(
            filename="contract.docx",
            file_type=FileType.DOCX,
            extracted_text="Текст договора",
            char_count=14,
            success=True,
        )
        analysis = AnalysisResult(
            document_type="Договор аренды",
            summary="Аренда офиса",
            analysis_success=True,
        )
        response = AnalyzeResponse(
            status="success",
            file_info=file_info,
            analysis=analysis,
        )
        assert response.status == "success"
        assert response.file_info.filename == "contract.docx"
        assert response.analysis.document_type == "Договор аренды"

    def test_default_status_is_success(self):
        file_info = FileProcessResult(filename="f.txt", file_type=FileType.TXT)
        analysis = AnalysisResult()
        response = AnalyzeResponse(file_info=file_info, analysis=analysis)
        assert response.status == "success"
