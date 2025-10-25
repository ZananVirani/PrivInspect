from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPAuthorizationCredentials
import logging
from app.config import settings
from app.middleware import validate_extension_headers
from app.routers.auth import verify_jwt_token
from app.models import AnalyzeRequest, AnalyzeResponse
from app.security.extension_auth import validate_extension_request

logger = logging.getLogger(__name__)
router = APIRouter()

async def analyze_privacy_data(data: dict) -> dict:
    """
    Analyze the privacy-related data from the browser extension.
    This is where you would implement your actual analysis logic.
    """
    # Placeholder analysis logic
    cookies_count = len(data.get("cookies", []))
    scripts_count = len(data.get("scripts", []))
    
    # Example privacy score calculation
    privacy_score = max(0, 100 - (cookies_count * 2) - (scripts_count * 1))
    
    findings = []
    if cookies_count > 10:
        findings.append("High number of tracking cookies detected")
    if scripts_count > 20:
        findings.append("Numerous third-party scripts loaded")
    
    return {
        "privacy_score": privacy_score,
        "cookies_analyzed": cookies_count,
        "scripts_analyzed": scripts_count,
        "findings": findings,
        "recommendations": [
            "Consider using a cookie blocker",
            "Review website permissions",
            "Enable enhanced tracking protection"
        ] if findings else ["Website appears to have good privacy practices"]
    }

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_website_privacy(
    analyze_data: AnalyzeRequest,
    request: Request,
    # extension_validation: dict = Depends(validate_extension_request),  # Temporarily disabled
    _: dict = Depends(validate_extension_headers),
    token_payload: dict = Depends(verify_jwt_token)
):
    """
    Analyze website privacy data from the browser extension.
    Requires valid JWT token and extension headers.
    """
    logger.info("Hiiiii")
    return AnalyzeResponse(
        privacy_score=1,
        cookies_analyzed=432,
        scripts_analyzed=34342,
    )
    # try:
    #     # Log the analysis request (without sensitive data)
    #     logger.info(
    #         f"Analysis request from IP: {request.client.host}, "
    #         f"URL: {analyze_data.url}, "
    #         # f"Extension ID: {extension_validation.get('extension_id', 'unknown')}, "  # Temporarily disabled
    #         f"Token type: {token_payload.get('type', 'unknown')}"
    #     )
        
    #     # Perform the privacy analysis
    #     analysis_result = await analyze_privacy_data({
    #         "cookies": analyze_data.cookies,
    #         "scripts": analyze_data.scripts,
    #         "url": analyze_data.url
    #     })
        
    #     return AnalyzeResponse(**analysis_result)
    
    # except Exception as e:
    #     logger.error(f"Error during analysis: {e}")
    #     raise HTTPException(
    #         status_code=500,
    #         detail="Internal server error during analysis"
    #     )
