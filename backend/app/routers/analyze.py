from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPAuthorizationCredentials
import logging
from typing import Set
from app.config import settings
from app.middleware import validate_extension_headers
from app.routers.auth import verify_jwt_token
from app.models import AnalyzeRequest, AnalyzeResponse, PrivacyFeatures
from app.security.extension_auth import validate_extension_request
from app.ml_scoring import get_ml_score_for_page, domain_scoring_service, domain_scoring_service
import json
import re

logger = logging.getLogger(__name__)
router = APIRouter()

# Fallback known tracker domains for when ML service is not available
FALLBACK_KNOWN_TRACKERS = {
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

# Tracker severity ranking (higher number = more severe)
TRACKER_SEVERITY_SCORES = {
    # Most severe - Major analytics and advertising trackers
    "google-analytics.com": 10, "googletagmanager.com": 10, "doubleclick.net": 10,
    "facebook.com": 9, "connect.facebook.net": 9, "facebook.net": 9,
    "googlesyndication.com": 9, "googleadservices.com": 9,
    
    # High severity - Major ad networks and social trackers
    "amazon-adsystem.com": 8, "adsystem.amazon.com": 8,
    "twitter.com": 7, "linkedin.com": 7, "instagram.com": 7,
    
    # Medium-high severity - Analytics and behavior tracking
    "hotjar.com": 6, "mixpanel.com": 6, "segment.com": 6, "amplitude.com": 6,
    "fullstory.com": 6,
    
    # Medium severity - Performance and other trackers
    "newrelic.com": 5, "pingdom.net": 5, "quantserve.com": 5,
    "scorecardresearch.com": 5, "comscore.com": 5,
    
    # Lower severity - Search engines and others
    "bing.com": 4, "yahoo.com": 4, "yandex.ru": 4, "baidu.com": 4,
    "t.co": 3, "fbcdn.net": 3,
    
    # Lowest severity - CDNs with potential tracking
    "cdnjs.cloudflare.com": 2, "ajax.googleapis.com": 2, "maxcdn.bootstrapcdn.com": 2
}

def get_tracker_severity_score(domain: str) -> int:
    """Get severity score for a tracking domain (higher = more severe)."""
    domain_lower = domain.lower()
    
    # Check exact match first
    if domain_lower in TRACKER_SEVERITY_SCORES:
        return TRACKER_SEVERITY_SCORES[domain_lower]
    
    # Check parent domain (for subdomains)
    def get_parent_domain(d):
        parts = d.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return d
    
    parent = get_parent_domain(domain_lower)
    if parent in TRACKER_SEVERITY_SCORES:
        return TRACKER_SEVERITY_SCORES[parent]
    
    # Default severity for unknown trackers
    return 1

def is_known_tracker(domain: str) -> bool:
    """Check if a domain is a known tracker using TrackerRadar data with subdomain matching."""
    domain_lower = domain.lower()
    
    # Helper function to check domain and its variations in TrackerRadar
    def check_trackerradar(check_domain):
        if not domain_scoring_service.is_loaded:
            return False
        return check_domain in domain_scoring_service.domain_features
    
    # Helper function to extract parent domain (e.g., 'metric-api.newrelic.com' -> 'newrelic.com')
    def get_parent_domain(d):
        parts = d.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])  # Get last two parts (domain.tld)
        return d
    
    # 1. Try exact match in TrackerRadar
    if check_trackerradar(domain_lower):
        return True
    
    # 2. Try without 'www.' prefix
    if domain_lower.startswith('www.'):
        base_domain = domain_lower[4:]
        if check_trackerradar(base_domain):
            return True
    
    # 3. Try adding 'www.' prefix
    www_domain = f"www.{domain_lower}"
    if check_trackerradar(www_domain):
        return True
    
    # 4. Try parent domain (for subdomains like metric-api.newrelic.com -> newrelic.com)
    parent_domain = get_parent_domain(domain_lower)
    if parent_domain != domain_lower and check_trackerradar(parent_domain):
        return True
    
    # 5. Try parent domain with www
    parent_www = f"www.{parent_domain}"
    if check_trackerradar(parent_www):
        return True
    
    # 6. Fallback to hardcoded list with same matching logic
    def check_fallback(check_domain):
        return check_domain in FALLBACK_KNOWN_TRACKERS
    
    # Check exact, www variants, and parent domain in fallback list
    if (check_fallback(domain_lower) or 
        (domain_lower.startswith('www.') and check_fallback(domain_lower[4:])) or
        check_fallback(www_domain) or
        (parent_domain != domain_lower and check_fallback(parent_domain)) or
        check_fallback(parent_www)):
        return True
    
    return False

logger = logging.getLogger(__name__)

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
    tracking_domains = set()  # All tracking domains (both third-party and first-party)
    third_party_request_count = 0
    
    # Process network requests
    for req in data.network_requests:
        if req.domain:
            all_domains.add(req.domain)
            # Backend computes third-party status
            if is_third_party_domain(req.domain, page_domain):
                third_party_domains.add(req.domain)
                third_party_request_count += 1
            # Track ALL tracker domains (third-party AND first-party)
            if is_known_tracker(req.domain):
                tracking_domains.add(req.domain)
    
    # Process script domains
    for script in data.scripts:
        if script.domain:
            all_domains.add(script.domain)
            if is_third_party_domain(script.domain, page_domain):
                third_party_domains.add(script.domain)
            # Track ALL tracker domains
            if is_known_tracker(script.domain):
                tracking_domains.add(script.domain)
    
    # Process cookie domains
    for cookie in data.raw_cookies:
        if cookie.domain:
            all_domains.add(cookie.domain)
            if is_third_party_domain(cookie.domain, page_domain):
                third_party_domains.add(cookie.domain)
            # Track ALL tracker domains
            if is_known_tracker(cookie.domain):
                tracking_domains.add(cookie.domain)
    
    # Feature 1: Number of unique third-party domains (across ALL sources: scripts, cookies, requests)
    features.num_third_party_domains = len(third_party_domains)
    
    # Feature 1b: Number of tracking domains (both third-party AND first-party)
    features.num_tracking_domains = len(tracking_domains)
    
    # Feature 1c: Total unique domains (both first-party and third-party)
    features.num_total_domains = len(all_domains)
    
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
    
    # Feature 10: Tracker script ratio (tracking domains / total domains)
    features.tracker_script_ratio = (
        features.num_tracking_domains / features.num_total_domains if features.num_total_domains > 0 else 0.0
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
    logger.info(f"  Feature 1b - Tracking domains: {features.num_tracking_domains}")
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
    if penalties.get("tracking_domains", 0) < 0:
        trackers = features.num_tracking_domains
        if trackers >= 11:
            findings.append(f"Excessive tracking detected ({trackers} tracking domains)")
            recommendations.append("Enable strict tracking protection and consider using a privacy-focused browser")
        elif trackers >= 6:
            findings.append(f"Heavy tracking detected ({trackers} tracking domains)")
            recommendations.append("Enable enhanced tracking protection and block third-party trackers")
        elif trackers >= 2:
            findings.append(f"Multiple tracking domains detected ({trackers} trackers)")
            recommendations.append("Consider enabling tracking protection in your browser")
        else:
            findings.append(f"Tracking domain detected ({trackers} tracker)")
            recommendations.append("Monitor for tracking activity")
    
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
    
    # Determine privacy level based on final score (aligned with letter grades)
    if score_result["score"] >= 75:
        privacy_level = "high"      # Matches A grade (75-100)
    elif score_result["score"] >= 60:
        privacy_level = "medium"    # Matches B grade (60-75)
    else:
        privacy_level = "low"       # Matches C, D, F grades (<60)
    
    # Extract unique third-party domains and trackers for response (from ALL sources)
    third_party_domains_for_response = set()
    known_trackers_for_response = set()
    
    # Check network requests
    for req in data.network_requests:
        if req.domain:
            if is_third_party_domain(req.domain, data.page_domain):
                third_party_domains_for_response.add(req.domain)
            # Check ALL domains for tracking (not just third-party)
            if is_known_tracker(req.domain):
                known_trackers_for_response.add(req.domain)
    
    # Check scripts
    for script in data.scripts:
        if script.domain:
            if is_third_party_domain(script.domain, data.page_domain):
                third_party_domains_for_response.add(script.domain)
            # Check ALL domains for tracking (not just third-party)
            if is_known_tracker(script.domain):
                known_trackers_for_response.add(script.domain)
    
    # Check cookies
    for cookie in data.raw_cookies:
        if cookie.domain:
            if is_third_party_domain(cookie.domain, data.page_domain):
                third_party_domains_for_response.add(cookie.domain)
            # Check ALL domains for tracking (not just third-party)
            if is_known_tracker(cookie.domain):
                known_trackers_for_response.add(cookie.domain)
    
    # Add fallback message if no issues detected
    if not findings:
        findings.append("No significant privacy issues detected")
        recommendations.append("Website demonstrates good privacy practices")
    
    # Sort known trackers by severity (most severe first)
    sorted_known_trackers = sorted(
        known_trackers_for_response, 
        key=lambda domain: get_tracker_severity_score(domain),
        reverse=True  # Most severe first
    )
    
    # Get individual domain scores for tracking domains
    tracking_domains_with_scores = []
    try:
        if data and domain_scoring_service.is_loaded:
            # Get detailed scoring for all domains
            domain_counts = domain_scoring_service.extract_domains_from_analyze_request(data)
            scoring_result = domain_scoring_service.score_domains(domain_counts)
            
            # Create lookup for domain scores
            domain_score_lookup = {ds.domain: ds.domain_safe_score for ds in scoring_result.domains}
            
            # Add scores to tracking domains
            for domain in sorted_known_trackers:
                score = domain_score_lookup.get(domain, 95.0)  # Fallback to 95.0
                tracking_domains_with_scores.append({
                    "domain": domain,
                    "score": round(score, 1)
                })
            
            logger.info(f"ML scoring successful. Created {len(tracking_domains_with_scores)} tracking domains with scores")
        else:
            # Fallback without scores
            for domain in sorted_known_trackers:
                tracking_domains_with_scores.append({
                    "domain": domain,
                    "score": 95.0
                })
            logger.info(f"ML scoring not available. Created {len(tracking_domains_with_scores)} tracking domains with fallback scores")
    except Exception as e:
        logger.warning(f"Failed to get domain scores: {e}")
        # Fallback without scores
        for domain in sorted_known_trackers:
            tracking_domains_with_scores.append({
                "domain": domain,
                "score": 95.0
            })
    
    logger.info(f"Final tracking_domains_with_scores: {tracking_domains_with_scores}")
    
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
        "known_trackers": sorted_known_trackers,
        "known_trackers_with_scores": tracking_domains_with_scores,
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
    
    # (1) third_party_domains penalty (gentler for non-tracking domains)
    non_tracking_domains = max(0, features.num_third_party_domains - features.num_tracking_domains)
    if non_tracking_domains == 0:
        penalties["third_party_domains"] = 0.0
    elif non_tracking_domains <= 5:
        penalties["third_party_domains"] = -0.5
    else:  # 6+ non-tracking third parties
        penalties["third_party_domains"] = -1.0
    
    # (1b) tracking_domains penalty (much heavier)
    trackers = features.num_tracking_domains
    if trackers == 0:
        penalties["tracking_domains"] = 0.0
    elif trackers == 1:
        penalties["tracking_domains"] = -3.0  # Significant penalty for even 1 tracker
    elif trackers <= 3:
        penalties["tracking_domains"] = -6.0
    elif trackers <= 5:
        penalties["tracking_domains"] = -9.0
    elif trackers <= 10:
        penalties["tracking_domains"] = -12.0
    else:  # 11+ trackers - very severe
        penalties["tracking_domains"] = -15.0
    
    # Removed third-party cookies penalty calculation
    
    # Removed tracker domains penalty calculation
    
    # (6) persistent_cookies penalty (simplified without third-party cookies dependency)
    persistent = features.num_persistent_cookies
    if persistent == 0:
        penalties["persistent_cookies"] = 0.0
    elif persistent <= 2:
        penalties["persistent_cookies"] = -0.5
    elif persistent <= 5:
        penalties["persistent_cookies"] = -1.0
    else:  # 6+
        penalties["persistent_cookies"] = -1.5
    
    # (7) has_analytics_global penalty (reduced)
    if features.has_analytics_global == 1:
        penalties["analytics_global"] = -1.0
    else:
        penalties["analytics_global"] = 0.0
    
    # (8) inline_scripts penalty (proportion-based and gentler)
    # Since we removed third-party scripts count, just check inline scripts count directly
    if features.num_inline_scripts == 0:
        penalties["inline_scripts"] = 0.0
    elif features.num_inline_scripts <= 3:
        penalties["inline_scripts"] = -0.5
    else:  # 4+ inline scripts
        penalties["inline_scripts"] = -1.0
    
    # (9) fingerprinting_flag penalty (reduced)
    if features.fingerprinting_flag == 1:
        penalties["fingerprinting"] = -2.0
    else:
        penalties["fingerprinting"] = 0.0
    
    # (10) tracker_script_ratio penalty (gentler)
    ratio = features.tracker_script_ratio
    if ratio <= 0.10:  # 10% or less tracker scripts
        penalties["tracker_script_ratio"] = 0.0
    elif ratio <= 0.25:  # 10-25% tracker scripts
        penalties["tracker_script_ratio"] = -0.5
    elif ratio <= 0.50:  # 25-50% tracker scripts
        penalties["tracker_script_ratio"] = -1.0
    else:  # 50%+ tracker scripts
        penalties["tracker_script_ratio"] = -1.5
    
    # Calculate total penalty and apply dynamic cap based on tracking severity
    total_penalty = sum(penalties.values())
    
    # Dynamic penalty cap - more trackers = higher cap
    if features.num_tracking_domains >= 10:
        penalty_cap = -25.0  # Heavy tracking deserves severe penalty
    elif features.num_tracking_domains >= 5:
        penalty_cap = -18.0  # Moderate tracking
    elif features.num_tracking_domains >= 1:
        penalty_cap = -15.0  # Some tracking
    else:
        penalty_cap = -10.0  # No tracking - gentle cap
        
    capped_penalty = max(total_penalty, penalty_cap)
    
    # Calculate final score
    final_score = ml_score + capped_penalty
    final_score = max(0.0, min(100.0, final_score))  # Clamp 0-100
    
    # Determine letter grade (shifted up for more realistic grading)
    if 75.0 <= final_score <= 100.0:
        grade = "A"
    elif 60.0 <= final_score < 75.0:
        grade = "B"
    elif 40.0 <= final_score < 60.0:
        grade = "C"
    elif 25.0 <= final_score < 40.0:
        grade = "D"
    else:  # 0-24
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
    
    # Heavy penalty for tracking domains (this is the main privacy concern)
    # Each tracking domain gets progressively more severe penalty
    if features.num_tracking_domains > 0:
        # Base penalty: 8 points per tracking domain
        base_penalty = features.num_tracking_domains * 8
        # Progressive penalty for many trackers (exponential growth)
        if features.num_tracking_domains >= 10:
            bonus_penalty = (features.num_tracking_domains - 9) * 5  # Extra 5 per tracker beyond 9
        else:
            bonus_penalty = 0
        tracking_penalty = min(base_penalty + bonus_penalty, 60)  # Max -60 for tracking
        score -= tracking_penalty
    
    # Moderate penalty for non-tracking third-party domains
    non_tracking_domains = max(0, features.num_third_party_domains - features.num_tracking_domains)
    score -= min(non_tracking_domains * 1, 15)  # Max -15 for non-tracking third parties
    
    # Other penalties
    score -= features.has_analytics_global * 10  # -10 for analytics
    score -= features.fingerprinting_flag * 15  # -15 for fingerprinting
    score -= min(features.num_persistent_cookies * 2, 20)  # Max -20 for persistent cookies
    
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
