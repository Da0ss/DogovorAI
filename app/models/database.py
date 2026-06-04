"""
Database connection and session management
Serverless-compatible: uses NullPool to avoid persistent connections on Vercel.
"""

import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.settings import settings

logger = logging.getLogger(__name__)

# ── Определяем, запущены ли мы в serverless-окружении ──────────────────────
_IS_SERVERLESS = (
    os.getenv("VERCEL") == "1"
    or os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None
)

# ── Supabase Transaction Pooler использует URL вида postgres:// ─────────────
# SQLAlchemy 2.x требует postgresql://, поэтому фиксируем схему.
def _fix_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


_DATABASE_URL = _fix_db_url(settings.database_url)

# ── Настройки engine ────────────────────────────────────────────────────────
try:
    if not _DATABASE_URL:
        raise ValueError("DATABASE_URL is empty — using fallback SQLite")

    if _IS_SERVERLESS:
        # На Vercel/Lambda: NullPool — каждый запрос открывает и закрывает соединение.
        # Это предотвращает утечки соединений между вызовами serverless functions.
        from sqlalchemy.pool import NullPool
        engine = create_engine(
            _DATABASE_URL,
            poolclass=NullPool,
            echo=settings.debug,
            connect_args={"connect_timeout": 10},
        )
        logger.info("ℹ️ SQLAlchemy: serverless режим (NullPool)")
    else:
        # Локально/Docker: обычный пул с проверкой соединений
        engine = create_engine(
            _DATABASE_URL,
            pool_pre_ping=True,   # Проверяем соединения перед использованием
            pool_size=2,           # Маленький пул для dev
            max_overflow=5,
            pool_recycle=300,      # Переиспользовать соединения раз в 5 минут
            echo=settings.debug,
        )
        logger.info("ℹ️ SQLAlchemy: стандартный режим (pool_size=2)")
except Exception as _e:
    # Fallback: SQLite in-memory для демо/стартового режима
    logger.warning(f"⚠️ PostgreSQL недоступен ({_e}), используется SQLite in-memory")
    engine = create_engine("sqlite:///", echo=settings.debug)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency to get database session

    Yields:
        Session: Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    Create all database tables
    Should be called during application startup
    """
    from app.models.models import Base
    Base.metadata.create_all(bind=engine)