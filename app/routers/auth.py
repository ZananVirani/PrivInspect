from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta
import logging
from app.config import settings
from app.middleware import validate_extension_headers

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

def create_jwt_token() -> str:
    """Create a JWT token with 15-minute expiry using the current JWT secret."""
    expiry = datetime.now() + timedelta(minutes=15)
    payload = {
        "exp": expiry,
        "iat": datetime.now(),
        "type": "access_token",
        "secret_version": "current"  # Track which secret was used
    }
    
    # Always use the current (primary) JWT secret for new tokens
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Verify and decode JWT token with graceful secret rotation support.
    Tries current secret first, then falls back to old secrets for grace period.
    """
    token = credentials.credentials
    jwt_secrets = settings.get_jwt_secrets()
    
    # Try each secret in order (current first, then old secrets)
    for i, secret in enumerate(jwt_secrets):
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            
            # Log which secret was used for monitoring
            secret_type = "current" if i == 0 else "old"
            if i > 0:  # Only log when using old secret
                logger.info(f"JWT token verified using {secret_type} secret")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            # Token expired - this is the same regardless of which secret
            logger.warning("JWT token expired")
            raise HTTPException(status_code=401, detail="Token expired")
            
        except jwt.InvalidTokenError:
            # Try next secret if available
            continue
    
    # If we get here, token couldn't be verified with any secret
    logger.warning("JWT token invalid - could not verify with current or old secret")
    raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/auth")
async def authenticate(
    request: Request,
    _: dict = Depends(validate_extension_headers)
):
    """
    Issue a short-lived JWT token for authenticated extension clients.
    Requires valid extension headers and origin.
    """
    try:
        token = create_jwt_token()
        
        logger.info(
            f"JWT token issued for IP: {request.client.host}, "
            f"User-Agent: {request.headers.get('user-agent', 'unknown')}"
        )
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 900  # 15 minutes in seconds
        }
    
    except Exception as e:
        logger.error(f"Error issuing JWT token: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error"
        )
