import os
import logging
from app.core.config import settings
from supabase import create_client, Client
from supabase.client import ClientOptions
from typing import Dict, Any, List


logger = logging.getLogger(__name__)


class SupabaseService:

    def __init__(self):

        self.url = settings.supabase_url
        self.secret_key = settings.supabase_secret_key

    def get_service_client(self) -> Client:
        """Create a service client with elevated permissions for system operations (webhooks, etc.)"""
        try:
            
            client = create_client(self.url, self.secret_key)
            return client

        except Exception as e:
            logger.error(f"Failed to create Supabase service client: {str(e)}")
            raise
    

    def get_client(self, user_jwt_token: str) -> Client:
        """Create a client using the user's JWT token for all operations"""
        try:
            # Create client with proper JWT authentication using ClientOptions
            # This ensures RLS policies work correctly
            options = ClientOptions(
                headers={"Authorization": f"Bearer {user_jwt_token}"} if user_jwt_token else {},
                auto_refresh_token=False  # Frontend handles token refresh
            )
            
            client = create_client(self.url, self.secret_key, options=options)
            return client
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {str(e)}")
            raise

# Global instance
supabase_service = SupabaseService()            