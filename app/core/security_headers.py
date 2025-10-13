import secrets
from typing import Dict, List, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all HTTP responses.
    
    Protects against:
    - XSS attacks (Content Security Policy)
    - Clickjacking (X-Frame-Options)
    - MIME type sniffing (X-Content-Type-Options)
    - Information leakage (Referrer-Policy)
    - Protocol downgrade attacks (HSTS)
    - Feature abuse (Permissions-Policy)
    """
    
    def __init__(
        self,
        app: ASGIApp,
        environment: str = "production",
        frontend_domain: Optional[str] = None,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1 year
        enable_csp: bool = True,
        csp_report_uri: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None
    ):
        super().__init__(app)
        self.environment = environment
        self.frontend_domain = frontend_domain or "https://describo.com"
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.enable_csp = enable_csp
        self.csp_report_uri = csp_report_uri
        self.custom_headers = custom_headers or {}
        
        # Generate nonce for inline scripts/styles if needed
        self.nonce = secrets.token_urlsafe(16)
        
        logger.info(f"Security headers middleware initialized for {environment} environment")
    
    async def dispatch(self, request: Request, call_next):
        """Process request and add security headers to response."""
        response = await call_next(request)
        
        # Add security headers
        self._add_security_headers(response, request)
        
        return response
    
    def _add_security_headers(self, response: Response, request: Request):
        """Add all security headers to the response."""
        
        # Content Security Policy
        if self.enable_csp:
            csp_header = self._build_csp_header(request)
            response.headers["Content-Security-Policy"] = csp_header
        
        # X-Frame-Options - Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # X-Content-Type-Options - Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Referrer Policy - Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # X-XSS-Protection - Legacy XSS protection for older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Permissions Policy - Control browser features
        permissions_policy = self._build_permissions_policy()
        response.headers["Permissions-Policy"] = permissions_policy
        
        # Cross-Origin Policies
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if self.environment != "development":
            response.headers["Cross-Origin-Opener-Policy"] = "same-origin"   

        # Strict Transport Security (HSTS) - Only for HTTPS
        if self.enable_hsts and self._is_https_request(request):
            hsts_header = f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            response.headers["Strict-Transport-Security"] = hsts_header
        
        # Server header removal/modification
        response.headers["Server"] = "Describo"
        
        # Add custom headers if provided
        for header_name, header_value in self.custom_headers.items():
            response.headers[header_name] = header_value
        
        # Cache control for sensitive endpoints
        if self._is_sensitive_endpoint(request):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    
    def _build_csp_header(self, request: Request) -> str:
        """Build Content Security Policy header based on environment."""
        
        # Base CSP directives
        csp_directives = {
            "default-src": ["'self'"],
            "script-src": self._get_script_src_policy(),
            "style-src": self._get_style_src_policy(),
            "img-src": self._get_img_src_policy(),
            "font-src": self._get_font_src_policy(),
            "connect-src": self._get_connect_src_policy(),
            "frame-src": ["'none'"],
            "object-src": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            "frame-ancestors": ["'none'"],
            "upgrade-insecure-requests": [] if self.environment != "development" else None

        }
        
        # Add report URI if configured
        if self.csp_report_uri:
            csp_directives["report-uri"] = [self.csp_report_uri]
        
        # Build CSP string
        csp_parts = []
        for directive, sources in csp_directives.items():
            if sources:
                csp_parts.append(f"{directive} {' '.join(sources)}")
            else:
                csp_parts.append(directive)
        
        return "; ".join(csp_parts)
    
    def _get_script_src_policy(self) -> List[str]:
        """Get script-src policy based on environment."""
        if self.environment == "development":
            return [
                "'self'",
                "'unsafe-inline'",  # Allow for development
                "'unsafe-eval'",    # Allow for development
                "https://cdn.jsdelivr.net",
                "https://unpkg.com"
            ]
        else:
            return [
                "'self'",
                f"'nonce-{self.nonce}'",  # Use nonce for inline scripts
                "https://cdn.jsdelivr.net",
                "https://unpkg.com"
            ]
    
    def _get_style_src_policy(self) -> List[str]:
        """Get style-src policy."""
        return [
            "'self'",
            "'unsafe-inline'",  # Often needed for CSS frameworks
            "https://fonts.googleapis.com",
            "https://cdn.jsdelivr.net"
        ]
    
    def _get_img_src_policy(self) -> List[str]:
        """Get img-src policy."""
        return [
            "'self'",
            "data:",  # Allow data URLs for images
            "https:",  # Allow HTTPS images
            "blob:"   # Allow blob URLs for uploaded images
        ]
    
    def _get_font_src_policy(self) -> List[str]:
        """Get font-src policy."""
        return [
            "'self'",
            "https://fonts.gstatic.com",
            "https://cdn.jsdelivr.net",
            "data:"
        ]
    
    def _get_connect_src_policy(self) -> List[str]:
        """Get connect-src policy for API calls."""
        connect_sources = [
            "'self'",
            "https://cdn.jsdelivr.net",  # This is already there!
            "https://api.openrouter.ai",
            "https://api.openrouter.ai",  # OpenRouter API
            "https://openrouter.ai",
            "https://*.supabase.co",      # Supabase
            "wss://*.supabase.co",        # Supabase WebSocket
        ]
        
        # Add frontend domain for CORS
        if self.frontend_domain:
            connect_sources.append(self.frontend_domain)
        
        # Add Vercel domains
        connect_sources.extend([
            "https://*.vercel.app",
            "https://vercel.com"
        ])
        
        return connect_sources
    
    def _build_permissions_policy(self) -> str:
        """Build Permissions Policy header."""
        policies = [
            "camera=()",           # Disable camera
            "microphone=()",       # Disable microphone
            "geolocation=()",      # Disable geolocation
            "payment=()",          # Disable payment API
            "usb=()",             # Disable USB API
            "magnetometer=()",     # Disable magnetometer
            "accelerometer=()",    # Disable accelerometer
            "gyroscope=()",       # Disable gyroscope
            "clipboard-write=(self)",  # Allow clipboard write for same origin
            "fullscreen=(self)"   # Allow fullscreen for same origin
        ]
        
        return ", ".join(policies)
    
    def _is_https_request(self, request: Request) -> bool:
        """Check if request is over HTTPS."""
        # Check various headers that indicate HTTPS
        return (
            request.url.scheme == "https" or
            request.headers.get("x-forwarded-proto") == "https" or
            request.headers.get("x-forwarded-ssl") == "on" or
            request.headers.get("x-url-scheme") == "https"
        )
    
    def _is_sensitive_endpoint(self, request: Request) -> bool:
        """Check if endpoint contains sensitive data."""
        sensitive_paths = [
            "/api/billing",
            "/api/descriptions",
            "/api/etsy",
            "/api/users",
            "/api/webhooks"
        ]
        
        path = request.url.path.lower()
        return any(sensitive_path in path for sensitive_path in sensitive_paths)


class SecurityHeadersConfig:
    """Configuration class for security headers."""
    
    @staticmethod
    def get_production_config(frontend_domain: str) -> Dict:
        """Get production security headers configuration."""
        return {
            "environment": "production",
            "frontend_domain": frontend_domain,
            "enable_hsts": True,
            "hsts_max_age": 31536000,  # 1 year
            "enable_csp": True,
            "csp_report_uri": None,  # Add your CSP report endpoint if available
            "custom_headers": {
                "X-Robots-Tag": "noindex, nofollow",  # Prevent indexing of API
            }
        }
    
    @staticmethod
    def get_development_config() -> Dict:
        """Get development security headers configuration."""
        return {
            "environment": "development",
            "frontend_domain": "http://192.168.1.134:5173",  # Vite dev server
            "enable_hsts": False,  # No HSTS for local development
            "enable_csp": False,
            "csp_report_uri": None,
            "custom_headers": {}
        }
    