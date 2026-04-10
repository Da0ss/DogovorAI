"""
Legal Service — Сервис для сопоставления юридических рисков с нормами права РК.
Обогащает результаты AI-анализа ссылками на конкретные статьи законов.
"""

import logging
from app.models.document import AnalysisResult, RiskItem
from app.data.legal_knowledge_base import find_law_for_risk

logger = logging.getLogger(__name__)


class LegalService:
    """
    Сервис обогащения рисков ссылками на законодательство РК.
    Принимает результат AI-анализа и добавляет к каждому риску law_reference и law_description.
    """

    @staticmethod
    def match_risks_to_laws(risks: list[RiskItem]) -> list[RiskItem]:
        """
        Сопоставляет найденные риски с нормами права из базы знаний.

        Args:
            risks: Список рисков от AI-анализа

        Returns:
            list[RiskItem]: Те же риски, дополненные полями law_reference и law_description
        """
        matched_count = 0

        for risk in risks:
            if risk.law_reference:
                # Уже заполнено (например, AI сам указал)
                continue

            law_ref, law_desc = find_law_for_risk(risk.category, risk.description)

            if law_ref:
                risk.law_reference = law_ref
                risk.law_description = law_desc
                matched_count += 1

        logger.info(
            f"⚖️ База знаний: сопоставлено {matched_count}/{len(risks)} рисков с нормами права"
        )
        return risks

    @staticmethod
    def enrich_analysis(analysis: AnalysisResult) -> AnalysisResult:
        """
        Обогащает весь результат анализа ссылками на законы.

        Args:
            analysis: Результат AI-анализа договора

        Returns:
            AnalysisResult: Тот же объект с дополненными rисками
        """
        if not analysis.analysis_success or not analysis.risks:
            return analysis

        analysis.risks = LegalService.match_risks_to_laws(analysis.risks)
        return analysis


# Singleton-like экземпляр
legal_service = LegalService()
