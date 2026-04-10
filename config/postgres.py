"""
PostgreSQL Database Connection (synchronous)
Direct PostgreSQL connection for administrative tasks
"""

import logging
from typing import Optional
import psycopg2
from psycopg2 import pool
from config.settings import settings

logger = logging.getLogger(__name__)

# Connection pool for better performance
_connection_pool: Optional[pool.SimpleConnectionPool] = None


def init_db_pool() -> pool.SimpleConnectionPool:
    """
    Initialize PostgreSQL connection pool.
    
    Returns:
        SimpleConnectionPool: Connection pool instance
    """
    global _connection_pool
    
    try:
        _connection_pool = pool.SimpleConnectionPool(
            1,  # Minimum connections
            5,  # Maximum connections
            user="postgres.akecuhplmhqzfhehfqlj",
            password="qscfredzawer",
            host="aws-1-ap-south-1.pooler.supabase.com",
            port=5432,
            database="postgres"
        )
        logger.info("✅ PostgreSQL connection pool инициализирован")
        return _connection_pool
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации pool: {str(e)}")
        raise


def get_db_connection():
    """
    Get connection from pool.
    
    Returns:
        connection: PostgreSQL connection
    """
    global _connection_pool
    
    if _connection_pool is None:
        init_db_pool()
    
    return _connection_pool.getconn()


def return_db_connection(conn):
    """
    Return connection to pool.
    
    Args:
        conn: PostgreSQL connection
    """
    global _connection_pool
    
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
    """Close all connections in pool"""
    global _connection_pool
    
    if _connection_pool:
        _connection_pool.closeall()
        logger.info("🛑 PostgreSQL connection pool закрыт")
