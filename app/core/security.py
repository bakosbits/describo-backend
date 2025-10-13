import jwt
import logging
import requests
import time
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from jwt import InvalidTokenError

from app.core.config import settings

logger = logging.getLogger(__name__)

jwks_cache = {
    "keys": [],
    "last_fetched": 0
}
CACHE_LIFETIME_SECONDS = 3600


def get_jwks():
    global jwks_cache
    current_time = time.time()
    
    if not jwks_cache["keys"] or (current_time - jwks_cache["last_fetched"]) > CACHE_LIFETIME_SECONDS:
        jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        try:
            response = requests.get(jwks_url)
            response.raise_for_status()
            jwks_cache["keys"] = response.json()["keys"]
            jwks_cache["last_fetched"] = current_time
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Could not fetch JWKS: {e}"
            )
    return jwks_cache["keys"]



async def verify_token(request: Request) -> dict:
    token = None
    auth_header = request.headers.get("Authorization")
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    try:
        jwks = get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise jwt.InvalidTokenError("Token header is missing 'kid'")

        signing_key = None
        for key in jwks:
            if key["kid"] == kid:
                signing_key = jwt.algorithms.ECAlgorithm.from_jwk(key)
                break
        
        if not signing_key:
            raise jwt.InvalidTokenError("Signing key not found in JWKS")

        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256"],
            audience="authenticated"
        )        

    
        return {"user": payload, "token": token}
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}"
        )




def verify_old_token(self, token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token and return payload."""

    try:
        # Decode the JWT token
        payload = jwt.decode(
            token,
            self.jwt_secret,
            algorithms=["HS256"],
            audience="authenticated"
        )

        return payload
    except InvalidTokenError as e:

        logger.error(f"JWT verification failed: {e}")
        return None

    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None

