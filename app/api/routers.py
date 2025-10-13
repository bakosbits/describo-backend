from fastapi import APIRouter, Depends, HTTPException, Request, Header
import stripe
import logging
from typing import Optional

from app.core.config import settings
from app.models.subscription import WebhookResponse
from app.services.stripe_service import stripe_service
from app.api.endpoints import billing, users, descriptions, etsy

logger = logging.getLogger(__name__)

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(descriptions.router, tags=["descriptions"])
api_router.include_router(etsy.router, prefix="/etsy", tags=["etsy"])

