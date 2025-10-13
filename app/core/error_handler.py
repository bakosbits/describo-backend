"""
Error handling and sanitization module.
Prevents information disclosure by sanitizing error messages sent to clients.
"""
import logging
import traceback
from typing import Optional, Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorSanitizer:
    """Sanitize error messages to prevent information disclosure."""
    
    # Map sensitive error patterns to generic messages
    ERROR_MAPPINGS = {
        # Database errors
        "duplicate key": "This resource already exists",
        "foreign key": "Related resource not found",
        "constraint": "Data validation failed",
        "column": "Invalid data format",
        "table": "Resource not found",
        "database": "Service temporarily unavailable",
        "connection": "Service temporarily unavailable",
        "timeout": "Request timeout - please try again",
        
        # Authentication/Authorization errors
        "token": "Authentication failed",
        "jwt": "Authentication failed",
        "signature": "Authentication failed",
        "expired": "Session expired - please login again",
        "unauthorized": "Access denied",
        "forbidden": "Access denied",
        "permission": "Access denied",
        "role": "Access denied",
        
        # Supabase specific
        "supabase": "Service error - please try again",
        "rls": "Access denied",
        "policy": "Access denied",
        
        # File/Storage errors
        "file not found": "Resource not found",
        "no such file": "Resource not found",
        "blob": "Storage service error",
        "upload": "File upload failed",
        
        # API/Network errors
        "api": "External service error",
        "http": "Network error",
        "ssl": "Secure connection failed",
        "certificate": "Secure connection failed",
        
        # Sensitive information patterns
        "password": "Invalid credentials",
        "secret": "Configuration error",
        "key": "Configuration error",
        "credential": "Invalid credentials",
        "env": "Configuration error",
        
        # System errors
        "memory": "System resource error",
        "disk": "System resource error",
        "cpu": "System resource error",
        "process": "System error",
        "thread": "System error",
    }
    
    # Status code specific generic messages
    STATUS_MESSAGES = {
        400: "Invalid request",
        401: "Authentication required",
        403: "Access denied",
        404: "Resource not found",
        405: "Method not allowed",
        409: "Resource conflict",
        410: "Resource no longer available",
        422: "Invalid data provided",
        429: "Too many requests - please try again later",
        500: "An internal error occurred",
        502: "Service temporarily unavailable",
        503: "Service temporarily unavailable",
        504: "Request timeout",
    }
    
    @classmethod
    def sanitize(cls, error_message: str, status_code: int = 500) -> str:
        """
        Sanitize error message for client response.
        
        Args:
            error_message: The original error message
            status_code: HTTP status code
            
        Returns:
            Sanitized error message safe for client
        """
        # Convert to lowercase for pattern matching
        error_lower = error_message.lower()
        
        # Log the full error server-side with stack trace
        logger.error(f"Error {status_code}: {error_message}")
        if status_code >= 500:
            logger.error(f"Stack trace:\n{traceback.format_exc()}")
        
        # Check for sensitive patterns and return generic message
        for pattern, sanitized in cls.ERROR_MAPPINGS.items():
            if pattern in error_lower:
                logger.debug(f"Sanitized error containing '{pattern}' to '{sanitized}'")
                return sanitized
        
        # Return status code specific message
        if status_code in cls.STATUS_MESSAGES:
            return cls.STATUS_MESSAGES[status_code]
        
        # Generic fallback based on status code range
        if status_code >= 500:
            return "An internal error occurred. Please try again later."
        elif status_code >= 400:
            return "Invalid request"
        
        return "An error occurred processing your request"
    
    @classmethod
    def create_error_response(
        cls,
        request: Request,
        status_code: int,
        error: Exception,
        request_id: Optional[str] = None
    ) -> JSONResponse:
        """
        Create a sanitized error response.
        
        Args:
            request: The FastAPI request object
            status_code: HTTP status code
            error: The exception that occurred
            request_id: Optional request ID for tracking
            
        Returns:
            JSONResponse with sanitized error
        """
        # Generate request ID if not provided
        if not request_id:
            import uuid
            request_id = str(uuid.uuid4())
        
        # Log detailed error information
        logger.error(
            f"Request failed - ID: {request_id}, "
            f"Path: {request.url.path}, "
            f"Method: {request.method}, "
            f"Status: {status_code}, "
            f"Error: {str(error)}, "
            f"Type: {type(error).__name__}"
        )
        
        # Log request details for debugging (be careful with sensitive data)
        logger.debug(
            f"Request details - ID: {request_id}, "
            f"Headers: {dict(request.headers)}, "
            f"Client: {request.client.host if request.client else 'unknown'}"
        )
        
        # Sanitize the error message
        sanitized_message = cls.sanitize(str(error), status_code)
        
        # Create response
        response_content = {
            "error": {
                "message": sanitized_message,
                "status": status_code,
                "request_id": request_id
            }
        }
        
        # In development mode, include more details (but still sanitized)
        from app.core.config import settings
        if settings.debug and settings.environment == "development":
            response_content["error"]["type"] = type(error).__name__
            response_content["error"]["path"] = request.url.path
        
        return JSONResponse(
            status_code=status_code,
            content=response_content
        )


class ErrorLogger:
    """Centralized error logging with context."""
    
    @staticmethod
    def log_error(
        error: Exception,
        context: Dict[str, Any],
        level: str = "error"
    ) -> str:
        """
        Log error with context information.
        
        Args:
            error: The exception to log
            context: Additional context information
            level: Log level (debug, info, warning, error, critical)
            
        Returns:
            Error ID for reference
        """
        import uuid
        error_id = str(uuid.uuid4())
        
        log_message = (
            f"Error ID: {error_id}\n"
            f"Type: {type(error).__name__}\n"
            f"Message: {str(error)}\n"
            f"Context: {context}\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )
        
        # Log at appropriate level
        log_func = getattr(logger, level, logger.error)
        log_func(log_message)
        
        return error_id
    
    @staticmethod
    def log_security_event(
        event_type: str,
        details: Dict[str, Any],
        severity: str = "warning"
    ):
        """
        Log security-related events.
        
        Args:
            event_type: Type of security event
            details: Event details
            severity: Event severity (info, warning, critical)
        """
        log_message = (
            f"SECURITY EVENT - Type: {event_type}\n"
            f"Severity: {severity}\n"
            f"Details: {details}"
        )
        
        if severity == "critical":
            logger.critical(log_message)
        elif severity == "warning":
            logger.warning(log_message)
        else:
            logger.info(log_message)