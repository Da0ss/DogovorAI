"""
Supabase Database Configuration and Client Initialization
"""

from typing import Optional
import logging
from supabase import create_client, Client
from config.settings import settings

# Настройка логирования
logger = logging.getLogger(__name__)


class SupabaseClient:
    """
    Wrapper around Supabase client for managing database connections.
    
    Handles initialization and connection checks.
    """

    _instance: Optional[Client] = None

    @classmethod
    def get_client(cls) -> Client:
        """
        Get or create Supabase client instance (singleton pattern).
        
        Returns:
            Client: Initialized Supabase client
            
        Raises:
            ValueError: If Supabase credentials are not configured
        """
        if cls._instance is None:
            cls._instance = cls._init_client()
        return cls._instance

    @staticmethod
    def _init_client() -> Client:
        """
        Initialize Supabase client with credentials from settings.
        
        Returns:
            Client: Initialized Supabase client
            
        Raises:
            ValueError: If Supabase URL or Key is missing
        """
        if not settings.supabase_url or not settings.supabase_key:
            raise ValueError(
                "Supabase URL and Key must be configured in environment variables"
            )

        try:
            client = create_client(
                supabase_url=settings.supabase_url,
                supabase_key=settings.supabase_key
            )
            logger.info("✅ Supabase client инициализирован успешно")
            return client
        except Exception as e:
            import traceback
            logger.error(f"❌ Ошибка при инициализации Supabase: {str(e)}")
            traceback.print_exc()
            raise

    @classmethod
    async def check_connection(cls) -> bool:
        """
        Check Supabase database connection.
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            client = cls.get_client()
            # Простая проверка через RPC или запрос
            # Используем health check таблицу или RPC функцию
            result = await client.table("_realtime_migrations").select("*").limit(1)
            logger.info("✅ Подключение к Supabase успешно проверено")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке подключения к Supabase: {str(e)}")
            return False


# Глобальный singleton для доступа к Supabase
def get_supabase_client() -> Client:
    """
    Get Supabase client instance.
    
    Returns:
        Client: Initialized Supabase client
    """
    return SupabaseClient.get_client()
