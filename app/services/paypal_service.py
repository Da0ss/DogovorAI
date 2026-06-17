import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
from sqlalchemy.orm import Session

from config.settings import settings
from app.models.models import Subscription

logger = logging.getLogger(__name__)


def parse_iso_datetime(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception as e:
        logger.error(f"Failed to parse datetime string '{dt_str}': {e}")
        return None


async def get_paypal_access_token() -> str:
    """
    Fetch an access token from PayPal using client credentials.
    """
    base_url = "https://api-m.paypal.com" if settings.paypal_mode == "live" else "https://api-m.sandbox.paypal.com"
    url = f"{base_url}/v1/oauth2/token"
    
    client_id = settings.paypal_client_id
    client_secret = settings.paypal_client_secret
    
    if not client_id or not client_secret:
        raise ValueError("PayPal Client ID and Client Secret must be configured in environment variables")
        
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={
                "Accept": "application/json",
                "Accept-Language": "en_US"
            },
            timeout=10.0
        )
        if resp.status_code != 200:
            logger.error(f"Failed to fetch PayPal token. Status: {resp.status_code}, Body: {resp.text}")
            resp.raise_for_status()
            
        return resp.json()["access_token"]


async def verify_webhook_signature(headers: Dict[str, str], body: Dict[str, Any], webhook_id: str) -> bool:
    """
    Verify PayPal webhook signature using PayPal's verify-webhook-signature API.
    """
    base_url = "https://api-m.paypal.com" if settings.paypal_mode == "live" else "https://api-m.sandbox.paypal.com"
    url = f"{base_url}/v1/notifications/verify-webhook-signature"
    
    try:
        token = await get_paypal_access_token()
    except Exception as e:
        logger.error(f"PayPal Signature verification skipped/failed: cannot retrieve access token: {e}")
        return False
        
    payload = {
        "auth_algo": headers.get("PAYPAL-AUTH-ALGO") or headers.get("paypal-auth-algo"),
        "cert_url": headers.get("PAYPAL-CERT-URL") or headers.get("paypal-cert-url"),
        "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID") or headers.get("paypal-transmission-id"),
        "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG") or headers.get("paypal-transmission-sig"),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME") or headers.get("paypal-transmission-time"),
        "webhook_id": webhook_id,
        "webhook_event": body
    }
    
    # Check if any required header is missing
    missing_headers = [k for k, v in payload.items() if k != "webhook_event" and not v]
    if missing_headers:
        logger.error(f"PayPal webhook verification failed: missing headers: {missing_headers}")
        return False
        
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                timeout=15.0
            )
            if resp.status_code != 200:
                logger.error(f"PayPal webhook signature API call failed. Status: {resp.status_code}, Body: {resp.text}")
                return False
                
            result = resp.json()
            status = result.get("verification_status")
            logger.info(f"PayPal signature verification status: {status}")
            return status == "SUCCESS"
        except Exception as e:
            logger.error(f"Error calling PayPal webhook verification API: {e}")
            return False


async def process_webhook_event(db: Session, event_data: Dict[str, Any]) -> bool:
    """
    Process verified PayPal webhook events and update the subscriptions table.
    """
    event_type = event_data.get("event_type")
    resource = event_data.get("resource", {}) or {}
    
    logger.info(f"Processing PayPal webhook event: {event_type}")

    # Resolve subscription ID from event resource
    subscription_id = None
    if event_type.startswith("BILLING.SUBSCRIPTION."):
        subscription_id = resource.get("id")
    elif event_type == "PAYMENT.SALE.COMPLETED":
        subscription_id = resource.get("billing_agreement_id")
        
    if not subscription_id:
        logger.warning(f"PayPal event {event_type} ignored: no subscription ID found in resource.")
        return False
        
    # Search for the subscription where provider = 'paypal' and provider_subscription_id matches
    sub = db.query(Subscription).filter(
        Subscription.provider == "paypal",
        Subscription.provider_subscription_id == subscription_id
    ).first()
    
    if not sub:
        logger.warning(f"PayPal subscription not found in DB: provider_subscription_id={subscription_id}")
        return False

    old_status = sub.status
    
    # PayPal subscription state transition logic
    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        sub.status = "active"
        start_time_str = resource.get("start_time")
        if start_time_str:
            sub.current_period_start = parse_iso_datetime(start_time_str)
            
    elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
        sub.status = "canceled"
        canceled_time_str = resource.get("status_update_time")
        if canceled_time_str:
            sub.canceled_at = parse_iso_datetime(canceled_time_str)
            
    elif event_type == "BILLING.SUBSCRIPTION.EXPIRED":
        sub.status = "expired"
        
    elif event_type in ("BILLING.SUBSCRIPTION.SUSPENDED", "BILLING.SUBSCRIPTION.PAYMENT.FAILED"):
        sub.status = "suspended"
        
    elif event_type == "PAYMENT.SALE.COMPLETED":
        sub.status = "active"
        # Extend billing period using sale create time if available
        create_time_str = resource.get("create_time")
        if create_time_str:
            sub.current_period_start = parse_iso_datetime(create_time_str)

    # Save event data log
    sub.provider_event_data = event_data
    sub.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        logger.info(
            f"Successfully updated PayPal subscription '{subscription_id}' status: {old_status} -> {sub.status}"
        )
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save PayPal webhook updates to database: {e}")
        return False
