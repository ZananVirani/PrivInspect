// API Service for backend communication
import { API_BASE_URL, EXTENSION_CLIENT_HEADER } from "../config";

// Updated interface to match simplified backend AnalyzeRequest model
export interface ComprehensivePrivacyData {
  // Basic page information
  page_url: string;
  page_title: string;
  page_domain: string;
  timestamp: string;

  // Cookie data with essential properties for privacy analysis
  raw_cookies: Array<{
    domain: string;
    secure?: boolean;
    expirationDate?: number;
    session?: boolean;
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

export interface AuthResponse {
  access_token: string;
}

class ApiService {
  private static async makeRequest(
    endpoint: string,
    options: RequestInit = {},
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
      throw error;
    }
  }

  static async authenticate(): Promise<AuthResponse> {
    return this.makeRequest("/api/v1/auth", {
      method: "POST",
      headers: {
        "X-Extension-Client": EXTENSION_CLIENT_HEADER,
        "User-Agent": "PrivInspect Extension v1.0",
      },
    });
  }

  // Updated method to handle comprehensive privacy data
  static async analyzeComprehensivePrivacy(
    data: ComprehensivePrivacyData,
    token: string,
  ): Promise<any> {
    if (!token) {
      throw new Error("No authentication token available");
    }

    return this.makeRequest("/api/v1/analyze", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Extension-Client": EXTENSION_CLIENT_HEADER,
        "User-Agent": "PrivInspect Extension v1.0",
      },
      body: JSON.stringify(data),
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
      return false;
    }
  }
}

export { ApiService };
