import os
import json
import logging
from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response, status, UploadFile, File
from fastapi.responses import JSONResponse
from app.api.deps import get_current_user, get_jwt_token
from app.services.supabase_service import supabase_service
from app.services.stripe_service import StripeService
# from app.services.blob_storage import blob_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/export-data")
async def export_user_data(
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """
    Export all user data including profile, contracts, and analyses
    """
    try:
        user_id = current_user["user_id"]
        client = supabase_service.get_client(jwt_token)
        
        # Get user profile
        profile_response = client.table("profiles").select("*").eq("id", user_id).execute()
        profile = profile_response.data[0] if profile_response.data else {}
        
        # Get user contracts
        contracts_response = client.table("contracts").select("*").eq("user_id", user_id).execute()
        contracts = contracts_response.data or []
        
        # Get contract analyses for user's contracts (with risk factors)
        analytics = []
        if contracts:
            contract_ids = [contract['id'] for contract in contracts]
            # Query contract_analysis by contract_id (not user_id) and include risk_factors
            analytics_response = client.table("contract_analysis").select("*, risk_factors(*)").in_("contract_id", contract_ids).execute()
            analytics = analytics_response.data or []
        
        # Calculate total risk factors across all analyses
        total_risk_factors = sum(len(analysis.get('risk_factors', [])) for analysis in analytics)
    
        # Compile export data
        export_data = {
            "export_info": {
                "exported_at": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "export_version": "1.1"
            },
            "profile": profile,
            "contracts": contracts,
            "contract_analyses": analytics,
            "summary": {
                "total_contracts": len(contracts),
                "total_analyses": len(analytics),
                "total_risk_factors": total_risk_factors,
                "subscription_plan": profile.get("subscription_plan", "pro_hac_vice"),
                "member_since": profile.get("created_at")
            }
        }
        
        # Convert to JSON string
        json_data = json.dumps(export_data, indent=2, default=str)
        
        # Return as downloadable file
        return Response(
            content=json_data,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=contract-critic-data-{datetime.utcnow().strftime('%Y-%m-%d')}.json"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting user data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export data: {str(e)}")

@router.delete("/delete-account")
async def delete_user_account(
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """
    Permanently delete user account and all associated data
    """
    try:
        from supabase import create_client
        from app.core.config import settings
        
        stripe_service = StripeService()
        user_id = current_user["user_id"]
        
        # Use user JWT client for data operations (respects RLS)
        user_client = supabase_service.get_client(jwt_token)
        
        # Use service role client for admin operations
        service_client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key or settings.supabase_pub_key
        )
        
        logger.info(f"Starting account deletion for user {user_id}")
        
        # Get user profile to check for Stripe data (using user client)
        profile_response = user_client.table("profiles").select("*").eq("id", user_id).execute()
        profile = profile_response.data[0] if profile_response.data else {}
        
        # Cancel Stripe subscription if exists
        if profile.get("stripe_subscription_id"):
            try:
                stripe_service.cancel_subscription(profile["stripe_subscription_id"])
                logger.info(f"Cancelled Stripe subscription {profile['stripe_subscription_id']}")
            except Exception as e:
                logger.warning(f"Failed to cancel Stripe subscription: {str(e)}")
        
        # Delete Stripe customer if exists
        if profile.get("stripe_customer_id"):
            try:
                stripe_service.delete_customer(profile["stripe_customer_id"])
                logger.info(f"Deleted Stripe customer {profile['stripe_customer_id']}")
            except Exception as e:
                logger.warning(f"Failed to delete Stripe customer: {str(e)}")
        
        # Delete user data from Supabase tables (in order due to foreign key constraints)
        # Use user client for data operations to respect RLS policies
        
        # First get user's contracts to find related analyses
        contracts_response = user_client.table("contracts").select("id").eq("user_id", user_id).execute()
        contract_ids = [contract['id'] for contract in (contracts_response.data or [])]
        
        # Delete risk factors first (child of contract_analysis)
        if contract_ids:
            # Get analysis IDs for the user's contracts
            analyses_response = user_client.table("contract_analysis").select("id").in_("contract_id", contract_ids).execute()
            analysis_ids = [analysis['id'] for analysis in (analyses_response.data or [])]
            
            if analysis_ids:
                # Delete risk factors using service client to bypass RLS if needed
                try:
                    risk_factors_response = user_client.table("risk_factors").delete().in_("analysis_id", analysis_ids).execute()
                    logger.info(f"Deleted {len(risk_factors_response.data or [])} risk factor records")
                except Exception as e:
                    logger.warning(f"User client failed for risk factors, trying service client: {str(e)}")
                    risk_factors_response = service_client.table("risk_factors").delete().in_("analysis_id", analysis_ids).execute()
                    logger.info(f"Deleted {len(risk_factors_response.data or [])} risk factor records with service client")
            
            # Delete contract analyses
            try:
                analyses_delete_response = user_client.table("contract_analysis").delete().in_("contract_id", contract_ids).execute()
                logger.info(f"Deleted {len(analyses_delete_response.data or [])} contract analysis records")
            except Exception as e:
                logger.warning(f"User client failed for analyses, trying service client: {str(e)}")
                analyses_delete_response = service_client.table("contract_analysis").delete().in_("contract_id", contract_ids).execute()
                logger.info(f"Deleted {len(analyses_delete_response.data or [])} contract analysis records with service client")
        
        # Delete contracts
        try:
            contracts_delete_response = user_client.table("contracts").delete().eq("user_id", user_id).execute()
            logger.info(f"Deleted {len(contracts_delete_response.data or [])} contract records")
        except Exception as e:
            logger.warning(f"User client failed for contracts, trying service client: {str(e)}")
            contracts_delete_response = service_client.table("contracts").delete().eq("user_id", user_id).execute()
            logger.info(f"Deleted {len(contracts_delete_response.data or [])} contract records with service client")
        
        # Delete profile
        try:
            profile_delete_response = user_client.table("profiles").delete().eq("id", user_id).execute()
            logger.info(f"Deleted profile for user {user_id}")
        except Exception as e:
            logger.warning(f"User client failed for profile, trying service client: {str(e)}")
            profile_delete_response = service_client.table("profiles").delete().eq("id", user_id).execute()
            logger.info(f"Deleted profile for user {user_id} with service client")
        
        # Delete auth user using service client (requires admin privileges)
        try:
            auth_response = service_client.auth.admin.delete_user(user_id)
            logger.info(f"Deleted auth user {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete auth user {user_id}: {str(e)}")
            # Don't fail the entire operation if auth deletion fails
            # The user data has been cleaned up, which is the most important part
            logger.warning("Auth user deletion failed, but user data has been cleaned up")
        
        return JSONResponse(
            content={
                "success": True,                
                "message": "Account successfully deleted",
                "deleted_at": datetime.utcnow().isoformat()
            },
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Error deleting user account: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")

@router.get("/profile", response_model=Dict[str, Any])
async def get_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """Retrieve user profile."""
    user_id = current_user.get('user_id')
    logger.info(f"Getting user profile for user_id: {user_id}")
    
    try:
        # Get user data from public.profiles table
        client = supabase_service.get_client(jwt_token)
        
        # Query the profiles table (RLS will ensure user can only access their own profile)
        response = client.table("profiles").select("*").eq("id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            profile = response.data[0]
            
            # Return profile data including terms fields
            profile_data = {
                'user_id': profile['id'],
                'first_name': profile.get('first_name'),
                'last_name': profile.get('last_name'),
                'email': profile.get('email'),
                'phone': profile.get('phone'),
                'created_at': profile.get('created_at'),
                'subscription_satus': profile.get('subscription_status'),
                'subscription_plan': profile.get('subscription_plan'),
                'stripe_customer_id': profile.get('stripe_customer_id'),
                'updated_at': profile.get('updated_at'),
                'terms_accepted_at': profile.get('terms_accepted_at'),
                'terms_version': profile.get('terms_version')
            }
            
            logger.info(f"Successfully retrieved user profile for user_id: {user_id}")
            return {"success": True, "data": profile_data}
        else:
            logger.warning(f"No profile found for user_id: {user_id}")
            # Return basic user data as fallback
            fallback_data = {
                'user_id': user_id,
                'first_name': None,
                'last_name': None,
                'email': current_user.get('email'),
                'phone': None
            }
            return {"success": True, "data": fallback_data}
            
    except Exception as e:
        logger.error(f"Error in get_user_profile for user_id: {user_id}. Error: {e}", exc_info=True)
        # Fallback to basic current_user data
        fallback_data = {
            'user_id': user_id,
            'first_name': None,
            'last_name': None,
            'email': current_user.get('email'),
            'phone': None
        }
        return {"success": True, "data": fallback_data}

@router.get("/stats", response_model=Dict[str, Any])
async def get_user_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """Retrieve user statistics."""
    user_id = current_user.get('user_id')
    logger.info(f"Fetching user stats for user_id: {user_id}")
    
    try:
        # Get user stats from Supabase
        stats = supabase_service.get_user_stats(user_id, jwt_token)
        
        if stats is None:
            logger.error(f"Failed to fetch user stats for user_id: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch user statistics"
            )
        
        logger.info(f"User stats fetched successfully for user_id: {user_id}")
        return {"success": True, "data": stats}
        
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching user stats for user_id: {user_id}. Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching user statistics"
        )

@router.post("/reset-analyses")
async def reset_monthly_analyses(
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """
    Reset monthly analysis count (for testing or manual reset)
    """
    try:
        client = supabase_service.get_client(jwt_token)
        
        # Call the database function to reset analyses
        response = client.rpc("reset_monthly_analyses").execute()
        
        return JSONResponse(
            content={
                "success": True,
                "message": "Monthly analyses reset successfully"
            },
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Error resetting monthly analyses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reset analyses: {str(e)}")

@router.post("/check-analysis-limit")
async def check_analysis_limit(
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """
    Check if user can perform another analysis and decrement count if allowed
    """
    try:
        client = supabase_service.get_client(jwt_token)
        
        # Call the database function to check and decrement
        response = client.rpc("decrement_analysis_count").execute()
        
        can_analyze = response.data if response.data is not None else False
        
        if can_analyze:
            return JSONResponse(
                content={
                    "success": True,
                    "can_analyze": True,
                    "message": "Analysis allowed"
                },
                status_code=200
            )
        else:
            return JSONResponse(
                content={
                    "success": False,
                    "can_analyze": False,
                    "message": "Analysis limit reached for current billing period"
                },
                status_code=403
            )
        
    except Exception as e:
        logger.error(f"Error checking analysis limit: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check analysis limit: {str(e)}")

@router.post("/create-profile")
async def create_profile(
    profile_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """
    Create user profile in the profiles table
    """
    try:
        user_id = current_user["user_id"]
        client = supabase_service.get_client(jwt_token)
        
        logger.info(f"Creating profile for user {user_id}")
        
        # Add user_id to the profile data
        profile_data["user_id"] = user_id
        
        # Ensure email is set
        if not profile_data.get("email"):
            profile_data["email"] = current_user.get("email")
        
        response = client.table("profiles").insert(profile_data).execute()
        
        if response.data:
            logger.info(f"Profile created successfully for user {user_id}")
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Profile created successfully",
                    "profile": response.data[0]
                },
                status_code=201
            )
        else:
            logger.error(f"Failed to create profile for user {user_id}")
            raise HTTPException(status_code=500, detail="Failed to create profile")
        
    except Exception as e:
        logger.error(f"Error creating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create profile: {str(e)}")

@router.post("/accept-terms")
async def accept_terms(
    terms_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """
    Update user's terms acceptance status
    """
    try:
        user_id = current_user["user_id"]
        client = supabase_service.get_client(jwt_token)
        
        logger.info(f"Updating terms acceptance for user {user_id}")
        
        # Update profile with terms acceptance
        update_data = {
            "terms_accepted_at": terms_data.get("accepted_at", datetime.utcnow().isoformat()),
            "terms_version": terms_data.get("terms_version", "1.0"),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        response = client.table("profiles").update(update_data).eq("id", user_id).execute()
        
        if response.data:
            logger.info(f"Terms acceptance updated successfully for user {user_id}")
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Terms accepted successfully",
                    "terms_version": update_data["terms_version"]
                },
                status_code=200
            )
        else:
            logger.error(f"Failed to update terms acceptance for user {user_id}")
            raise HTTPException(status_code=500, detail="Failed to update terms acceptance")
        
    except Exception as e:
        logger.error(f"Error updating terms acceptance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update terms acceptance: {str(e)}")

@router.post("/update-display-name")
async def update_display_name(
    display_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """
    Update user's display name in Supabase auth metadata
    """
    try:
        user_id = current_user["user_id"]
        display_name = display_data.get("display_name", "")
        
        logger.info(f"Updating display name for user {user_id} to: {display_name}")
        
        # Update the auth user metadata using service role
        from supabase import create_client
        from app.core.config import settings
        
        service_client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key or settings.supabase_pub_key
        )
        
        # Update user metadata
        response = service_client.auth.admin.update_user_by_id(
            user_id,
            {"user_metadata": {"display_name": display_name}}
        )
        
        if response:
            logger.info(f"Display name updated successfully for user {user_id}")
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Display name updated successfully"
                },
                status_code=200
            )
        else:
            logger.error(f"Failed to update display name for user {user_id}")
            raise HTTPException(status_code=500, detail="Failed to update display name")
            
    except Exception as e:
        logger.error(f"Error updating display name: {str(e)}")
        # Don't fail the whole profile update if display name update fails
        return JSONResponse(
            content={
                "success": False,
                "message": f"Display name update failed: {str(e)}"
            },
            status_code=200  # Return 200 to not break the profile update flow
        )

@router.post("/create-stripe-customer")
async def create_stripe_customer(
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """
    Create Stripe customer for the user
    """
    try:
        logger.info("Creating Stripe customer for user")
        stripe_service = StripeService()
        user_id = current_user["user_id"]
        client = supabase_service.get_client(jwt_token)
        
        logger.info(f"Creating Stripe customer for user {user_id}")
        
        # Get user profile for customer creation
        profile_response = client.table("profiles").select("*").eq("id", user_id).execute()
        
        if not profile_response.data:
            logger.warning(f"No profile found for user {user_id}, using basic info")
            # Create Stripe customer with basic info
            stripe_customer_id = await stripe_service.create_stripe_customer(
                user_id=user_id,
                email=current_user.get("email"),
                user_jwt=jwt_token
            )
        else:
            profile = profile_response.data[0]
            # Create Stripe customer with profile info
            stripe_customer_id = await stripe_service.create_stripe_customer(
                user_id=user_id,
                email=profile.get("email", current_user.get("email")),
                first_name=profile.get('first_name'),
                last_name=profile.get('last_name'),
                user_jwt=jwt_token
            )
        
        
        if stripe_customer_id:
            
            logger.info(f"Stripe customer created successfully for user {user_id}: {stripe_customer_id}")
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Stripe customer created successfully",
                    "customer_id": stripe_customer_id
                },
                status_code=201
            )
        else:
            logger.error(f"Failed to create Stripe customer for user {user_id}")
            raise HTTPException(status_code=500, detail="Failed to create Stripe customer")
        
    except Exception as e:
        logger.error(f"Error creating Stripe customer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create Stripe customer: {str(e)}")

@router.post("/upload-avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """
    Upload user avatar image
    """
    try:
        user_id = current_user["user_id"]
        
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Validate file size (5MB limit)
        file_content = await file.read()
        if len(file_content) > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(status_code=400, detail="File size must be less than 5MB")
        
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            raise HTTPException(status_code=400, detail="Unsupported file format. Use JPG, PNG, GIF, or WebP")
        
        unique_filename = f"avatar_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{file_extension}"
        
        # Upload to blob storage
        blob_result = blob_service.upload_file_sync(
            file_content,
            unique_filename,
            file.content_type,
            user_id=user_id
        )
        
        if not blob_result:
            raise HTTPException(status_code=500, detail="Failed to upload avatar to storage")
        
        # Update user profile with new avatar URL
        client = supabase_service.get_client(jwt_token)
        update_response = client.table("profiles").update({
            "avatar_url": blob_result['url'],
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", user_id).execute()
        
        if not update_response.data:
            # Clean up uploaded file if profile update failed
            try:
                blob_service.delete_file_sync(blob_result['url'])
            except:
                pass
            raise HTTPException(status_code=500, detail="Failed to update profile with avatar")
        
        logger.info(f"Avatar uploaded successfully for user {user_id}: {blob_result['url']}")
        
        return JSONResponse(
            content={
                "success": True,
                "message": "Avatar uploaded successfully",
                "avatar_url": blob_result['url']
            },
            status_code=200
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading avatar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload avatar: {str(e)}")



# # --- Authentication & User Profile ---
# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     try:
#         user = supabase.auth.get_user(token)
#         if not user: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user credentials")
#         return user
#     except Exception:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

# async def get_user_profile_data(user_id: str) -> UserProfile:
#     res = supabase.table('profiles').select('*').eq('id', user_id).execute()
#     if not res.data: raise HTTPException(status_code=404, detail="Profile not found")
#     return UserProfile(**res.data[0])

# # --- State Token for OAuth ---
# def create_state_token(user_id: str) -> str:
#     payload = {'exp': datetime.utcnow() + timedelta(minutes=15), 'iat': datetime.utcnow(), 'sub': user_id}
#     return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# def verify_state_token(token: str) -> str:
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
#         return payload['sub']
#     except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
#         raise HTTPException(status_code=400, detail="Invalid or expired state token.")