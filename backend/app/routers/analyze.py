from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPAuthorizationCredentials
import logging
from typing import Set
from app.config import settings
from app.middleware import validate_extension_headers
from app.routers.auth import verify_jwt_token
from app.models import AnalyzeRequest, AnalyzeResponse, PrivacyFeatures
from app.security.extension_auth import validate_extension_request
from app.ml_scoring import get_ml_score_for_page
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
    
    # Feature 1: Number of unique third-party domains (across ALL sources: scripts, cookies, requests)
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
    
    # Feature 4a: Number of third-party requests
    features.num_third_party_requests = third_party_request_count
    
    # Feature 4b: Fraction of requests that are third-party
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
    logger.info(f"  Feature 4a - Third-party requests: {features.num_third_party_requests}")
    logger.info(f"  Feature 4b - Third-party request fraction: {features.fraction_third_party_requests:.3f}")
    logger.info(f"  Feature 5 - Known tracker domains: {features.num_known_tracker_domains}")
    logger.info(f"  Feature 6 - Persistent cookies: {features.num_persistent_cookies}")
    logger.info(f"  Feature 7 - Has analytics globals: {features.has_analytics_global}")
    logger.info(f"  Feature 8 - Inline scripts: {features.num_inline_scripts}")
    logger.info(f"  Feature 9 - Fingerprinting detected: {features.fingerprinting_flag}")
    logger.info(f"  Feature 10 - Tracker script ratio: {features.tracker_script_ratio:.3f}")
    
    # Compute privacy score using hybrid ML + heuristics system
    score_result = compute_privacy_score(features, data)  # Pass original data for ML scoring
    privacy_score = int(score_result["score"])  # Convert to int for backward compatibility
    
    # Generate findings and recommendations based on heuristic penalties
    findings = []
    recommendations = []
    
    # Get the individual penalties from score breakdown
    penalties = score_result["breakdown"]["individual_penalties"]
    
    # Generate findings and recommendations based on which heuristics triggered penalties
    if penalties["third_party_domains"] < 0:
        domains = features.num_third_party_domains
        if domains >= 8:
            findings.append(f"Excessive third-party domains detected ({domains} domains)")
            recommendations.append("Use a tracker blocker or privacy-focused browser")
        elif domains >= 4:
            findings.append(f"High number of third-party domains ({domains} domains)")
            recommendations.append("Consider enabling enhanced tracking protection")
        else:
            findings.append(f"Some third-party domains present ({domains} domains)")
            recommendations.append("Monitor third-party content for privacy")
    
    if penalties["third_party_scripts"] < 0:
        scripts = features.num_third_party_scripts
        if scripts >= 16:
            findings.append(f"Very high number of third-party scripts ({scripts} scripts)")
            recommendations.append("Use script blockers to reduce tracking exposure")
        elif scripts >= 7:
            findings.append(f"High number of third-party scripts ({scripts} scripts)")
            recommendations.append("Review and limit third-party script loading")
        else:
            findings.append(f"Moderate third-party script usage ({scripts} scripts)")
            recommendations.append("Monitor script sources for privacy compliance")
    
    if penalties["third_party_cookies"] < 0:
        cookies = features.num_third_party_cookies
        if cookies >= 7:
            findings.append(f"Excessive third-party cookies ({cookies} cookies)")
            recommendations.append("Clear cookies regularly and block third-party cookies")
        elif cookies >= 3:
            findings.append(f"Multiple third-party cookies detected ({cookies} cookies)")
            recommendations.append("Consider blocking third-party cookies in browser settings")
        else:
            findings.append(f"Some third-party cookies present ({cookies} cookies)")
            recommendations.append("Review cookie settings for privacy")
    
    if penalties["third_party_requests"] < 0:
        fraction = features.fraction_third_party_requests
        if fraction > 0.60:
            findings.append(f"Very high third-party request ratio ({fraction:.1%} of requests)")
            recommendations.append("Use comprehensive ad and tracker blocking")
        elif fraction > 0.30:
            findings.append(f"High third-party request ratio ({fraction:.1%} of requests)")
            recommendations.append("Enable strict privacy protection in browser")
        else:
            findings.append(f"Moderate third-party request activity ({fraction:.1%} of requests)")
            recommendations.append("Monitor network requests for privacy")
    
    if penalties["tracker_domains"] < 0:
        trackers = features.num_known_tracker_domains
        if trackers >= 3:
            findings.append(f"Multiple known tracking services detected ({trackers} trackers)")
            recommendations.append("Use comprehensive tracker blocking immediately")
        elif trackers == 2:
            findings.append(f"Known tracking services detected ({trackers} trackers)")
            recommendations.append("Enable enhanced tracking protection")
        else:
            findings.append(f"Known tracking service detected ({trackers} tracker)")
            recommendations.append("Consider using privacy-focused browser extensions")
    
    if penalties["persistent_cookies"] < 0:
        persistent = features.num_persistent_cookies
        if persistent >= 10:
            findings.append(f"Excessive persistent cookies ({persistent} long-term cookies)")
            recommendations.append("Clear cookies and enable automatic cookie deletion")
        elif persistent >= 6:
            findings.append(f"High number of persistent cookies ({persistent} long-term cookies)")
            recommendations.append("Configure browser to limit cookie lifetime")
        else:
            findings.append(f"Some persistent cookies detected ({persistent} long-term cookies)")
            recommendations.append("Review cookie retention settings")
    
    if penalties["analytics_global"] < 0:
        findings.append("Website analytics tracking detected")
        recommendations.append("Use privacy-focused search engines and browsers")
    
    if penalties["inline_scripts"] < 0:
        inline = features.num_inline_scripts
        if inline >= 11:
            findings.append(f"Excessive inline scripts ({inline} embedded scripts)")
            recommendations.append("Use strict content security policies")
        elif inline >= 7:
            findings.append(f"High number of inline scripts ({inline} embedded scripts)")
            recommendations.append("Enable script blocking for enhanced security")
        else:
            findings.append(f"Multiple inline scripts detected ({inline} embedded scripts)")
            recommendations.append("Monitor inline script content for privacy")
    
    if penalties["fingerprinting"] < 0:
        findings.append("Browser fingerprinting techniques detected")
        recommendations.append("Use fingerprint-resistant browser or enable fingerprint protection")
    
    if penalties["tracker_script_ratio"] < 0:
        ratio = features.tracker_script_ratio
        if ratio >= 0.30:
            findings.append(f"Very high tracker script ratio ({ratio:.1%} of scripts are trackers)")
            recommendations.append("Use aggressive script blocking and privacy tools")
        elif ratio >= 0.15:
            findings.append(f"High tracker script ratio ({ratio:.1%} of scripts are trackers)")
            recommendations.append("Enable comprehensive script filtering")
        else:
            findings.append(f"Some tracking scripts detected ({ratio:.1%} of scripts are trackers)")
            recommendations.append("Consider using script blockers")
    
    # Determine privacy level based on final score
    if score_result["score"] >= 90:
        privacy_level = "high"
    elif score_result["score"] >= 75:
        privacy_level = "medium"
    else:
        privacy_level = "low"
    
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
    
    # Add fallback message if no issues detected
    if not findings:
        findings.append("No significant privacy issues detected")
        recommendations.append("Website demonstrates good privacy practices")
    
    return {
        "privacy_score": privacy_score,
        "cookies_analyzed": len(data.raw_cookies),
        "scripts_analyzed": len(data.scripts),
        "computed_features": features,
        "score_breakdown": score_result["breakdown"],
        "privacy_grade": score_result["grade_letter"],
        "findings": findings,
        "recommendations": recommendations,
        "third_party_domains": list(third_party_domains_for_response),
        "known_trackers": list(known_trackers_for_response),
        "privacy_level": privacy_level
    }

def compute_privacy_score(features: PrivacyFeatures, analyze_request: AnalyzeRequest = None) -> dict:
    """
    Hybrid ML + Heuristics Privacy Scoring System
    
    Returns a privacy score with detailed breakdown.
    ML score starts at domain-based prediction, then heuristics adjust downward.
    """
    # Get ML model prediction for domain-based scoring
    try:
        if analyze_request:
            # Use original request data for ML scoring (contains actual domains)
            ml_score = get_ml_score_for_page(analyze_request)
        else:
            # Fallback for when only features are available
            ml_score = get_ml_score_for_page(features)
    except Exception as e:
        logger.warning(f"ML scoring failed, using fallback: {e}")
        ml_score = 100.0  # Fallback to safe default
    
    # Initialize penalty calculations
    penalties = {}
    total_penalty = 0.0
    
    # (1) num_third_party_domains penalty
    domains = features.num_third_party_domains
    if domains == 0:
        penalties["third_party_domains"] = 0.0
    elif 1 <= domains <= 3:
        penalties["third_party_domains"] = -1.0  # -2/2 = -1
    elif 4 <= domains <= 7:
        penalties["third_party_domains"] = -2.0  # -4/2 = -2
    else:  # 8+
        penalties["third_party_domains"] = -3.0  # -6/2 = -3
    
    # (2) num_third_party_scripts penalty
    scripts = features.num_third_party_scripts
    if 0 <= scripts <= 2:
        penalties["third_party_scripts"] = 0.0
    elif 3 <= scripts <= 6:
        penalties["third_party_scripts"] = -1.0  # -2/2 = -1
    elif 7 <= scripts <= 15:
        penalties["third_party_scripts"] = -2.0  # -4/2 = -2
    else:  # 16+
        penalties["third_party_scripts"] = -3.0  # -6/2 = -3
    
    # (3) num_third_party_cookies penalty
    cookies = features.num_third_party_cookies
    if cookies == 0:
        penalties["third_party_cookies"] = 0.0
    elif 1 <= cookies <= 2:
        penalties["third_party_cookies"] = -1.0  # -2/2 = -1
    elif 3 <= cookies <= 6:
        penalties["third_party_cookies"] = -2.0  # -4/2 = -2
    else:  # 7+
        penalties["third_party_cookies"] = -3.0  # -6/2 = -3
    
    # (4) fraction_third_party_requests penalty
    fraction = features.fraction_third_party_requests
    if fraction < 0.10:
        penalties["third_party_requests"] = 0.0
    elif 0.10 <= fraction <= 0.30:
        penalties["third_party_requests"] = -1.0  # -2/2 = -1
    elif 0.30 < fraction <= 0.60:
        penalties["third_party_requests"] = -2.0  # -4/2 = -2
    else:  # > 0.60
        penalties["third_party_requests"] = -3.0  # -6/2 = -3
    
    # (5) num_known_tracker_domains penalty (largest single penalty)
    trackers = features.num_known_tracker_domains
    if trackers == 0:
        penalties["tracker_domains"] = 0.0
    elif trackers == 1:
        penalties["tracker_domains"] = -2.0  # -4/2 = -2
    elif trackers == 2:
        penalties["tracker_domains"] = -3.0  # -6/2 = -3
    else:  # 3+
        penalties["tracker_domains"] = -5.0  # -10/2 = -5
    
    # (6) num_persistent_cookies penalty
    persistent = features.num_persistent_cookies
    if 0 <= persistent <= 1:
        penalties["persistent_cookies"] = 0.0
    elif 2 <= persistent <= 5:
        penalties["persistent_cookies"] = -1.0  # -2/2 = -1
    elif 6 <= persistent <= 10:
        penalties["persistent_cookies"] = -2.0  # -4/2 = -2
    else:  # 10+
        penalties["persistent_cookies"] = -3.0  # -6/2 = -3
    
    # (7) has_analytics_global penalty
    if features.has_analytics_global == 1:
        penalties["analytics_global"] = -2.0  # -3/2 = -1.5, rounded to -2
    else:
        penalties["analytics_global"] = 0.0
    
    # (8) num_inline_scripts penalty
    inline = features.num_inline_scripts
    if 0 <= inline <= 2:
        penalties["inline_scripts"] = 0.0
    elif 3 <= inline <= 6:
        penalties["inline_scripts"] = -1.0  # -2/2 = -1
    elif 6 < inline <= 10:
        penalties["inline_scripts"] = -2.0  # -3/2 = -1.5, rounded to -2
    else:  # 11+
        penalties["inline_scripts"] = -3.0  # -5/2 = -2.5, rounded to -3
    
    # (9) fingerprinting_flag penalty
    if features.fingerprinting_flag == 1:
        penalties["fingerprinting"] = -4.0  # -8/2 = -4
    else:
        penalties["fingerprinting"] = 0.0
    
    # (10) tracker_script_ratio penalty
    ratio = features.tracker_script_ratio
    if 0.00 <= ratio <= 0.05:
        penalties["tracker_script_ratio"] = 0.0
    elif 0.05 < ratio <= 0.15:
        penalties["tracker_script_ratio"] = -1.0  # -2/2 = -1
    elif 0.15 < ratio <= 0.30:
        penalties["tracker_script_ratio"] = -2.0  # -4/2 = -2
    else:  # 0.30+
        penalties["tracker_script_ratio"] = -3.0  # -6/2 = -3
    
    # Calculate total penalty and apply cap (also reduced by half)
    total_penalty = sum(penalties.values())
    capped_penalty = max(total_penalty, -20.0)  # Cap at -20
    
    # Calculate final score
    final_score = ml_score + capped_penalty
    final_score = max(0.0, min(100.0, final_score))  # Clamp 0-100
    
    # Determine letter grade
    if 90.0 <= final_score <= 100.0:
        grade = "A"
    elif 75.0 <= final_score < 90.0:
        grade = "B"
    elif 60.0 <= final_score < 75.0:
        grade = "C"
    elif 40.0 <= final_score < 60.0:
        grade = "D"
    else:  # 0-39
        grade = "F"
    
    return {
        "score": final_score,
        "grade_letter": grade,
        "breakdown": {
            "ml_base_score": ml_score,
            "total_penalty_applied": capped_penalty,
            "total_penalty_raw": total_penalty,
            "penalty_cap_applied": capped_penalty != total_penalty,
            "individual_penalties": penalties,
            "final_score": final_score
        }
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
