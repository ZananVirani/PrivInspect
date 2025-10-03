from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class CookieData(BaseModel):
    """Model for cookie data from browser extension."""
    name: str
    value: str
    domain: str
    path: str = "/"
    secure: bool = False
    httpOnly: bool = False
    sameSite: Optional[str] = None

class ScriptData(BaseModel):
    """Model for script data from browser extension."""
    src: str
    type: str = "text/javascript"
    async_load: bool = False
    defer: bool = False

class AnalyzeRequest(BaseModel):
    """Request model for privacy analysis."""
    url: str
    cookies: List[CookieData] = []
    scripts: List[ScriptData] = []
    additional_data: Optional[Dict[str, Any]] = None

class AnalyzeResponse(BaseModel):
    """Response model for privacy analysis results."""
    privacy_score: int
    cookies_analyzed: int
    scripts_analyzed: int
    findings: List[str]
    recommendations: List[str]

class AuthResponse(BaseModel):
    """Response model for authentication endpoint."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes

class ErrorResponse(BaseModel):
    """Standard error response model."""
    detail: str
    error_code: Optional[str] = None
