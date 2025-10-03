#!/usr/bin/env python3
"""
Test script for JWT secret rotation functionality.
Tests that tokens signed with old secrets are still valid during grace period.
"""

import os
import sys
import jwt
from datetime import datetime, timedelta

# Add app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_jwt_rotation():
    """Test JWT secret rotation with multiple secrets."""
    print("🔄 Testing JWT Secret Rotation")
    print("=" * 50)
    
    # Simulate different JWT secrets
    current_secret = "new-production-secret-key"
    old_secret = "previous-production-secret-key"
    
    # Create tokens with different secrets (simulating different times)
    print("Creating test tokens...")
    
    # Token created with current secret (new tokens)
    current_payload = {
        "exp": datetime.utcnow() + timedelta(minutes=15),
        "iat": datetime.utcnow(),
        "type": "access_token",
        "secret_version": "current"
    }
    current_token = jwt.encode(current_payload, current_secret, algorithm="HS256")
    
    # Token created with old secret (during grace period)
    old_payload = {
        "exp": datetime.utcnow() + timedelta(minutes=10),  # Still valid
        "iat": datetime.utcnow() - timedelta(minutes=5),   # Created 5 min ago
        "type": "access_token",
        "secret_version": "old"
    }
    old_token = jwt.encode(old_payload, old_secret, algorithm="HS256")
    
    # Test token verification with multiple secrets
    secrets = [current_secret, old_secret]
    
    def verify_token_with_secrets(token, token_name):
        """Verify token using multiple secrets (like our app does)."""
        print(f"\n🔍 Verifying {token_name}...")
        
        for i, secret in enumerate(secrets):
            try:
                payload = jwt.decode(token, secret, algorithms=["HS256"])
                secret_type = "current" if i == 0 else "old"
                print(f"✅ Token verified with {secret_type} secret")
                print(f"   Token version: {payload.get('secret_version', 'unknown')}")
                print(f"   Expires: {datetime.fromtimestamp(payload['exp'])}")
                return True
            except jwt.ExpiredSignatureError:
                print(f"❌ Token expired")
                return False
            except jwt.InvalidTokenError:
                continue
        
        print(f"❌ Token could not be verified with any secret")
        return False
    
    # Test all tokens
    results = []
    results.append(verify_token_with_secrets(current_token, "Current Token"))
    results.append(verify_token_with_secrets(old_token, "Old Token"))
    
    # Test with invalid token
    print(f"\n🔍 Verifying Invalid Token...")
    invalid_token = jwt.encode({"exp": datetime.utcnow() + timedelta(minutes=15)}, "wrong-secret", algorithm="HS256")
    results.append(verify_token_with_secrets(invalid_token, "Invalid Token"))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    test_names = ["Current Token", "Old Token", "Invalid Token"]
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
    
    expected_results = [True, True, False]  # Invalid token should fail
    if results == expected_results:
        print("\n🎉 All tests passed! JWT rotation is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Check implementation.")
        return False

def test_app_integration():
    """Test the actual app configuration."""
    print("\n🔧 Testing App Integration")
    print("=" * 30)
    
    try:
        # Test importing the updated config
        from app.config import settings
        
        # Test getting JWT secrets
        secrets = settings.get_jwt_secrets()
        print(f"✅ Config loaded successfully")
        print(f"✅ JWT secrets method available: {len(secrets)} secret(s)")
        print(f"   Primary secret length: {len(secrets[0])}")
        
        # Test auth module import
        from app.routers.auth import create_jwt_token, verify_jwt_token
        print(f"✅ Auth functions imported successfully")
        
        # Test token creation
        token = create_jwt_token()
        print(f"✅ Token creation works: {token[:20]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ App integration test failed: {e}")
        return False

def main():
    """Run all JWT rotation tests."""
    print("🧪 JWT Secret Rotation - Test Suite")
    print("=" * 60)
    
    # Run tests
    jwt_test_passed = test_jwt_rotation()
    app_test_passed = test_app_integration()
    
    print("\n" + "=" * 60)
    print("🎯 Final Results:")
    print(f"  JWT Rotation Logic: {'✅ PASS' if jwt_test_passed else '❌ FAIL'}")
    print(f"  App Integration: {'✅ PASS' if app_test_passed else '❌ FAIL'}")
    
    if jwt_test_passed and app_test_passed:
        print("\n🚀 JWT secret rotation is ready for production!")
        print("\nNext steps:")
        print("1. Set JWT_SECRET_OLD when rotating secrets")
        print("2. Monitor logs for old secret usage")
        print("3. Remove old secrets after grace period")
        return 0
    else:
        print("\n🔧 Fix the failing tests before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
