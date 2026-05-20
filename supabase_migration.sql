-- ============================================================
-- DogovorAI — Суpabase SQL Migration
-- Выполнить в: Supabase Dashboard → SQL Editor → Run
--
-- Создаёт таблицы: profiles, verification_codes
-- Совместима с Supabase Auth (auth.users).
-- ============================================================

-- Расширения (если ещё не включены)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. PROFILES (основная таблица пользователей)
--
-- id: UUID — для Supabase Auth users = auth.users.id
--           для локальных email/password users = сгенерированный UUID
--
-- ВАЖНО: FK на auth.users намеренно НЕ добавлен, чтобы поддержать
--        как Supabase Auth, так и локальную email/password авторизацию.
--        Для production с чистым Supabase Auth можно добавить:
--        REFERENCES auth.users(id) ON DELETE CASCADE
-- ============================================================

CREATE TABLE IF NOT EXISTS public.profiles (
    -- Primary key (UUID, совместим с auth.users.id)
    id                  text            PRIMARY KEY,

    -- Auth
    email               text            NOT NULL UNIQUE,
    hashed_password     text,                           -- NULL для Google/OTP OAuth пользователей
    is_verified         boolean         NOT NULL DEFAULT false,
    full_name           text,
    avatar_url          text,
    auth_provider       text            NOT NULL DEFAULT 'local'
                                        CHECK (auth_provider IN ('local', 'google', 'otp', 'supabase')),

    -- Subscription & Billing
    plan_type           text            NOT NULL DEFAULT 'basic'
                                        CHECK (plan_type IN ('basic', 'pro', 'max')),
    subscription_status text            NOT NULL DEFAULT 'inactive'
                                        CHECK (subscription_status IN (
                                            'inactive', 'active', 'past_due', 'canceled', 'trialing'
                                        )),
    stripe_customer_id  text            UNIQUE,

    -- Usage tracking (синхронизировано с UsageLimiter в коде)
    analyses_used       integer         NOT NULL DEFAULT 0 CHECK (analyses_used >= 0),
    analyses_limit      integer         DEFAULT 3,           -- NULL = безлимит (план Max)
    analyses_reset_at   timestamptz,                         -- Дата следующего сброса счётчика

    -- Timestamps
    created_at          timestamptz     NOT NULL DEFAULT now(),
    updated_at          timestamptz     NOT NULL DEFAULT now()
);

COMMENT ON TABLE  public.profiles IS 'Профили пользователей DogovorAI. Совместима с Supabase auth.users.';
COMMENT ON COLUMN public.profiles.id IS 'UUID строка. Для Supabase Auth = auth.users.id. Для local auth = случайный UUID.';
COMMENT ON COLUMN public.profiles.hashed_password IS 'bcrypt хеш пароля. NULL для OAuth пользователей.';
COMMENT ON COLUMN public.profiles.analyses_limit IS 'NULL = безлимит (план Max). 3 = Basic, 30 = Pro.';
COMMENT ON COLUMN public.profiles.auth_provider IS 'Источник авторизации: local (пароль), google (OAuth), otp (magic link).';

-- ============================================================
-- 2. VERIFICATION_CODES (OTP и email-верификация)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.verification_codes (
    id          text            PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id     text            NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    code        varchar(6)      NOT NULL,
    purpose     text            NOT NULL DEFAULT 'email_verify'
                                CHECK (purpose IN ('email_verify', 'otp_login', 'password_reset')),
    is_used     boolean         NOT NULL DEFAULT false,
    expires_at  timestamptz     NOT NULL DEFAULT (now() + interval '10 minutes'),
    created_at  timestamptz     NOT NULL DEFAULT now()
);

COMMENT ON TABLE  public.verification_codes IS 'OTP коды и email-верификация. Очищаются автоматически после использования.';

-- ============================================================
-- 3. ИНДЕКСЫ (ускорение частых запросов)
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_profiles_email               ON public.profiles (email);
CREATE INDEX IF NOT EXISTS idx_profiles_plan_type           ON public.profiles (plan_type);
CREATE INDEX IF NOT EXISTS idx_profiles_stripe_customer_id  ON public.profiles (stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_profiles_analyses_reset_at   ON public.profiles (analyses_reset_at);
CREATE INDEX IF NOT EXISTS idx_verification_user_id         ON public.verification_codes (user_id);
CREATE INDEX IF NOT EXISTS idx_verification_expires         ON public.verification_codes (expires_at);
CREATE INDEX IF NOT EXISTS idx_verification_code_lookup
    ON public.verification_codes (user_id, code, is_used, expires_at);

-- ============================================================
-- 4. AUTO-UPDATE updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_profiles_updated_at ON public.profiles;
CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- 5. AUTO-CREATE PROFILE для Supabase Auth пользователей
--    (Google OAuth, Magic Link)
--    Срабатывает при создании записи в auth.users
-- ============================================================

CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name, avatar_url, is_verified, auth_provider)
    VALUES (
        NEW.id::text,
        NEW.email,
        NEW.raw_user_meta_data->>'full_name',
        NEW.raw_user_meta_data->>'avatar_url',
        true,
        COALESCE(NEW.raw_user_meta_data->>'provider', 'supabase')
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_on_auth_user_created ON auth.users;
CREATE TRIGGER trg_on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_auth_user();

-- ============================================================
-- 6. RLS (Row Level Security) — каждый видит только своё
-- ============================================================

ALTER TABLE public.profiles           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.verification_codes ENABLE ROW LEVEL SECURITY;

-- profiles
DROP POLICY IF EXISTS "profiles_select_own" ON public.profiles;
CREATE POLICY "profiles_select_own"
    ON public.profiles FOR SELECT
    USING (auth.uid()::text = id);

DROP POLICY IF EXISTS "profiles_update_own" ON public.profiles;
CREATE POLICY "profiles_update_own"
    ON public.profiles FOR UPDATE
    USING (auth.uid()::text = id)
    WITH CHECK (auth.uid()::text = id);

-- verification_codes
DROP POLICY IF EXISTS "vcodes_select_own" ON public.verification_codes;
CREATE POLICY "vcodes_select_own"
    ON public.verification_codes FOR SELECT
    USING (auth.uid()::text = user_id);

-- ============================================================
-- 7. ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: атомарный инкремент счётчика
-- ============================================================

CREATE OR REPLACE FUNCTION public.increment_analyses_used(p_user_id text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_used  integer;
    v_limit integer;
BEGIN
    SELECT analyses_used, analyses_limit
    INTO v_used, v_limit
    FROM public.profiles
    WHERE id = p_user_id
    FOR UPDATE;

    -- NULL limit = безлимит (план Max)
    IF v_limit IS NOT NULL AND v_used >= v_limit THEN
        RETURN false;
    END IF;

    UPDATE public.profiles
    SET analyses_used = analyses_used + 1
    WHERE id = p_user_id;

    RETURN true;
END;
$$;

COMMENT ON FUNCTION public.increment_analyses_used IS
    'Атомарный инкремент счётчика анализов с проверкой лимита. Возвращает false при превышении.';

-- ============================================================
-- ГОТОВО. Таблицы созданы:
--   public.profiles         — основная таблица пользователей
--   public.verification_codes — коды верификации
-- ============================================================
