"""
DogovorAI Main Application Entry Point
FastAPI application with CORS, health checks and Supabase integration.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
import json
import httpx
from starlette.types import Message
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from config.settings import settings
from config.database import get_supabase_client
from app.api import health
from app.api import analysis
from app.api import auth
from app.api import subscriptions
from app.api import contracts

from app.api import metrics
from app.api import history
from app.api import admin

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


# ── Maintenance mode middleware ──────────────────────────────────
_MAINTENANCE_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>DogovorAI — Техническое обслуживание</title>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@600;700;800&display=swap" rel="stylesheet">
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{min-height:100vh;background:linear-gradient(135deg,#0f172a,#1e293b);display:flex;align-items:center;justify-content:center;font-family:'Manrope',sans-serif;color:#e2e8f0;text-align:center;padding:20px}
    .icon{font-size:72px;margin-bottom:24px}
    h1{font-size:28px;font-weight:800;margin-bottom:12px}
    p{font-size:15px;color:#94a3b8;max-width:420px;line-height:1.7}
  </style>
</head>
<body>
  <div><div class="icon">🔧</div><h1>Техническое обслуживание</h1><p>Сервис DogovorAI временно недоступен. Мы проводим плановые работы для улучшения качества. Пожалуйста, зайдите позже.</p></div>
</body>
</html>"""


async def set_body(request: Request, body: bytes):
    """Restore the request body stream after reading it in a middleware."""
    async def receive() -> Message:
        return {"type": "http.request", "body": body, "more_body": False}
    request._receive = receive


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """
    HTTP Middleware that adds standard security headers to all responses
    to align with OWASP and best practices (HSTS, CSP, XSS-Protection, etc.).
    """
    response = await call_next(request)
    
    # 1. HSTS (Strict-Transport-Security): Enforces HTTPS (1 year)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    
    # 2. X-Frame-Options: Anti-Clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # 3. X-Content-Type-Options: Prevents MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # 4. Referrer-Policy: Limit referrer information passed
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # 5. X-XSS-Protection: Disable XSS filtering (CSP covers it, standard in modern sites)
    response.headers["X-XSS-Protection"] = "0"
    
    # 6. Permissions-Policy: Deactivate sensitive browser API access
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    
    # 7. Content-Security-Policy (CSP): Restrict script, stylesheet, and API request sources
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://www.google.com https://www.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://fonts.cdnfonts.com; "
        "font-src 'self' data: https://fonts.gstatic.com https://fonts.cdnfonts.com; "
        "img-src 'self' data: blob: https://*.supabase.co https://lh3.googleusercontent.com; "
        "connect-src 'self' https://*.supabase.co https://www.google.com https://*.supabase.net; "
        "frame-src 'self' https://www.google.com;"
    )
    response.headers["Content-Security-Policy"] = csp_policy
    
    return response


@app.middleware("http")
async def recaptcha_v3_verification_middleware(request: Request, call_next):
    """
    Bot Protection: Validates reCAPTCHA token on registration and login endpoints.
    Skips verification if RECAPTCHA_SECRET_KEY is not defined (dev environment).
    """
    auth_endpoints = ["/api/auth/register", "/api/auth/login"]
    
    if request.url.path in auth_endpoints and request.method == "POST":
        # Skip reCAPTCHA verification in dev/test environment to not break tests
        if settings.debug or os.getenv("PYTEST_RUNNING") == "1":
            return await call_next(request)

        secret = settings.recaptcha_secret_key
        if secret:
            client_ip = request.client.host if request.client else "unknown"
            token = request.headers.get("X-Recaptcha-Token")
            
            if not token:
                # Read request body to extract recaptcha_token from JSON
                body_bytes = await request.body()
                await set_body(request, body_bytes)
                
                try:
                    body_json = json.loads(body_bytes)
                    token = body_json.get("recaptcha_token")
                except Exception:
                    pass
            
            if not token:
                logger.warning(
                    f"🔒 Bot Protection: Blocked request to {request.url.path} - "
                    f"missing reCAPTCHA token. IP: {client_ip}"
                )
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Пожалуйста, пройдите проверку reCAPTCHA."}
                )
            
            # Post verification to Google siteverify API
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "https://www.google.com/recaptcha/api/siteverify",
                        data={"secret": secret, "response": token},
                        timeout=5.0
                    )
                    result = resp.json()
            except Exception as e:
                logger.error(
                    f"❌ reCAPTCHA System Error: Verification service request failed: {str(e)}. IP: {client_ip}"
                )
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Не удалось проверить reCAPTCHA. Попробуйте позже."}
                )
            
            if not result.get("success"):
                logger.warning(
                    f"⚠️ Bot Protection: Blocked request to {request.url.path} - "
                    f"invalid/failed reCAPTCHA verification. IP: {client_ip}"
                )
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Проверка reCAPTCHA не пройдена. Попробуйте снова."}
                )
                
    return await call_next(request)


@app.middleware("http")
async def security_logging_middleware(request: Request, call_next):
    """
    Security Auditing Middleware.
    Tracks and logs failed access attempts with IP address tracking.
    """
    client_ip = request.client.host if request.client else "unknown"
    response = await call_next(request)
    
    # Audit status code 401 Unauthorized and 403 Forbidden
    if response.status_code in [401, 403]:
        logger.warning(
            f"🔒 Security Audit Event: Access Denied ({response.status_code}) on "
            f"{request.method} {request.url.path}. IP: {client_ip}"
        )
        
    return response


@app.middleware("http")
async def maintenance_middleware(request: Request, call_next):
    """Return 503 for non-admin routes when maintenance mode is on."""
    if admin.is_maintenance_mode():
        path = request.url.path
        # Always allow admin portal and health check
        if path.startswith("/admin-portal") or path == "/health":
            return await call_next(request)
        # API requests get JSON 503
        if path.startswith("/api"):
            return JSONResponse(status_code=503, content={"error": "Сервис на техническом обслуживании"})
        # Everything else gets a nice HTML page
        return HTMLResponse(status_code=503, content=_MAINTENANCE_HTML)
    return await call_next(request)


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root path to /app for frontend serving."""
    return RedirectResponse(url="/app")


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
app.include_router(admin.router)

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
