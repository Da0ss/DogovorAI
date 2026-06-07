"""
Тесты для Contracts API и Analysis API.
Проверка HTTP-эндпоинтов через TestClient.
"""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.document import AnalysisResult, FileProcessResult, FileType, RiskLevel


# ============================================================
# Тесты: Contracts API
# ============================================================

class TestContractsAPI:
    """HTTP-тесты эндпоинтов /api/contracts."""

    def test_create_contract_unknown_type(self, client):
        """Неизвестный тип договора возвращает 422."""
        response = client.post("/api/contracts/create", json={
            "type": "unknown_type",
            "data": {}
        })
        assert response.status_code == 422

    def test_create_contract_missing_data(self, client):
        """Пустые данные для sale-договора возвращают 422."""
        with patch("app.services.contract_generator.generate_docx",
                   side_effect=Exception("DOCX error")):
            response = client.post("/api/contracts/create", json={
                "type": "sale",
                "data": {}  # missing required fields
            })
        assert response.status_code == 422

    def test_create_contract_json_sale_success(self, client):
        """Успешная генерация sale-договора возвращает JSON с download_url."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            tmp_path = f.name
            f.write(b"fake docx content")
        try:
            with patch("app.services.contract_generator.generate_sale_contract",
                       return_value=tmp_path):
                response = client.post("/api/contracts/create-json", json={
                    "type": "sale",
                    "data": {
                        "seller_name": "Петров И.И.",
                        "buyer_name": "Иванов А.А.",
                        "amount": 100000.0,
                        "date": "01.01.2026"
                    }
                })
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is True
            assert "download_url" in body
        finally:
            os.unlink(tmp_path)

    def test_create_contract_json_labor_success(self, client):
        """Успешная генерация labor-договора возвращает JSON с download_url."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            tmp_path = f.name
            f.write(b"fake docx content")
        try:
            with patch("app.services.contract_generator.generate_labor_contract",
                       return_value=tmp_path):
                response = client.post("/api/contracts/create-json", json={
                    "type": "labor",
                    "data": {
                        "employer_name": "ТОО Тест",
                        "employee_name": "Иванов А.А.",
                        "salary": 300000.0,
                        "position": "Разработчик",
                        "start_date": "01.01.2026"
                    }
                })
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is True
        finally:
            os.unlink(tmp_path)

    def test_download_contract_not_found(self, client):
        """Несуществующий файл возвращает 404."""
        response = client.get("/api/contracts/download/nonexistent_file.docx")
        assert response.status_code == 404

    def test_download_contract_path_traversal_blocked(self, client):
        """Попытка path traversal блокируется (400)."""
        response = client.get("/api/contracts/download/../../../etc/passwd")
        assert response.status_code in (400, 404)

    def test_suggest_endpoint_returns_text(self, client):
        """POST /contracts/suggest возвращает сгенерированный текст."""
        with patch("app.services.contract_suggest.suggest_contract_text",
                   new_callable=AsyncMock,
                   return_value="X.1. Условия договора соответствуют ГК РК."):
            response = client.post("/api/contracts/suggest", json={
                "contract_type": "sale",
                "field": "conditions",
                "prompt": "Стандартные условия купли-продажи товара"
            })
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "suggested_text" in body

    def test_suggest_endpoint_invalid_field(self, client):
        """Неизвестное поле договора возвращает 422."""
        response = client.post("/api/contracts/suggest", json={
            "contract_type": "sale",
            "field": "invalid_field_xyz",
            "prompt": "Текст"
        })
        assert response.status_code == 422


# ============================================================
# Тесты: Analysis API
# ============================================================

class TestAnalysisAPI:
    """HTTP-тесты эндпоинтов /api/analyze."""

    def _make_analysis_result(self) -> AnalysisResult:
        from app.models.document import RiskItem, RiskLevel
        return AnalysisResult(
            document_type="Договор аренды",
            summary="Договор аренды помещения",
            risks=[
                RiskItem(
                    category="Оплата",
                    description="Срок оплаты не определён",
                    risk_level=RiskLevel.HIGH,
                    recommendation="Указать срок",
                )
            ],
            total_risks=1,
            high_risk_count=1,
            medium_risk_count=0,
            overall_risk_level=RiskLevel.HIGH,
            recommendations=["Уточните условия оплаты"],
            analysis_success=True,
        )

    def _make_file_result(self, text="Договор аренды. " * 30) -> FileProcessResult:
        return FileProcessResult(
            filename="test.txt",
            file_type=FileType.TXT,
            extracted_text=text,
            char_count=len(text),
            page_count=1,
            success=True,
        )

    def test_analyze_endpoint_success(self, client):
        """Успешный анализ TXT-файла возвращает структурированные риски."""
        file_content = b"Dogovor arendy. " * 30
        analysis = self._make_analysis_result()

        with patch("app.services.file_service.FileService.process_uploaded_file",
                   new_callable=AsyncMock,
                   return_value=self._make_file_result()):
            with patch("app.api.analysis.analyze_contract_text",
                       new_callable=AsyncMock,
                       return_value=analysis):
                with patch("app.api.analysis.LegalService.enrich_analysis",
                           return_value=analysis):
                    response = client.post(
                        "/api/analyze",
                        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
                    )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert "analysis" in body
        assert "file_info" in body

    def test_analyze_formats_endpoint(self, client):
        """GET /api/analyze/formats возвращает список форматов."""
        response = client.get("/api/analyze/formats")
        assert response.status_code == 200
        body = response.json()
        assert "supported_formats" in body
        formats = [f["extension"] for f in body["supported_formats"]]
        assert "pdf" in formats
        assert "docx" in formats
        assert "txt" in formats

    def test_analyze_file_processing_error(self, client):
        """Ошибка обработки файла возвращает 400."""
        file_content = b"fake docx content PK"
        failed_result = FileProcessResult(
            filename="bad.txt",
            file_type=FileType.UNKNOWN,
            extracted_text="",
            success=False,
            error_message="Unsupported file format",
        )
        with patch("app.services.file_service.FileService.process_uploaded_file",
                   new_callable=AsyncMock,
                   return_value=failed_result):
            response = client.post(
                "/api/analyze",
                files={"file": ("bad.txt", io.BytesIO(file_content), "text/plain")},
            )
        assert response.status_code == 400

    def test_analyze_ai_service_unavailable(self, client):
        """Если AI недоступен — возвращается 503."""
        from app.services.ai_service import AI_UNAVAILABLE_PREFIX
        ai_fail = AnalysisResult(
            analysis_success=False,
            error_message=f"{AI_UNAVAILABLE_PREFIX}: AI is down",
        )
        with patch("app.services.file_service.FileService.process_uploaded_file",
                   new_callable=AsyncMock,
                   return_value=self._make_file_result()):
            with patch("app.api.analysis.analyze_contract_text",
                       new_callable=AsyncMock,
                       return_value=ai_fail):
                response = client.post(
                    "/api/analyze",
                    files={"file": ("test.txt", io.BytesIO(b"contract " * 20), "text/plain")},
                )
        assert response.status_code == 503

    def test_usage_me_anonymous(self, client):
        """GET /api/usage/me без токена возвращает базовую информацию."""
        response = client.get("/api/usage/me")
        assert response.status_code == 200
        body = response.json()
        assert "used" in body
        assert "limit" in body
        assert "plan" in body
        assert body["success"] is True

    def test_usage_me_with_token(self, client):
        """GET /api/usage/me с токеном вызывает usage_limiter.get_usage."""
        with patch("app.services.usage_limiter.usage_limiter.get_usage",
                   return_value={"used": 1, "limit": 3, "plan": "basic",
                                 "plan_name": "Basic", "reset_at": None}) as mock:
            response = client.get(
                "/api/usage/me",
                headers={"Authorization": "Bearer some-token"}
            )
        assert response.status_code == 200
        mock.assert_called_once()

    def test_analyze_with_usage_limit_exceeded(self, client):
        """При превышении лимита возвращается 402."""
        from app.services.usage_limiter import UsageLimitError
        with patch("app.services.usage_limiter.usage_limiter.check_limit",
                   side_effect=UsageLimitError(used=3, limit=3, plan="basic")):
            response = client.post(
                "/api/analyze",
                files={"file": ("test.txt", io.BytesIO(b"data"), "text/plain")},
                headers={"Authorization": "Bearer some-token"}
            )
        assert response.status_code == 402
        body = response.json()
        assert body["detail"]["error"] == "limit_exceeded"
