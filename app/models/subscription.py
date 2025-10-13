from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# Request Models
class CreateCheckoutSessionRequest(BaseModel):
    plan: str = Field(..., description="Subscription plan: pro_hac_vice, pro, or force_majeure")
    success_url: Optional[str] = Field(None, description="URL to redirect after successful payment")
    cancel_url: Optional[str] = Field(None, description="URL to redirect after cancelled payment")
    
    class Config:
        json_schema_extra = {
            "example": {
                "plan": "pro",
                "success_url": "https://yourapp.com/success",
                "cancel_url": "https://yourapp.com/cancel"
            }
        }


class CreatePortalSessionRequest(BaseModel):
    return_url: Optional[str] = Field(None, description="URL to return to from customer portal")

    
    class Config:
        json_schema_extra = {
            "example": {
                "return_url": "https://yourapp.com/account"

            }
        }


# Response Models
class CheckoutSessionResponse(BaseModel):
    success: bool
    checkout_url: str
    message: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "checkout_url": "https://checkout.stripe.com/pay/cs_test_...",
                "message": "Checkout session created successfully"
            }
        }


class PortalSessionResponse(BaseModel):
    success: bool
    portal_url: str
    message: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "portal_url": "https://billing.stripe.com/session/...",
                "message": "Portal session created successfully"
            }
        }


class SubscriptionInfo(BaseModel):
    plan: str = Field(..., description="Current subscription plan")
    status: str = Field(..., description="Subscription status")
    credits_remaining: int = Field(..., description="Number of credits remaining")
    credit_reset_date: Optional[datetime] = Field(None, description="When credits reset")
    subscription_start_date: Optional[datetime] = Field(None, description="When subscription started")
    subscription_end_date: Optional[datetime] = Field(None, description="When subscription ends")
    has_stripe_customer: bool = Field(..., description="Whether user has Stripe customer record")
    
    class Config:
        json_schema_extra = {
            "example": {
                "plan": "maker",
                "status": "active",
                "credits_remaining": 25,
                "credits_reset_date": "2024-02-01T00:00:00Z",
                "subscription_start_date": "2024-01-01T00:00:00Z",
                "subscription_end_date": None,
                "has_stripe_customer": True
            }
        }


class SubscriptionInfoResponse(BaseModel):
    success: bool
    data: SubscriptionInfo
    message: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "plan": "maker",
                    "status": "active",
                    "credits_remaining": 25,
                    "credit_reset_date": "2024-02-01T00:00:00Z",
                    "subscription_start_date": "2024-01-01T00:00:00Z",
                    "subscription_end_date": None,
                    "has_stripe_customer": True
                },
                "message": "Subscription info retrieved successfully"
            }
        }


class WebhookResponse(BaseModel):
    success: bool
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Webhook processed successfully"
            }
        }


class UsageCheckResponse(BaseModel):
    success: bool
    can_analyze: bool
    analyses_remaining: int
    plan: str
    message: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "can_analyze": True,
                "credits_remaining": 25,
                "plan": "covenant",
                "message": "Analysis allowed"
            }
        }