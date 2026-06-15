"""
Supabase Database Configuration and Client Initialization
"""

from typing import Optional
import logging

try:
    from supabase import create_client, Client
except ImportError:
    # supabase пакет может быть недоступен — определяем заглушки
    create_client = None  # type: ignore
    Client = object  # type: ignore

from config.settings import settings

# Настройка логирования
logger = logging.getLogger(__name__)


class SupabaseClient:
    """
    Wrapper around Supabase client for managing database connections.
    
    Handles initialization and connection checks.
    """

    _instance: Optional[Client] = None
    _admin_instance: Optional[Client] = None

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
            cls._instance = cls._init_client(use_service_key=False)
        return cls._instance

    @classmethod
    def get_admin_client(cls) -> Client:
        """
        Get or create Supabase admin client instance using service role key (singleton pattern).
        
        Returns:
            Client: Initialized Supabase admin client
            
        Raises:
            ValueError: If Supabase credentials are not configured
        """
        if cls._admin_instance is None:
            cls._admin_instance = cls._init_client(use_service_key=True)
        return cls._admin_instance

    @staticmethod
    def _init_client(use_service_key: bool = False) -> Client:
        """
        Initialize Supabase client with credentials from settings.
        
        Returns:
            Client: Initialized Supabase client
            
        Raises:
            ValueError: If Supabase URL or Key is missing
        """
        url = settings.supabase_url
        key = (
            settings.supabase_service_key
            if use_service_key and settings.supabase_service_key
            else settings.supabase_key
        )

        if not url or not key:
            raise ValueError(
                "Supabase URL and Key must be configured in environment variables"
            )

        if create_client is None:
            raise ValueError(
                "Supabase package is not installed — run: pip install supabase"
            )

        try:
            client = create_client(
                supabase_url=url,
                supabase_key=key
            )
            key_type = "service_role" if use_service_key and settings.supabase_service_key else "anon"
            logger.info(f"✅ Supabase client ({key_type}) инициализирован успешно")
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


def get_supabase_admin_client() -> Client:
    """
    Get Supabase admin client instance (bypasses Row Level Security).
    
    Returns:
        Client: Initialized Supabase client
    """
    return SupabaseClient.get_admin_client()
