"""
Тесты для FileService — проверка извлечения текста из различных форматов.
"""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import UploadFile

from app.services.file_service import FileService
from app.models.document import FileType


# ============================================================
# Вспомогательные функции для создания мок-файлов
# ============================================================

def make_upload_file(filename: str, content: bytes, content_type: str) -> UploadFile:
    """Создаёт мок UploadFile для тестирования."""
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.read = AsyncMock(return_value=content)
    return mock_file


# ============================================================
# Тесты: определение типов файлов
# ============================================================

class TestFileTypeDetection:
    """Тесты определения типа файла по MIME-типу и расширению."""

    @pytest.mark.asyncio
    async def test_pdf_by_mime_type(self):
        """Файл с MIME application/pdf должен определяться как PDF."""
        file = make_upload_file("contract.pdf", b"fake", "application/pdf")
        with patch.object(FileService, "extract_text_from_pdf", return_value=("текст договора", 2)):
            result = await FileService.process_uploaded_file(file)
        assert result.file_type == FileType.PDF

    @pytest.mark.asyncio
    async def test_docx_by_mime_type(self):
        """Файл с MIME .docx должен определяться как DOCX."""
        file = make_upload_file(
            "contract.docx",
            b"fake",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        with patch.object(FileService, "extract_text_from_docx", return_value=("текст договора", 5)):
            result = await FileService.process_uploaded_file(file)
        assert result.file_type == FileType.DOCX

    @pytest.mark.asyncio
    async def test_image_jpg_by_mime_type(self):
        """Файл с MIME image/jpeg должен определяться как IMAGE."""
        file = make_upload_file("scan.jpg", b"fake", "image/jpeg")
        with patch.object(FileService, "extract_text_from_image_ocr", return_value=("текст из OCR", 1)):
            result = await FileService.process_uploaded_file(file)
        assert result.file_type == FileType.IMAGE

    @pytest.mark.asyncio
    async def test_unknown_format_returns_error(self):
        """Неподдерживаемый формат должен вернуть ошибку."""
        file = make_upload_file("archive.zip", b"fake", "application/zip")
        result = await FileService.process_uploaded_file(file)
        assert result.success is False
        assert result.file_type == FileType.UNKNOWN
        assert "Неподдерживаемый формат" in result.error_message

    @pytest.mark.asyncio
    async def test_pdf_by_extension_fallback(self):
        """Если MIME не определён — используем расширение файла."""
        file = make_upload_file("contract.pdf", b"fake", "application/octet-stream")
        with patch.object(FileService, "extract_text_from_pdf", return_value=("текст договора", 1)):
            result = await FileService.process_uploaded_file(file)
        assert result.file_type == FileType.PDF


# ============================================================
# Тесты: ограничение размера файла
# ============================================================

class TestFileSizeValidation:
    """Тесты валидации размера файла."""

    @pytest.mark.asyncio
    async def test_file_too_large_returns_error(self):
        """Файл больше 20 МБ должен вернуть ошибку."""
        large_content = b"x" * (21 * 1024 * 1024)  # 21 МБ
        file = make_upload_file("large.pdf", large_content, "application/pdf")
        result = await FileService.process_uploaded_file(file)
        assert result.success is False
        assert "слишком большой" in result.error_message

    @pytest.mark.asyncio
    async def test_normal_size_file_passes(self):
        """Файл нормального размера должен обрабатываться без ошибок."""
        normal_content = b"x" * (5 * 1024 * 1024)  # 5 МБ
        file = make_upload_file("normal.pdf", normal_content, "application/pdf")
        with patch.object(FileService, "extract_text_from_pdf", return_value=("текст договора", 3)):
            result = await FileService.process_uploaded_file(file)
        assert result.success is True


# ============================================================
# Тесты: результат обработки
# ============================================================

class TestFileProcessResult:
    """Тесты корректности результата обработки."""

    @pytest.mark.asyncio
    async def test_pdf_result_has_correct_fields(self):
        """Результат обработки PDF должен содержать корректные поля."""
        file = make_upload_file("doc.pdf", b"fake_pdf_bytes", "application/pdf")
        expected_text = "Договор подряда\nСтороны договорились..."
        expected_pages = 3

        with patch.object(FileService, "extract_text_from_pdf", return_value=(expected_text, expected_pages)):
            result = await FileService.process_uploaded_file(file)

        assert result.success is True
        assert result.filename == "doc.pdf"
        assert result.file_type == FileType.PDF
        assert result.extracted_text == expected_text
        assert result.page_count == expected_pages
        assert result.char_count == len(expected_text)
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_empty_text_returns_error(self):
        """Пустой текст после извлечения должен вернуть ошибку."""
        file = make_upload_file("empty.pdf", b"fake", "application/pdf")
        with patch.object(FileService, "extract_text_from_pdf", return_value=("   ", 0)):
            result = await FileService.process_uploaded_file(file)
        assert result.success is False
        assert "Текст не найден" in result.error_message

    @pytest.mark.asyncio
    async def test_extraction_error_returns_failure(self):
        """Если извлечение вызывает ValueError — возвращаем ошибку, не исключение."""
        file = make_upload_file("broken.pdf", b"not_a_pdf", "application/pdf")
        with patch.object(FileService, "extract_text_from_pdf", side_effect=ValueError("Файл повреждён")):
            result = await FileService.process_uploaded_file(file)
        assert result.success is False
        assert "Файл повреждён" in result.error_message


# ============================================================
# Тесты: статические методы извлечения текста
# ============================================================

class TestTextExtraction:
    """Тесты статических методов извлечения текста."""

    def test_extract_pdf_raises_on_invalid_bytes(self):
        """Некорректные байты должны вызывать ValueError."""
        with pytest.raises(ValueError, match="Не удалось обработать PDF"):
            FileService.extract_text_from_pdf(b"not_a_valid_pdf_content_12345")

    def test_extract_docx_raises_on_invalid_bytes(self):
        """Некорректные байты должны вызывать ValueError."""
        with pytest.raises(ValueError, match="Не удалось обработать DOCX"):
            FileService.extract_text_from_docx(b"not_a_valid_docx_content_12345")


class TestPdfExtractionFallback:
    """Тестирование fallback-режима извлечения PDF (PyMuPDF -> pypdf)."""

    @patch("pypdf.PdfReader")
    def test_extract_pdf_using_pypdf_fallback_success(self, mock_pdf_reader):
        """Проверяет успешное извлечение текста с помощью pypdf, если PyMuPDF (fitz) недоступен."""
        # Настройка мока pypdf
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Текст из pypdf"
        mock_pdf_reader.return_value.pages = [mock_page]

        # Симулируем отсутствие fitz (PyMuPDF)
        with patch.dict("sys.modules", {"fitz": None}):
            text, page_count = FileService.extract_text_from_pdf(b"dummy_pdf_bytes")

        assert page_count == 1
        assert "Текст из pypdf" in text
        mock_pdf_reader.assert_called_once()

