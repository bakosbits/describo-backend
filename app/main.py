import logging
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.exceptions import RequestValidationError
from app.core.lifespan import lifespan
from app.core.config import settings
from app.core.exceptions import (
    DescriboException,
    Describo_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from app.core.security_headers import SecurityHeadersMiddleware, SecurityHeadersConfig

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FastAPI backend for Describo",
    lifespan=lifespan,
    debug=settings.debug,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_hosts,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=settings.enable_hsts,
    hsts_max_age=settings.hsts_max_age,
    enable_csp=settings.enable_csp,
    csp_report_uri=settings.csp_report_uri
)

# Exception handlers
app.add_exception_handler(DescriboException, Describo_exception_handler)
app.add_exception_handler(Exception, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

@app.get("/")
async def serve_frontend():
    """Serve the frontend application."""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "index.html")
    
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return {"message": "Describo API is running", "version": settings.app_version}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": "development" if settings.debug else "production"
    }


@app.get("/{path:path}")
async def serve_frontend_routes(path: str):
    # Don't intercept API routes or FastAPI built-in endpoints
    if path.startswith("api/") or path in ["openapi.json", "docs", "redoc"]:
        return {"error": "API endpoint not found", "path": path}
    
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    file_path = os.path.join(static_dir, path)
    index_path = os.path.join(static_dir, "index.html")
    
    # If the file exists, serve it
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    # Otherwise, serve index.html for SPA routing
    elif os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return {"error": "File not found", "path": path}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )


