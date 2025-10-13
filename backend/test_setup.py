#!/usr/bin/env python3
"""
Test script to validate the FastAPI server setup.
Run this to check if all dependencies are properly installed and configured.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all required packages can be imported."""
    print("Testing imports...")
    
    try:
        import fastapi
        print(f"✅ FastAPI: {fastapi.__version__}")
    except ImportError as e:
        print(f"❌ FastAPI import failed: {e}")
        return False
    
    try:
        import uvicorn
        print(f"✅ Uvicorn available")
    except ImportError as e:
        print(f"❌ Uvicorn import failed: {e}")
        return False
    
    try:
        import jwt
        print(f"✅ PyJWT available")
    except ImportError as e:
        print(f"❌ PyJWT import failed: {e}")
        return False
    
    try:
        import redis
        print(f"✅ Redis: {redis.__version__}")
    except ImportError as e:
        print(f"❌ Redis import failed: {e}")
        return False
    
    try:
        import pydantic
        print(f"✅ Pydantic: {pydantic.__version__}")
    except ImportError as e:
        print(f"❌ Pydantic import failed: {e}")
        return False
    
    return True

def test_app_imports():
    """Test if our app modules can be imported."""
    print("\nTesting app imports...")
    
    try:
        from app.config import settings
        print(f"✅ Config loaded - JWT Secret length: {len(settings.JWT_SECRET)}")
        print(f"✅ Allowed Origin: {settings.ALLOWED_ORIGIN}")
    except ImportError as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        from app.models import AnalyzeRequest, AuthResponse
        print("✅ Models imported successfully")
    except ImportError as e:
        print(f"❌ Models import failed: {e}")
        return False
    
    try:
        from app.middleware import SecurityMiddleware
        print("✅ Middleware imported successfully")
    except ImportError as e:
        print(f"❌ Middleware import failed: {e}")
        return False
    
    try:
        from app.routers import auth, analyze
        print("✅ Routers imported successfully")
    except ImportError as e:
        print(f"❌ Routers import failed: {e}")
        return False
    
    return True

def test_jwt_functionality():
    """Test JWT token creation and validation."""
    print("\nTesting JWT functionality...")
    
    try:
        from app.routers.auth import create_jwt_token
        import jwt as jwt_lib
        from app.config import settings
        
        # Create a token
        token = create_jwt_token()
        print(f"✅ JWT token created: {token[:20]}...")
        
        # Verify the token
        payload = jwt_lib.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        print(f"✅ JWT token verified - type: {payload.get('type')}")
        
        return True
    except Exception as e:
        print(f"❌ JWT functionality test failed: {e}")
        return False

def test_app_creation():
    """Test if the FastAPI app can be created."""
    print("\nTesting FastAPI app creation...")
    
    try:
        # Note: We can't fully test the app without Redis running
        # But we can test if the app can be imported
        import main
        print("✅ Main module imported successfully")
        
        # Test if we can access the app object
        app = main.app
        print(f"✅ FastAPI app created - Title: {app.title}")
        
        return True
    except Exception as e:
        print(f"❌ App creation test failed: {e}")
        print("Note: This might fail if Redis is not running, which is expected for this test.")
        return False

def main():
    """Run all tests."""
    print("🔍 Privacy Inspector API - Setup Validation")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_app_imports,
        test_jwt_functionality,
        test_app_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Start Redis: brew install redis && brew services start redis")
        print("2. Update .env with your actual Chrome extension ID")
        print("3. Run the server: python main.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
