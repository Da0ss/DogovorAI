import logging
from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.services.subscription_service import billing_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


class CheckoutRequest(BaseModel):
    user_id: str
    plan: str


class CheckoutResponse(BaseModel):
    checkout_url: Optional[str] = None
    message: str


class UsageResponse(BaseModel):
    used: int
    limit: Optional[int]
    plan: str
    status: str = "inactive"


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(req: CheckoutRequest) -> CheckoutResponse:
    try:
        url = billing_manager.create_checkout(req.user_id, req.plan)
        if url is None:
            return CheckoutResponse(checkout_url=None, message="Switched to Basic")
        return CheckoutResponse(checkout_url=url, message="Redirect to Stripe")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        import traceback
        err_msg = "".join(traceback.format_exception(None, e, e.__traceback__))
        logger.error(f"Checkout failed details: {err_msg}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Checkout failed: {str(e)}")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        result = billing_manager.handle_webhook(payload, sig)
        return result
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/usage/{user_id}", response_model=UsageResponse)
def get_usage(user_id: str) -> UsageResponse:
    try:
        return UsageResponse(**billing_manager.get_usage(user_id))
    except Exception as e:
        logger.error(f"Usage error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed")


@router.get("/profile/{user_id}")
def get_subscription_profile(user_id: str) -> dict:
    profile = billing_manager.get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    return {
        "plan_type": profile.get("plan_type", "basic"),
        "subscription_status": profile.get("subscription_status", "inactive"),
        "analyses_used": profile.get("analyses_used", 0),
        "analyses_limit": billing_manager.get_plan_limit(profile.get("plan_type", "basic")),
        "stripe_customer_id": profile.get("stripe_customer_id"),
    }
