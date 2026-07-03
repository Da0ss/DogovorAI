"""
Тесты для Legal Service и Legal Knowledge Base.
Проверка сопоставления рисков с нормами права РК.
"""

import pytest
from app.data.legal_knowledge_base import find_law_for_risk, LEGAL_KNOWLEDGE, ALL_KEYWORDS
from app.models.document import AnalysisResult, RiskItem, RiskLevel
from app.services.legal_service import LegalService


# ============================================================
# Тесты: find_law_for_risk
# ============================================================

class TestFindLawForRisk:
    """Тесты поиска норм права по категории и описанию риска."""

    def test_finds_oplatа_law(self):
        """Поиск по категории 'Оплата' должен вернуть ссылку на закон."""
        ref, desc = find_law_for_risk("Оплата", "Срок оплаты не определён")
        assert ref is not None
        assert "ГК РК" in ref
        assert desc is not None

    def test_finds_rastorzhenie_law(self):
        """Поиск по категории 'Расторжение' должен вернуть ссылку на закон."""
        ref, desc = find_law_for_risk("Расторжение", "Одностороннее расторжение без уведомления")
        assert ref is not None
        assert desc is not None

    def test_finds_otvetstvennost_law(self):
        """Поиск по слову 'ответственность' должен вернуть норму."""
        ref, desc = find_law_for_risk("Ответственность", "Размытая ответственность сторон")
        assert ref is not None

    def test_no_match_returns_none_none(self):
        """Неизвестная категория должна вернуть (None, None)."""
        ref, desc = find_law_for_risk("НесуществующаяКатегория", "Некое описание без ключевых слов xyz")
        assert ref is None
        assert desc is None

    def test_case_insensitive_search(self):
        """Поиск должен быть регистронезависимым."""
        ref1, _ = find_law_for_risk("ОПЛАТА", "СРОК НЕ ОПРЕДЕЛЁН")
        ref2, _ = find_law_for_risk("оплата", "срок не определён")
        assert ref1 == ref2

    def test_description_contains_keyword(self):
        """Ключевое слово из базы в описании тоже должно находиться."""
        # "неустойка" — keyword in LEGAL_KNOWLEDGE
        ref, desc = find_law_for_risk("Прочее", "Неустойка является завышенной")
        assert ref is not None
        assert "293" in ref or "297" in ref

    def test_all_keywords_exist_in_knowledge(self):
        """ALL_KEYWORDS должен совпадать с ключами LEGAL_KNOWLEDGE."""
        assert set(ALL_KEYWORDS) == set(LEGAL_KNOWLEDGE.keys())

    def test_knowledge_base_structure(self):
        """Каждая запись базы знаний должна иметь law_reference и law_description."""
        for keyword, info in LEGAL_KNOWLEDGE.items():
            assert "law_reference" in info, f"Missing law_reference for '{keyword}'"
            assert "law_description" in info, f"Missing law_description for '{keyword}'"
            assert info["law_reference"], f"Empty law_reference for '{keyword}'"
            assert info["law_description"], f"Empty law_description for '{keyword}'"


# ============================================================
# Тесты: LegalService.match_risks_to_laws
# ============================================================

class TestMatchRisksToLaws:
    """Тесты сопоставления списка рисков с нормами права."""

    def _make_risk(self, category: str, description: str,
                   law_ref: str = None) -> RiskItem:
        return RiskItem(
            category=category,
            description=description,
            risk_level=RiskLevel.MEDIUM,
            law_reference=law_ref,
        )

    def test_enriches_risk_with_law(self):
        """Риск по категории 'оплата' должен получить ссылку на закон."""
        risks = [self._make_risk("Оплата", "Срок оплаты не определён")]
        enriched = LegalService.match_risks_to_laws(risks)
        assert enriched[0].law_reference is not None
        assert enriched[0].law_description is not None

    def test_skips_already_filled_law(self):
        """Риск с уже заполненным law_reference не должен перезаписываться."""
        original_ref = "ГК РК ст. 999"
        risks = [self._make_risk("Оплата", "Срок не указан", law_ref=original_ref)]
        enriched = LegalService.match_risks_to_laws(risks)
        assert enriched[0].law_reference == original_ref

    def test_unknown_category_remains_without_law(self):
        """Риск с неизвестной категорией остаётся без ссылки."""
        risks = [self._make_risk("ЧтоТоНовое", "Описание без ключевых слов xyz123")]
        enriched = LegalService.match_risks_to_laws(risks)
        assert enriched[0].law_reference is None

    def test_empty_risks_list(self):
        """Пустой список рисков обрабатывается без ошибок."""
        result = LegalService.match_risks_to_laws([])
        assert result == []

    def test_multiple_risks_enriched(self):
        """Несколько рисков обогащаются одновременно."""
        risks = [
            self._make_risk("Оплата", "Срок оплаты не определён"),
            self._make_risk("Расторжение", "Расторжение без уведомления"),
        ]
        enriched = LegalService.match_risks_to_laws(risks)
        # At least one should be enriched
        enriched_refs = [r.law_reference for r in enriched if r.law_reference]
        assert len(enriched_refs) >= 1


# ============================================================
# Тесты: LegalService.enrich_analysis
# ============================================================

class TestEnrichAnalysis:
    """Тесты обогащения полного результата анализа."""

    def _make_analysis(self, risks=None, success=True) -> AnalysisResult:
        risks = risks or []
        return AnalysisResult(
            document_type="Договор аренды",
            summary="Тест",
            risks=risks,
            total_risks=len(risks),
            analysis_success=success,
        )

    def test_enriches_analysis_with_risks(self):
        """Успешный анализ с рисками должен быть обогащён."""
        risk = RiskItem(
            category="Оплата",
            description="Срок оплаты не указан",
            risk_level=RiskLevel.HIGH,
        )
        analysis = self._make_analysis(risks=[risk])
        enriched = LegalService.enrich_analysis(analysis)
        assert enriched.risks[0].law_reference is not None

    def test_failed_analysis_unchanged(self):
        """Провальный анализ (analysis_success=False) возвращается без изменений."""
        analysis = self._make_analysis(success=False)
        result = LegalService.enrich_analysis(analysis)
        assert result.analysis_success is False

    def test_empty_risks_unchanged(self):
        """Анализ без рисков возвращается без изменений."""
        analysis = self._make_analysis(risks=[])
        result = LegalService.enrich_analysis(analysis)
        assert result.risks == []

    def test_returns_same_analysis_object(self):
        """Функция должна возвращать тот же объект (in-place enrichment)."""
        analysis = self._make_analysis(risks=[
            RiskItem(category="Срок", description="Срок просрочки", risk_level=RiskLevel.LOW)
        ])
        result = LegalService.enrich_analysis(analysis)
        assert result is analysis
