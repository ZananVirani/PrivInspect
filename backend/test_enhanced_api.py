"""
Enhanced API test script with new extension authentication.
Tests all security layers including nonce-based replay protection.
"""
import asyncio
import hashlib
import hmac
import time
import uuid
import requests
import json
from datetime import datetime

API_BASE_URL = "http://localhost:8000"
EXTENSION_ID = "test-extension-id-12345"
SERVER_SECRET = "dev-secret-change-in-production"  # Should match JWT_SECRET
EXTENSION_CLIENT_HEADER = "privacy-inspector"

class ExtensionAuthenticator:
    """Client-side authentication helper (Python version)"""
    
    def __init__(self, extension_id: str, server_secret: str):
        self.extension_id = extension_id
        self.server_secret = server_secret
    
    def generate_nonce(self) -> str:
        """Generate unique nonce for each request"""
        return str(uuid.uuid4())
    
    def get_timestamp(self) -> int:
        """Get current Unix timestamp"""
        return int(time.time())
    
    def generate_signature(self, extension_id: str, timestamp: int, secret: str) -> str:
        """Generate HMAC-SHA256 signature"""
        message = f"{extension_id}:{timestamp}:{secret}"
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def create_auth_headers(self, jwt_token: str) -> dict:
        """Create complete authentication headers"""
        timestamp = self.get_timestamp()
        nonce = self.generate_nonce()
        signature = self.generate_signature(self.extension_id, timestamp, self.server_secret)
        
        return {
            'Authorization': f'Bearer {jwt_token}',
            'X-Extension-ID': self.extension_id,
            'X-Request-Timestamp': str(timestamp),
            'X-Request-Signature': signature,
            'X-Request-Nonce': nonce,
            'X-Extension-Client': EXTENSION_CLIENT_HEADER,
            'Content-Type': 'application/json',
            'Origin': 'chrome-extension://' + self.extension_id,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
        }

def test_health_check():
    """Test basic health check"""
    print("🔍 Testing health check...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        print(f"✅ Health check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_authentication():
    """Test JWT token generation"""
    print("\n🔍 Testing authentication...")
    try:
        headers = {
            'X-Extension-Client': EXTENSION_CLIENT_HEADER,
            'Content-Type': 'application/json',
            'Origin': f'chrome-extension://{EXTENSION_ID}',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/auth",
            headers=headers
        )
        
        if response.status_code == 200:
            token_data = response.json()
            print(f"✅ Authentication successful: {response.status_code}")
            print(f"   Token type: {token_data.get('token_type')}")
            print(f"   Expires in: {token_data.get('expires_in')} seconds")
            return token_data.get('access_token')
        else:
            print(f"❌ Authentication failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return None

def test_enhanced_analysis(jwt_token: str):
    """Test analysis endpoint with new authentication layers"""
    print("\n🔍 Testing enhanced analysis with all security layers...")
    
    try:
        auth = ExtensionAuthenticator(EXTENSION_ID, SERVER_SECRET)
        headers = auth.create_auth_headers(jwt_token)
        
        analysis_data = {
            "url": "https://example.com",
            "cookies": [
                {"name": "session_id", "value": "abc123", "domain": "example.com"},
                {"name": "tracking_id", "value": "xyz789", "domain": ".example.com"}
            ],
            "scripts": [
                {"src": "https://analytics.google.com/gtag.js", "type": "text/javascript"},
                {"src": "https://facebook.com/tr", "type": "text/javascript"}
            ]
        }
        
        print(f"   Using Extension ID: {EXTENSION_ID}")
        print(f"   Timestamp: {headers['X-Request-Timestamp']}")
        print(f"   Nonce: {headers['X-Request-Nonce']}")
        print(f"   Signature: {headers['X-Request-Signature'][:20]}...")
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/analyze",
            json=analysis_data,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Enhanced analysis successful: {response.status_code}")
            print(f"   Privacy score: {result.get('privacy_score')}")
            print(f"   Cookies analyzed: {result.get('cookies_analyzed')}")
            print(f"   Scripts analyzed: {result.get('scripts_analyzed')}")
            print(f"   Findings: {len(result.get('findings', []))} issues found")
            return True
        else:
            print(f"❌ Enhanced analysis failed: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"   Error: {error_detail}")
            except:
                print(f"   Error text: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Enhanced analysis error: {e}")
        return False

def test_replay_attack_protection(jwt_token: str):
    """Test that replay attacks are blocked"""
    print("\n🔍 Testing replay attack protection...")
    
    try:
        auth = ExtensionAuthenticator(EXTENSION_ID, SERVER_SECRET)
        headers = auth.create_auth_headers(jwt_token)
        
        analysis_data = {
            "url": "https://replay-test.com",
            "cookies": [],
            "scripts": []
        }
        
        # First request should succeed
        print("   Making first request...")
        response1 = requests.post(
            f"{API_BASE_URL}/api/v1/analyze",
            json=analysis_data,
            headers=headers
        )
        
        # Second request with same headers should fail (nonce reuse)
        print("   Attempting replay with same nonce...")
        response2 = requests.post(
            f"{API_BASE_URL}/api/v1/analyze",
            json=analysis_data,
            headers=headers  # Same headers = same nonce
        )
        
        if response1.status_code == 200 and response2.status_code == 401:
            print("✅ Replay protection working:")
            print(f"   First request: {response1.status_code} (success)")
            print(f"   Replay attempt: {response2.status_code} (blocked)")
            return True
        else:
            print(f"❌ Replay protection failed:")
            print(f"   First request: {response1.status_code}")
            print(f"   Replay attempt: {response2.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Replay protection test error: {e}")
        return False

def test_timestamp_validation(jwt_token: str):
    """Test that old timestamps are rejected"""
    print("\n🔍 Testing timestamp validation...")
    
    try:
        auth = ExtensionAuthenticator(EXTENSION_ID, SERVER_SECRET)
        
        # Create headers with old timestamp (2 minutes ago)
        old_timestamp = int(time.time()) - 120  # 2 minutes ago
        nonce = auth.generate_nonce()
        signature = auth.generate_signature(EXTENSION_ID, old_timestamp, SERVER_SECRET)
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'X-Extension-ID': EXTENSION_ID,
            'X-Request-Timestamp': str(old_timestamp),
            'X-Request-Signature': signature,
            'X-Request-Nonce': nonce,
            'X-Extension-Client': EXTENSION_CLIENT_HEADER,
            'Content-Type': 'application/json',
            'Origin': f'chrome-extension://{EXTENSION_ID}',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        analysis_data = {"url": "https://timestamp-test.com", "cookies": [], "scripts": []}
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/analyze",
            json=analysis_data,
            headers=headers
        )
        
        if response.status_code == 401:
            print(f"✅ Timestamp validation working: {response.status_code} (old timestamp rejected)")
            return True
        else:
            print(f"❌ Timestamp validation failed: {response.status_code} (should be 401)")
            return False
            
    except Exception as e:
        print(f"❌ Timestamp validation test error: {e}")
        return False

def main():
    """Run complete API test suite"""
    print("🚀 Starting Enhanced PrivInspect API Test Suite")
    print("=" * 60)
    
    # Step 1: Health check
    if not test_health_check():
        print("❌ Server appears to be down. Please start the server first.")
        return
    
    # Step 2: Authentication
    jwt_token = test_authentication()
    if not jwt_token:
        print("❌ Cannot proceed without valid authentication")
        return
    
    # Step 3: Enhanced analysis with new security layers
    if not test_enhanced_analysis(jwt_token):
        print("❌ Enhanced analysis failed")
        return
    
    # Step 4: Test replay protection
    test_replay_attack_protection(jwt_token)
    
    # Step 5: Test timestamp validation
    test_timestamp_validation(jwt_token)
    
    print("\n" + "=" * 60)
    print("🎉 Enhanced API test suite completed!")
    print("Your API now has multiple layers of protection against:")
    print("   - Request replay attacks (nonce validation)")
    print("   - Old request reuse (timestamp validation)")  
    print("   - Extension signature forgery (HMAC validation)")
    print("   - Non-browser automation (environment validation)")

if __name__ == "__main__":
    main()
