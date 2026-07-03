"""
Тесты для Pydantic схем договоров.
Проверка валидации входных данных.
"""

import pytest
from pydantic import ValidationError

from app.schemas.contract import (
    SaleContractRequest,
    LaborContractRequest,
    ContractCreateRequest,
    ContractType,
    ContractField,
    SuggestRequest,
    SuggestResponse,
    ContractCreateResponse,
)


# ============================================================
# Тесты: SaleContractRequest
# ============================================================

class TestSaleContractRequest:
    """Тесты валидации запроса на создание договора купли-продажи."""

    def test_valid_sale_request(self):
        req = SaleContractRequest(
            seller_name="Петров И.И.",
            buyer_name="Иванов А.А.",
            amount=150000.0,
            date="01.01.2026"
        )
        assert req.seller_name == "Петров И.И."
        assert req.amount == 150000.0

    def test_negative_amount_raises(self):
        """Отрицательная сумма не должна проходить валидацию."""
        with pytest.raises(ValidationError):
            SaleContractRequest(
                seller_name="А",
                buyer_name="Б",
                amount=-100.0,
                date="01.01.2026"
            )

    def test_zero_amount_raises(self):
        """Нулевая сумма не должна проходить валидацию (gt=0)."""
        with pytest.raises(ValidationError):
            SaleContractRequest(
                seller_name="А",
                buyer_name="Б",
                amount=0.0,
                date="01.01.2026"
            )

    def test_empty_seller_name_raises(self):
        """Пустое имя продавца не проходит валидацию."""
        with pytest.raises(ValidationError):
            SaleContractRequest(
                seller_name="",
                buyer_name="Б",
                amount=100.0,
                date="01.01.2026"
            )

    def test_missing_required_fields_raises(self):
        """Отсутствующие обязательные поля вызывают ошибку."""
        with pytest.raises(ValidationError):
            SaleContractRequest(seller_name="А")

    def test_integer_amount_accepted(self):
        """Целочисленная сумма принимается как float."""
        req = SaleContractRequest(
            seller_name="А",
            buyer_name="Б",
            amount=50000,
            date="01.01.2026"
        )
        assert req.amount == 50000.0


# ============================================================
# Тесты: LaborContractRequest
# ============================================================

class TestLaborContractRequest:
    """Тесты валидации запроса на создание трудового договора."""

    def test_valid_labor_request(self):
        req = LaborContractRequest(
            employer_name="ТОО Тест",
            employee_name="Сидоров С.С.",
            salary=300000.0,
            position="Разработчик",
            start_date="01.02.2026"
        )
        assert req.position == "Разработчик"

    def test_negative_salary_raises(self):
        with pytest.raises(ValidationError):
            LaborContractRequest(
                employer_name="ТОО",
                employee_name="Работник",
                salary=-1.0,
                position="Менеджер",
                start_date="01.01.2026"
            )

    def test_empty_position_raises(self):
        with pytest.raises(ValidationError):
            LaborContractRequest(
                employer_name="ТОО",
                employee_name="Работник",
                salary=100000.0,
                position="",
                start_date="01.01.2026"
            )

    def test_missing_start_date_raises(self):
        with pytest.raises(ValidationError):
            LaborContractRequest(
                employer_name="ТОО",
                employee_name="Работник",
                salary=100000.0,
                position="Менеджер",
            )


# ============================================================
# Тесты: ContractCreateRequest
# ============================================================

class TestContractCreateRequest:
    """Тесты обёртки запроса на создание договора."""

    def test_valid_sale_request(self):
        req = ContractCreateRequest(
            type=ContractType.SALE,
            data={"seller_name": "А", "buyer_name": "Б", "amount": 100.0, "date": "01.01.2026"}
        )
        assert req.type == ContractType.SALE
        assert isinstance(req.data, dict)

    def test_valid_labor_request(self):
        req = ContractCreateRequest(
            type=ContractType.LABOR,
            data={"employer_name": "ТОО", "employee_name": "Работник",
                  "salary": 100000.0, "position": "Dev", "start_date": "01.01.2026"}
        )
        assert req.type == ContractType.LABOR

    def test_invalid_type_raises(self):
        """Неизвестный тип договора вызывает ValidationError."""
        with pytest.raises(ValidationError):
            ContractCreateRequest(type="unknown", data={})


# ============================================================
# Тесты: ContractType enum
# ============================================================

class TestContractTypeEnum:
    """Тесты значений перечисления ContractType."""

    def test_sale_value(self):
        assert ContractType.SALE.value == "sale"

    def test_labor_value(self):
        assert ContractType.LABOR.value == "labor"

    def test_from_string(self):
        assert ContractType("sale") == ContractType.SALE
        assert ContractType("labor") == ContractType.LABOR

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            ContractType("invalid")


# ============================================================
# Тесты: ContractField enum
# ============================================================

class TestContractFieldEnum:
    """Тесты значений перечисления ContractField."""

    def test_all_fields_exist(self):
        expected = {"conditions", "penalties", "deadlines", "liability", "termination", "payment_terms", "custom"}
        actual = {f.value for f in ContractField}
        assert expected == actual

    def test_field_from_string(self):
        assert ContractField("conditions") == ContractField.CONDITIONS
        assert ContractField("custom") == ContractField.CUSTOM


# ============================================================
# Тесты: SuggestRequest
# ============================================================

class TestSuggestRequest:
    """Тесты валидации запроса AI-подсказки."""

    def test_valid_suggest_request(self):
        req = SuggestRequest(
            contract_type=ContractType.SALE,
            field=ContractField.CONDITIONS,
            prompt="Стандартные условия договора купли-продажи"
        )
        assert req.prompt == "Стандартные условия договора купли-продажи"

    def test_short_prompt_raises(self):
        """Prompt менее 3 символов не проходит валидацию."""
        with pytest.raises(ValidationError):
            SuggestRequest(
                contract_type=ContractType.SALE,
                field=ContractField.CONDITIONS,
                prompt="ab"
            )

    def test_long_prompt_raises(self):
        """Prompt более 2000 символов не проходит валидацию."""
        with pytest.raises(ValidationError):
            SuggestRequest(
                contract_type=ContractType.SALE,
                field=ContractField.CONDITIONS,
                prompt="а" * 2001
            )

    def test_with_context(self):
        """Контекст (опциональный) принимается корректно."""
        req = SuggestRequest(
            contract_type=ContractType.LABOR,
            field=ContractField.PAYMENT_TERMS,
            prompt="Условия оплаты труда",
            context={"employee_name": "Иванов", "salary": "300000"}
        )
        assert req.context == {"employee_name": "Иванов", "salary": "300000"}

    def test_without_context(self):
        """Без контекста поле равно None."""
        req = SuggestRequest(
            contract_type=ContractType.SALE,
            field=ContractField.PENALTIES,
            prompt="Штрафные санкции"
        )
        assert req.context is None


# ============================================================
# Тесты: SuggestResponse и ContractCreateResponse
# ============================================================

class TestResponseSchemas:
    """Тесты схем ответов."""

    def test_suggest_response(self):
        resp = SuggestResponse(
            success=True,
            field="conditions",
            suggested_text="X.1. Текст условий.",
            message="Готово"
        )
        assert resp.success is True
        assert resp.field == "conditions"

    def test_contract_create_response(self):
        resp = ContractCreateResponse(
            success=True,
            message="Договор сгенерирован",
            filename="abc123.docx",
            download_url="/api/contracts/download/abc123.docx"
        )
        assert resp.success is True
        assert "abc123" in resp.download_url

    def test_contract_create_response_optional_fields(self):
        """filename и download_url — опциональные."""
        resp = ContractCreateResponse(success=False, message="Ошибка")
        assert resp.filename is None
        assert resp.download_url is None
