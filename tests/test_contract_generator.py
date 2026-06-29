"""
Тесты для Contract Generator — проверка генерации DOCX-договоров.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.contract_generator import (
    _replace_placeholder,
    _replace_in_paragraph,
    DOCX_AVAILABLE,
    GENERATED_DIR,
    TEMPLATES_DIR,
)


# ============================================================
# Тесты: замена плейсхолдеров
# ============================================================

class TestReplacePlaceholder:
    """Тесты функции _replace_placeholder."""

    def test_simple_replacement(self):
        """Одиночный плейсхолдер заменяется корректно."""
        text = "Привет, {{name}}!"
        result = _replace_placeholder(text, {"name": "Иван"})
        assert result == "Привет, Иван!"

    def test_multiple_replacements(self):
        """Несколько плейсхолдеров заменяются корректно."""
        text = "{{seller_name}} продаёт {{buyer_name}}"
        result = _replace_placeholder(text, {
            "seller_name": "Петров",
            "buyer_name": "Иванов",
        })
        assert result == "Петров продаёт Иванов"

    def test_no_placeholder_unchanged(self):
        """Текст без плейсхолдеров остаётся неизменным."""
        text = "Обычный текст без подстановок."
        result = _replace_placeholder(text, {"key": "value"})
        assert result == text

    def test_numeric_value_converted_to_string(self):
        """Числовое значение конвертируется в строку."""
        text = "Сумма: {{amount}} тенге"
        result = _replace_placeholder(text, {"amount": 100000})
        assert result == "Сумма: 100000 тенге"

    def test_unused_context_keys_ignored(self):
        """Лишние ключи в context не вызывают ошибок."""
        text = "Договор №{{number}}"
        result = _replace_placeholder(text, {"number": "42", "unused_key": "ignored"})
        assert result == "Договор №42"

    def test_missing_key_placeholder_remains(self):
        """Плейсхолдер без значения в context остаётся в тексте."""
        text = "Имя: {{name}}"
        result = _replace_placeholder(text, {})
        assert result == "Имя: {{name}}"

    def test_empty_text(self):
        """Пустой текст возвращается без изменений."""
        result = _replace_placeholder("", {"key": "value"})
        assert result == ""

    def test_partial_match_not_replaced(self):
        """Частичное совпадение (одна скобка) не заменяется."""
        text = "{name} и {{name}}"
        result = _replace_placeholder(text, {"name": "Тест"})
        # Only double-brace form is replaced
        assert "Тест" in result
        assert "{name}" in result


# ============================================================
# Тесты: замена в параграфе
# ============================================================

class TestReplaceInParagraph:
    """Тесты функции _replace_in_paragraph."""

    def _make_paragraph(self, runs_text: list[str]):
        """Создаёт мок-параграф с заданными run-текстами."""
        para = MagicMock()
        runs = []
        for t in runs_text:
            run = MagicMock()
            run.text = t
            runs.append(run)
        para.runs = runs

        # para.text — соединение всех runs
        def get_text():
            return "".join(r.text for r in para.runs)
        type(para).text = property(lambda self: get_text())
        return para

    def test_no_placeholder_skips(self):
        """Параграф без плейсхолдеров не изменяется."""
        para = self._make_paragraph(["Обычный текст"])
        original_text = para.runs[0].text
        _replace_in_paragraph(para, {"key": "value"})
        assert para.runs[0].text == original_text

    def test_simple_run_replacement(self):
        """Плейсхолдер в одном run заменяется корректно."""
        para = self._make_paragraph(["Имя: {{name}}"])
        _replace_in_paragraph(para, {"name": "Ахмет"})
        assert para.runs[0].text == "Имя: Ахмет"


# ============================================================
# Тесты: директории и пути
# ============================================================

class TestDirectoriesAndPaths:
    """Тесты настройки директорий."""

    def test_templates_dir_is_path(self):
        """TEMPLATES_DIR должен быть объектом Path."""
        assert isinstance(TEMPLATES_DIR, Path)

    def test_generated_dir_is_path(self):
        """GENERATED_DIR должен быть объектом Path."""
        assert isinstance(GENERATED_DIR, Path)

    def test_templates_dir_contains_docx_subdir(self):
        """TEMPLATES_DIR должен указывать на templates_docx папку."""
        assert "templates_docx" in str(TEMPLATES_DIR)

    def test_vercel_uses_tmp(self):
        """На Vercel GENERATED_DIR должен указывать на /tmp."""
        with patch.dict(os.environ, {"VERCEL": "1"}):
            import importlib
            import app.services.contract_generator as cg
            importlib.reload(cg)
            assert "/tmp" in str(cg.GENERATED_DIR)


# ============================================================
# Тесты: generate_docx — негативные кейсы
# ============================================================

class TestGenerateDocxErrors:
    """Тесты функции generate_docx — обработка ошибок."""

    def test_missing_template_raises_file_not_found(self):
        """Если шаблон не найден — должен бросаться FileNotFoundError."""
        from app.services.contract_generator import generate_docx
        with pytest.raises(FileNotFoundError, match="Шаблон не найден"):
            generate_docx("/nonexistent/path/template.docx", {})

    def test_no_docx_raises_runtime_error(self):
        """Если python-docx недоступен — должен бросаться RuntimeError."""
        import tempfile, shutil
        tmpdir = tempfile.mkdtemp()
        try:
            # Create a dummy template file
            tpl = os.path.join(tmpdir, "test.docx")
            with open(tpl, "w") as f:
                f.write("dummy")

            from app.services.contract_generator import generate_docx
            with patch("app.services.contract_generator.DOCX_AVAILABLE", False):
                with patch("app.services.contract_generator._DocxDocument", None):
                    with pytest.raises(RuntimeError, match="python-docx"):
                        generate_docx(tpl, {})
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================
# Тесты: generate_sale_contract / generate_labor_contract
# ============================================================

class TestContractGenerators:
    """Тесты generate_sale_contract и generate_labor_contract."""

    @pytest.fixture
    def mock_generate_docx(self):
        """Патчит generate_docx, чтобы не создавать реальный файл."""
        with patch("app.services.contract_generator.generate_docx",
                   return_value="/tmp/fake.docx") as mock:
            yield mock

    def test_generate_sale_contract_calls_generate_docx(self, mock_generate_docx):
        """generate_sale_contract должен вызывать generate_docx с правильным шаблоном."""
        from app.services.contract_generator import generate_sale_contract
        result = generate_sale_contract({
            "seller_name": "Петров И.И.",
            "buyer_name": "Иванов А.А.",
            "amount": 150000.0,
            "date": "01.01.2026",
        })
        assert mock_generate_docx.called
        args, kwargs = mock_generate_docx.call_args
        assert "sale_contract.docx" in args[0]
        assert result == "/tmp/fake.docx"

    def test_generate_sale_contract_formats_amount(self, mock_generate_docx):
        """Сумма должна передаваться в отформатированном виде (с разделителями)."""
        from app.services.contract_generator import generate_sale_contract
        generate_sale_contract({
            "seller_name": "А",
            "buyer_name": "Б",
            "amount": 1000000.0,
            "date": "01.01.2026",
        })
        _, kwargs = mock_generate_docx.call_args
        context = mock_generate_docx.call_args[0][1]
        assert "1,000,000.00" in context["amount"]

    def test_generate_labor_contract_calls_generate_docx(self, mock_generate_docx):
        """generate_labor_contract должен вызывать generate_docx с правильным шаблоном."""
        from app.services.contract_generator import generate_labor_contract
        result = generate_labor_contract({
            "employer_name": "ТОО Тест",
            "employee_name": "Иванов И.И.",
            "salary": 300000.0,
            "position": "Разработчик",
            "start_date": "01.02.2026",
        })
        assert mock_generate_docx.called
        args, _ = mock_generate_docx.call_args
        assert "labor_contract.docx" in args[0]
        assert result == "/tmp/fake.docx"

    def test_generate_labor_contract_formats_salary(self, mock_generate_docx):
        """Зарплата должна передаваться в отформатированном виде."""
        from app.services.contract_generator import generate_labor_contract
        generate_labor_contract({
            "employer_name": "ТОО",
            "employee_name": "Работник",
            "salary": 500000.0,
            "position": "Менеджер",
            "start_date": "01.03.2026",
        })
        context = mock_generate_docx.call_args[0][1]
        assert "500,000.00" in context["salary"]
