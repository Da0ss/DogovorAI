# 🔐 Настройка Google OAuth для DogovorAI

## Шаг 1: Google Cloud Console

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com)
2. Создайте новый проект или выберите существующий
3. Перейдите в **APIs & Services → OAuth consent screen**
   - Тип: **External**
   - Заполните название приложения: `DogovorAI`
   - Email поддержки: ваш email
   - Authorized domains: можно оставить пустым для dev
   - Сохраните
4. Перейдите в **APIs & Services → Credentials**
   - Нажмите **Create Credentials → OAuth 2.0 Client IDs**
   - Application type: **Web application**
   - Name: `DogovorAI Web`
   - **Authorized redirect URIs** — добавьте:
     ```
     https://ifqpijqgcrrrldupmode.supabase.co/auth/v1/callback
     ```
   - Нажмите **Create**
5. Сохраните **Client ID** и **Client Secret**

## Шаг 2: Supabase Dashboard

1. Откройте [Supabase Dashboard](https://supabase.com/dashboard) → ваш проект
2. Перейдите в **Authentication → Providers**
3. Найдите **Google** и нажмите **Enable**
4. Вставьте:
   - **Client ID** — из Google Cloud Console
   - **Client Secret** — из Google Cloud Console
5. Сохраните

## Шаг 3: SQL Setup

1. В Supabase Dashboard перейдите в **SQL Editor**
2. Нажмите **New Query**
3. Скопируйте содержимое файла `scripts/setup_google_auth.sql`
4. Нажмите **Run**
5. Убедитесь что таблица `profiles` появилась в **Table Editor**

## Шаг 4: Переменные окружения

Добавьте в файл `.env`:

```env
GOOGLE_CLIENT_ID=ваш-client-id-из-google
GOOGLE_CLIENT_SECRET=ваш-client-secret-из-google
GOOGLE_REDIRECT_URI=http://localhost:8000/app/auth/callback
```

## Шаг 5: Перезапуск

```bash
# Перезапустите сервер
bash ./scripts/run_dev.sh
```

Готово! Кнопки "Войти через Google" появятся на страницах логина и регистрации.

## Проверка

1. Откройте http://localhost:8000/app/login
2. Нажмите «Войти через Google»
3. Авторизуйтесь в Google
4. Вы будете перенаправлены обратно в DogovorAI
5. В навигации отобразится ваше имя и аватар
