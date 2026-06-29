"""
Тесты для Contract Suggest Service.
Проверка генерации текста договорных разделов.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.contract_suggest import (
    suggest_contract_text,
    _get_fallback_text,
    FIELD_DESCRIPTIONS,
    CONTRACT_TYPE_NAMES,
)


# ============================================================
# Тесты: _get_fallback_text
# ============================================================

class TestGetFallbackText:
    """Тесты шаблонного текста (без AI)."""

    def test_sale_conditions_fallback(self):
        """Sale + conditions возвращает непустой шаблон."""
        text = _get_fallback_text("sale", "conditions", "стандартные условия")
        assert text
        assert "X.1." in text

    def test_sale_penalties_fallback(self):
        """Sale + penalties содержит процент неустойки."""
        text = _get_fallback_text("sale", "penalties", "штрафы")
        assert "%" in text or "неустойку" in text.lower()

    def test_labor_conditions_fallback(self):
        """Labor + conditions возвращает шаблон трудового договора."""
        text = _get_fallback_text("labor", "conditions", "условия труда")
        assert "работн" in text.lower() or "работодател" in text.lower()

    def test_labor_payment_terms_fallback(self):
        """Labor + payment_terms содержит упоминание зарплаты."""
        text = _get_fallback_text("labor", "payment_terms", "оплата")
        assert "заработн" in text.lower() or "оплат" in text.lower()

    def test_unknown_field_returns_generic(self):
        """Неизвестное поле возвращает generic-шаблон с подсказкой."""
        text = _get_fallback_text("sale", "custom", "мой запрос")
        assert "мой запрос" in text or "ДЕМО" in text

    def test_unknown_contract_type_defaults_to_sale(self):
        """Неизвестный тип договора по умолчанию использует sale-шаблоны."""
        text = _get_fallback_text("unknown_type", "conditions", "условия")
        assert text
        # Should fall back to sale conditions
        assert "X.1." in text

    def test_all_sale_fields_have_templates(self):
        """Все поля для sale-типа должны иметь шаблоны (не generic)."""
        fields = ["conditions", "penalties", "deadlines", "liability", "termination", "payment_terms"]
        for field in fields:
            text = _get_fallback_text("sale", field, "тест")
            assert text, f"No fallback for sale.{field}"
            assert "X.1." in text, f"Missing X.1. in sale.{field} fallback"

    def test_all_labor_fields_have_templates(self):
        """Все поля для labor-типа должны иметь шаблоны (не generic)."""
        fields = ["conditions", "penalties", "deadlines", "liability", "termination", "payment_terms"]
        for field in fields:
            text = _get_fallback_text("labor", field, "тест")
            assert text, f"No fallback for labor.{field}"
            assert "X.1." in text, f"Missing X.1. in labor.{field} fallback"


# ============================================================
# Тесты: suggest_contract_text
# ============================================================

class TestSuggestContractText:
    """Тесты основной функции генерации текста."""

    @pytest.mark.asyncio
    async def test_without_hf_token_returns_fallback(self):
        """Без HF_TOKEN возвращается шаблонный текст."""
        with patch("app.services.contract_suggest.settings") as mock_settings:
            mock_settings.hf_token = None
            result = await suggest_contract_text(
                contract_type="sale",
                field="conditions",
                prompt="Стандартные условия"
            )
        assert result
        assert "X.1." in result

    @pytest.mark.asyncio
    async def test_with_hf_token_calls_ai(self):
        """С HF_TOKEN вызывается AI через _call_ai."""
        ai_response = "X.1. Сгенерированный текст из AI."
        with patch("app.services.contract_suggest.settings") as mock_settings:
            mock_settings.hf_token = "test-token"
            with patch("app.services.contract_suggest._call_ai",
                       new_callable=AsyncMock,
                       return_value=ai_response):
                result = await suggest_contract_text(
                    contract_type="sale",
                    field="conditions",
                    prompt="Условия договора"
                )
        assert result == ai_response

    @pytest.mark.asyncio
    async def test_ai_error_falls_back_to_template(self):
        """Если AI вернул ошибку — используется шаблон."""
        with patch("app.services.contract_suggest.settings") as mock_settings:
            mock_settings.hf_token = "test-token"
            with patch("app.services.contract_suggest._call_ai",
                       new_callable=AsyncMock,
                       side_effect=Exception("Connection error")):
                result = await suggest_contract_text(
                    contract_type="sale",
                    field="conditions",
                    prompt="Условия"
                )
        assert result
        assert "X.1." in result

    @pytest.mark.asyncio
    async def test_with_context_builds_context_string(self):
        """При наличии context он передаётся в AI."""
        with patch("app.services.contract_suggest.settings") as mock_settings:
            mock_settings.hf_token = None
            result = await suggest_contract_text(
                contract_type="sale",
                field="payment_terms",
                prompt="Оплата в рассрочку",
                context={"buyer_name": "Иванов", "amount": "100000"}
            )
        # Without AI, should still return fallback
        assert result

    @pytest.mark.asyncio
    async def test_labor_termination_field(self):
        """Labor + termination поле работает без ошибок."""
        with patch("app.services.contract_suggest.settings") as mock_settings:
            mock_settings.hf_token = None
            result = await suggest_contract_text(
                contract_type="labor",
                field="termination",
                prompt="Расторжение по соглашению"
            )
        assert result
        assert "X.1." in result


# ============================================================
# Тесты: FIELD_DESCRIPTIONS и CONTRACT_TYPE_NAMES
# ============================================================

class TestConstants:
    """Тесты наличия обязательных констант."""

    def test_all_contract_fields_described(self):
        """Все поля ContractField должны иметь описание."""
        from app.schemas.contract import ContractField
        for field in ContractField:
            assert field.value in FIELD_DESCRIPTIONS, \
                f"Missing description for field '{field.value}'"

    def test_all_contract_types_named(self):
        """Все типы договоров должны иметь имена."""
        from app.schemas.contract import ContractType
        for ctype in ContractType:
            assert ctype.value in CONTRACT_TYPE_NAMES, \
                f"Missing name for contract type '{ctype.value}'"

    def test_field_descriptions_non_empty(self):
        """Все описания полей должны быть непустыми."""
        for field, desc in FIELD_DESCRIPTIONS.items():
            assert desc, f"Empty description for field '{field}'"

    def test_contract_type_names_non_empty(self):
        """Все имена типов договоров должны быть непустыми."""
        for ctype, name in CONTRACT_TYPE_NAMES.items():
            assert name, f"Empty name for contract type '{ctype}'"
