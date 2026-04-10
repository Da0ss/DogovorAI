# 🚀 Реализация системы регистрации пользователей с email подтверждением

## ✅ Что реализовано

### 1. **База данных (PostgreSQL + SQLAlchemy)**
- **Модели**: `User` и `VerificationCode` в `app/models/models.py`
- **Подключение**: SQLAlchemy engine в `app/models/database.py`
- **Миграции**: Alembic конфигурация и начальная миграция
- **Скрипт инициализации**: `scripts/init_db.py` для создания таблиц

### 2. **Безопасность**
- **Хеширование паролей**: bcrypt через passlib
- **Генерация кодов**: 6-значные случайные коды через secrets
- **Срок действия**: 10 минут на код подтверждения

### 3. **API Endpoints**
- `POST /api/auth/register` — регистрация пользователя
- `POST /api/auth/verify` — подтверждение email
- `POST /api/auth/resend-code` — повторная отправка кода

### 4. **CRUD операции**
- **Создание пользователя** с валидацией email
- **Генерация кодов подтверждения**
- **Проверка кодов** с учетом срока действия
- **Обновление статуса** верификации

### 5. **Структура файлов**
```
app/models/
├── models.py      # SQLAlchemy модели
├── schemas.py     # Pydantic схемы
├── database.py    # Подключение к БД
└── crud.py        # Бизнес-логика

app/api/
└── auth.py        # API эндпоинты аутентификации

scripts/
└── init_db.py     # Инициализация БД

alembic/           # Миграции базы данных
├── alembic.ini
├── env.py
└── versions/
    └── 001_initial.py

tests/
└── test_auth.py   # Тесты аутентификации
```

## 🗄️ Схема базы данных

### Таблица `users`
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Таблица `verification_codes`
```sql
CREATE TABLE verification_codes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    code VARCHAR(6) NOT NULL,
    expires_at TIMESTAMP NOT NULL
);
```

## 🔧 Установка и запуск

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения
Обновите `.env`:
```env
DATABASE_URL=postgresql://postgres.ifqpijqgcrrrldupmode:[rexvup-worrot-hijVa0]@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres
```

### 3. Инициализация базы данных
```bash
python scripts/init_db.py
```

### 4. Запуск приложения
```bash
python main.py
```

## 📡 API Использование

### Регистрация
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

### Подтверждение (код из логов)
```bash
curl -X POST "http://localhost:8000/api/auth/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "code": "123456"
  }'
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest tests/test_auth.py -v

# С покрытием
pytest tests/test_auth.py --cov=app.models
```

## 🔒 Безопасность

- **Пароли**: Хешируются с bcrypt (salt rounds = 12)
- **Коды подтверждения**: 6-значные, одноразовые, с истечением
- **Email валидация**: Через Pydantic EmailStr
- **SQL инъекции**: Предотвращены через SQLAlchemy ORM

## 📋 Следующие шаги

1. **JWT токены** для аутентификации сессий
2. **Email отправка** через SMTP (вместо логов)
3. **Rate limiting** для защиты от спама
4. **Пароль reset** функционал
5. **OAuth** интеграция (Google, GitHub)

---

**Статус**: ✅ Полностью реализовано  
**Тестирование**: ✅ Базовые тесты написаны  
**Документация**: ✅ README обновлен  
**Дата**: 10 апреля 2026 г.