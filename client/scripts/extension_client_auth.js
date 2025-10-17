/**
 * Use like:
 * // Simple usage
const auth = new ExtensionAuthenticator(chrome.runtime.id);
const token = await auth.getAuthToken();
const result = await auth.makeAuthenticatedRequest('/analyze', data, token);

// Or with enhanced retry logic
const enhancedAuth = new EnhancedExtensionAuthenticator(chrome.runtime.id);
const result = await enhancedAuth.makeRequestWithRetry('/analyze', data, token);
 */

// Extension Authentication Helper for Chrome Extension
class ExtensionAuthenticator {
  constructor(extensionId, serverUrl = "http://localhost:8000/api/v1") {
    this.extensionId = extensionId;
    this.serverUrl = serverUrl;
    // Default JWT secret for development - CHANGE FOR PRODUCTION!
    this.defaultSecret = "dev-secret-change-in-production";
  }

  // Generate a unique nonce for each request
  generateNonce() {
    return "xxxx-xxxx-4xxx-yxxx".replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  // Generate timestamp
  getTimestamp() {
    return Math.floor(Date.now() / 1000);
  }

  // Generate HMAC-SHA256 signature (requires crypto-js library or native crypto)
  async generateSignature(extensionId, timestamp, secret) {
    const message = `${extensionId}:${timestamp}:${secret}`;
    const encoder = new TextEncoder();
    const data = encoder.encode(message);
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    const signature = await crypto.subtle.sign("HMAC", key, data);
    return Array.from(new Uint8Array(signature))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  // Create authenticated request headers
  async createAuthHeaders(jwtToken, serverSecret = this.defaultSecret) {
    const timestamp = this.getTimestamp();
    const nonce = this.generateNonce();
    const signature = await this.generateSignature(
      this.extensionId,
      timestamp,
      serverSecret
    );

    return {
      Authorization: `Bearer ${jwtToken}`,
      "X-Extension-ID": this.extensionId,
      "X-Request-Timestamp": timestamp.toString(),
      "X-Request-Signature": signature,
      "X-Request-Nonce": nonce,
      "X-Extension-Client": "privacy-inspector", // CORRECT: Must match server config
      "Content-Type": "application/json",
      // Required for browser validation
      Origin: `chrome-extension://${this.extensionId}`,
      "User-Agent": navigator.userAgent || "Chrome Extension",
    };
  }

  // Make authenticated request to your API
  async makeAuthenticatedRequest(
    endpoint,
    data,
    jwtToken,
    serverSecret = this.defaultSecret
  ) {
    const headers = await this.createAuthHeaders(jwtToken, serverSecret);

    const response = await fetch(`${this.serverUrl}${endpoint}`, {
      method: "POST",
      headers: headers,
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `API request failed: ${response.status} ${response.statusText} - ${errorText}`
      );
    }

    return response.json();
  }

  // Get JWT token from auth endpoint
  async getAuthToken() {
    const headers = {
      "X-Extension-Client": "privacy-inspector",
      "Content-Type": "application/json",
      Origin: `chrome-extension://${this.extensionId}`,
      "User-Agent": navigator.userAgent || "Chrome Extension",
    };

    const response = await fetch(`${this.serverUrl}/auth`, {
      method: "POST",
      headers: headers,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `Authentication failed: ${response.status} - ${errorText}`
      );
    }

    const tokenData = await response.json();
    return tokenData.access_token;
  }
}

// UPDATED USAGE EXAMPLE - Correct configuration
/*
const authenticator = new ExtensionAuthenticator(
    chrome.runtime.id, // Unique extension ID
    'http://localhost:8000/api/v1' // Correct server URL with /api/v1 prefix
);

// Complete workflow - authentication + analysis:
async function analyzePrivacyData(privacyData) {
    try {
        // Step 1: Get JWT token (no server secret needed for auth)
        const jwtToken = await authenticator.getAuthToken();
        
        // Step 2: Make authenticated analysis request
        const result = await authenticator.makeAuthenticatedRequest(
            '/analyze', // Endpoint (will become /api/v1/analyze)
            { 
                url: privacyData.url,
                cookies: privacyData.cookies || [],
                scripts: privacyData.scripts || []
            },
            jwtToken
            // serverSecret is optional - uses default if not provided
        );
        
        return result;
    } catch (error) {
        console.error('Privacy analysis failed:', error);
        throw error;
    }
}

// Simplified usage for quick testing:
async function quickTest() {
    const auth = new ExtensionAuthenticator('test-extension-id-12345');
    
    try {
        const token = await auth.getAuthToken();
        console.log('✅ Authentication successful');
        
        const result = await auth.makeAuthenticatedRequest('/analyze', {
            url: 'https://example.com',
            cookies: [],
            scripts: []
        }, token);
        
        console.log('✅ Analysis successful:', result);
    } catch (error) {
        console.error('❌ Error:', error.message);
    }
}
*/

// PRODUCTION DEPLOYMENT CHECKLIST:

// 1. Update server configuration in your extension's manifest.json
const manifestUpdates = {
  // Allow your production server domain
  host_permissions: ["https://your-production-api.com/*"],

  // Content Security Policy for production
  content_security_policy: {
    extension_pages:
      "script-src 'self'; object-src 'self'; connect-src https://your-production-api.com",
  },

  // Required permissions
  permissions: ["storage", "activeTab"],
};

// 2. Environment configuration
const PRODUCTION_CONFIG = {
  serverUrl: "https://your-production-api.com/api/v1",
  extensionClientHeader: "privacy-inspector", // Keep this same
  jwtSecret: "your-production-secret-32-chars-min", // MUST change for production
};

// 3. Secure storage implementation for production
async function securelyStoreToken(token) {
  // Store JWT token securely in Chrome extension storage
  await chrome.storage.local.set({
    jwt_token: token,
    token_timestamp: Date.now(),
  });
}

async function getStoredToken() {
  const result = await chrome.storage.local.get([
    "jwt_token",
    "token_timestamp",
  ]);
  const tokenAge = Date.now() - (result.token_timestamp || 0);

  // Token expires in 15 minutes (900000 ms), refresh if older than 14 minutes
  if (!result.jwt_token || tokenAge > 840000) {
    return null; // Need to get new token
  }

  return result.jwt_token;
}

// 4. Enhanced error handling and retry logic
class EnhancedExtensionAuthenticator extends ExtensionAuthenticator {
  constructor(extensionId, serverUrl, options = {}) {
    super(extensionId, serverUrl);
    this.maxRetries = options.maxRetries || 3;
    this.retryDelay = options.retryDelay || 1000; // 1 second
  }

  async makeRequestWithRetry(endpoint, data, jwtToken, retries = 0) {
    try {
      return await this.makeAuthenticatedRequest(endpoint, data, jwtToken);
    } catch (error) {
      if (retries < this.maxRetries && this.shouldRetry(error)) {
        console.warn(
          `Request failed, retrying in ${this.retryDelay}ms... (${
            retries + 1
          }/${this.maxRetries})`
        );
        await new Promise((resolve) => setTimeout(resolve, this.retryDelay));
        return this.makeRequestWithRetry(endpoint, data, jwtToken, retries + 1);
      }
      throw error;
    }
  }

  shouldRetry(error) {
    // Retry on network errors, server errors, but not on authentication errors
    const retryableErrors = [500, 502, 503, 504, 429]; // Server errors and rate limiting
    const nonRetryableErrors = [401, 403]; // Authentication/authorization errors

    if (error.message.includes("Failed to fetch")) return true; // Network error

    const statusMatch = error.message.match(/(\d{3})/);
    if (statusMatch) {
      const status = parseInt(statusMatch[1]);
      return (
        retryableErrors.includes(status) && !nonRetryableErrors.includes(status)
      );
    }

    return false;
  }
}

// Export for use in Chrome extension
if (typeof module !== "undefined" && module.exports) {
  module.exports = { ExtensionAuthenticator, EnhancedExtensionAuthenticator };
}
