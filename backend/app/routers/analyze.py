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
import re

logger = logging.getLogger(__name__)
router = APIRouter()

# Known tracker domains - matches the frontend list
KNOWN_TRACKERS = {
    # Analytics trackers
    "google-analytics.com", "googletagmanager.com", "googleadservices.com", 
    "doubleclick.net", "facebook.com", "facebook.net", "fbcdn.net", 
    "connect.facebook.net",
    # Ad networks
    "googlesyndication.com", "adsystem.amazon.com", "amazon-adsystem.com", 
    "adsymptotic.com",
    # Social media trackers
    "twitter.com", "t.co", "linkedin.com", "instagram.com",
    # Other common trackers
    "hotjar.com", "mixpanel.com", "segment.com", "amplitude.com", 
    "fullstory.com", "loggly.com", "newrelic.com", "pingdom.net", 
    "quantserve.com", "scorecardresearch.com", "comscore.com", 
    "bing.com", "yahoo.com", "yandex.ru", "baidu.com",
    # CDNs often used for tracking
    "cdnjs.cloudflare.com", "ajax.googleapis.com", "maxcdn.bootstrapcdn.com"
}

def is_known_tracker(domain: str) -> bool:
    """Check if a domain is a known tracker."""
    return domain.lower() in KNOWN_TRACKERS

logger = logging.getLogger(__name__)
router = APIRouter()

def extract_domain_from_url(url: str) -> str:
    """Extract domain from URL safely."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower()
    except:
        return ""

def extract_domain_keywords(domain: str) -> set:
    """Extract meaningful keywords from a domain for first-party detection."""
    # Remove common prefixes and TLD
    clean_domain = domain.replace("www.", "").split('.')[0]  # Get the main part before first dot
    
    # Split by common separators to get keywords
    import re
    parts = re.split(r'[.\-_]', clean_domain)
    
    # Filter out common generic words and keep meaningful keywords
    generic_words = {'www', 'cdn', 'static', 'assets', 'api', 'img', 'images', 'js', 'css', 'media', 
                    'content', 'data', 'files', 'docs', 'blog', 'news', 'store', 'shop', 'mail', 
                    'email', 'support', 'help', 'admin', 'secure'}
    
    keywords = set()
    
    for part in parts:
        if len(part) >= 3 and part.lower() not in generic_words:
            keywords.add(part.lower())
    
    return keywords

def is_third_party_domain(request_domain: str, page_domain: str) -> bool:
    """Check if a domain is third-party relative to page domain using keyword matching."""
    # Remove www. prefix for comparison
    clean_request = request_domain.replace("www.", "").lower()
    clean_page = page_domain.replace("www.", "").lower()
    
    # If domains are exactly the same, it's first-party
    if clean_request == clean_page:
        return False
    
    # Check if request domain is a subdomain of page domain (traditional first-party)
    if clean_request.endswith(f".{clean_page}"):
        return False
    
    # Check if page domain is a subdomain of request domain  
    if clean_page.endswith(f".{clean_request}"):
        return False
    
    # Extract the base domain (e.g., "mail.google.com" -> "google.com")
    def get_base_domain(domain):
        parts = domain.split('.')
        if len(parts) >= 2:
            # For common cases, return the last two parts (domain.tld)
            return '.'.join(parts[-2:])
        return domain
    
    # Check if they share the same base domain
    base_request = get_base_domain(clean_request)
    base_page = get_base_domain(clean_page)
    
    if base_request == base_page:
        return False  # Same base domain = first-party
    
    # Extract keywords from both domains for additional matching
    page_keywords = extract_domain_keywords(clean_page)
    request_keywords = extract_domain_keywords(clean_request)
    
    # If they share significant keywords, consider them first-party
    for page_keyword in page_keywords:
        if len(page_keyword) >= 4:  # Only consider meaningful keywords
            for request_keyword in request_keywords:
                if len(request_keyword) >= 4:
                    # Check for exact match or one contains the other
                    if (page_keyword == request_keyword or 
                        page_keyword in request_keyword or 
                        request_keyword in page_keyword):
                        return False  # First-party
    
    # If no match, it's third-party
    return True

def compute_privacy_features(data: AnalyzeRequest) -> PrivacyFeatures:
    """
    Compute all 10 privacy features from the collected data.
    This demonstrates feature extraction from raw extension data.
    Backend now handles all third-party and tracker detection.
    """
    page_domain = data.page_domain
    
    # Feature computation
    features = PrivacyFeatures()
    
    # Process all data sources for comprehensive domain and tracker analysis
    all_domains = set()
    third_party_domains = set()
    tracker_domains = set()
    third_party_request_count = 0
    
    # Process network requests
    for req in data.network_requests:
        if req.domain:
            all_domains.add(req.domain)
            # Backend computes third-party status
            if is_third_party_domain(req.domain, page_domain):
                third_party_domains.add(req.domain)
                third_party_request_count += 1
            # Backend computes tracker status
            if is_known_tracker(req.domain):
                tracker_domains.add(req.domain)
    
    # Process script domains
    for script in data.scripts:
        if script.domain:
            all_domains.add(script.domain)
            if is_third_party_domain(script.domain, page_domain):
                third_party_domains.add(script.domain)
            if is_known_tracker(script.domain):
                tracker_domains.add(script.domain)
    
    # Process cookie domains
    for cookie in data.raw_cookies:
        if cookie.domain:
            all_domains.add(cookie.domain)
            if is_third_party_domain(cookie.domain, page_domain):
                third_party_domains.add(cookie.domain)
            if is_known_tracker(cookie.domain):
                tracker_domains.add(cookie.domain)
    
    # Feature 1: Number of unique third-party domains (across ALL sources)
    features.num_third_party_domains = len(third_party_domains)
    
    # Feature 2: Number of third-party scripts - backend computes third-party status
    third_party_scripts = 0
    for script in data.scripts:
        if script.domain and is_third_party_domain(script.domain, page_domain):
            third_party_scripts += 1
    features.num_third_party_scripts = third_party_scripts
    
    # Feature 3: Number of third-party cookies - backend computes third-party status
    third_party_cookies = 0
    for cookie in data.raw_cookies:
        if is_third_party_domain(cookie.domain, page_domain):
            third_party_cookies += 1
    features.num_third_party_cookies = third_party_cookies
    
    # Feature 4: Fraction of requests that are third-party
    total_requests = len(data.network_requests)
    features.fraction_third_party_requests = (
        third_party_request_count / total_requests if total_requests > 0 else 0.0
    )
    
    # Feature 5: Number of known tracker domains
    features.num_known_tracker_domains = len(tracker_domains)
    
    # Feature 6: Number of persistent cookies (non-session cookies)
    persistent_cookies = 0
    for cookie in data.raw_cookies:
        # A cookie is persistent if:
        # 1. It's explicitly marked as non-session (session=False), OR
        # 2. It has an expirationDate set (which means it persists beyond session)
        if (not cookie.session) or (cookie.expirationDate is not None):
            persistent_cookies += 1
    features.num_persistent_cookies = persistent_cookies
    
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
    
    # Feature 8: Number of inline scripts (simplified - we don't have inline flag)
    # Since frontend only sends domain, we can't distinguish inline vs external
    # Count scripts with no domain as inline scripts
    inline_scripts = sum(1 for script in data.scripts if not script.domain)
    features.num_inline_scripts = inline_scripts
    
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
    tracker_scripts = 0
    for script in data.scripts:
        if script.domain and is_known_tracker(script.domain):
            tracker_scripts += 1
    
    features.tracker_script_ratio = (
        tracker_scripts / third_party_scripts if third_party_scripts > 0 else 0.0
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
    
    # Extract unique third-party domains and trackers for response (from ALL sources)
    third_party_domains_for_response = set()
    known_trackers_for_response = set()
    
    # Check network requests
    for req in data.network_requests:
        if req.domain:
            if is_third_party_domain(req.domain, data.page_domain):
                third_party_domains_for_response.add(req.domain)
            if is_known_tracker(req.domain):
                known_trackers_for_response.add(req.domain)
    
    # Check scripts
    for script in data.scripts:
        if script.domain:
            if is_third_party_domain(script.domain, data.page_domain):
                third_party_domains_for_response.add(script.domain)
            if is_known_tracker(script.domain):
                known_trackers_for_response.add(script.domain)
    
    # Check cookies
    for cookie in data.raw_cookies:
        if cookie.domain:
            if is_third_party_domain(cookie.domain, data.page_domain):
                third_party_domains_for_response.add(cookie.domain)
            if is_known_tracker(cookie.domain):
                known_trackers_for_response.add(cookie.domain)
    
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
        "third_party_domains": list(third_party_domains_for_response),
        "known_trackers": list(known_trackers_for_response),
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
