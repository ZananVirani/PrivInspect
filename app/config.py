import os
import json
from pydantic_settings import BaseSettings
from typing import Optional

def read_secret_file(file_path: str) -> str:
    """Read secret from file path."""
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        raise ValueError(f"Secret file not found: {file_path}")

def get_secret(secret_name: str, default: str = None) -> str:
    """
    Get secret from multiple sources in order of priority:
    1. Environment variable {SECRET_NAME}
    2. File path from {SECRET_NAME}_FILE environment variable
    3. Default value
    """
    # First try direct environment variable
    direct_env = os.getenv(secret_name)
    if direct_env:
        return direct_env
    
    # Then try file path from environment variable
    file_path_env = f"{secret_name}_FILE"
    file_path = os.getenv(file_path_env)
    if file_path:
        return read_secret_file(file_path)
    
    # Finally use default
    if default is not None:
        return default
    
    raise ValueError(f"Secret {secret_name} not found in environment or file")

def get_optional_secret(secret_name: str, default: str = None) -> Optional[str]:
    """
    Get optional secret - returns None if not found instead of raising error.
    Used for JWT rotation secrets that may not always be present.
    """
    try:
        return get_secret(secret_name, default)
    except ValueError:
        return None

class Settings(BaseSettings):
    """Application settings with secure secret management."""
    
    # JWT Configuration - CRITICAL SECRET
    JWT_SECRET: str = get_secret("JWT_SECRET", "dev-secret-change-in-production")
    
    # JWT Secret Rotation - OPTIONAL OLD SECRET FOR GRACE PERIOD
    JWT_SECRET_OLD: Optional[str] = get_optional_secret("JWT_SECRET_OLD")
    
    # Extension Security - MODERATE SECRET
    EXTENSION_CLIENT_HEADER: str = get_secret("EXTENSION_CLIENT_HEADER", "privacy-inspector")
    
    # Extension Origin - PUBLIC BUT CONFIGURABLE
    ALLOWED_ORIGIN: str = get_secret("ALLOWED_ORIGIN", "chrome-extension://your-extension-id-here")
    
    # Redis Configuration
    REDIS_URL: str = get_secret("REDIS_URL", "redis://localhost:6379")
    
    # Server Configuration
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Rate Limiting
    AUTH_RATE_LIMIT: int = int(os.getenv("AUTH_RATE_LIMIT", "10"))
    ANALYZE_RATE_LIMIT: int = int(os.getenv("ANALYZE_RATE_LIMIT", "5"))
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    def get_jwt_secrets(self) -> list[str]:
        """
        Get all JWT secrets for token verification (current + old secret for grace period).
        Returns secrets in order: current secret first, then old secret if present.
        """
        secrets = [self.JWT_SECRET]
        
        if self.JWT_SECRET_OLD:
            secrets.append(self.JWT_SECRET_OLD)
            
        return secrets

# Global settings instance
settings = Settings()
