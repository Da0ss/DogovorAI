import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
from fastapi import HTTPException
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


async def create_paypal_subscription(
    db: Session,
    user_id: str,
    plan_name: str,
    email: str,
    origin: Optional[str] = None
) -> Optional[str]:
    """
    Create a PayPal subscription via the PayPal API and save an inactive record to the database.
    Returns the approval checkout URL.
    """
    token = await get_paypal_access_token()
    
    plan_id = None
    if plan_name == "pro":
        plan_id = settings.paypal_plan_id_pro or "P-TESTPROPLAN"
    elif plan_name == "max":
        plan_id = settings.paypal_plan_id_max or "P-TESTMAXPLAN"
    else:
        raise ValueError(f"Unknown plan: {plan_name}")
        
    base_url = origin or settings.app_url
    if base_url.endswith("/"):
        base_url = base_url[:-1]
        
    api_url = "https://api-m.paypal.com" if settings.paypal_mode == "live" else "https://api-m.sandbox.paypal.com"
    url = f"{api_url}/v1/billing/subscriptions"
    
    payload = {
        "plan_id": plan_id,
        "return_url": f"{base_url}/app/profile?payment=success",
        "cancel_url": f"{base_url}/app/profile?payment=canceled",
        "subscriber": {
            "email_address": email
        },
        "application_context": {
            "brand_name": "DogovorAI",
            "locale": "ru-RU",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "SUBSCRIBE_NOW"
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            },
            timeout=15.0
        )
        
        if resp.status_code != 201:
            logger.error(f"Failed to create PayPal subscription. Status: {resp.status_code}, Body: {resp.text}")
            raise HTTPException(status_code=500, detail="Failed to initiate PayPal subscription")
            
        result = resp.json()
        paypal_sub_id = result.get("id")
        
        # Find approval url
        approval_url = None
        for link in result.get("links", []):
            if link.get("rel") == "approve":
                approval_url = link.get("href")
                break
                
        if not approval_url:
            raise ValueError("No approval link found in PayPal response")
            
        # Clean up any existing inactive PayPal subscription for this user to keep it clean
        db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.provider == "paypal",
            Subscription.status == "inactive"
        ).delete(synchronize_session=False)
        
        sub = Subscription(
            user_id=user_id,
            provider="paypal",
            provider_subscription_id=paypal_sub_id,
            plan_type=plan_name,
            status="inactive",
            provider_event_data=result
        )
        db.add(sub)
        db.commit()
        
        return approval_url


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
        if sub.user:
            sub.user.plan_type = sub.plan_type
            sub.user.subscription_status = "active"
            
    elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
        sub.status = "canceled"
        canceled_time_str = resource.get("status_update_time")
        if canceled_time_str:
            sub.canceled_at = parse_iso_datetime(canceled_time_str)
        if sub.user:
            sub.user.plan_type = "basic"
            sub.user.subscription_status = "canceled"
            
    elif event_type == "BILLING.SUBSCRIPTION.EXPIRED":
        sub.status = "expired"
        if sub.user:
            sub.user.plan_type = "basic"
            sub.user.subscription_status = "expired"
            
    elif event_type in ("BILLING.SUBSCRIPTION.SUSPENDED", "BILLING.SUBSCRIPTION.PAYMENT.FAILED"):
        sub.status = "suspended"
        if sub.user:
            sub.user.subscription_status = "suspended"
            
    elif event_type == "PAYMENT.SALE.COMPLETED":
        sub.status = "active"
        # Extend billing period using sale create time if available
        create_time_str = resource.get("create_time")
        if create_time_str:
            sub.current_period_start = parse_iso_datetime(create_time_str)
        if sub.user:
            sub.user.plan_type = sub.plan_type
            sub.user.subscription_status = "active"

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
