"""
Admin Portal API — DogovorAI
Isolated admin dashboard with hardcoded credentials (admin:admin123).
Session-based authentication using HMAC-signed cookies.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.models import AnalysisResult, Document, User, Subscription

logger = logging.getLogger(__name__)

# ── Admin credentials (loaded from env with fallbacks) ──────────
ADMIN_USERNAME = os.getenv("ADMIN_PORTAL_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PORTAL_PASS", "admin123")

# Log warning if default credentials are used in production
if ADMIN_USERNAME == "admin" and ADMIN_PASSWORD == "admin123":
    try:
        from config.settings import settings
        if not settings.debug:
            logger.warning(
                "🚨 SECURITY WARNING: Admin portal is using default credentials in production! "
                "Please configure 'ADMIN_PORTAL_USER' and 'ADMIN_PORTAL_PASS' env variables."
            )
    except Exception:
        pass

# ── Session signing (HMAC-based, no extra deps) ────────────────
_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", secrets.token_hex(32))
SESSION_MAX_AGE = 7200  # 2 hours


def _sign_session(data: dict) -> str:
    """Create a signed session token with expiration."""
    payload = json.dumps({**data, "exp": int(time.time()) + SESSION_MAX_AGE})
    encoded = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(_SECRET_KEY.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{sig}"


def _verify_session(token: str) -> Optional[dict]:
    """Verify and decode a session token. Returns None on failure."""
    try:
        encoded, sig = token.split(".", 1)
        expected = hmac.new(
            _SECRET_KEY.encode(), encoded.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


# ── Maintenance mode (file-based for persistence across restarts)
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
MAINTENANCE_FILE = PROJECT_ROOT / ".maintenance_mode"
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def is_maintenance_mode() -> bool:
    """Check if maintenance mode is currently enabled."""
    return MAINTENANCE_FILE.exists()


def set_maintenance_mode(enabled: bool):
    """Toggle maintenance mode on/off."""
    if enabled:
        MAINTENANCE_FILE.write_text("on")
    else:
        MAINTENANCE_FILE.unlink(missing_ok=True)


# ── Router ──────────────────────────────────────────────────────
router = APIRouter(prefix="/admin-portal", tags=["Admin Portal"])


# ── Auth dependency ─────────────────────────────────────────────
def require_admin_session(request: Request) -> dict:
    """Validate admin session cookie. Raises 401 if invalid."""
    token = request.cookies.get("admin_session")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    data = _verify_session(token)
    if not data or data.get("user") != ADMIN_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    return data


# ════════════════════════════════════════════════════════════════
# Page routes
# ════════════════════════════════════════════════════════════════

@router.get("/", include_in_schema=False)
async def admin_root():
    """Redirect /admin-portal/ to the login page."""
    return RedirectResponse(url="/admin-portal/login")


@router.get("/login", include_in_schema=False)
async def admin_login_page():
    """Serve the admin login HTML page."""
    path = FRONTEND_DIR / "admin_login.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse(status_code=404, content={"error": "Admin login page not found"})


@router.get("/dashboard", include_in_schema=False)
async def admin_dashboard_page(request: Request):
    """Serve the admin dashboard (protected). Redirects to login if unauthenticated."""
    token = request.cookies.get("admin_session")
    if not token or not _verify_session(token):
        return RedirectResponse(url="/admin-portal/login")
    path = FRONTEND_DIR / "admin_dashboard.html"
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse(status_code=404, content={"error": "Admin dashboard not found"})


# ════════════════════════════════════════════════════════════════
# API: Authentication
# ════════════════════════════════════════════════════════════════

class AdminLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/api/login")
async def admin_login(data: AdminLoginRequest):
    """Authenticate admin with hardcoded credentials."""
    if data.username != ADMIN_USERNAME or data.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учётные данные",
        )

    token = _sign_session({"user": ADMIN_USERNAME})
    response = JSONResponse(content={"success": True, "message": "Авторизация успешна"})
    response.set_cookie(
        key="admin_session",
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
        path="/admin-portal",
    )
    return response


@router.post("/api/logout")
async def admin_logout():
    """Clear admin session cookie."""
    response = JSONResponse(content={"success": True})
    response.delete_cookie("admin_session", path="/admin-portal")
    return response


@router.get("/api/check-auth")
async def check_auth(_session: dict = Depends(require_admin_session)):
    """Verify current admin session is valid."""
    return {"authenticated": True, "user": _session.get("user")}


# ════════════════════════════════════════════════════════════════
# API: Dashboard Statistics
# ════════════════════════════════════════════════════════════════

@router.get("/api/stats")
def admin_stats(
    db: Session = Depends(get_db),
    _s: dict = Depends(require_admin_session),
):
    """Return aggregated platform statistics for the dashboard overview."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    verified = (
        db.query(func.count(User.id)).filter(User.is_verified.is_(True)).scalar() or 0
    )

    plan_rows = (
        db.query(User.plan_type, func.count(User.id)).group_by(User.plan_type).all()
    )
    plans = {"basic": 0, "pro": 0, "max": 0}
    for plan, cnt in plan_rows:
        k = (plan or "basic").lower()
        if k in plans:
            plans[k] = cnt

    total_analyses = int(db.query(func.sum(User.analyses_used)).scalar() or 0)
    total_documents = db.query(func.count(Document.id)).scalar() or 0

    now = datetime.utcnow()
    new_7d = (
        db.query(func.count(User.id))
        .filter(User.created_at >= now - timedelta(days=7))
        .scalar()
        or 0
    )
    banned = (
        db.query(func.count(User.id))
        .filter(User.subscription_status == "banned")
        .scalar()
        or 0
    )

    # Дополнительные бизнес-метрики и KPI
    active_subscriptions = db.query(func.count(Subscription.id)).filter(Subscription.status == "active").scalar() or 0
    total_tokens = int(db.query(func.sum(AnalysisResult.ai_tokens_used)).scalar() or 0)
    avg_risks = round(float(db.query(func.avg(AnalysisResult.total_risks)).scalar() or 0.0), 1)
    
    paying_users = plans.get("pro", 0) + plans.get("max", 0)
    conversion_rate = round((paying_users / total_users * 100), 1) if total_users > 0 else 0.0

    return {
        "total_users": total_users,
        "verified_users": verified,
        "total_analyses": total_analyses,
        "total_documents": total_documents,
        "plans": plans,
        "new_users_7d": new_7d,
        "banned_users": banned,
        "maintenance_mode": is_maintenance_mode(),
        "active_subscriptions": active_subscriptions,
        "total_tokens": total_tokens,
        "avg_risks": avg_risks,
        "conversion_rate": conversion_rate,
    }



# ════════════════════════════════════════════════════════════════
# API: User Management
# ════════════════════════════════════════════════════════════════

@router.get("/api/users")
def admin_users(
    search: str = "",
    plan_filter: str = "",
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    _s: dict = Depends(require_admin_session),
):
    """Return paginated user list with optional search/filter."""
    q = db.query(User)
    if search:
        q = q.filter(User.email.ilike(f"%{search}%"))
    if plan_filter:
        q = q.filter(User.plan_type == plan_filter)

    total = q.count()
    users = (
        q.order_by(desc(User.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "is_verified": u.is_verified,
                "plan_type": u.plan_type or "basic",
                "subscription_status": u.subscription_status or "inactive",
                "analyses_used": u.analyses_used or 0,
                "analyses_limit": u.analyses_limit,
                "auth_provider": u.auth_provider or "local",
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total + limit - 1) // limit),
    }


class PlanUpdateRequest(BaseModel):
    plan_type: str


@router.patch("/api/users/{user_id}/plan")
def update_user_plan(
    user_id: str,
    data: PlanUpdateRequest,
    db: Session = Depends(get_db),
    _s: dict = Depends(require_admin_session),
):
    """Change a user's subscription plan."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    valid_plans = {"basic", "pro", "max"}
    if data.plan_type not in valid_plans:
        raise HTTPException(
            status_code=400, detail=f"Invalid plan. Must be one of: {valid_plans}"
        )

    plan_limits = {"basic": 3, "pro": 30, "max": None}
    user.plan_type = data.plan_type
    user.analyses_limit = plan_limits[data.plan_type]
    if data.plan_type != "basic":
        user.subscription_status = "active"
    db.commit()

    logger.info(f"✅ Admin changed user {user.email} plan to {data.plan_type}")
    return {"success": True, "message": f"Plan updated to {data.plan_type}"}


@router.patch("/api/users/{user_id}/ban")
def toggle_ban(
    user_id: str,
    db: Session = Depends(get_db),
    _s: dict = Depends(require_admin_session),
):
    """Toggle ban/unban for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.subscription_status == "banned":
        user.subscription_status = "inactive"
        msg = "User unbanned"
    else:
        user.subscription_status = "banned"
        msg = "User banned"
    db.commit()

    logger.info(f"✅ Admin {msg}: {user.email}")
    return {"success": True, "message": msg, "new_status": user.subscription_status}


@router.delete("/api/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    _s: dict = Depends(require_admin_session),
):
    """Delete a user account permanently."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    email = user.email
    db.delete(user)
    db.commit()

    logger.info(f"🗑️ Admin deleted user: {email}")
    return {"success": True, "message": "User deleted"}


# ════════════════════════════════════════════════════════════════
# API: Document Management
# ════════════════════════════════════════════════════════════════

@router.get("/api/documents")
def admin_documents(
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    _s: dict = Depends(require_admin_session),
):
    """Return paginated list of all uploaded documents."""
    q = db.query(Document, User.email).join(User, Document.user_id == User.id)
    total = q.count()
    rows = (
        q.order_by(desc(Document.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.original_name or doc.filename,
                "file_type": doc.file_type,
                "file_size_bytes": doc.file_size_bytes or 0,
                "user_email": email,
                "storage_path": doc.storage_path,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc, email in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total + limit - 1) // limit),
    }


@router.get("/api/documents/{doc_id}/download")
def download_document(
    doc_id: str,
    db: Session = Depends(get_db),
    _s: dict = Depends(require_admin_session),
):
    """Download a document file for quality control."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.storage_path:
        fp = Path(doc.storage_path)
        if fp.exists():
            return FileResponse(str(fp), filename=doc.original_name or doc.filename)

    raise HTTPException(status_code=404, detail="File not found on disk")


# ════════════════════════════════════════════════════════════════
# API: Recent Activity Feed
# ════════════════════════════════════════════════════════════════

@router.get("/api/activity")
def admin_activity(
    db: Session = Depends(get_db),
    _s: dict = Depends(require_admin_session),
):
    """Return the last 10 analysis results for the activity feed."""
    rows = (
        db.query(AnalysisResult, Document.original_name, User.email)
        .join(Document, AnalysisResult.document_id == Document.id)
        .join(User, AnalysisResult.user_id == User.id)
        .order_by(desc(AnalysisResult.created_at))
        .limit(10)
        .all()
    )

    return {
        "activity": [
            {
                "id": ar.id,
                "document_name": dname or "—",
                "user_email": email,
                "risk_level": ar.overall_risk_level or "n/a",
                "total_risks": ar.total_risks or 0,
                "high_risk_count": ar.high_risk_count or 0,
                "success": ar.success,
                "created_at": ar.created_at.isoformat() if ar.created_at else None,
            }
            for ar, dname, email in rows
        ],
    }


# ════════════════════════════════════════════════════════════════
# API: Maintenance Mode
# ════════════════════════════════════════════════════════════════

class MaintenanceRequest(BaseModel):
    enabled: bool


@router.get("/api/maintenance")
def get_maintenance_status(_s: dict = Depends(require_admin_session)):
    """Get current maintenance mode status."""
    return {"enabled": is_maintenance_mode()}


@router.post("/api/maintenance")
def set_maintenance(
    data: MaintenanceRequest, _s: dict = Depends(require_admin_session)
):
    """Toggle maintenance mode on/off."""
    set_maintenance_mode(data.enabled)
    state = "включён" if data.enabled else "выключен"
    logger.info(f"🔧 Maintenance mode {state} by admin")
    return {"success": True, "enabled": data.enabled}
