from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Union
import logging
from .error_handler import ErrorSanitizer, ErrorLogger

logger = logging.getLogger(__name__)


class DescriboException(Exception):
    """Base exception for Describo application."""
    
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(DescriboException):
    """Authentication related errors."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(DescriboException):
    """Authorization related errors."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class NotFoundError(DescriboException):
    """Resource not found errors."""
    
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class ValidationError(DescriboException):
    """Validation related errors."""
    
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class FileUploadError(DescriboException):
    """File upload related errors."""
    
    def __init__(self, message: str = "File upload failed"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class ExternalServiceError(DescriboException):
    """External service related errors."""
    
    def __init__(self, message: str = "External service error"):
        super().__init__(message, status.HTTP_502_BAD_GATEWAY)


async def Describo_exception_handler(
    request: Request, 
    exc: DescriboException
) -> JSONResponse:
    """Handle custom Describo exceptions with sanitization."""
    # Log the full error details server-side
    error_id = ErrorLogger.log_error(
        exc,
        context={
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else "unknown"
        }
    )
    
    # Sanitize the error message for the client
    sanitized_message = ErrorSanitizer.sanitize(exc.message, exc.status_code)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": sanitized_message,
            "status_code": exc.status_code,
            "error_id": error_id
        }
    )


async def http_exception_handler(
    request: Request, 
    exc: HTTPException
) -> JSONResponse:
    """Handle FastAPI HTTP exceptions with sanitization."""
    # Generate error ID for tracking
    import uuid
    error_id = str(uuid.uuid4())
    
    # Log the full error details to console (captured by Vercel)
    logger.error(f"[ERROR_ID: {error_id}] HTTP Exception")
    logger.error(f"  Status: {exc.status_code}")
    logger.error(f"  Detail: {exc.detail}")
    logger.error(f"  Path: {request.url.path}")
    logger.error(f"  Method: {request.method}")
    logger.error(f"  Client: {request.client.host if request.client else 'unknown'}")
    
    # Sanitize the error message for the client
    sanitized_message = ErrorSanitizer.sanitize(str(exc.detail), exc.status_code)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": sanitized_message,
            "status_code": exc.status_code,
            "error_id": error_id
        }
    )


async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors with sanitization."""
    # Generate error ID for tracking
    import uuid
    error_id = str(uuid.uuid4())
    
    # Log the full validation errors to console (captured by Vercel)
    logger.warning(f"[ERROR_ID: {error_id}] Validation Error")
    logger.warning(f"  Path: {request.url.path}")
    logger.warning(f"  Method: {request.method}")
    logger.warning(f"  Errors: {exc.errors()}")
    
    # Sanitize validation errors - only show field names, not values
    sanitized_errors = []
    for error in exc.errors():
        # Extract field path without exposing actual values
        field_path = " -> ".join(str(loc) for loc in error["loc"] if loc != "body")
        
        # Sanitize the error message to avoid exposing sensitive data
        error_msg = error['msg']
        # Remove any actual values from error messages
        if "value is not a valid" in error_msg:
            error_msg = "Invalid value format"
        elif "ensure this value" in error_msg:
            error_msg = "Value does not meet requirements"
        
        if field_path:
            sanitized_errors.append(f"{field_path}: {error_msg}")
        else:
            sanitized_errors.append(error_msg)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Invalid data provided",
            "details": sanitized_errors[:5],  # Limit to 5 errors to prevent info leakage
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "error_id": error_id
        }
    )


async def general_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions with sanitization."""
    # Generate error ID for tracking
    import uuid
    error_id = str(uuid.uuid4())
    
    # Log the full error details to console (captured by Vercel)
    logger.critical(f"[ERROR_ID: {error_id}] UNEXPECTED ERROR")
    logger.critical(f"  Type: {type(exc).__name__}")
    logger.critical(f"  Message: {str(exc)}")
    logger.critical(f"  Path: {request.url.path}")
    logger.critical(f"  Method: {request.method}")
    logger.critical(f"  Client: {request.client.host if request.client else 'unknown'}")
    
    # Log full stack trace for debugging
    import traceback
    logger.critical(f"  Stack trace:\n{traceback.format_exc()}")
    
    # Always return generic message for unexpected errors
    sanitized_message = "An internal error occurred. Please try again later."
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": sanitized_message,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "error_id": error_id
        }
    )