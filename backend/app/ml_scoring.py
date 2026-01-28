"""
Domain Scoring API Integration

This module adds ML-based domain scoring to the existing FastAPI application.
It loads a pre-trained domain risk model and provides endpoints for scoring domains.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Union
import logging

import joblib
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Import existing models from the main app
from app.models import AnalyzeRequest

logger = logging.getLogger(__name__)

class DomainScore(BaseModel):
    """Individual domain score result"""
    domain: str
    count: int
    domain_known: bool
    domain_safe_score: float
    weight: float

class DomainScoringRequest(BaseModel):
    """Request model for domain scoring endpoint"""
    domains: List[Dict[str, Union[str, int]]]  # [{"domain": "example.com", "count": 3}, ...]

class DomainScoringResponse(BaseModel):
    """Response model for domain scoring endpoint"""
    domains: List[DomainScore]
    aggregated_ml_score: float
    model_used: str
    total_domains: int
    known_domains: int
    unknown_domains: int

class ModelInfo(BaseModel):
    """Model metadata response"""
    model_type: str
    feature_names: List[str]
    total_domains_in_training: int
    model_path: str
    features_path: str

class DomainScoringService:
    """Service for ML-based domain scoring"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.model_type = None
        self.domain_features = {}
        self.is_loaded = False
        
        # Configuration
        self.DOMAIN_MULTIPLIER = 3.0  # Weight multiplier for known domains
        self.UNKNOWN_DOMAIN_SCORE = 95.0  # Default score for unknown domains
        
    def load_model(self, model_path: str, features_path: str):
        """Load trained model and domain features"""
        try:
            # Load model artifacts
            if not Path(model_path).exists():
                logger.warning(f"Model file not found: {model_path}")
                return False
                
            artifacts = joblib.load(model_path)
            self.model = artifacts['model']
            self.scaler = artifacts['scaler']
            self.feature_names = artifacts['feature_names']
            self.model_type = artifacts.get('model_type', 'unknown')
            
            # Load domain features
            if Path(features_path).exists():
                with open(features_path, 'r') as f:
                    self.domain_features = json.load(f)
            else:
                logger.warning(f"Features file not found: {features_path}")
                self.domain_features = {}
            
            self.is_loaded = True
            logger.info(f"Model loaded successfully: {self.model_type}")
            logger.info(f"Known domains: {len(self.domain_features)}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False
    
    def compute_domain_safe_score(self, domain: str) -> tuple[float, bool]:
        """
        Compute safety score for a single domain
        Returns (score, is_known) where score is 0-100 (higher = safer)
        """
        if not self.is_loaded:
            logger.debug(f"ML service not loaded, returning unknown score for {domain}")
            return self.UNKNOWN_DOMAIN_SCORE, False
        
        original_domain = domain.lower()
        
        # List of domain variations to try
        variations_to_try = [
            original_domain,  # Exact match first
        ]
        
        # Remove common prefixes
        if original_domain.startswith('www.'):
            variations_to_try.append(original_domain[4:])
        else:
            variations_to_try.append(f"www.{original_domain}")
            
        # Try without common tracking subdomains
        tracking_prefixes = ['stats.', 'analytics.', 'tracking.', 'data.', 'metrics.', 'secure.', 'api.', 'cdn.', 'static.']
        for prefix in tracking_prefixes:
            if original_domain.startswith(prefix):
                base_domain = original_domain[len(prefix):]
                variations_to_try.append(base_domain)
                variations_to_try.append(f"www.{base_domain}")
                
        # Try parent domain for complex subdomains
        parts = original_domain.split('.')
        if len(parts) >= 3:
            parent_domain = '.'.join(parts[-2:])  # Get domain.tld
            variations_to_try.append(parent_domain)
            variations_to_try.append(f"www.{parent_domain}")
        
        # Remove duplicates while preserving order
        unique_variations = []
        seen = set()
        for var in variations_to_try:
            if var not in seen:
                unique_variations.append(var)
                seen.add(var)
        
        # Try each variation
        for variation in unique_variations:
            if variation in self.domain_features:
                logger.debug(f"Found ML score for '{original_domain}' using variation '{variation}'")
                try:
                    # Get domain features
                    features = self.domain_features[variation]
                    
                    # Convert to numpy array in correct order
                    feature_values = np.array([features[name] for name in self.feature_names]).reshape(1, -1)
                    
                    # Scale features
                    feature_values_scaled = self.scaler.transform(feature_values)
                    
                    # Predict tracking intensity (0-1, higher = more tracking)
                    predicted_intensity = self.model.predict(feature_values_scaled)[0]
                    
                    # Convert to safety score (0-100, higher = safer)
                    domain_safe_score = round((1.0 - predicted_intensity) * 100, 2)
                    domain_safe_score = max(0.0, min(100.0, domain_safe_score))  # Clamp to 0-100
                    
                    return domain_safe_score, True
                    
                except Exception as e:
                    logger.error(f"Error computing score for domain {original_domain} (variation {variation}): {e}")
                    continue
        
        # If no variation worked, log and return unknown score
        logger.debug(f"Domain '{original_domain}' not found in tracker radar data (tried {len(unique_variations)} variations)")
        return self.UNKNOWN_DOMAIN_SCORE, False
    
    def score_domains(self, domain_counts: List[Dict[str, Union[str, int]]]) -> DomainScoringResponse:
        """
        Score multiple domains and compute aggregated ML score
        """
        domain_scores = []
        total_weight = 0.0
        weighted_score_sum = 0.0
        known_domains = 0
        
        for item in domain_counts:
            domain = item['domain']
            count = item['count']
            
            # Compute domain score
            domain_safe_score, is_known = self.compute_domain_safe_score(domain)
            
            # Compute weight
            multiplier = self.DOMAIN_MULTIPLIER if is_known else 1.0
            weight = count * multiplier
            
            # Add to aggregation
            total_weight += weight
            weighted_score_sum += domain_safe_score * weight
            
            if is_known:
                known_domains += 1
            
            # Store domain score
            domain_scores.append(DomainScore(
                domain=domain,
                count=count,
                domain_known=is_known,
                domain_safe_score=domain_safe_score,
                weight=weight
            ))
        
        # Compute aggregated ML score
        if total_weight > 0:
            aggregated_ml_score = weighted_score_sum / total_weight
        else:
            aggregated_ml_score = self.UNKNOWN_DOMAIN_SCORE
        
        # Clamp to 0-100
        aggregated_ml_score = max(0.0, min(100.0, aggregated_ml_score))
        
        return DomainScoringResponse(
            domains=domain_scores,
            aggregated_ml_score=round(aggregated_ml_score, 2),
            model_used=self.model_type if self.is_loaded else "none",
            total_domains=len(domain_scores),
            known_domains=known_domains,
            unknown_domains=len(domain_scores) - known_domains
        )
    
    def extract_domains_from_analyze_request(self, request: AnalyzeRequest) -> List[Dict[str, Union[str, int]]]:
        """Extract domains and counts from AnalyzeRequest using normalized domain names"""
        # Import normalize_domain function from analyze module
        from app.routers.analyze import normalize_domain
        
        domain_counts = {}
        
        # Extract from network requests
        for req in request.network_requests:
            if req.domain:
                normalized_domain = normalize_domain(req.domain)
                domain_counts[normalized_domain] = domain_counts.get(normalized_domain, 0) + 1
        
        # Extract from scripts
        for script in request.scripts:
            if script.domain:
                normalized_domain = normalize_domain(script.domain)
                domain_counts[normalized_domain] = domain_counts.get(normalized_domain, 0) + 1
        
        # Extract from cookies
        for cookie in request.raw_cookies:
            if cookie.domain:
                normalized_domain = normalize_domain(cookie.domain)
                domain_counts[normalized_domain] = domain_counts.get(normalized_domain, 0) + 1
        
        # Convert to list format
        return [{"domain": domain, "count": count} for domain, count in domain_counts.items()]

# Global service instance
domain_scoring_service = DomainScoringService()

# Router for domain scoring endpoints
router = APIRouter(prefix="/model", tags=["model"])

@router.get("/info", response_model=ModelInfo)
async def get_model_info():
    """Get information about the loaded model"""
    if not domain_scoring_service.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    return ModelInfo(
        model_type=domain_scoring_service.model_type,
        feature_names=domain_scoring_service.feature_names,
        total_domains_in_training=len(domain_scoring_service.domain_features),
        model_path="models/domain_risk_model.pkl",
        features_path="models/domain_features.json"
    )

@router.post("/score_domains", response_model=DomainScoringResponse)
async def score_domains(request: Union[DomainScoringRequest, AnalyzeRequest]):
    """
    Score domains for privacy risk
    
    Accepts either:
    1. DomainScoringRequest with explicit domain list
    2. AnalyzeRequest (existing format) - domains will be extracted
    """
    try:
        # Handle different request types
        if isinstance(request, DomainScoringRequest):
            domain_counts = request.domains
        else:  # AnalyzeRequest
            domain_counts = domain_scoring_service.extract_domains_from_analyze_request(request)
        
        # Score domains
        result = domain_scoring_service.score_domains(domain_counts)
        return result
        
    except Exception as e:
        logger.error(f"Error scoring domains: {e}")
        raise HTTPException(status_code=500, detail=f"Domain scoring error: {str(e)}")

def initialize_domain_scoring():
    """Initialize domain scoring service at startup"""
    # Model files are in the parent directory from backend/
    import os
    backend_dir = Path(__file__).parent.parent  # Go up from backend/app/ to backend/
    project_root = backend_dir.parent  # Go up from backend/ to project root
    
    model_path = project_root / "models" / "domain_risk_model.pkl"
    features_path = project_root / "models" / "domain_features.json"
    
    logger.info(f"Looking for model at: {model_path}")
    logger.info(f"Looking for features at: {features_path}")
    
    success = domain_scoring_service.load_model(str(model_path), str(features_path))
    if success:
        logger.info("Domain scoring service initialized successfully")
    else:
        logger.warning("Domain scoring service failed to load - will use fallback scores")

def get_ml_score_for_page(features: Union[AnalyzeRequest, "PrivacyFeatures"]) -> float:
    """
    Get ML score for a page (for integration with existing scoring pipeline)
    Returns aggregated ML score that can be used in compute_privacy_score
    """
    try:
        if not domain_scoring_service.is_loaded:
            return 100.0  # Fallback to original placeholder score
        
        # Handle both AnalyzeRequest and PrivacyFeatures input
        domain_counts = []
        if hasattr(features, 'third_party_domains') and features.third_party_domains:
            # PrivacyFeatures input
            for domain in features.third_party_domains:
                domain_counts.append({"domain": domain, "count": 1})
        elif hasattr(features, 'network_requests'):
            # AnalyzeRequest input
            domain_counts = domain_scoring_service.extract_domains_from_analyze_request(features)
        
        if not domain_counts:
            return 100.0  # No domains to score
        
        result = domain_scoring_service.score_domains(domain_counts)
        return result.aggregated_ml_score
        
    except Exception as e:
        logger.error(f"Error getting ML score: {e}")
        return 100.0  # Fallback on error