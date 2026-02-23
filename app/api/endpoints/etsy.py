"""This is the webhook endpoint for an upcoming project"""
from supabase import create_client, Client
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import RedirectResponse
import logging
from app.models.user import UserProfile
from app.core.config import settings
from app.api.deps import get_current_user
from app.services import etsy_service

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Etsy Endpoints ---
@router.get("/etsy/connect")
def etsy_connect(current_user: dict = Depends(get_current_user)):
    state = create_state_token(current_user.user.id)
    return {"authorization_url": etsy_service.get_authorization_url(state)}

@router.get("/etsy/callback")
async def etsy_callback(code: str, state: str):
    try:
        user_id = verify_state_token(state)
        tokens = etsy_service.exchange_code_for_tokens(code)
        shop = etsy_service.get_etsy_shop(tokens['access_token'])
        
        update_data = {
            'etsy_access_token': tokens['access_token'],
            'etsy_refresh_token': tokens['refresh_token']
        }
        if shop:
            update_data['etsy_shop_id'] = shop['shop_id']

        supabase.table('profiles').update(update_data).eq('id', user_id).execute()
        return RedirectResponse(url="http://localhost:3000/dashboard?etsy_connected=true")
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000/error?message=Failed to connect Etsy account: {e}")

@router.get("/etsy/listings")
async def get_etsy_listings(current_user: dict = Depends(get_current_user)):
    profile = await get_user_profile_data(current_user.user.id)
    if not profile.etsy_shop_id or not profile.etsy_access_token:
        raise HTTPException(status_code=400, detail="Etsy account not connected or no shop found.")
    listings = etsy_service.get_shop_listings(profile.etsy_access_token, profile.etsy_shop_id)
    return listings