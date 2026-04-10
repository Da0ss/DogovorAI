# DogovorAI ⚖️🤖

**DogovorAI** — это интеллектуальный ассистент для анализа и автоматизации заполнения юридических документов. Система выявляет скрытые риски, проверяет положения на соответствие актуальному законодательству и помогает пользователям избегать юридических ловушек.

## 🛠 Технологический стек
- **Backend:** Python (FastAPI)
- **Frontend:** TypeScript, HTML/CSS
- **AI Core:** Kimi API (LLM для анализа текста) + OCR (для обработки изображений)
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
# Используя venv
python3.11 -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
```

### Шаг 3: Установка зависимостей
```bash
pip install -r requirements.txt
```

### Шаг 4: Настройка базы данных
```bash
# Инициализация таблиц базы данных
python scripts/init_db.py
```

### Шаг 5: Запуск приложения
```bash
# Development режим (с автозагрузкой)
python main.py

# Или через uvicorn напрямую
uvicorn main:app --reload --host 0.0.0.0 --port 8000
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

#### Повторная отправка кода
```bash
POST /api/auth/resend-code?email=user@example.com
```

### Пример использования

1. **Регистрация:**
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

2. **Проверьте логи** — код подтверждения будет выведен в консоль:
```
📧 Verification code for user 1: 123456
```

3. **Подтверждение:**
```bash
curl -X POST "http://localhost:8000/api/auth/verify" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "code": "123456"}'
```

### API Documentation
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI Schema:** http://localhost:8000/openapi.json

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
│   │   └── health.py     # Health check endpoints
│   ├── services/         # Business logic
│   │   └── database_service.py
│   ├── models/           # Pydantic schemas
│   └── __init__.py
├── config/
│   ├── settings.py       # Configuration from env
│   ├── database.py       # Supabase client
│   └── __init__.py
├── tests/                # Unit tests
│   ├── test_health.py
│   ├── conftest.py
│   └── __init__.py
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
- `SUPABASE_SERVICE_KEY` — Служебный ключ (для админ операций)
- `DEBUG` — Включить debug режим (True/False)
- `HOST` — Адрес хоста (по умолчанию 0.0.0.0)
- `PORT` — Порт приложения (по умолчанию 8000)