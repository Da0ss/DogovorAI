import logging
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services import paypal_service
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/paypal", tags=["PayPal"])


@router.post("/webhook")
async def paypal_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint for receiving and processing PayPal webhook notifications.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse JSON body from PayPal webhook request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    # Extract required headers for signature verification (case-insensitive checks)
    headers = {
        "PAYPAL-AUTH-ALGO": request.headers.get("PAYPAL-AUTH-ALGO") or request.headers.get("paypal-auth-algo", ""),
        "PAYPAL-CERT-URL": request.headers.get("PAYPAL-CERT-URL") or request.headers.get("paypal-cert-url", ""),
        "PAYPAL-TRANSMISSION-ID": request.headers.get("PAYPAL-TRANSMISSION-ID") or request.headers.get("paypal-transmission-id", ""),
        "PAYPAL-TRANSMISSION-SIG": request.headers.get("PAYPAL-TRANSMISSION-SIG") or request.headers.get("paypal-transmission-sig", ""),
        "PAYPAL-TRANSMISSION-TIME": request.headers.get("PAYPAL-TRANSMISSION-TIME") or request.headers.get("paypal-transmission-time", "")
    }

    webhook_id = settings.paypal_webhook_id
    if not webhook_id:
        logger.error("PAYPAL_WEBHOOK_ID is not configured in settings/environment variables.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PayPal webhook service is unconfigured"
        )

    # Validate signature via PayPal API
    is_valid = await paypal_service.verify_webhook_signature(headers, payload, webhook_id)
    if not is_valid:
        logger.warning("PayPal webhook signature verification failed.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature verification failed"
        )

    # Update database record based on the event payload
    success = await paypal_service.process_webhook_event(db, payload)
    if not success:
        return {"status": "error", "message": "Webhook verified, but processing was skipped or failed"}

    return {"status": "success", "message": "PayPal webhook processed successfully"}
