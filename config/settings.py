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

    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/app/auth/callback"

    # Optional: Kimi API (for future integration)
    kimi_api_key: Optional[str] = None
    
    # Optional: Hugging Face Token
    hf_token: Optional[str] = None
    
    # Optional: Kimi Model
    kimi_model: str = "moonshotai/Kimi-K2.5:fireworks-ai"
    
    # Database
    database_url: str

    # Email / SMTP settings
    email_host: Optional[str] = None
    email_port: int = 587
    email_user: Optional[str] = None
    email_password: Optional[str] = None
    email_from: Optional[str] = None
    email_use_tls: bool = True
    email_use_ssl: bool = False

    @property
    def email_configured(self) -> bool:
        return bool(
            self.email_host
            and self.email_user
            and self.email_password
            and self.email_from
        )

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
