from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
import stripe
import logging
from typing import Optional
from app.api.deps import get_current_user, get_jwt_token
from app.models.description import DescriptionRequest
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Generation Endpoint ---
@router.post("/description/generate")
async def generate_and_update_description(req: DescriptionRequest, current_user: dict = Depends(get_current_user)):
    profile = await get_user_profile_data(current_user.user.id)

    # 1. Check credits
    if profile.credits is None or profile.credits < 1:
        raise HTTPException(status_code=403, detail="Insufficient credits.")

    # 2. Get listing from Etsy to find its title
    listing = etsy_service.get_listing(profile.etsy_access_token, req.listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Etsy listing not found.")

    # 3. Generate description
    new_description = ai_service.generate_description(
        product_title=listing.get('title', ''),
        features=req.features,
        tone=req.tone
    )
    if not new_description:
        raise HTTPException(status_code=500, detail="Failed to generate description.")

    # 4. Update Etsy listing
    etsy_service.update_listing_description(
        access_token=profile.etsy_access_token,
        shop_id=profile.etsy_shop_id,
        listing_id=req.listing_id,
        description=new_description
    )

    # 5. Decrement credits
    supabase.table('profiles').update({'credits': profile.credits - 1}).eq('id', profile.id).execute()

    return {"description": new_description}