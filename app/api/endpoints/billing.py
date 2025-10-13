
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
import stripe
import logging
from typing import Optional
from app.api.deps import get_current_user, get_jwt_token
from app.models.subscription import (
    CreateCheckoutSessionRequest,
    CreatePortalSessionRequest,
    CheckoutSessionResponse,
    PortalSessionResponse,
    SubscriptionInfoResponse,
    SubscriptionInfo,
    WebhookResponse,
    UsageCheckResponse
)
from app.services.stripe_service import stripe_service
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()



# @app.post("/stripe/create-portal-session")
# async def create_portal_session(current_user: dict = Depends(get_current_user)):
#     """Creates a Stripe Customer Portal session for the user to manage their subscription."""
#     profile = await get_user_profile_data(current_user.user.id)

#     if not profile.stripe_customer_id:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Stripe customer ID not found for this user."
#         )

#     session = stripe_service.create_portal_session(profile.stripe_customer_id)
#     if not session:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to create Stripe portal session."
#         )

#     return {"url": session.url}


@router.post("/{plan}/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    plan: str,
    request: CreateCheckoutSessionRequest,
    current_user: dict = Depends(get_current_user),
    user_jwt: str = Depends(get_jwt_token)
):
    """Create a Stripe checkout session for subscription or one-time payment"""
    try:
        user_id = current_user["user_id"]
        
        # Set default URLs if not provided
        base_url = f"https://{settings.frontend_domain}" if settings.frontend_domain else "http://localhost:8000"
        success_url = request.success_url or f"{base_url}/account?payment=success"
        cancel_url = request.cancel_url or f"{base_url}/account?payment=cancelled"
        
        # Validate plan
        valid_plans = ['pro_hac_vice', 'covenant', 'force_majeure']
        if plan not in valid_plans:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid plan. Must be one of: {', '.join(valid_plans)}"
            )
        
        # Create checkout session
        checkout_url = await stripe_service.create_checkout_session(
            user_id=user_id,
            plan=plan,
            success_url=success_url,
            cancel_url=cancel_url,
            user_jwt=user_jwt
        )
        
        return CheckoutSessionResponse(
            success=True,
            checkout_url=checkout_url,
            message="Checkout session created successfully"
        )
        
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

