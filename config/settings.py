"""
Application Settings Configuration
Loads environment variables and provides typed configuration.
"""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application Settings
    
    Loads configuration from environment variables.
    Environment variables should be defined in .env file.
    """

    # Application
    app_name: str = "DogovorAI"
    app_version: str = "0.1.0"
    app_description: str = "Intelligent assistant for analyzing legal documents"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_service_key: Optional[str] = None

    # Optional: Kimi API (for future integration)
    kimi_api_key: Optional[str] = None
    
    # Optional: Hugging Face Token
    hf_token: Optional[str] = None
    
    # Optional: Kimi Model
    kimi_model: str = "moonshotai/Kimi-K2.5:fireworks-ai"
    
    # Database
    database_url: str

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",  # Игнорировать лишние переменные (например, PYTHONUNBUFFERED)
    }

    @property
    def is_production(self) -> bool:
        """Проверка режима production"""
        return not self.debug


# Создаем глобальный объект настроек
settings = Settings()
