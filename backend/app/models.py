from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Cookie data model with essential properties for privacy analysis
class CookieData(BaseModel):
    """Model for cookie data from browser extension."""
    domain: str
    secure: Optional[bool] = False
    expirationDate: Optional[float] = None  # Timestamp for persistent cookie detection
    session: Optional[bool] = True  # True if session cookie, False if persistent

# Simplified script data model - only what frontend sends
class ScriptData(BaseModel):
    """Model for script data from browser extension."""
    domain: Optional[str] = None

# Network request data model - what frontend sends
class NetworkRequestData(BaseModel):
    """Model for network request data from browser extension."""
    url: str
    method: str
    type: str
    timestamp: str
    domain: Optional[str] = None

# Analytics detection flags for feature 7
class AnalyticsFlags(BaseModel):
    """Analytics detection flags."""
    has_google_analytics: bool = False
    has_gtag: bool = False
    has_facebook_pixel: bool = False
    has_data_layer: bool = False
    detected_analytics: List[str] = []

# Fingerprinting detection flags for feature 9
class FingerprintingFlags(BaseModel):
    """Fingerprinting detection flags."""
    canvas_fingerprinting: bool = False
    audio_fingerprinting: bool = False
    webgl_fingerprinting: bool = False
    font_fingerprinting: bool = False
    detected_methods: List[str] = []

# Pre-computed privacy features for validation
class PrivacyFeatures(BaseModel):
    """Pre-computed privacy features for the 10 core metrics."""
    num_third_party_domains: int = 0       # Feature 1
    num_third_party_scripts: int = 0       # Feature 2
    num_third_party_cookies: int = 0       # Feature 3
    num_third_party_requests: int = 0      # Feature 4a - Number of third-party requests
    fraction_third_party_requests: float = 0.0  # Feature 4b - Fraction of third-party requests
    num_known_tracker_domains: int = 0     # Feature 5
    num_persistent_cookies: int = 0        # Feature 6
    has_analytics_global: int = 0          # Feature 7 (boolean as int)
    num_inline_scripts: int = 0            # Feature 8
    fingerprinting_flag: int = 0           # Feature 9 (boolean as int)
    tracker_script_ratio: float = 0.0     # Feature 10

# Enhanced analyze request with all required data
class AnalyzeRequest(BaseModel):
    """Request model for comprehensive privacy analysis with all 10 features."""
    # Basic page information
    page_url: str
    page_title: str
    page_domain: str
    timestamp: str
    
    # Raw data for backend feature extraction
    raw_cookies: List[CookieData] = []
    scripts: List[ScriptData] = []
    network_requests: List[NetworkRequestData] = []
    
    # Detection flags
    analytics_flags: Optional[AnalyticsFlags] = None
    fingerprinting_flags: Optional[FingerprintingFlags] = None
    
    # Pre-computed features for validation (optional)
    privacy_features: Optional[PrivacyFeatures] = None
    
    # Legacy fields for backward compatibility
    cookies: List[str] = []  # Simple cookie strings
    additional_data: Optional[Dict[str, Any]] = None

class AnalyzeResponse(BaseModel):
    """Enhanced response model for privacy analysis results."""
    # Original response fields
    privacy_score: int
    cookies_analyzed: int
    scripts_analyzed: int
    
    # New comprehensive analysis fields
    analysis_id: Optional[str] = None
    
    # Feature extraction results (what backend computed)
    computed_features: Optional[PrivacyFeatures] = None
    
    # Detailed findings
    findings: List[str] = []
    recommendations: List[str] = []
    
    # Third-party analysis
    third_party_domains: List[str] = []
    known_trackers: List[str] = []
    
    # Privacy assessment
    privacy_level: Optional[str] = None  # "low", "medium", "high"
    risk_factors: List[str] = []

class AuthResponse(BaseModel):
    """Response model for authentication endpoint."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes

class ErrorResponse(BaseModel):
    """Standard error response model."""
    detail: str
    error_code: Optional[str] = None
