#!/usr/bin/env python3
"""
Example test client to demonstrate API usage.
This simulates how your Chrome extension would interact with the API.
"""

import requests
import json
import time

# API Configuration
BASE_URL = "http://localhost:8000/api/v1"
EXTENSION_HEADERS = {
    "X-Extension-Client": "privacy-inspector",
    "Content-Type": "application/json"
}

def test_auth_endpoint():
    """Test the authentication endpoint."""
    print("🔐 Testing Authentication Endpoint...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth",
            headers=EXTENSION_HEADERS
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            auth_data = response.json()
            print(f"✅ Authentication successful!")
            print(f"Token Type: {auth_data['token_type']}")
            print(f"Expires In: {auth_data['expires_in']} seconds")
            print(f"Token: {auth_data['access_token'][:30]}...")
            return auth_data['access_token']
        else:
            print(f"❌ Authentication failed: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Make sure the server is running on localhost:8000")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_analyze_endpoint(token):
    """Test the analyze endpoint with a JWT token."""
    print("\n🔍 Testing Analysis Endpoint...")
    
    # Sample data that would come from a browser extension
    sample_data = {
        "url": "https://example.com",
        "cookies": [
            {
                "name": "_ga",
                "value": "GA1.2.123456789.987654321",
                "domain": "example.com",
                "path": "/",
                "secure": True,
                "httpOnly": False,
                "sameSite": "Lax"
            },
            {
                "name": "session_id",
                "value": "abc123def456",
                "domain": "example.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "sameSite": "Strict"
            }
        ],
        "scripts": [
            {
                "src": "https://www.google-analytics.com/analytics.js",
                "type": "text/javascript",
                "async_load": True
            },
            {
                "src": "https://connect.facebook.net/en_US/fbevents.js",
                "type": "text/javascript",
                "async_load": True
            }
        ]
    }
    
    headers = EXTENSION_HEADERS.copy()
    headers["Authorization"] = f"Bearer {token}"
    
    try:
        response = requests.post(
            f"{BASE_URL}/analyze",
            headers=headers,
            json=sample_data
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            analysis = response.json()
            print("✅ Analysis successful!")
            print(f"Privacy Score: {analysis['privacy_score']}/100")
            print(f"Cookies Analyzed: {analysis['cookies_analyzed']}")
            print(f"Scripts Analyzed: {analysis['scripts_analyzed']}")
            print("Findings:")
            for finding in analysis['findings']:
                print(f"  - {finding}")
            print("Recommendations:")
            for rec in analysis['recommendations']:
                print(f"  - {rec}")
            return True
        else:
            print(f"❌ Analysis failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_rate_limiting(token):
    """Test rate limiting by making multiple requests quickly."""
    print("\n⏱️  Testing Rate Limiting...")
    
    headers = EXTENSION_HEADERS.copy()
    headers["Authorization"] = f"Bearer {token}"
    
    sample_data = {
        "url": "https://test-rate-limit.com",
        "cookies": [],
        "scripts": []
    }
    
    success_count = 0
    rate_limited_count = 0
    
    for i in range(8):  # Try 8 requests (limit is 5 per minute)
        try:
            response = requests.post(
                f"{BASE_URL}/analyze",
                headers=headers,
                json=sample_data
            )
            
            if response.status_code == 200:
                success_count += 1
                print(f"Request {i+1}: ✅ Success")
            elif response.status_code == 429:
                rate_limited_count += 1
                print(f"Request {i+1}: ⏱️  Rate limited")
            else:
                print(f"Request {i+1}: ❌ Other error ({response.status_code})")
                
        except Exception as e:
            print(f"Request {i+1}: ❌ Error: {e}")
        
        time.sleep(0.1)  # Small delay between requests
    
    print(f"Rate Limiting Test Results:")
    print(f"  Successful requests: {success_count}")
    print(f"  Rate limited requests: {rate_limited_count}")
    
    if rate_limited_count > 0:
        print("✅ Rate limiting is working correctly!")
    else:
        print("⚠️  Rate limiting might not be active (Redis might not be running)")

def test_security_headers():
    """Test security measures by sending invalid requests."""
    print("\n🛡️  Testing Security Measures...")
    
    # Test without extension header
    print("Testing request without X-Extension-Client header...")
    response = requests.post(f"{BASE_URL}/auth", headers={"Content-Type": "application/json"})
    if response.status_code == 401:
        print("✅ Correctly rejected request without extension header")
    else:
        print(f"❌ Expected 401, got {response.status_code}")
    
    # Test with wrong extension header
    print("Testing request with wrong X-Extension-Client header...")
    wrong_headers = {"X-Extension-Client": "malicious-extension", "Content-Type": "application/json"}
    response = requests.post(f"{BASE_URL}/auth", headers=wrong_headers)
    if response.status_code == 401:
        print("✅ Correctly rejected request with wrong extension header")
    else:
        print(f"❌ Expected 401, got {response.status_code}")

def main():
    """Run all API tests."""
    print("🧪 Privacy Inspector API - Functionality Tests")
    print("=" * 60)
    print("Note: Make sure the server is running with 'python main.py'")
    print("=" * 60)
    
    # Test authentication
    token = test_auth_endpoint()
    if not token:
        print("❌ Cannot proceed without authentication token")
        return 1
    
    # Test analysis
    analyze_success = test_analyze_endpoint(token)
    if not analyze_success:
        print("❌ Analysis test failed")
    
    # Test rate limiting
    test_rate_limiting(token)
    
    # Test security
    test_security_headers()
    
    print("\n" + "=" * 60)
    print("🎯 Tests completed!")
    print("\nIf you see rate limiting or security rejections, that's good!")
    print("It means the protection mechanisms are working correctly.")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
