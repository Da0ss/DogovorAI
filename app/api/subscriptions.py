import logging
from fastapi import APIRouter, Request, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services import paypal_service
from app.services.subscription_service import billing_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


class CheckoutRequest(BaseModel):
    user_id: str
    plan: str
    provider: Optional[str] = "stripe"
    origin: Optional[str] = None


class CheckoutResponse(BaseModel):
    checkout_url: Optional[str] = None
    message: str


class UsageResponse(BaseModel):
    used: int
    limit: Optional[int]
    plan: str
    status: str = "inactive"


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(req: CheckoutRequest, db: Session = Depends(get_db)) -> CheckoutResponse:
    plan_ranks = {"basic": 0, "pro": 1, "max": 2}
    new_rank = plan_ranks.get(req.plan.lower(), 0)
    
    profile = billing_manager.get_profile(req.user_id)
    if profile:
        current_plan = profile.get("plan_type", "basic").lower()
        current_rank = plan_ranks.get(current_plan, 0)
        
        if new_rank < current_rank:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Downgrading to a lower plan is not permitted.")
        elif new_rank == current_rank:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are already on this plan.")

    try:
        provider = (req.provider or "stripe").lower()
        if provider == "stripe":
            url = billing_manager.create_checkout(req.user_id, req.plan, origin=req.origin)
            if url is None:
                return CheckoutResponse(checkout_url=None, message="Switched to Basic")
            return CheckoutResponse(checkout_url=url, message="Redirect to Stripe")
        elif provider == "paypal":
            if req.plan.lower() == "basic":
                from app.models.models import User
                db.query(User).filter(User.id == req.user_id).update({
                    "plan_type": "basic",
                    "subscription_status": "active"
                })
                db.commit()
                return CheckoutResponse(checkout_url=None, message="Switched to Basic")
                
            profile_data = billing_manager.get_profile(req.user_id)
            if not profile_data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
                
            url = await paypal_service.create_paypal_subscription(
                db=db,
                user_id=req.user_id,
                plan_name=req.plan.lower(),
                email=profile_data.get("email", ""),
                origin=req.origin
            )
            return CheckoutResponse(checkout_url=url, message="Redirect to PayPal")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid provider. Must be stripe or paypal.")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        import traceback
        err_msg = "".join(traceback.format_exception(None, e, e.__traceback__))
        logger.error(f"Checkout failed details: {err_msg}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Checkout failed: {str(e)}")


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        result = billing_manager.handle_webhook(payload, sig, db=db)
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
