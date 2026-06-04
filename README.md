# DogovorAI ⚖️🤖

**DogovorAI** — это интеллектуальный ассистент для анализа и автоматизации заполнения юридических документов. Система выявляет скрытые риски, проверяет положения на соответствие актуальному законодательству и помогает пользователям избегать юридических ловушек.

## 🛠 Технологический стек
- **Backend:** Python (FastAPI)
- **Frontend:** статические HTML/CSS/JS файлы
- **AI Core:** Kimi API через Hugging Face Router + OCR через Google Vision на Vercel
- **Database & Auth:** Supabase
- **Version Control:** GitHub

## 🚀 Основной функционал (MVP)
1. **Мультиформатный анализ:** Загрузка PDF, DOCX и изображений (фото договоров).
2. **Risk Detection:** Автоматический поиск потенциально опасных пунктов.
3. **Legal Grounding:** Ссылки на официальные статьи законов для подтверждения правомерности или нарушений.
4. **Smart Filling:** Подсказки по правильному заполнению полей.

## 📦 Установка и запуск

### Требования
- Python 3.11+
- pip или uv package manager
- Supabase проект (создать на https://supabase.com)

### Шаг 1: Клонирование репозитория
```bash
git clone https://github.com/yourusername/DogovorAI.git
cd DogovorAI
```

### Шаг 2: Создание виртуального окружения
```bash
python3.11 -m venv .venv
source .venv/bin/activate  # На Windows: .venv\Scripts\activate
```

### Шаг 3: Установка зависимостей
```bash
pip install -r requirements-dev.txt
```

### Шаг 4: Настройка переменных окружения
```bash
cp .env.example .env
```

Заполните `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL`, `HF_TOKEN` и при необходимости `GOOGLE_CLOUD_VISION_API_KEY`.

### Шаг 5: Настройка базы данных
```bash
python scripts/init_db.py
```

### Шаг 6: Запуск приложения
```bash
source .venv/bin/activate
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Если хотите запускать напрямую из проекта
./scripts/run_dev.sh
```

Приложение будет доступно на `http://localhost:8000`

### API Endpoints для аутентификации

#### Регистрация пользователя
```bash
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

#### Подтверждение email
```bash
POST /api/auth/verify
Content-Type: application/json

{
  "email": "user@example.com",
  "code": "123456"
}
```

> **Внимание:** Теперь используется Supabase Auth для отправки кодов подтверждения. Настройте email/SMS шаблоны в панели управления Supabase.

#### Повторная отправка кода
```bash
POST /api/auth/resend-code?email=user@example.com
```

#### Вход в систему
```bash
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

### Настройка Supabase Auth

1. **Перейдите в панель управления Supabase:**
   - Откройте ваш проект в [Supabase Dashboard](https://supabase.com/dashboard)
   - Перейдите в раздел **Authentication** → **Settings**

2. **Настройте Email Templates:**
   - В разделе **Email Templates** настройте шаблоны для:
     - **Confirm signup** — подтверждение регистрации
     - **Invite user** — приглашение пользователя
     - **Reset password** — сброс пароля

3. **Настройте SMS (опционально):**
   - В разделе **SMS** настройте провайдера для отправки SMS кодов

4. **Настройте Auth Settings:**
   - **Site URL:** `http://localhost:8000` (для разработки)
   - **Redirect URLs:** добавьте `http://localhost:8000/*`
   - **JWT Expiry:** настройте время жизни токенов

### Пример использования

1. **Регистрация:**
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

2. **Проверьте email** — код подтверждения будет отправлен на указанный email через Supabase.

3. **Подтверждение:**
```bash
curl -X POST "http://localhost:8000/api/auth/verify" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "code": "123456"}'
```

4. **Вход в систему:**
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

### API Documentation
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI Schema:** http://localhost:8000/openapi.json

### Деплой На Vercel

Проект рассчитан на один Vercel deployment: `main.py` запускает FastAPI через `Mangum`, отдаёт `/api/*` и статический frontend из `frontend/` по `/app`.

1. Импортируйте репозиторий в Vercel.
2. Скопируйте переменные из `.env.vercel.example` в Vercel → Settings → Environment Variables.
3. Для `DATABASE_URL` используйте Supabase Transaction Pooler URL.
4. В Supabase Auth укажите:
   - Site URL: `https://your-vercel-app.vercel.app`
   - Redirect URL: `https://your-vercel-app.vercel.app/app/auth/callback`
5. Добавьте `ADMIN_EMAILS` для доступа к `/api/metrics/*` и `/api/auth/users`.
6. Добавьте `GOOGLE_CLOUD_VISION_API_KEY`, если нужен анализ JPG/PNG.

В production демо-анализ отключён: если `HF_TOKEN` не настроен или AI API недоступен, `/api/analyze` и `/api/contracts/analyze` вернут `503`.

### Health Check Endpoints
```bash
# Основная проверка здоровья
curl http://localhost:8000/health

# Проверка подключения к БД
curl http://localhost:8000/api/health/database

# Kubernetes readiness probe
curl http://localhost:8000/api/health/ready

# Kubernetes liveness probe
curl http://localhost:8000/api/health/live
```

### Тестирование
```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=app tests/

# Конкретный тест
pytest tests/test_health.py -v
```

### Структура проекта
```
.
├── app/
│   ├── api/              # API endpoints
│   │   ├── auth.py       # Authentication endpoints
│   │   └── health.py     # Health check endpoints
│   ├── services/         # Business logic
│   │   ├── auth_service.py    # Supabase Auth service
│   │   ├── database_service.py
│   │   └── email_service.py   # SMTP email service (опционально)
│   ├── models/           # Pydantic schemas
│   │   ├── crud.py       # Database operations (deprecated)
│   │   ├── models.py     # SQLAlchemy models (deprecated)
│   │   └── schemas.py    # Pydantic schemas
│   └── __init__.py
├── config/
│   ├── settings.py       # Configuration from env
│   ├── database.py       # Supabase client
│   └── __init__.py
├── frontend/             # Static frontend files
│   ├── index.html        # Main page
│   ├── register.html     # Registration page
│   ├── login.html        # Login page
│   ├── js/
│   │   ├── register.js   # Registration logic
│   │   └── login.js      # Login logic
│   └── css/
│       └── styles.css    # Styles
├── tests/                # Unit tests
│   ├── test_auth.py      # Auth tests
│   ├── test_health.py    # Health tests
│   ├── conftest.py
│   └── __init__.py
├── scripts/              # Utility scripts
│   └── run_dev.sh        # Development runner
├── main.py               # FastAPI application entry point
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
├── pyproject.toml       # Project configuration
└── README.md            # This file
```

### Разработка
```bash
# Форматирование кода
black .

# Проверка типов
mypy app/

# Linting
flake8 app/
```

### Переменные окружения
Полный список переменных см. в `.env.example`:
- `SUPABASE_URL` — URL вашего Supabase проекта
- `SUPABASE_KEY` — Публичный ключ для клиента
- `DATABASE_URL` — PostgreSQL URL, для Vercel используйте Supabase Transaction Pooler
- `SUPABASE_SERVICE_KEY` — Служебный ключ (опционально для admin-операций)
- `HF_TOKEN` — токен Hugging Face Router для Kimi AI
- `GOOGLE_CLOUD_VISION_API_KEY` — OCR для изображений на Vercel
- `ADMIN_EMAILS` — список email администраторов через запятую
- `APP_URL` и `ALLOWED_ORIGINS` — публичный URL и разрешённые CORS origins
- `DEBUG` — Включить debug режим (True/False)
- `HOST` — Адрес хоста (по умолчанию 0.0.0.0)
- `PORT` — Порт приложения (по умолчанию 8000)

> **Аутентификация:** В production используются только валидные Supabase sessions. Local-token режим доступен только в `DEBUG`/pytest.
