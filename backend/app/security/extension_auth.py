"""
Enhanced security measures for browser extension authentication.
Implements multiple layers of protection against request replay attacks.
"""

import hashlib
import hmac
import time
import uuid
from typing import Optional, Dict, Any
from fastapi import HTTPException, Request
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class ExtensionAuthenticator:
    """Advanced authentication specifically designed for browser extensions."""
    
    def __init__(self):
        self.nonce_store = {}  # In production, use Redis with TTL
        self.nonce_ttl = 300  # 5 minutes
        
    def generate_challenge_response(self, extension_id: str, timestamp: int) -> str:
        """
        Generate a challenge-response based on extension ID and timestamp.
        This creates a unique signature that's hard to replay.
        """
        # Create a message from extension ID, timestamp, and server secret
        message = f"{extension_id}:{timestamp}:{settings.JWT_SECRET}"
        
        # Generate HMAC signature
        signature = hmac.new(
            settings.JWT_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_challenge_response(self, extension_id: str, timestamp: int, signature: str) -> bool:
        """
        Verify the challenge-response signature.
        Prevents replay attacks by checking timestamp freshness.
        """
        # Check timestamp freshness (prevent replay attacks)
        current_time = int(time.time())
        if abs(current_time - timestamp) > 30:  # 30 second window
            logger.warning(f"Timestamp too old/future: {timestamp} vs {current_time}")
            return False
        
        # Verify signature
        expected_signature = self.generate_challenge_response(extension_id, timestamp)
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(signature, expected_signature)
    
    def generate_request_nonce(self) -> str:
        """Generate a unique nonce for each request."""
        return str(uuid.uuid4())
    
    def validate_nonce(self, nonce: str) -> bool:
        """
        Validate and consume a nonce (prevents replay attacks).
        Each nonce can only be used once.
        """
        current_time = time.time()
        
        # Clean up expired nonces
        expired_nonces = [
            n for n, timestamp in self.nonce_store.items()
            if current_time - timestamp > self.nonce_ttl
        ]
        for expired in expired_nonces:
            del self.nonce_store[expired]
        
        # Check if nonce already used
        if nonce in self.nonce_store:
            logger.warning(f"Nonce replay attempt: {nonce}")
            return False
        
        # Store nonce
        self.nonce_store[nonce] = current_time
        return True
    
    def validate_extension_environment(self, request: Request) -> Dict[str, Any]:
        """
        Validate that the request is coming from a genuine browser extension environment.
        This checks for browser-specific headers and characteristics.
        """
        headers = request.headers
        
        # Check for browser extension indicators
        user_agent = headers.get("user-agent", "")
        if not any(browser in user_agent.lower() for browser in ["chrome", "firefox", "safari", "edge"]):
            raise HTTPException(
                status_code=401,
                detail="Request must come from a supported browser"
            )
        
        # Check for fetch/XMLHttpRequest origin (extensions use these)
        sec_fetch_site = headers.get("sec-fetch-site")
        sec_fetch_mode = headers.get("sec-fetch-mode")
        
        # Extension requests typically have these characteristics
        if sec_fetch_site and sec_fetch_site not in ["none", "same-origin"]:
            logger.warning(f"Suspicious sec-fetch-site: {sec_fetch_site}")
        
        if sec_fetch_mode and sec_fetch_mode not in ["cors", "same-origin"]:
            logger.warning(f"Suspicious sec-fetch-mode: {sec_fetch_mode}")
        
        # Additional validation can be added here
        return {
            "user_agent": user_agent,
            "sec_fetch_site": sec_fetch_site,
            "sec_fetch_mode": sec_fetch_mode,
            "validated": True
        }

# Global instance
extension_auth = ExtensionAuthenticator()

async def validate_extension_request(request: Request) -> Dict[str, Any]:
    """
    Comprehensive validation for extension requests.
    Combines multiple security checks to prevent abuse.
    """
    try:
        # 1. Validate browser environment
        env_validation = extension_auth.validate_extension_environment(request)
        
        # 2. Get extension-specific headers
        extension_id = request.headers.get("X-Extension-ID")
        timestamp_str = request.headers.get("X-Request-Timestamp")
        signature = request.headers.get("X-Request-Signature")
        nonce = request.headers.get("X-Request-Nonce")
        
        if not all([extension_id, timestamp_str, signature, nonce]):
            raise HTTPException(
                status_code=401,
                detail="Missing required extension authentication headers"
            )
        
        # 3. Validate timestamp and signature
        try:
            timestamp = int(timestamp_str)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid timestamp format")
        
        if not extension_auth.verify_challenge_response(extension_id, timestamp, signature):
            raise HTTPException(
                status_code=401,
                detail="Invalid extension signature"
            )
        
        # 4. Validate nonce (prevent replay)
        if not extension_auth.validate_nonce(nonce):
            raise HTTPException(
                status_code=401,
                detail="Invalid or reused nonce"
            )
        
        logger.info(f"Extension request validated: {extension_id} from {request.client.host}")
        
        return {
            "extension_id": extension_id,
            "timestamp": timestamp,
            "nonce": nonce,
            **env_validation
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extension validation error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Extension validation failed"
        )
