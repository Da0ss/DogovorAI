"""
DogovorAI Main Application Entry Point
FastAPI application with CORS, health checks and Supabase integration.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from config.database import get_supabase_client
from app.api import health

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"🚀 Запуск {settings.app_name} v{settings.app_version}")
    try:
        # Инициализируем Supabase клиент
        client = get_supabase_client()
        logger.info("✅ Приложение успешно запущено")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске приложения: {str(e)}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Остановка приложения")


# Создание FastAPI приложения
app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan
)

# CORS Middleware - разрешаем запросы с фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> dict:
    """
    Root endpoint with API information.
    
    Returns:
        dict: Information about the API
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": settings.app_description,
        "status": "🟢 Running"
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Basic health check endpoint.
    
    Returns:
        dict: Health status
    """
    return {
        "status": "🟢 OK",
        "service": settings.app_name
    }


# Include routers from API modules
app.include_router(health.router, prefix="/api", tags=["Health"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
