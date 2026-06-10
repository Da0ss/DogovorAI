-- ============================================================
-- DogovorAI — Fix Migration: Add missing columns to profiles
-- Выполнить в: Supabase Dashboard → SQL Editor → Run
-- ============================================================
-- Добавляет колонки которые есть в SQLAlchemy модели но отсутствуют в БД

-- 1. subscription_expiry_date — дата окончания подписки
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS subscription_expiry_date timestamptz;

COMMENT ON COLUMN public.profiles.subscription_expiry_date IS
    'Дата окончания активной подписки (Pro/Max). NULL = бессрочно или нет подписки.';

-- 2. Проверим что все остальные нужные колонки тоже есть
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS consent_accepted boolean NOT NULL DEFAULT false;

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS consent_accepted_at timestamptz;

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS analyses_used integer NOT NULL DEFAULT 0;

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS analyses_limit integer DEFAULT 3;

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS analyses_reset_at timestamptz;

-- 3. Убеждаемся что updated_at есть
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

-- ============================================================
-- Проверка: вывести все колонки таблицы profiles
-- ============================================================
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'profiles'
ORDER BY ordinal_position;
