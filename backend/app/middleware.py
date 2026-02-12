from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from typing import Callable
from app.config import settings

logger = logging.getLogger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """Custom security middleware for logging and basic protection."""
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Log all incoming requests
        logger.info(
            f"Request: {request.method} {request.url} from {request.client.host} "
            f"User-Agent: {request.headers.get('user-agent', 'unknown')}"
        )
        
        # Process the request
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response

async def validate_extension_headers(request: Request) -> dict:
    """
    Validate required extension headers and origin.
    This dependency ensures requests come from the authorized extension.
    """
    # Log request details for security monitoring
    user_agent = request.headers.get("user-agent", "unknown")
    logger.info(f"Request from {request.client.host}, User-Agent: {user_agent}")
    
    # Check required extension client header
    client_header = request.headers.get("X-Extension-Client")
    if client_header != settings.EXTENSION_CLIENT_HEADER:
        logger.warning(
            f"Invalid or missing X-Extension-Client header from {request.client.host}. "
            f"Expected: {settings.EXTENSION_CLIENT_HEADER}, Got: {client_header}"
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid extension client header"
        )
    
    # Validate origin for extension requests
    origin = request.headers.get("origin")
    if settings.ALLOWED_ORIGIN != "*" and origin != settings.ALLOWED_ORIGIN:
        logger.warning(
            f"Invalid origin from {request.client.host}. "
            f"Expected: {settings.ALLOWED_ORIGIN}, Got: {origin}, UA: {user_agent}"
        )
        raise HTTPException(
            status_code=403,
            detail="Invalid origin"
        )
    
    # Log successful validation
    logger.info(f"Extension headers validated for {request.client.host}")
    
    return {
        "client_header": client_header,
        "origin": origin,
        "user_agent": user_agent,
        "validated": True
    }
