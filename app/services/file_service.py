"""
File Service — Сервис для извлечения текста из документов различных форматов.
Поддерживает: PDF, DOCX, изображения (JPG/PNG) через OCR.
"""

import io
import os
import logging
from typing import Optional

from fastapi import UploadFile

from app.models.document import FileProcessResult, FileType

logger = logging.getLogger(__name__)

# Пути к Tesseract OCR на разных системах (в порядке приоритета)
_TESSERACT_PATHS = [
    "/opt/homebrew/bin/tesseract",   # macOS Apple Silicon (M1/M2/M3)
    "/usr/local/bin/tesseract",      # macOS Intel
    "/usr/bin/tesseract",            # Linux
    "tesseract",                     # Системный PATH (fallback)
]


def _configure_tesseract() -> str:
    """
    Автоматически находит tesseract в системе и настраивает pytesseract.

    Returns:
        str: Путь к найденному tesseract или 'tesseract' если не найден
    """
    try:
        import pytesseract
        for path in _TESSERACT_PATHS:
            if path == "tesseract" or os.path.isfile(path):
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info(f"✅ Tesseract найден: {path}")
                return path
    except ImportError:
        pass
    logger.warning("⚠️ pytesseract не установлен")
    return "tesseract"


# Настраиваем Tesseract при загрузке модуля
_TESSERACT_CMD = _configure_tesseract()

# Максимальный размер файла: 20 МБ
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

# Поддерживаемые MIME-типы
SUPPORTED_MIME_TYPES = {
    "application/pdf": FileType.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
    "application/msword": FileType.DOCX,
    "image/jpeg": FileType.IMAGE,
    "image/jpg": FileType.IMAGE,
    "image/png": FileType.IMAGE,
    "image/tiff": FileType.IMAGE,
}


class FileService:
    """
    Сервис для обработки загруженных файлов.
    Извлекает текст из PDF, DOCX и изображений (через OCR).
    """

    @staticmethod
    def extract_text_from_pdf(file_bytes: bytes) -> tuple[str, int]:
        """
        Извлекает текст из PDF-файла.

        Args:
            file_bytes: Байты PDF-файла

        Returns:
            tuple: (извлечённый текст, количество страниц)

        Raises:
            ValueError: Если файл повреждён или не является PDF
        """
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text_parts = []
            page_count = len(doc)

            for page_num in range(page_count):
                page = doc[page_num]
                page_text = page.get_text("text")
                if page_text.strip():
                    text_parts.append(f"[Страница {page_num + 1}]\n{page_text}")

            doc.close()

            full_text = "\n\n".join(text_parts)
            logger.info(f"✅ PDF обработан: {page_count} стр., {len(full_text)} символов")
            return full_text, page_count

        except ImportError:
            logger.error("❌ PyMuPDF не установлен. Выполните: pip install PyMuPDF")
            raise ValueError("Не удалось обработать PDF")
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке PDF: {str(e)}")
            raise ValueError(f"Не удалось обработать PDF: {str(e)}")

    @staticmethod
    def extract_text_from_docx(file_bytes: bytes) -> tuple[str, int]:
        """
        Извлекает текст из DOCX-файла.

        Args:
            file_bytes: Байты DOCX-файла

        Returns:
            tuple: (извлечённый текст, количество параграфов)

        Raises:
            ValueError: Если файл повреждён или не является DOCX
        """
        try:
            from docx import Document

            doc = Document(io.BytesIO(file_bytes))
            paragraphs = []

            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)

            # Также извлекаем текст из таблиц
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(
                        cell.text.strip() for cell in row.cells if cell.text.strip()
                    )
                    if row_text:
                        paragraphs.append(row_text)

            full_text = "\n".join(paragraphs)
            para_count = len(paragraphs)
            logger.info(f"✅ DOCX обработан: {para_count} параграфов, {len(full_text)} символов")
            return full_text, para_count

        except ImportError:
            logger.error("❌ python-docx не установлен. Выполните: pip install python-docx")
            raise ValueError("Не удалось обработать DOCX")
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке DOCX: {str(e)}")
            raise ValueError(f"Не удалось обработать DOCX: {str(e)}")

    @staticmethod
    def extract_text_from_image_ocr(file_bytes: bytes) -> tuple[str, int]:
        """
        Извлекает текст из изображения с помощью Tesseract OCR.

        Args:
            file_bytes: Байты изображения (JPG/PNG/TIFF)

        Returns:
            tuple: (извлечённый через OCR текст, 1)

        Raises:
            ValueError: Если Tesseract не установлен или произошла ошибка OCR
        """
        try:
            from PIL import Image
            import pytesseract

            # Убеждаемся что путь к tesseract настроен
            _configure_tesseract()

            image = Image.open(io.BytesIO(file_bytes))

            # Применяем OCR с поддержкой русского и английского языков
            ocr_config = "--oem 3 --psm 3"

            # Пробуем сначала русский + английский, потом только английский
            available_langs = pytesseract.get_languages(config="")
            if "rus" in available_langs:
                lang = "rus+eng"
            else:
                lang = "eng"
                logger.warning(
                    "⚠️ Русский язык OCR не установлен. "
                    "Для полной поддержки: brew install tesseract-lang"
                )

            extracted_text = pytesseract.image_to_string(
                image,
                lang=lang,
                config=ocr_config
            )

            cleaned_text = extracted_text.strip()
            logger.info(f"✅ OCR завершён (lang={lang}): {len(cleaned_text)} символов извлечено")
            return cleaned_text, 1

        except ImportError as e:
            logger.error(f"❌ Зависимость для OCR не установлена: {str(e)}")
            raise ValueError(
                "Для OCR нужны: pytesseract, Pillow и Tesseract. "
                "Установите: brew install tesseract tesseract-lang && pip install pytesseract Pillow"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка OCR: {str(e)}")
            raise ValueError(f"Ошибка при распознавании текста: {str(e)}")


    @classmethod
    async def process_uploaded_file(cls, file: UploadFile) -> FileProcessResult:
        """
        Основной метод: принимает загруженный файл, определяет тип и извлекает текст.

        Args:
            file: FastAPI UploadFile объект

        Returns:
            FileProcessResult: Результат обработки с извлечённым текстом
        """
        filename = file.filename or "unknown"
        content_type = file.content_type or ""

        logger.info(f"📄 Обработка файла: {filename} (тип: {content_type})")

        # Определяем тип файла
        file_type = SUPPORTED_MIME_TYPES.get(content_type.lower())

        # Если MIME-тип не определён — пробуем по расширению
        if file_type is None:
            ext = filename.lower().split(".")[-1] if "." in filename else ""
            ext_map = {
                "pdf": FileType.PDF,
                "docx": FileType.DOCX,
                "doc": FileType.DOCX,
                "jpg": FileType.IMAGE,
                "jpeg": FileType.IMAGE,
                "png": FileType.IMAGE,
            }
            file_type = ext_map.get(ext, FileType.UNKNOWN)

        if file_type == FileType.UNKNOWN:
            return FileProcessResult(
                filename=filename,
                file_type=FileType.UNKNOWN,
                success=False,
                error_message=(
                    f"Неподдерживаемый формат файла: {content_type}. "
                    "Поддерживаются: PDF, DOCX, JPG, PNG"
                )
            )

        # Читаем файл
        file_bytes = await file.read()

        # Проверка размера
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            return FileProcessResult(
                filename=filename,
                file_type=file_type,
                success=False,
                error_message=f"Файл слишком большой: {len(file_bytes) // 1024 // 1024} МБ. Максимум: 20 МБ"
            )

        try:
            # Извлекаем текст в зависимости от типа
            if file_type == FileType.PDF:
                extracted_text, page_count = cls.extract_text_from_pdf(file_bytes)
            elif file_type == FileType.DOCX:
                extracted_text, page_count = cls.extract_text_from_docx(file_bytes)
            elif file_type == FileType.IMAGE:
                extracted_text, page_count = cls.extract_text_from_image_ocr(file_bytes)
            else:
                raise ValueError("Неизвестный тип файла")

            if not extracted_text.strip():
                return FileProcessResult(
                    filename=filename,
                    file_type=file_type,
                    success=False,
                    error_message="Текст не найден в документе. Возможно, файл пустой или защищён."
                )

            return FileProcessResult(
                filename=filename,
                file_type=file_type,
                extracted_text=extracted_text,
                page_count=page_count,
                char_count=len(extracted_text),
                success=True
            )

        except ValueError as e:
            return FileProcessResult(
                filename=filename,
                file_type=file_type,
                success=False,
                error_message=str(e)
            )
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при обработке {filename}: {str(e)}")
            return FileProcessResult(
                filename=filename,
                file_type=file_type,
                success=False,
                error_message=f"Внутренняя ошибка при обработке файла: {str(e)}"
            )


# Singleton-like экземпляр сервиса
file_service = FileService()
