-- ============================================================
-- DogovorAI — ИСПРАВЛЕНИЕ ТИПОВ КОЛОНОК
-- Выполнить в: Supabase Dashboard → SQL Editor → Run
--
-- Проблема: user_id в таблицах имеет тип UUID,
--           но Python-код генерирует текстовые UUID строки.
-- Решение: меняем все UUID колонки связанные с profiles.id на TEXT
-- ============================================================

-- 1. Отключаем RLS чтобы можно было менять типы
ALTER TABLE public.documents         DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_results  DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions     DISABLE ROW LEVEL SECURITY;

-- 2. Удаляем RLS политики
DROP POLICY IF EXISTS "documents: select own"        ON public.documents;
DROP POLICY IF EXISTS "documents: insert own"        ON public.documents;
DROP POLICY IF EXISTS "documents: delete own"        ON public.documents;
DROP POLICY IF EXISTS "analysis: select own"         ON public.analysis_results;
DROP POLICY IF EXISTS "analysis: insert own"         ON public.analysis_results;
DROP POLICY IF EXISTS "subscriptions: select own"    ON public.subscriptions;

-- 3. Удаляем FK-ограничения
ALTER TABLE public.documents         DROP CONSTRAINT IF EXISTS documents_user_id_fkey;
ALTER TABLE public.analysis_results  DROP CONSTRAINT IF EXISTS analysis_results_user_id_fkey;
ALTER TABLE public.subscriptions     DROP CONSTRAINT IF EXISTS subscriptions_user_id_fkey;

-- 4. Меняем типы колонок: UUID -> TEXT
ALTER TABLE public.documents        ALTER COLUMN user_id    TYPE text;
ALTER TABLE public.analysis_results ALTER COLUMN user_id    TYPE text;
ALTER TABLE public.subscriptions    ALTER COLUMN user_id    TYPE text;

-- 5. Проверяем итоговые типы
SELECT 
    table_name, 
    column_name, 
    data_type
FROM information_schema.columns
WHERE column_name IN ('id', 'user_id')
  AND table_name IN ('profiles', 'documents', 'analysis_results', 'subscriptions', 'verification_codes')
ORDER BY table_name, column_name;
