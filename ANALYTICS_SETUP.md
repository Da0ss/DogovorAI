# Настройка аналитики (Google Analytics 4 & PostHog) в DogovorAI

В проекте DogovorAI интегрирована аналитика через **Google Analytics 4 (GA4)**, **Google Tag Manager (GTM)** и **PostHog**. 

Все ключи и идентификаторы вынесены в настройки бэкенда и файл `.env`. Это позволяет легко переключать аналитические кабинеты без изменения кода страниц.

---

## 1. Как настроить файл `.env`

Добавьте следующие переменные в ваш файл `.env` в корневой директории проекта:

```env
# Идентификатор потока данных Google Analytics 4 (начинается с G-)
GA_MEASUREMENT_ID=G-G6SYPHRVJL

# Идентификатор контейнера Google Tag Manager (начинается с GTM-)
GTM_ID=GTM-KSV7XQ6S

# API Ключ проекта PostHog (начинается с phc_)
POSTHOG_API_KEY=phc_nJvUqL8Gbc2WdsY5rfX5w8xuok5uVgMJc68zKLKN4nmk

# Хост PostHog (США: https://us.i.posthog.com, Европа: https://eu.i.posthog.com)
POSTHOG_HOST=https://us.i.posthog.com
```

---

## 2. Инструкция: Как получить ключи

### Google Analytics 4 (GA4)
1. Перейдите в [Google Analytics](https://analytics.google.com/) и войдите под своим Google-аккаунтом.
2. Если у вас нет аккаунта, нажмите **Создать аккаунт** и введите название вашей компании/проекта.
3. Создайте **Ресурс (Property)**:
   - Введите название ресурса (например, `DogovorAI`).
   - Выберите часовой пояс и валюту.
4. В разделе настройки сбора данных выберите платформу **Веб (Web)**.
5. Настройте веб-поток (Web Stream):
   - Укажите URL вашего сайта (например, `https://dogovorai.xyz` или `http://localhost:8000`).
   - Назовите поток (например, `DogovorAI Production`).
   - Нажмите **Создать поток**.
6. Скопируйте **Идентификатор показателя (Measurement ID)**. Он выглядит как `G-XXXXXXXXXX`.
7. Вставьте этот идентификатор в `.env` как `GA_MEASUREMENT_ID`.

---

### Google Tag Manager (GTM)
*Примечание: Использование GTM необязательно. Если он вам не нужен, просто оставьте переменную `GTM_ID` пустой в `.env`.*

1. Перейдите в [Google Tag Manager](https://tagmanager.google.com/).
2. Создайте новый аккаунт и добавьте контейнер:
   - Выберите целевую платформу: **Веб (Web)**.
3. После создания контейнера в верхней панели управления вы увидите код вида `GTM-XXXXXXX`.
4. Скопируйте его и вставьте в `.env` как `GTM_ID`.

---

### PostHog
1. Зарегистрируйтесь на сайте [PostHog](https://posthog.com/). Выберите регион хостинга данных:
   - **US Cloud** (хост: `https://us.i.posthog.com`)
   - **EU Cloud** (хост: `https://eu.i.posthog.com`) — рекомендуется, если пользователи находятся ближе к Европе/СНГ.
2. Войдите в панель управления и создайте проект (Project).
3. Перейдите в **Project Settings** (настройки проекта, иконка шестеренки внизу левого меню).
4. Найдите раздел **API Keys** и скопируйте **Project API Key**. Он начинается с `phc_`.
5. Вставьте его в `.env` как `POSTHOG_API_KEY`.
6. Укажите соответствующий хост в `POSTHOG_HOST` (`https://us.i.posthog.com` or `https://eu.i.posthog.com`).

---

## 3. Проверка работы аналитики

Чтобы убедиться, что события корректно отправляются в ваши кабинеты:

1. Запустите проект локально.
2. Откройте сайт в браузере с параметром `?ga_debug` в URL, например:
   `http://localhost:8000/app?ga_debug`
3. Откройте консоль разработчика (F12 -> Console). Вы увидите логи инициализации:
   ```text
   [Analytics] DebugView mode ON — события видны в GA4 & PostHog
   [Analytics] analytics_helper.js loaded with GA4 & PostHog.
   ```
4. При кликах, переходах по страницам и отправке договоров в консоли будут логироваться отправляемые события, например:
   ```text
   [Analytics] trackEvent: main_page_viewed {debug_mode: true}
   ```
5. Перейдите в раздел **DebugView** в настройках ресурса Google Analytics или в раздел **Live Events** в PostHog, чтобы увидеть события в реальном времени.
