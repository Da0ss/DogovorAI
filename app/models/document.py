"""
Document Models — Pydantic схемы для работы с документами и результатами анализа.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class FileType(str, Enum):
    """Поддерживаемые типы файлов."""
    PDF = "pdf"
    DOCX = "docx"
    IMAGE = "image"
    TXT = "txt"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """Уровень риска для найденного пункта договора."""
    HIGH = "high"        # Критический риск
    MEDIUM = "medium"    # Умеренный риск
    LOW = "low"          # Незначительный риск


class FileProcessResult(BaseModel):
    """
    Результат обработки загруженного файла.

    Attributes:
        filename: Имя исходного файла
        file_type: Тип файла (pdf, docx, image)
        extracted_text: Извлечённый текст из документа
        page_count: Количество страниц (для PDF)
        char_count: Количество символов в тексте
        success: Успешность обработки
        error_message: Сообщение об ошибке (если есть)
    """
    filename: str
    file_type: FileType
    extracted_text: str = ""
    page_count: int = 0
    char_count: int = 0
    success: bool = True
    error_message: Optional[str] = None


class RiskItem(BaseModel):
    """
    Один найденный риск в договоре.

    Attributes:
        category: Категория риска (оплата, расторжение, ответственность и т.д.)
        description: Описание риска на русском языке
        risk_level: Уровень опасности риска
        original_clause: Оригинальный текст пункта из договора
        recommendation: Рекомендация по устранению риска
        law_reference: Ссылка на статью закона (заполняется LegalService)
        law_description: Краткое описание нормы права
    """
    category: str = Field(..., description="Категория риска")
    description: str = Field(..., description="Описание риска")
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM)
    original_clause: Optional[str] = Field(None, description="Исходный текст пункта")
    recommendation: Optional[str] = Field(None, description="Рекомендация")
    law_reference: Optional[str] = Field(None, description="Ссылка на закон (напр. ГК РК ст. 401)")
    law_description: Optional[str] = Field(None, description="Описание нормы права")


class AnalysisResult(BaseModel):
    """
    Полный результат анализа договора.

    Attributes:
        document_type: Тип договора (подряда, аренды, трудовой и т.д.)
        summary: Краткое резюме договора
        risks: Список найденных рисков
        total_risks: Общее количество рисков
        high_risk_count: Количество критических рисков
        overall_risk_level: Общий уровень риска
        recommendations: Общие рекомендации
        analysis_success: Успешность анализа
        error_message: Сообщение об ошибке (если есть)
    """
    document_type: str = "Неопределён"
    summary: str = ""
    risks: list[RiskItem] = []
    total_risks: int = 0
    high_risk_count: int = 0
    overall_risk_level: RiskLevel = RiskLevel.LOW
    recommendations: list[str] = []
    analysis_success: bool = True
    error_message: Optional[str] = None


class AnalyzeResponse(BaseModel):
    """
    Ответ API на запрос анализа документа.

    Attributes:
        status: Статус выполнения запроса
        file_info: Информация об обработанном файле
        analysis: Результаты анализа договора
    """
    status: str = "success"
    file_info: FileProcessResult
    analysis: AnalysisResult
