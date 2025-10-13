from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr

class UserProfile(BaseModel):
    email: str
    credits: Optional[int] = None
    subscription_status: Optional[str] = None
    subscription_type: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    etsy_user_id: Optional[str] = None
    etsy_shop_id: Optional[str] = None
    etsy_access_token: Optional[str] = None
    etsy_refresh_token: Optional[str] = None

# Request Models
class UserPreferencesRequest(BaseModel):
    theme: Optional[str] = None
    notifications: Optional[bool] = None
    default_analysis_type: Optional[str] = None
    language: Optional[str] = None
    
    class Config:
       json_schema_extra = {
            "example": {
                "theme": "dark",
                "notifications": True,
                "default_analysis_type": "professional",
                "language": "en"
            }
        }


# Response Models
class UserProfileResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    
    class Config:
       json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "user_id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "user@example.com",
                    "role": "authenticated"
                }
            }
        }


class UserPreferencesResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    message: Optional[str] = None
    
    class Config:
       json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "theme": "light",
                    "notifications": True,
                    "default_analysis_type": "professional",
                    "language": "en"
                }
            }
        }


class AuthVerificationResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    message: str
    
    class Config:
       json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "authenticated": True,
                    "user_id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "user@example.com",
                    "role": "authenticated"
                },
                "message": "Authentication valid"
            }
        }


class AuthInfoResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    
    class Config:
       json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "auth_methods": {
                        "email_password": True,
                        "oauth_providers": ["google", "github", "azure"]
                    },
                    "features": {
                        "email_verification": True,
                        "password_reset": True,
                        "social_login": True
                    },
                    "message": "Authentication is handled by Supabase Auth. Use the frontend client for login/registration."
                }
            }
        }