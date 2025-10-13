from typing import Dict, Any
import jwt
import logging
from fastapi import Depends, Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client
from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.services.supabase_service import supabase_service

logger = logging.getLogger(__name__)

# Security scheme for JWT tokens
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get the current authenticated user.
    Validates Supabase JWT token from Authorization header.
    """

    if Request.method == "OPTIONS":
        return None
    
    try:
        token = credentials.credentials
        
        # Decode and validate Supabase JWT token
        # Supabase uses HS256 algorithm with the JWT secret
        try:
            payload = jwt.decode(
                token,
                settings.supabase_secret_key,
                algorithms=["HS256"],
                audience="authenticated",
                leeway=10
            )

            # Extract user information from Supabase JWT
            user_info = {
                "user_id": payload.get("sub"),  # Supabase uses 'sub' for user ID
                "email": payload.get("email"),
                "role": payload.get("role", "authenticated")
            }
            
            if not user_info["user_id"]:
                raise AuthenticationError("Invalid token: missing user ID")
                
            return user_info
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid JWT token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise AuthenticationError(f"Authentication failed: {str(e)}")


async def get_current_user_id(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> str:
    """
    FastAPI dependency to get the current user's ID.
    """
    return current_user["user_id"]


async def get_current_user_email(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> str:
    """
    FastAPI dependency to get the current user's email.
    """
    return current_user["email"]


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    FastAPI dependency to require admin role.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def get_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    FastAPI dependency to extract JWT token for service calls.
    """
    return credentials.credentials


async def get_user_subscription(
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get the current user's subscription information.
    """
    try:
        user_id = current_user["user_id"]

        # Fetch user profile from Supabase using the proper service client
        client = supabase_service.get_client(jwt_token)
        response = client.table("profiles").select("subscription_plan").eq("id", user_id).single().execute()
        
        if response.data:
            subscription_plan = response.data.get("subscription_plan", "none")
        else:
            subscription_plan = "none"
        
    except Exception as e:
        logger.error(f"Error fetching subscription info for user {current_user.get('user_id', 'unknown')}: {str(e)}")
        # Default to no subscription on error
        return {
            "plan": "none",
            "can_access_dashboard": False,
            "can_access_analytics": False,
            "can_access_compare": False
        }

