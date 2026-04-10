"""
Тесты для AI Service — проверка анализа договоров через Kimi API.
Используют мок-ответы для тестирования без реального API.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai_service import analyze_contract_text, _parse_ai_response, _get_demo_analysis
from app.models.document import AnalysisResult, RiskLevel


# ============================================================
# Тесты: парсинг AI-ответа
# ============================================================

class TestParseAIResponse:
    """Тесты парсинга JSON-ответа от Kimi."""

    def test_parse_valid_response(self):
        """Корректный JSON должен парситься без ошибок."""
        raw = json.dumps({
            "document_type": "Договор подряда",
            "summary": "Договор между ИП и заказчиком на выполнение ремонтных работ.",
            "risks": [
                {
                    "category": "Оплата",
                    "description": "Срок оплаты не определён",
                    "risk_level": "high",
                    "original_clause": "Оплата производится по требованию",
                    "recommendation": "Указать конкретный срок оплаты"
                },
                {
                    "category": "Расторжение",
                    "description": "Нет порядка расторжения",
                    "risk_level": "medium",
                    "recommendation": "Добавить раздел о расторжении"
                }
            ],
            "recommendations": ["Проконсультируйтесь с юристом", "Уточните сроки"]
        })

        result = _parse_ai_response(raw)

        assert result.analysis_success is True
        assert result.document_type == "Договор подряда"
        assert result.total_risks == 2
        assert result.high_risk_count == 1
        assert result.overall_risk_level == RiskLevel.HIGH
        assert len(result.recommendations) == 2

    def test_parse_response_with_markdown_wrapper(self):
        """JSON обёрнутый в ```json ``` должен парситься корректно."""
        raw = '```json\n{"document_type": "Договор аренды", "summary": "Тест", "risks": [], "recommendations": []}\n```'
        result = _parse_ai_response(raw)
        assert result.analysis_success is True
        assert result.document_type == "Договор аренды"
        assert result.total_risks == 0

    def test_parse_empty_risks_array(self):
        """Пустой массив рисков должен давать overall_level = low."""
        raw = json.dumps({
            "document_type": "Акт",
            "summary": "Без рисков",
            "risks": [],
            "recommendations": []
        })
        result = _parse_ai_response(raw)
        assert result.total_risks == 0
        assert result.overall_risk_level == RiskLevel.LOW

    def test_parse_invalid_json_returns_error(self):
        """Битый JSON должен возвращать AnalysisResult с analysis_success=False."""
        result = _parse_ai_response("не_валидный_json{{{")
        assert result.analysis_success is False
        assert result.error_message is not None
        assert "JSON" in result.error_message

    def test_parse_all_risk_levels(self):
        """Все уровни риска должны корректно парситься."""
        raw = json.dumps({
            "document_type": "Тест",
            "summary": "Тест",
            "risks": [
                {"category": "A", "description": "High", "risk_level": "high"},
                {"category": "B", "description": "Medium", "risk_level": "medium"},
                {"category": "C", "description": "Low", "risk_level": "low"},
            ],
            "recommendations": []
        })
        result = _parse_ai_response(raw)
        assert result.total_risks == 3
        assert result.high_risk_count == 1
        levels = [r.risk_level for r in result.risks]
        assert RiskLevel.HIGH in levels
        assert RiskLevel.MEDIUM in levels
        assert RiskLevel.LOW in levels


# ============================================================
# Тесты: analyze_contract_text
# ============================================================

class TestAnalyzeContractText:
    """Тесты основной функции анализа договора."""

    @pytest.mark.asyncio
    async def test_short_text_returns_error(self):
        """Слишком короткий текст должен возвращать ошибку без вызова API."""
        result = await analyze_contract_text("Привет")
        assert result.analysis_success is False
        assert "слишком короткий" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_empty_text_returns_error(self):
        """Пустой текст должен возвращать ошибку."""
        result = await analyze_contract_text("")
        assert result.analysis_success is False

    @pytest.mark.asyncio
    async def test_demo_mode_without_token(self):
        """Без HF_TOKEN должен возвращаться демо-анализ."""
        contract = "Договор подряда между Заказчиком и Исполнителем. " * 10

        with patch("app.services.ai_service.settings") as mock_settings:
            mock_settings.hf_token = None
            mock_settings.kimi_model = "test-model"
            result = await analyze_contract_text(contract)

        assert result.analysis_success is True
        assert "ДЕМО" in result.summary or "Демо" in result.document_type
        assert result.total_risks > 0

    @pytest.mark.asyncio
    async def test_successful_api_call(self):
        """При наличии токена — должен вызываться AsyncOpenAI и возвращать результат."""
        contract = "Договор аренды помещения. Арендодатель предоставляет помещение. " * 20

        mock_response = json.dumps({
            "document_type": "Договор аренды",
            "summary": "Аренда офисного помещения",
            "risks": [
                {
                    "category": "Оплата",
                    "description": "Размер арендной платы не индексируется",
                    "risk_level": "medium",
                    "recommendation": "Добавить условие индексации"
                }
            ],
            "recommendations": ["Уточнить порядок индексации арендной платы"]
        })

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content=mock_response))]
            )
        )

        with patch("app.services.ai_service.settings") as mock_settings:
            mock_settings.hf_token = "test-token-123"
            mock_settings.kimi_model = "test-model"
            with patch("openai.AsyncOpenAI", return_value=mock_client):
                result = await analyze_contract_text(contract)

        assert result.analysis_success is True
        assert result.document_type == "Договор аренды"
        assert result.total_risks == 1

    @pytest.mark.asyncio
    async def test_api_error_returns_failure(self):
        """Ошибка API должна возвращаться как AnalysisResult с analysis_success=False."""
        contract = "Договор подряда между сторонами. Работы выполняются своевременно. " * 10

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API connection timeout")
        )

        with patch("app.services.ai_service.settings") as mock_settings:
            mock_settings.hf_token = "test-token"
            mock_settings.kimi_model = "test-model"
            with patch("openai.AsyncOpenAI", return_value=mock_client):
                result = await analyze_contract_text(contract)

        assert result.analysis_success is False
        assert "Ошибка AI сервиса" in result.error_message


# ============================================================
# Тесты: демо-анализ
# ============================================================

class TestDemoAnalysis:
    """Тесты демо-режима."""

    def test_demo_returns_analysis_result(self):
        """Демо-режим должен возвращать непустой результат."""
        result = _get_demo_analysis("Тестовый договор")
        assert isinstance(result, AnalysisResult)
        assert result.analysis_success is True
        assert result.total_risks > 0
        assert result.high_risk_count >= 0

    def test_demo_has_recommendations(self):
        """Демо-режим должен содержать рекомендации с упоминанием HF_TOKEN."""
        result = _get_demo_analysis("Любой текст")
        assert len(result.recommendations) > 0
        combined = " ".join(result.recommendations)
        assert "HF_TOKEN" in combined
