"""
Database Service Module
Provides high-level database operations and health checks.
"""

import logging
from typing import Dict, Any, Optional
from supabase import Client
from config.database import get_supabase_client

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Service class for database operations.
    
    Encapsulates Supabase operations and provides business logic layer.
    """

    def __init__(self, client: Optional[Client] = None):
        """
        Initialize DatabaseService.
        
        Args:
            client: Optional Supabase client. If None, gets the default client.
        """
        self.client = client or get_supabase_client()

    async def check_connection(self) -> Dict[str, Any]:
        """
        Check database connection status.
        
        Attempts to connect to Supabase and verify the connection.
        
        Returns:
            dict: Connection status with details
            
        Example:
            {
                "status": "connected",
                "database": "Supabase",
                "message": "✅ Успешно подключено"
            }
        """
        try:
            # Пытаемся выполнить простой запрос к БД
            # Используем информационную схему PostgreSQL
            result = await self.client.table("information_schema.tables").select(
                "table_schema"
            ).limit(1)

            logger.info("✅ Подключение к БД успешно")
            return {
                "status": "connected",
                "database": "Supabase PostgreSQL",
                "message": "✅ Успешно подключено к базе данных"
            }
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке подключения: {str(e)}")
            return {
                "status": "disconnected",
                "database": "Supabase PostgreSQL",
                "message": f"❌ Ошибка подключения: {str(e)}"
            }

    async def get_database_info(self) -> Dict[str, Any]:
        """
        Get basic information about the database.
        
        Returns:
            dict: Database information
        """
        try:
            connection_status = await self.check_connection()
            return {
                "service": "DogovorAI Database",
                "provider": "Supabase",
                "connection": connection_status,
                "status": "ready"
            }
        except Exception as e:
            logger.error(f"❌ Ошибка при получении информации БД: {str(e)}")
            return {
                "service": "DogovorAI Database",
                "provider": "Supabase",
                "status": "error",
                "message": str(e)
            }


# Создаем глобальный экземпляр сервиса
_db_service: Optional[DatabaseService] = None


def get_database_service() -> DatabaseService:
    """
    Get or create DatabaseService instance.
    
    Returns:
        DatabaseService: Initialized service instance
    """
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
