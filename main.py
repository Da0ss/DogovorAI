"""
DogovorAI Main Application Entry Point
FastAPI application with CORS, health checks and Supabase integration.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from config.settings import settings
from config.database import get_supabase_client
from app.api import health
from app.api import analysis
from app.api import auth
from app.api import subscriptions
from app.api import contracts
from app.api import metrics
from app.api import history

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

def _allowed_cors_origins() -> list[str]:
    """Resolve CORS origins without wildcard credentials in production."""
    raw_origins = os.getenv("ALLOWED_ORIGINS", "")
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    if settings.debug:
        return origins or [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]

    if settings.app_url and not settings.app_url.startswith("http://localhost"):
        origins.append(settings.app_url.rstrip("/"))

    vercel_url = os.getenv("VERCEL_URL", "").strip()
    if vercel_url:
        origins.append(f"https://{vercel_url}")

    return sorted(set(origins))


_allowed_origins = _allowed_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
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
        "status": "\U0001F7E2 Running"
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
        "status": "\U0001F7E2 OK",
        "service": settings.app_name
    }


# Include routers from API modules
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(subscriptions.router, prefix="/api", tags=["Subscriptions"])
app.include_router(contracts.router, prefix="/api", tags=["Contracts"])
app.include_router(metrics.router, prefix="/api", tags=["Metrics"])
app.include_router(history.router, prefix="/api", tags=["History"])

# Раздача статических файлов фронтенда
PROJECT_ROOT = Path(__file__).parent.resolve()
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Поиск frontend-директории (локально, Netlify, Vercel)
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = PROJECT_ROOT.parent.parent / "frontend"

# На Vercel статика обычно не нужна (фронт деплоится отдельно),
# поэтому монтируем только если директория существует и не пустая
try:
    if FRONTEND_DIR.exists() and any(FRONTEND_DIR.iterdir()):
        app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
        logger.info(f"✅ Фронтенд подключён из {FRONTEND_DIR}")
    else:
        logger.info("ℹ️ Директория фронтенда не найдена — статика отключена (нормально для Vercel)")
except Exception as _e:
    logger.warning(f"⚠️ Не удалось подключить статику: {_e}")


def _frontend_response(filename: str, label: str):
    """Serve a static frontend HTML page."""
    path = FRONTEND_DIR / filename
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse(status_code=404, content={"error": f"{label} not found"})


@app.get("/app", include_in_schema=False)
async def serve_frontend():
    return _frontend_response("index.html", "Frontend")


@app.get("/app/register", include_in_schema=False)
async def serve_register():
    return _frontend_response("register.html", "Register page")


@app.get("/app/login", include_in_schema=False)
async def serve_login():
    return _frontend_response("login.html", "Login page")


@app.get("/app/auth/callback", include_in_schema=False)
async def serve_auth_callback():
    return _frontend_response("auth_callback.html", "Auth callback page")


@app.get("/app/profile", include_in_schema=False)
async def serve_profile():
    return _frontend_response("profile.html", "Profile page")


@app.get("/app/contracts", include_in_schema=False)
async def serve_contracts():
    return _frontend_response("contracts.html", "Contracts page")


@app.get("/app/metrics", include_in_schema=False)
async def serve_metrics():
    return _frontend_response("metrics.html", "Metrics page")


@app.get("/app/history", include_in_schema=False)
async def serve_history():
    return _frontend_response("history.html", "History page")

# ============================================================
# Vercel / AWS Lambda handler (через Mangum)
# Vercel вызывает этот объект как serverless function.
# ============================================================
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    handler = None  # локальный запуск без Mangum
    logger.info("ℹ️ Mangum не установлен — используется uvicorn (локальный режим)")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
