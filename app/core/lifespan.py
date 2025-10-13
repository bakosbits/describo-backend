import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routers import api_router
from app.core.security import get_jwks
from app.core.config import settings
from app.core.security_headers import SecurityHeadersMiddleware, SecurityHeadersConfig

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Code to run on STARTUP ---

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout, # Direct logs to standard output
    )

    # Pre-fetch and cache the Supabase JWKS
    logger.info("Application startup:")
    logger.info("Pre-fetching Supabase JWKS")
    try:
        get_jwks()
        logger.info("Supabase JWKS successfully fetched and cached.")
        
    except Exception as e:
        # If we can't get the keys, the app is insecure and should not start.
        logger.critical(f"CRITICAL: Failed to fetch Supabase JWKS on startup. Application cannot start. Error: {e}")
        # Raising an exception here will stop the FastAPI server from starting.
        raise RuntimeError("Failed to fetch JWKS on startup.")    
    

    # API routes
    logger.info("Registering API routes...")
    app.include_router(api_router, prefix="/api")
    logger.info("API routes registered successfully")

    # Debug: Print all registered routes
    if settings.debug: # Only print routes in debug mode
        logger.info("=== Registered Routes ===")
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                logger.info(f"{list(route.methods)} {route.path}")
        logger.info("========================")


    # Static file serving (for frontend)
    logger.info("Configuring static directory")
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")



    # Application startup with security validation.
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # Security configuration validation
    logger.info("Validating security configuration...")
    
    # Security Headers middleware
    if settings.enable_security_headers:
        # First, determine the frontend_domain based on the environment
        frontend_domain = settings.frontend_domain
        if not frontend_domain:
            if settings.environment == "production":
                frontend_domain = "https://www.describo.com" # Your actual production domain
            else: # development
                frontend_domain = "http://localhost:3000" # Frontend dev server

        # Next, get the base security config for the environment
        if settings.environment == "production":
            security_config = SecurityHeadersConfig.get_production_config(frontend_domain)
        else: # development
            security_config = SecurityHeadersConfig.get_development_config()

        # Finally, apply any specific overrides from the settings
        security_config.update({
            "enable_hsts": settings.enable_hsts,
            "hsts_max_age": settings.hsts_max_age,
            "enable_csp": settings.enable_csp,
            "csp_report_uri": settings.csp_report_uri,
        })

        logger.info(f"Security headers middleware enabled for '{settings.environment}' environment")
    else:
        logger.warning("Security headers middleware is disabled")

    # Check critical security settings
    security_checks = []
    
    # Supabase configuration validation
    if not settings.supabase_url:
        security_checks.append("❌ CRITICAL: supabase url is not configured")
    elif not settings.supabase_url.startswith("https://"):
        security_checks.append("⚠️  WARNING: supabase urlshould use HTTPS")
    else:
        security_checks.append("✅ supabase url is properly configured")
    
    # Supabase secret key
    if not settings.supabase_secret_key:
        security_checks.append("❌ CRITICAL: supabase_secret_key is not configured")
    elif len(settings.supabase_secret_key) < 32:
        security_checks.append("❌ CRITICAL: supabase_secret_key is too short (minimum 32 characters)")
    else:
        security_checks.append("✅ supabase_secret_key is properly configured")
        
    # Supabase publishable key
    if not settings.supabase_pub_key:
        security_checks.append("❌ CRITICAL: supabase pub key is not configured")
    else:
        security_checks.append("✅ supabase pub key is configured")
    
    # Log all security checks
    logger.info("Security Configuration Status:")
    for check in security_checks:
        logger.info(f"{check}")
    
    # Fail fast if critical security issues exist
    critical_issues = [check for check in security_checks if "❌ CRITICAL" in check]
    if critical_issues:
        logger.critical("CRITICAL SECURITY ISSUES DETECTED - APPLICATION CANNOT START")
        for issue in critical_issues:
            logger.critical(issue)
        raise RuntimeError(
            "Critical security configuration issues detected. "
            "Please configure all required environment variables before starting the application."
        )
    
    # Warn about non-critical issues
    warnings = [check for check in security_checks if "⚠️  WARNING" in check]
    if warnings:
        logger.warning("Security warnings detected:")
        for warning in warnings:
            logger.warning(warning)
    
    logger.info(f"CORS origins: {settings.cors_origins}")
    
    logger.info("Application started successfully with secure configuration ✅")
    
    yield
    
    # --- Code to run on SHUTDOWN ---
    logger.info("Application shutdown.")