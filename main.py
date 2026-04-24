"""
DogovorAI Main Application Entry Point
FastAPI application with CORS, health checks and Supabase integration.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from config.settings import settings
from config.database import get_supabase_client
from app.api import health
from app.api import analysis
from app.api import auth
from app.api import subscriptions
from app.api import contracts

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
        # TEMPORARILY DISABLE DB INIT FOR TESTING
        # from app.models.database import create_tables
        # import threading
        
        # def init_db():
        #     try:
        #         create_tables()
        #         logger.info("✅ База данных инициализирована")
        #     except Exception as e:
        #         logger.warning(f"⚠️ Ошибка инициализации БД: {str(e)}")
        
        # db_thread = threading.Thread(target=init_db, daemon=True)
        # db_thread.start()

        # Пытаемся инициализировать Supabase клиент (с таймаутом)
        try:
            client = get_supabase_client()
            logger.info("✅ Supabase подключён")
        except Exception as e:
            logger.warning(f"⚠️ Supabase недоступен: {str(e)}")
    except Exception as e:
        # Не падаем — продолжаем без Supabase (демо-режим)
        logger.warning(f"⚠️ Ошибка при стартапе (демо-режим): {str(e)}")
        logger.warning("   Обновите SUPABASE_URL и SUPABASE_KEY в .env для полной работы")

    logger.info("✅ Приложение успешно запущено")
    logger.info(f"   📖 Swagger UI: http://localhost:{settings.port}/docs")
    logger.info(f"   🌐 Веб-интерфейс: http://localhost:{settings.port}/app")

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
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(subscriptions.router, prefix="/api", tags=["Subscriptions"])
app.include_router(contracts.router, prefix="/api", tags=["Contracts"])

# Раздача статических файлов фронтенда
# В Netlify функции выполняются глубоко в подпапках, поэтому ищем фронтенд от корня проекта
PROJECT_ROOT = Path(__file__).parent.resolve()
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Если мы в Netlify Functions, то __file__ может быть в netlify/functions/
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = PROJECT_ROOT.parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    logger.info(f"✅ Фронтенд подключён из {FRONTEND_DIR}")
else:
    logger.warning(f"⚠️ Директория фронтенда не найдена: {FRONTEND_DIR}")


# Главная страница — отдаём index.html
@app.get("/app", include_in_schema=False)
async def serve_frontend():
    """Отдаёт главную страницу DogovorAI."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"error": "Frontend not found"}


@app.get("/app/register", include_in_schema=False)
async def serve_register():
    """Serve the registration page."""
    register_path = FRONTEND_DIR / "register.html"
    if register_path.exists():
        return FileResponse(str(register_path))
    return {"error": "Register page not found"}


@app.get("/app/login", include_in_schema=False)
async def serve_login():
    """Serve the login page."""
    login_path = FRONTEND_DIR / "login.html"
    if login_path.exists():
        return FileResponse(str(login_path))
    return {"error": "Login page not found"}


@app.get("/app/auth/callback", include_in_schema=False)
async def serve_auth_callback():
    """Serve the OAuth callback page (handles Google OAuth redirect)."""
    callback_path = FRONTEND_DIR / "auth_callback.html"
    if callback_path.exists():
        return FileResponse(str(callback_path))
    return {"error": "Auth callback page not found"}


@app.get("/app/profile", include_in_schema=False)
async def serve_profile():
    """Serve the user profile & subscription page."""
    profile_path = FRONTEND_DIR / "profile.html"
    if profile_path.exists():
        return FileResponse(str(profile_path))
    return {"error": "Profile page not found"}


@app.get("/app/contracts", include_in_schema=False)
async def serve_contracts():
    """Serve the contract generation page."""
    contracts_path = FRONTEND_DIR / "contracts.html"
    if contracts_path.exists():
        return FileResponse(str(contracts_path))
    return {"error": "Contracts page not found"}



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )