"""
Admin Metrics API — DogovorAI
Provides aggregated statistics from the local PostgreSQL database.
Secured: only accessible with a valid user token.
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.database import get_db
from app.models.models import User
from app.api.auth import require_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/summary")
def get_metrics_summary(
    request: Request,
    db: Session = Depends(get_db),
    _admin_user: dict = Depends(require_admin_user),
) -> dict:
    """
    Returns platform-wide metrics:
    - total users, verified users
    - users by plan (basic / pro / max)
    - total analyses performed
    - new users last 7 days / last 30 days
    - daily new-users for the last 14 days (sparkline)
    """
    # --- Core counts ---
    total_users = db.query(func.count(User.id)).scalar() or 0
    verified_users = db.query(func.count(User.id)).filter(User.is_verified == True).scalar() or 0

    # --- Plan breakdown ---
    plan_counts = (
        db.query(User.plan_type, func.count(User.id))
        .group_by(User.plan_type)
        .all()
    )
    plans = {"basic": 0, "pro": 0, "max": 0}
    for plan, cnt in plan_counts:
        key = (plan or "basic").lower()
        if key in plans:
            plans[key] = cnt

    # --- Total analyses ---
    total_analyses = db.query(func.sum(User.analyses_used)).scalar() or 0

    # --- New users in last 7 / 30 days ---
    now = datetime.utcnow()
    new_7d = (
        db.query(func.count(User.id))
        .filter(User.created_at >= now - timedelta(days=7))
        .scalar() or 0
    )
    new_30d = (
        db.query(func.count(User.id))
        .filter(User.created_at >= now - timedelta(days=30))
        .scalar() or 0
    )

    # --- Daily signups last 14 days (for sparkline chart) ---
    daily_signups = []
    for i in range(13, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        cnt = (
            db.query(func.count(User.id))
            .filter(User.created_at >= day_start, User.created_at < day_end)
            .scalar() or 0
        )
        daily_signups.append({
            "date": day_start.strftime("%d.%m"),
            "count": cnt
        })

    # --- Avg analyses per user ---
    avg_analyses = round(total_analyses / total_users, 1) if total_users else 0

    # --- Active subscriptions (pro + max) ---
    paid_users = plans["pro"] + plans["max"]

    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "unverified_users": total_users - verified_users,
        "plans": plans,
        "total_analyses": int(total_analyses),
        "avg_analyses_per_user": avg_analyses,
        "new_users_7d": new_7d,
        "new_users_30d": new_30d,
        "daily_signups": daily_signups,
        "paid_users": paid_users,
        "conversion_rate": round((paid_users / total_users * 100), 1) if total_users else 0,
        "generated_at": now.isoformat()
    }
