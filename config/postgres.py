"""
PostgreSQL Database Connection (synchronous)
Direct PostgreSQL connection for administrative tasks.
Serverless-compatible: on Vercel uses direct connections instead of a persistent pool.
"""

import os
import logging
from typing import Optional
import psycopg2
from psycopg2 import pool
from urllib.parse import urlparse
from config.settings import settings

logger = logging.getLogger(__name__)

# Определяем serverless-окружение
_IS_SERVERLESS = (
    os.getenv("VERCEL") == "1"
    or os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None
)

# Connection pool for non-serverless environments
_connection_pool: Optional[pool.SimpleConnectionPool] = None


def _get_conn_kwargs() -> dict:
    """Разбирает DATABASE_URL и возвращает kwargs для psycopg2.connect."""
    raw_url = settings.database_url
    # Фикс: postgres:// → postgresql://
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql://", 1)
    url = urlparse(raw_url)
    return dict(
        user=url.username or "postgres",
        password=url.password,
        host=url.hostname or "localhost",
        port=url.port or 5432,
        database=url.path.lstrip("/") or "postgres",
        connect_timeout=10,
    )


def init_db_pool() -> pool.SimpleConnectionPool:
    """
    Initialize PostgreSQL connection pool (только для не-serverless окружений).

    Returns:
        SimpleConnectionPool: Connection pool instance
    """
    global _connection_pool

    if _IS_SERVERLESS:
        logger.warning("⚠️ init_db_pool() вызван в serverless-режиме — пул не создаётся")
        return None  # type: ignore

    try:
        kwargs = _get_conn_kwargs()
        _connection_pool = pool.SimpleConnectionPool(1, 5, **kwargs)
        logger.info("✅ PostgreSQL connection pool инициализирован")
        return _connection_pool
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации pool: {str(e)}")
        raise


def get_db_connection():
    """
    Get a PostgreSQL connection.
    - В serverless-режиме: прямое соединение (без пула).
    - Локально: из пула соединений.

    Returns:
        connection: PostgreSQL connection
    """
    global _connection_pool

    if _IS_SERVERLESS:
        # Прямое соединение на каждый запрос — безопасно в serverless
        kwargs = _get_conn_kwargs()
        return psycopg2.connect(**kwargs)

    if _connection_pool is None:
        init_db_pool()

    return _connection_pool.getconn()


def return_db_connection(conn):
    """
    Return connection to pool (или закрыть в serverless-режиме).

    Args:
        conn: PostgreSQL connection
    """
    global _connection_pool

    if _IS_SERVERLESS:
        # В serverless режиме — просто закрываем соединение
        try:
            conn.close()
        except Exception:
            pass
        return

    if _connection_pool:
        _connection_pool.putconn(conn)


async def test_postgres_connection() -> bool:
    """
    Test PostgreSQL connection.

    Returns:
        bool: True if connection successful
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        cursor.close()
        return_db_connection(conn)

        logger.info(f"✅ PostgreSQL подключение успешно: {version[0]}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения PostgreSQL: {str(e)}")
        return False


def close_db_pool():
    """Close all connections in pool (только для не-serverless)."""
    global _connection_pool

    if _IS_SERVERLESS:
        return  # Ничего не делаем в serverless

    if _connection_pool:
        _connection_pool.closeall()
        logger.info("🛑 PostgreSQL connection pool закрыт")

