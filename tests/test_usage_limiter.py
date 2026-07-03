"""
Тесты для Usage Limiter Service.
Проверка лимитов использования, сброса по месяцам, декодирования JWT.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.services.usage_limiter import (
    UsageLimiter,
    UsageLimitError,
    PLAN_LIMITS,
    PLAN_NAMES,
    _decode_jwt_email,
    _next_month_reset,
    _now_utc,
)


# ============================================================
# Тесты: вспомогательные функции
# ============================================================

class TestHelpers:
    """Тесты вспомогательных функций."""

    def test_now_utc_is_aware(self):
        """_now_utc() должен возвращать timezone-aware datetime."""
        now = _now_utc()
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc

    def test_next_month_reset_december(self):
        """Декабрь → следующий месяц: январь следующего года."""
        dt = datetime(2024, 12, 15, tzinfo=timezone.utc)
        result = _next_month_reset(dt)
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 1

    def test_next_month_reset_regular(self):
        """Обычный месяц → следующий."""
        dt = datetime(2024, 6, 10, tzinfo=timezone.utc)
        result = _next_month_reset(dt)
        assert result.year == 2024
        assert result.month == 7
        assert result.day == 1

    def test_next_month_reset_timezone_aware(self):
        """_next_month_reset должен возвращать aware datetime."""
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = _next_month_reset(dt)
        assert result.tzinfo is not None


# ============================================================
# Тесты: декодирование JWT email
# ============================================================

class TestDecodeJwtEmail:
    """Тесты извлечения email из JWT без проверки подписи."""

    def _make_token(self, payload: dict) -> str:
        """Создаёт JWT-подобный токен с заданным payload."""
        import json, base64
        header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b'=').decode()
        payload_json = json.dumps(payload).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_json).rstrip(b'=').decode()
        return f"{header}.{payload_b64}.fakesig"

    def test_extracts_email_from_payload(self):
        """email из payload.email извлекается корректно."""
        token = self._make_token({"email": "user@example.com", "sub": "123"})
        email = _decode_jwt_email(token)
        assert email == "user@example.com"

    def test_extracts_email_from_user_metadata(self):
        """email из payload.user_metadata.email тоже извлекается."""
        token = self._make_token({"user_metadata": {"email": "meta@example.com"}})
        email = _decode_jwt_email(token)
        assert email == "meta@example.com"

    def test_invalid_token_returns_none(self):
        """Невалидный токен должен вернуть None."""
        assert _decode_jwt_email("not.a.jwt") is None
        assert _decode_jwt_email("only-two.parts") is None
        assert _decode_jwt_email("") is None

    def test_no_email_in_payload_returns_none(self):
        """Payload без email должен вернуть None."""
        token = self._make_token({"sub": "123", "exp": 9999999999})
        email = _decode_jwt_email(token)
        assert email is None


# ============================================================
# Тесты: PLAN_LIMITS и PLAN_NAMES
# ============================================================

class TestPlanConfig:
    """Тесты конфигурации тарифных планов."""

    def test_basic_plan_has_limit_3(self):
        assert PLAN_LIMITS["basic"] == 3

    def test_pro_plan_has_limit_30(self):
        assert PLAN_LIMITS["pro"] == 30

    def test_max_plan_is_unlimited(self):
        assert PLAN_LIMITS["max"] is None

    def test_all_plans_have_names(self):
        for plan in ["basic", "pro", "max"]:
            assert plan in PLAN_NAMES
            assert PLAN_NAMES[plan]


# ============================================================
# Тесты: UsageLimitError
# ============================================================

class TestUsageLimitError:
    """Тесты исключения UsageLimitError."""

    def test_attributes_set_correctly(self):
        """Исключение должно хранить used, limit, plan."""
        err = UsageLimitError(used=3, limit=3, plan="basic")
        assert err.used == 3
        assert err.limit == 3
        assert err.plan == "basic"

    def test_message_contains_used_and_limit(self):
        """Сообщение об ошибке должно содержать used/limit."""
        err = UsageLimitError(used=5, limit=5, plan="pro")
        msg = str(err)
        assert "5/5" in msg

    def test_reset_date_in_message(self):
        """Если указана дата reset_at — она должна быть в сообщении."""
        err = UsageLimitError(used=3, limit=3, plan="basic",
                              reset_at="2026-07-01T00:00:00+00:00")
        msg = str(err)
        assert "01.07.2026" in msg or "2026" in msg


# ============================================================
# Тесты: UsageLimiter.resolve_user
# ============================================================

class TestResolveUser:
    """Тесты определения типа пользователя по токену."""

    def setup_method(self):
        self.limiter = UsageLimiter()

    def test_empty_token_returns_anonymous(self):
        result = self.limiter.resolve_user("")
        assert result["user_type"] == "anonymous"

    def test_none_token_returns_anonymous(self):
        result = self.limiter.resolve_user(None)
        assert result["user_type"] == "anonymous"

    def test_local_token_returns_local(self):
        uid = "550e8400-e29b-41d4-a716-446655440000"
        result = self.limiter.resolve_user(f"local-token-{uid}")
        assert result["user_type"] == "local"
        assert result["user_id"] == uid

    def test_local_token_without_uid_returns_anonymous(self):
        result = self.limiter.resolve_user("local-token-")
        assert result["user_type"] == "anonymous"

    def test_supabase_token_returns_supabase(self):
        result = self.limiter.resolve_user("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.sig")
        assert result["user_type"] == "supabase"

    def test_jwt_token_treated_as_supabase(self):
        """Любой не-local токен treated as Supabase JWT."""
        result = self.limiter.resolve_user("some-random-token-value")
        assert result["user_type"] == "supabase"


# ============================================================
# Тесты: UsageLimiter.get_plan_limit
# ============================================================

class TestGetPlanLimit:
    """Тесты получения лимита плана."""

    def setup_method(self):
        self.limiter = UsageLimiter()

    def test_basic_plan_limit(self):
        assert self.limiter.get_plan_limit("basic") == 3

    def test_pro_plan_limit(self):
        assert self.limiter.get_plan_limit("pro") == 30

    def test_max_plan_unlimited(self):
        assert self.limiter.get_plan_limit("max") is None

    def test_unknown_plan_defaults_to_basic(self):
        assert self.limiter.get_plan_limit("unknown_plan") == 3

    def test_uppercase_plan_name(self):
        """Регистр не должен влиять на результат."""
        assert self.limiter.get_plan_limit("BASIC") == 3
        assert self.limiter.get_plan_limit("PRO") == 30


# ============================================================
# Тесты: monthly reset (_maybe_reset_monthly)
# ============================================================

class TestMaybeResetMonthly:
    """Тесты ежемесячного сброса счётчика."""

    def setup_method(self):
        self.limiter = UsageLimiter()

    def _make_user(self, analyses_used=0, reset_at=None):
        user = MagicMock()
        user.analyses_used = analyses_used
        user.analyses_reset_at = reset_at
        return user

    def test_sets_reset_at_if_none(self):
        """Если reset_at не задан — устанавливается следующий месяц."""
        db = MagicMock()
        user = self._make_user(analyses_used=2, reset_at=None)
        self.limiter._maybe_reset_monthly(db, user)
        assert user.analyses_reset_at is not None
        db.commit.assert_called_once()

    def test_resets_counter_when_past_due(self):
        """Если reset_at в прошлом — счётчик сбрасывается."""
        db = MagicMock()
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        user = self._make_user(analyses_used=5, reset_at=past)
        self.limiter._maybe_reset_monthly(db, user)
        assert user.analyses_used == 0
        db.commit.assert_called()

    def test_no_reset_if_future(self):
        """Если reset_at в будущем — счётчик не сбрасывается."""
        db = MagicMock()
        future = datetime(2099, 1, 1, tzinfo=timezone.utc)
        user = self._make_user(analyses_used=2, reset_at=future)
        self.limiter._maybe_reset_monthly(db, user)
        assert user.analyses_used == 2

    def test_naive_reset_at_handled(self):
        """Naive datetime reset_at не должен вызывать ошибку."""
        db = MagicMock()
        past_naive = datetime(2020, 1, 1)  # no tzinfo
        user = self._make_user(analyses_used=3, reset_at=past_naive)
        self.limiter._maybe_reset_monthly(db, user)
        assert user.analyses_used == 0


# ============================================================
# Тесты: _build_info
# ============================================================

class TestBuildInfo:
    """Тесты формирования словаря info о пользователе."""

    def setup_method(self):
        self.limiter = UsageLimiter()

    def _make_user(self, plan="basic", used=0, reset_at=None):
        user = MagicMock()
        user.plan_type = plan
        user.analyses_used = used
        user.analyses_reset_at = reset_at
        return user

    def test_basic_plan_info(self):
        user = self._make_user("basic", 1)
        info = self.limiter._build_info(user)
        assert info["plan"] == "basic"
        assert info["used"] == 1
        assert info["limit"] == 3
        assert info["allowed"] is True

    def test_max_plan_unlimited(self):
        user = self._make_user("max", 100)
        info = self.limiter._build_info(user)
        assert info["limit"] is None

    def test_reset_at_serialized(self):
        dt = datetime(2026, 7, 1, tzinfo=timezone.utc)
        user = self._make_user("pro", 5, reset_at=dt)
        info = self.limiter._build_info(user)
        assert "2026" in info["reset_at"]


# ============================================================
# Тесты: _check_limit_by_user
# ============================================================

class TestCheckLimitByUser:
    """Тесты проверки лимитов для конкретного пользователя."""

    def setup_method(self):
        self.limiter = UsageLimiter()

    def _make_user(self, plan="basic", used=0):
        user = MagicMock()
        user.plan_type = plan
        user.analyses_used = used
        user.analyses_reset_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
        return user

    def test_under_limit_returns_info(self):
        """Пользователь в рамках лимита получает info."""
        db = MagicMock()
        user = self._make_user("basic", 2)
        info = self.limiter._check_limit_by_user(user, db)
        assert info["allowed"] is True

    def test_at_limit_raises_error(self):
        """Пользователь на лимите получает UsageLimitError."""
        db = MagicMock()
        user = self._make_user("basic", 3)
        with pytest.raises(UsageLimitError) as exc_info:
            self.limiter._check_limit_by_user(user, db)
        err = exc_info.value
        assert err.used == 3
        assert err.limit == 3

    def test_max_plan_never_raises(self):
        """Max-план никогда не вызывает ошибку."""
        db = MagicMock()
        user = self._make_user("max", 9999)
        info = self.limiter._check_limit_by_user(user, db)
        assert info["allowed"] is True
        assert info["limit"] is None


# ============================================================
# Тесты: check_limit (универсальный)
# ============================================================

class TestCheckLimit:
    """Интеграционные тесты универсальной проверки лимитов."""

    def setup_method(self):
        self.limiter = UsageLimiter()

    def test_anonymous_token_allowed(self):
        """Анонимный (None) токен — разрешён с базовыми лимитами."""
        result = self.limiter.check_limit(None)
        assert result["allowed"] is True

    def test_empty_string_token_allowed(self):
        """Пустой токен — разрешён."""
        result = self.limiter.check_limit("")
        assert result["allowed"] is True

    def test_local_token_checks_db(self):
        """Local-токен делает запрос к БД."""
        with patch.object(self.limiter, "check_limit_local",
                          return_value={"allowed": True, "used": 0, "limit": 3,
                                        "plan": "basic", "plan_name": "Basic",
                                        "reset_at": None}) as mock:
            self.limiter.check_limit("local-token-some-uuid")
            mock.assert_called_once_with("some-uuid")

    def test_supabase_token_checks_supabase(self):
        """JWT-токен делает запрос через Supabase."""
        with patch.object(self.limiter, "check_limit_supabase",
                          return_value={"allowed": True, "used": 0, "limit": 3,
                                        "plan": "basic", "plan_name": "Basic",
                                        "reset_at": None}) as mock:
            self.limiter.check_limit("jwt.token.value")
            mock.assert_called_once_with("jwt.token.value")
