from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis
import logging
from contextlib import asynccontextmanager
from datetime import datetime
import uvicorn

from app.config import settings
from app.routers import auth, analyze
from app.middleware import SecurityMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Redis connection for rate limiting on startup."""
    try:
        # Connect to Redis
        redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis_client)
        logger.info("Redis connection established for rate limiting")
        yield
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise
    finally:
        await FastAPILimiter.close()
        logger.info("Redis connection closed")

# Create FastAPI application
app = FastAPI(
    title="Privacy Inspector API",
    description="Secure API for browser extension privacy analysis",
    version="1.0.0",
    docs_url=None,  # Disable docs in production
    redoc_url=None,  # Disable redoc in production
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(SecurityMiddleware)

# Add CORS middleware with restricted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ALLOWED_ORIGIN] if settings.ALLOWED_ORIGIN != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["Authorization", "Content-Type", "X-Extension-Client"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception for {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.
    Returns detailed status of all critical services.
    """
    health_status = {
        "status": "healthy",
        "service": "privacy-inspector-api",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "components": {}
    }
    
    overall_healthy = True
    
    # Check Redis connection
    try:
        redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        await redis_client.ping()
        await redis_client.close()
        health_status["components"]["redis"] = {
            "status": "healthy",
            "message": "Redis connection successful"
        }
    except Exception as e:
        health_status["components"]["redis"] = {
            "status": "unhealthy", 
            "message": f"Redis connection failed: {str(e)}"
        }
        overall_healthy = False
    
    # Check JWT secret configuration
    try:
        jwt_secrets = settings.get_jwt_secrets()
        health_status["components"]["jwt"] = {
            "status": "healthy",
            "message": f"JWT configured with {len(jwt_secrets)} secret(s)"
        }
    except Exception as e:
        health_status["components"]["jwt"] = {
            "status": "unhealthy",
            "message": f"JWT configuration error: {str(e)}"
        }
        overall_healthy = False
    
    # Check critical configuration
    config_issues = []
    if settings.JWT_SECRET == "dev-secret-change-in-production":
        config_issues.append("Using default JWT secret (SECURITY RISK)")
    if settings.ALLOWED_ORIGIN == "chrome-extension://your-extension-id-here":
        config_issues.append("Using placeholder extension origin")
    if settings.DEBUG:
        config_issues.append("Debug mode enabled")
    
    if config_issues:
        health_status["components"]["configuration"] = {
            "status": "warning",
            "message": "Configuration issues detected",
            "issues": config_issues
        }
        # Don't mark as unhealthy for warnings, but flag them
    else:
        health_status["components"]["configuration"] = {
            "status": "healthy", 
            "message": "Configuration validated"
        }
    
    # Set overall status
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    
    # Return appropriate HTTP status code
    status_code = 200 if overall_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content=health_status
    )

# Include routers with rate limiting
app.include_router(
    auth.router,
    prefix="/api/v1",
    dependencies=[Depends(RateLimiter(times=10, seconds=60))]  # 10 requests per minute
)

app.include_router(
    analyze.router,
    prefix="/api/v1",
    dependencies=[Depends(RateLimiter(times=5, seconds=60))]   # 5 requests per minute for analysis
)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload in production
        access_log=True
    )
