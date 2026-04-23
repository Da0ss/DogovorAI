"""
Pydantic schemas for contract generation requests.
Validates input data for sale and labor contracts.
Includes AI suggestion request/response schemas.
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class ContractType(str, Enum):
    """Supported contract types."""
    SALE = "sale"
    LABOR = "labor"


class SaleContractRequest(BaseModel):
    """
    Schema for sale contract generation.

    Fields:
        seller_name: Full name of the seller
        buyer_name: Full name of the buyer
        amount: Contract amount (must be > 0)
        date: Contract date (e.g. "01.01.2026")
    """
    seller_name: str = Field(..., min_length=1, description="ФИО продавца")
    buyer_name: str = Field(..., min_length=1, description="ФИО покупателя")
    amount: float = Field(..., gt=0, description="Сумма договора (> 0)")
    date: str = Field(..., min_length=1, description="Дата договора")


class LaborContractRequest(BaseModel):
    """
    Schema for labor contract generation.

    Fields:
        employer_name: Full name or company name of the employer
        employee_name: Full name of the employee
        salary: Monthly salary (must be > 0)
        position: Job position/title
        start_date: Employment start date (e.g. "01.01.2026")
    """
    employer_name: str = Field(..., min_length=1, description="Наименование работодателя")
    employee_name: str = Field(..., min_length=1, description="ФИО работника")
    salary: float = Field(..., gt=0, description="Заработная плата (> 0)")
    position: str = Field(..., min_length=1, description="Должность")
    start_date: str = Field(..., min_length=1, description="Дата начала работы")


class ContractCreateRequest(BaseModel):
    """
    Unified contract creation request.

    Fields:
        type: Contract type ("sale" or "labor")
        data: Contract-specific data (SaleContractRequest or LaborContractRequest)
    """
    type: ContractType = Field(..., description="Тип договора: 'sale' или 'labor'")
    data: dict = Field(..., description="Данные для заполнения шаблона")


class ContractCreateResponse(BaseModel):
    """Response after successful contract generation (returns filename for download)."""
    success: bool
    message: str
    filename: Optional[str] = None
    download_url: Optional[str] = None


class ContractResponse(BaseModel):
    """Response schema for contract generation (used for error/info responses)."""
    success: bool
    message: str
    filename: Optional[str] = None


# --- AI Suggestion schemas ---

class ContractField(str, Enum):
    """Contract fields that can be enhanced by AI."""
    CONDITIONS = "conditions"
    PENALTIES = "penalties"
    DEADLINES = "deadlines"
    LIABILITY = "liability"
    TERMINATION = "termination"
    PAYMENT_TERMS = "payment_terms"
    CUSTOM = "custom"


class SuggestRequest(BaseModel):
    """
    Request to generate AI suggestion for a contract clause.

    Fields:
        contract_type: Type of contract (sale or labor)
        field: Which contract field to suggest text for
        prompt: User's description of what they need
        context: Optional existing contract data for better suggestions
    """
    contract_type: ContractType = Field(..., description="Тип договора")
    field: ContractField = Field(..., description="Поле договора для генерации")
    prompt: str = Field(..., min_length=3, max_length=2000, description="Описание желаемого текста")
    context: Optional[dict] = Field(None, description="Контекст договора для более точных предложений")


class SuggestResponse(BaseModel):
    """AI suggestion response."""
    success: bool
    field: str
    suggested_text: str
    message: str = ""
