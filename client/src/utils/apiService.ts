// API Service for backend communication
const API_BASE_URL = "http://localhost:8000";

// Updated interface to match simplified backend AnalyzeRequest model
export interface ComprehensivePrivacyData {
  // Basic page information
  page_url: string;
  page_title: string;
  page_domain: string;
  timestamp: string;

  // Simplified raw data - backend handles all third-party detection
  raw_cookies: Array<{
    domain: string;
    secure?: boolean;
  }>;

  scripts: Array<{
    domain?: string;
  }>;

  network_requests: Array<{
    url: string;
    method: string;
    type: string;
    timestamp: string;
    domain?: string;
  }>;

  // Detection flags
  analytics_flags?: {
    has_google_analytics: boolean;
    has_gtag: boolean;
    has_facebook_pixel: boolean;
    has_data_layer: boolean;
    detected_analytics: string[];
  };

  fingerprinting_flags?: {
    canvas_fingerprinting: boolean;
    audio_fingerprinting: boolean;
    webgl_fingerprinting: boolean;
    font_fingerprinting: boolean;
    detected_methods: string[];
  };
}

// Legacy interfaces for backward compatibility
export interface PageAnalysisData {
  page_url: string;
  page_title: string;
  cookies: string[];
  raw_cookies?: Array<{
    name: string;
    value: string;
    domain: string;
  }>;
  scripts: Array<{
    src: string | null;
    inline: boolean;
    type: string;
    content_preview?: string;
  }>;
  forms: Array<{
    action: string;
    method: string;
    inputs: Array<{
      type: string;
      name: string;
      required: boolean;
    }>;
  }>;
  network_requests?: Array<{
    url: string;
    method: string;
    type: string;
    timestamp: string;
  }>;
  timestamp: string;
}

export interface BackendAnalysisRequest {
  url: string;
  cookies: Array<{
    name: string;
    value: string;
    domain: string;
  }>;
  scripts: Array<{
    content_preview?: string | null;
    inline: boolean;
    src?: string | null;
    type?: string;
  }>;
  additional_data?: any;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
}

export interface AnalysisResponse {
  analysis_id?: string;
  privacy_score?: number;
  threats?: string[];
  recommendations?: string[];
  error?: string;
}

class ApiService {
  private static async makeRequest(
    endpoint: string,
    options: RequestInit = {}
  ) {
    const url = `${API_BASE_URL}${endpoint}`;

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
        },
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API request failed for ${endpoint}:`, error);
      throw error;
    }
  }

  static async authenticate(): Promise<AuthResponse> {
    return this.makeRequest("/api/v1/auth", {
      method: "POST",
      headers: {
        "X-Extension-Client": "privacy-inspector",
        "User-Agent": "PrivInspect Extension v1.0",
      },
      body: JSON.stringify({
        username: "demo_user",
        password: "demo_password",
      }),
    });
  }

  // Updated method to handle comprehensive privacy data
  static async analyzeComprehensivePrivacy(
    data: ComprehensivePrivacyData,
    token: string
  ): Promise<any> {
    if (!token) {
      throw new Error("No authentication token available");
    }

    console.log("🔍 Sending comprehensive privacy data to backend:", data);

    return this.makeRequest("/api/v1/analyze", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Extension-Client": "privacy-inspector",
        "User-Agent": "PrivInspect Extension v1.0",
      },
      body: JSON.stringify(data),
    });
  }

  // Legacy method for backward compatibility
  static async analyzePrivacy(
    data: PageAnalysisData,
    token: string
  ): Promise<any> {
    if (!token) {
      throw new Error("No authentication token available");
    }

    // Transform frontend data to backend format
    const backendRequest: BackendAnalysisRequest = {
      url: data.page_url,
      cookies:
        data.raw_cookies ||
        data.cookies.map((cookieString) => {
          // Parse cookie string "name=value" format if raw_cookies not available
          const [name, ...valueParts] = cookieString.split("=");
          const value = valueParts.join("=");
          return {
            name: name?.trim() || "",
            value: value?.trim() || "",
            domain: new URL(data.page_url).hostname,
          };
        }),
      scripts: data.scripts
        .filter((script) => script.src || script.inline) // Include both external and inline scripts
        .map((script) => ({
          src: script.src || "", // Backend expects src to be required, use empty string for inline
          content_preview: script.inline
            ? script.content_preview || null
            : null,
          inline: script.inline,
          type: script.type,
        })),
      additional_data: {
        page_title: data.page_title,
        forms: data.forms,
        network_requests: data.network_requests || [],
      },
    };

    return this.makeRequest("/api/v1/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        "X-Extension-Client": "privacy-inspector",
        "User-Agent": "PrivInspect Extension v1.0",
      },
      body: JSON.stringify(backendRequest),
    });
  }

  static async getStoredToken(): Promise<string | null> {
    return new Promise((resolve) => {
      chrome.storage.local.get(["authToken"], (result) => {
        resolve(result.authToken || null);
      });
    });
  }

  static async storeToken(token: string): Promise<void> {
    return new Promise((resolve) => {
      chrome.storage.local.set({ authToken: token }, () => {
        resolve();
      });
    });
  }

  static async clearToken(): Promise<void> {
    return new Promise((resolve) => {
      chrome.storage.local.remove(["authToken"], () => {
        resolve();
      });
    });
  }

  static isTokenValid(token: string | null): boolean {
    if (!token) return false;

    try {
      const parts = token.split(".");
      if (parts.length !== 3) return false;

      const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
      const payload = JSON.parse(atob(base64));
      const currentTime = Math.floor(Date.now() / 1000);

      return currentTime < payload.exp - 30;
    } catch (error) {
      console.error("Token validation error:", error);
      return false;
    }
  }
}

export { ApiService };
