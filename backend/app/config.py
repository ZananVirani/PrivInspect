import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")

    JWT_SECRET_OLD: Optional[str] = os.environ.get("JWT_SECRET_OLD")

    EXTENSION_CLIENT_HEADER: str = os.environ.get("EXTENSION_CLIENT_HEADER", "privacy-inspector")

    ALLOWED_ORIGIN: str = os.environ.get("ALLOWED_ORIGIN", "chrome-extension://your-extension-id-here")
    
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")
    
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"
    
    AUTH_RATE_LIMIT: int = int(os.environ.get("AUTH_RATE_LIMIT", "10"))
    ANALYZE_RATE_LIMIT: int = int(os.environ.get("ANALYZE_RATE_LIMIT", "60"))
    
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
