from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPAuthorizationCredentials
import logging
from typing import Set
from app.config import settings
from app.middleware import validate_extension_headers
from app.routers.auth import verify_jwt_token
from app.models import AnalyzeRequest, AnalyzeResponse, PrivacyFeatures
from app.security.extension_auth import validate_extension_request
import json

logger = logging.getLogger(__name__)
router = APIRouter()

logger = logging.getLogger(__name__)
router = APIRouter()

def extract_domain_from_url(url: str) -> str:
    """Extract domain from URL safely."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower()
    except:
        return ""

def is_third_party_domain(request_domain: str, page_domain: str) -> bool:
    """Check if a domain is third-party relative to page domain."""
    clean_request = request_domain.replace("www.", "")
    clean_page = page_domain.replace("www.", "")
    return not clean_request.endswith(clean_page) and clean_request != clean_page

def compute_privacy_features(data: AnalyzeRequest) -> PrivacyFeatures:
    """
    Compute all 10 privacy features from the collected data.
    This demonstrates feature extraction from raw extension data.
    """
    page_domain = data.page_domain
    
    # Feature computation
    features = PrivacyFeatures()
    
    # Process network requests for domain and tracker analysis
    all_domains = set()
    third_party_domains = set()
    tracker_domains = set()
    third_party_request_count = 0
    
    for req in data.network_requests:
        if req.domain:
            all_domains.add(req.domain)
            if req.is_third_party:
                third_party_domains.add(req.domain)
                third_party_request_count += 1
            if req.is_known_tracker:
                tracker_domains.add(req.domain)
    
    # Feature 1: Number of unique third-party domains
    features.num_third_party_domains = len(third_party_domains)
    
    # Feature 2: Number of third-party scripts
    features.num_third_party_scripts = sum(1 for script in data.scripts if script.is_third_party)
    
    # Feature 3: Number of third-party cookies
    features.num_third_party_cookies = sum(
        1 for cookie in data.raw_cookies 
        if is_third_party_domain(cookie.domain, page_domain)
    )
    
    # Feature 4: Fraction of requests that are third-party
    total_requests = len(data.network_requests)
    features.fraction_third_party_requests = (
        third_party_request_count / total_requests if total_requests > 0 else 0.0
    )
    
    # Feature 5: Number of known tracker domains
    features.num_known_tracker_domains = len(tracker_domains)
    
    # Feature 6: Number of persistent cookies (non-session)
    features.num_persistent_cookies = sum(
        1 for cookie in data.raw_cookies 
        if not cookie.session and cookie.expirationDate
    )
    
    # Feature 7: Has analytics globals (boolean converted to int)
    has_analytics = False
    if data.analytics_flags:
        has_analytics = (
            data.analytics_flags.has_google_analytics or
            data.analytics_flags.has_gtag or
            data.analytics_flags.has_facebook_pixel or
            data.analytics_flags.has_data_layer
        )
    features.has_analytics_global = 1 if has_analytics else 0
    
    # Feature 8: Number of inline scripts
    features.num_inline_scripts = sum(1 for script in data.scripts if script.inline)
    
    # Feature 9: Fingerprinting flag (boolean converted to int)
    has_fingerprinting = False
    if data.fingerprinting_flags:
        has_fingerprinting = (
            data.fingerprinting_flags.canvas_fingerprinting or
            data.fingerprinting_flags.audio_fingerprinting or
            data.fingerprinting_flags.webgl_fingerprinting or
            data.fingerprinting_flags.font_fingerprinting
        )
    features.fingerprinting_flag = 1 if has_fingerprinting else 0
    
    # Feature 10: Tracker script ratio
    third_party_script_count = features.num_third_party_scripts
    known_tracker_script_count = sum(1 for script in data.scripts if script.is_known_tracker)
    features.tracker_script_ratio = (
        known_tracker_script_count / third_party_script_count 
        if third_party_script_count > 0 else 0.0
    )
    
    return features

async def analyze_privacy_data(data: AnalyzeRequest) -> dict:
    """
    Comprehensive privacy analysis using all 10 core features.
    """
    # Compute privacy features
    features = compute_privacy_features(data)
    
    # Log feature extraction for validation
    logger.info(f"Privacy Feature Extraction for {data.page_url}:")
    logger.info(f"  Feature 1 - Third-party domains: {features.num_third_party_domains}")
    logger.info(f"  Feature 2 - Third-party scripts: {features.num_third_party_scripts}")
    logger.info(f"  Feature 3 - Third-party cookies: {features.num_third_party_cookies}")
    logger.info(f"  Feature 4 - Third-party request fraction: {features.fraction_third_party_requests:.3f}")
    logger.info(f"  Feature 5 - Known tracker domains: {features.num_known_tracker_domains}")
    logger.info(f"  Feature 6 - Persistent cookies: {features.num_persistent_cookies}")
    logger.info(f"  Feature 7 - Has analytics globals: {features.has_analytics_global}")
    logger.info(f"  Feature 8 - Inline scripts: {features.num_inline_scripts}")
    logger.info(f"  Feature 9 - Fingerprinting detected: {features.fingerprinting_flag}")
    logger.info(f"  Feature 10 - Tracker script ratio: {features.tracker_script_ratio:.3f}")
    
    # Compute privacy score based on features
    privacy_score = calculate_privacy_score(features)
    
    # Generate findings and recommendations
    findings = []
    recommendations = []
    risk_factors = []
    
    if features.num_third_party_domains > 10:
        findings.append(f"High number of third-party domains ({features.num_third_party_domains})")
        recommendations.append("Consider using a tracker blocker")
        risk_factors.append("excessive_third_parties")
    
    if features.num_known_tracker_domains > 0:
        findings.append(f"Known tracking domains detected ({features.num_known_tracker_domains})")
        recommendations.append("Enable enhanced tracking protection")
        risk_factors.append("known_trackers")
    
    if features.has_analytics_global:
        findings.append("Analytics tracking detected")
        risk_factors.append("analytics_tracking")
    
    if features.fingerprinting_flag:
        findings.append("Fingerprinting techniques detected")
        recommendations.append("Use fingerprinting protection")
        risk_factors.append("fingerprinting")
    
    if features.num_persistent_cookies > 5:
        findings.append(f"Many persistent cookies ({features.num_persistent_cookies})")
        recommendations.append("Regularly clear cookies")
        risk_factors.append("persistent_cookies")
    
    # Determine privacy level
    privacy_level = "high"
    if len(risk_factors) >= 3 or features.num_known_tracker_domains > 5:
        privacy_level = "low"
    elif len(risk_factors) >= 1:
        privacy_level = "medium"
    
    # Extract unique third-party domains and trackers for response
    third_party_domains = set()
    known_trackers = set()
    
    for req in data.network_requests:
        if req.is_third_party and req.domain:
            third_party_domains.add(req.domain)
        if req.is_known_tracker and req.domain:
            known_trackers.add(req.domain)
    
    if not findings:
        findings.append("No significant privacy issues detected")
        recommendations.append("Website appears to have good privacy practices")
    
    return {
        "privacy_score": privacy_score,
        "cookies_analyzed": len(data.raw_cookies),
        "scripts_analyzed": len(data.scripts),
        "computed_features": features,
        "findings": findings,
        "recommendations": recommendations,
        "third_party_domains": list(third_party_domains),
        "known_trackers": list(known_trackers),
        "privacy_level": privacy_level,
        "risk_factors": risk_factors
    }

def calculate_privacy_score(features: PrivacyFeatures) -> int:
    """Calculate privacy score from 0-100 based on features."""
    score = 100
    
    # Deduct points for privacy-reducing features
    score -= min(features.num_third_party_domains * 2, 30)  # Max -30 for third parties
    score -= min(features.num_known_tracker_domains * 5, 25)  # Max -25 for trackers
    score -= features.has_analytics_global * 10  # -10 for analytics
    score -= features.fingerprinting_flag * 15  # -15 for fingerprinting
    score -= min(features.num_persistent_cookies * 2, 20)  # Max -20 for persistent cookies
    score -= min(features.fraction_third_party_requests * 30, 15)  # Max -15 for third-party requests
    
    return max(score, 0)

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_website_privacy(
    analyze_data: AnalyzeRequest,
    request: Request,
    # extension_validation: dict = Depends(validate_extension_request),  # Temporarily disabled
    _: dict = Depends(validate_extension_headers),
    token_payload: dict = Depends(verify_jwt_token)
):
    """
    Comprehensive privacy analysis with all 10 core features.
    Logs detailed feature extraction and validation data.
    """
    try:
        # Log basic request info
        logger.info(f"=== PRIVACY ANALYSIS REQUEST ===")
        logger.info(f"Page URL: {analyze_data.page_url}")
        logger.info(f"Page Domain: {analyze_data.page_domain}")
        logger.info(f"Raw Cookies: {len(analyze_data.raw_cookies)}")
        logger.info(f"Scripts: {len(analyze_data.scripts)}")
        logger.info(f"Network Requests: {len(analyze_data.network_requests)}")
        
        # Validate required data is present
        if not analyze_data.raw_cookies and not analyze_data.scripts and not analyze_data.network_requests:
            logger.warning("Request contains no data for analysis")
            raise HTTPException(
                status_code=400,
                detail="No privacy data provided for analysis"
            )
        
        # Log analytics and fingerprinting detection
        if analyze_data.analytics_flags:
            logger.info(f"Analytics detected: {analyze_data.analytics_flags.detected_analytics}")
        if analyze_data.fingerprinting_flags:
            logger.info(f"Fingerprinting methods: {analyze_data.fingerprinting_flags.detected_methods}")
        
        # If frontend provided pre-computed features, log them for validation
        if analyze_data.privacy_features:
            logger.info("Frontend provided pre-computed features for validation:")
            logger.info(f"  Frontend computed - Third-party domains: {analyze_data.privacy_features.num_third_party_domains}")
            logger.info(f"  Frontend computed - Known trackers: {analyze_data.privacy_features.num_known_tracker_domains}")
        
        # Perform comprehensive analysis
        analysis_result = await analyze_privacy_data(analyze_data)
        
        logger.info(f"Analysis completed with privacy score: {analysis_result['privacy_score']}")
        logger.info(f"Privacy level: {analysis_result['privacy_level']}")
        logger.info("=== END ANALYSIS ===")
        
        return AnalyzeResponse(**analysis_result)
    
    except Exception as e:
        logger.error(f"Error during privacy analysis: {e}")
        logger.error(f"Request data: {analyze_data}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during analysis: {str(e)}"
        )
