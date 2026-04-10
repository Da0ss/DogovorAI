"""
Health Check API Endpoints
Provides endpoints for monitoring application and database health.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from app.services.database_service import get_database_service
from config.postgres import test_postgres_connection

router = APIRouter(prefix="/health")


@router.get("/", tags=["Health"])
async def health_status() -> Dict[str, Any]:
    """
    Get general application health status.
    
    Returns:
        dict: Health status information
        
    Example:
        {
            "status": "🟢 healthy",
            "service": "DogovorAI",
            "checks": {...}
        }
    """
    try:
        db_service = get_database_service()
        db_status = await db_service.get_database_info()

        return {
            "status": "🟢 healthy",
            "service": "DogovorAI",
            "database": db_status,
            "message": "✅ Все системы в норме"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"❌ Health check failed: {str(e)}"
        )


@router.get("/database", tags=["Health"])
async def database_health() -> Dict[str, Any]:
    """
    Check database connection health.
    
    Returns:
        dict: Database health status
        
    Raises:
        HTTPException: If database connection fails
        
    Example:
        {
            "status": "connected",
            "database": "Supabase PostgreSQL",
            "message": "✅ Успешно подключено"
        }
    """
    try:
        db_service = get_database_service()
        db_status = await db_service.check_connection()

        if db_status["status"] == "disconnected":
            raise HTTPException(
                status_code=503,
                detail=db_status["message"]
            )

        return db_status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"❌ Database health check failed: {str(e)}"
        )


@router.get("/ready", tags=["Health"])
async def readiness_check() -> Dict[str, str]:
    """
    Kubernetes-style readiness probe endpoint.
    
    Returns:
        dict: Readiness status
    """
    try:
        db_service = get_database_service()
        await db_service.check_connection()
        return {
            "status": "ready",
            "service": "DogovorAI"
        }
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Service not ready"
        )


@router.get("/live", tags=["Health"])
async def liveness_check() -> Dict[str, str]:
    """
    Kubernetes-style liveness probe endpoint.
    
    Returns:
        dict: Liveness status
    """
    return {
        "status": "alive",
        "service": "DogovorAI"
    }
