// Import tracker detection utilities
import { getDomainFromUrl } from "../utils/trackerDetection";

// Track network requests (fallback for content script level tracking)
const networkRequests: Array<{
  url: string;
  method: string;
  type: string;
  timestamp: string;
}> = [];

// Analytics globals detection for feature 7: has_analytics_global
interface AnalyticsFlags {
  has_google_analytics: boolean;
  has_gtag: boolean;
  has_facebook_pixel: boolean;
  has_data_layer: boolean;
  detected_analytics: string[];
}

// Fingerprinting detection for feature 9: fingerprinting_flag
interface FingerprintingFlags {
  canvas_fingerprinting: boolean;
  audio_fingerprinting: boolean;
  webgl_fingerprinting: boolean;
  font_fingerprinting: boolean;
  detected_methods: string[];
}

let analyticsFlags: AnalyticsFlags = {
  has_google_analytics: false,
  has_gtag: false,
  has_facebook_pixel: false,
  has_data_layer: false,
  detected_analytics: [],
};

let fingerprintingFlags: FingerprintingFlags = {
  canvas_fingerprinting: false,
  audio_fingerprinting: false,
  webgl_fingerprinting: false,
  font_fingerprinting: false,
  detected_methods: [],
};

// Override fetch to monitor network requests (fallback)
const originalFetch = window.fetch;
window.fetch = function (...args) {
  const url = args[0] instanceof Request ? args[0].url : (args[0] as string);
  const method =
    args[1]?.method || (args[0] instanceof Request ? args[0].method : "GET");

  const requestData = {
    url: url,
    method: method,
    type: "fetch",
    timestamp: new Date().toISOString(),
  };

  networkRequests.push(requestData);
  return originalFetch.apply(this, args);
};

// Override XMLHttpRequest to monitor AJAX requests (fallback)
const originalXHROpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function (
  method: string,
  url: string | URL,
  async: boolean = true,
  username?: string | null,
  password?: string | null
) {
  const requestData = {
    url: url.toString(),
    method: method,
    type: "xhr",
    timestamp: new Date().toISOString(),
  };

  networkRequests.push(requestData);
  return originalXHROpen.call(this, method, url, async, username, password);
};

// Message handler for popup communication
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) {
    console.warn("Rejected message from foreign extension:", sender.id);
    return;
  }

  switch (message.type) {
    case "PING":
      sendResponse({ status: "PONG" });
      break;

    case "GET_PAGE_INFO":
      // Return basic page info for popup display
      const cookieCount = document.cookie
        ? document.cookie.split(";").length
        : 0;
      const scriptCount = document.querySelectorAll("script").length;
      sendResponse({
        cookieCount,
        scriptCount,
        webRequestCount: networkRequests.length,
      });
      break;

    case "COLLECT_PRIVACY_DATA":
      // This will be implemented to collect comprehensive data
      collectComprehensivePrivacyData()
        .then((data) => {
          sendResponse(data);
        })
        .catch((error) => {
          console.error("Error collecting comprehensive privacy data:", error);
          sendResponse({ error: "Failed to collect privacy data" });
        });
      return true;

    case "GET_WEB_REQUEST_COUNT":
      sendResponse({ webRequestCount: networkRequests.length });
      break;

    default:
      sendResponse({ error: "Unknown message type" });
  }
  return true;
});

// Placeholder for comprehensive data collection - will implement next
async function collectComprehensivePrivacyData() {
  const currentDomain = window.location.hostname;

  // Collect cookies from document.cookie
  const rawCookies = [];
  if (document.cookie) {
    const cookies = document.cookie.split(";");
    for (const cookie of cookies) {
      const [name, ...valueParts] = cookie.trim().split("=");
      if (name && valueParts.length > 0) {
        rawCookies.push({
          domain: currentDomain,
          secure: window.location.protocol === "https:",
        });
      }
    }
  }

  // Collect scripts
  const scripts = [];
  const allScripts = document.querySelectorAll("script");
  for (const script of allScripts) {
    const scriptData = {
      domain: script.src ? getDomainFromUrl(script.src) : null,
    };
    scripts.push(scriptData);
  }

  // Enhanced analytics detection
  analyticsFlags.has_google_analytics =
    !!(window as any).ga ||
    !!(window as any).gtag ||
    document.querySelector('script[src*="google-analytics"]') !== null;
  analyticsFlags.has_gtag =
    !!(window as any).gtag ||
    document.querySelector('script[src*="gtag"]') !== null;
  analyticsFlags.has_facebook_pixel =
    !!(window as any).fbq ||
    document.querySelector('script[src*="facebook"]') !== null;
  analyticsFlags.has_data_layer = !!(window as any).dataLayer;

  // Update detected analytics array
  analyticsFlags.detected_analytics = [];
  if (analyticsFlags.has_google_analytics)
    analyticsFlags.detected_analytics.push("google_analytics");
  if (analyticsFlags.has_gtag) analyticsFlags.detected_analytics.push("gtag");
  if (analyticsFlags.has_facebook_pixel)
    analyticsFlags.detected_analytics.push("facebook_pixel");
  if (analyticsFlags.has_data_layer)
    analyticsFlags.detected_analytics.push("data_layer");

  // Enhanced fingerprinting detection
  fingerprintingFlags.canvas_fingerprinting =
    document.querySelectorAll("canvas").length > 0;
  fingerprintingFlags.audio_fingerprinting =
    !!(window as any).AudioContext || !!(window as any).webkitAudioContext;
  fingerprintingFlags.webgl_fingerprinting = !!document
    .querySelector("canvas")
    ?.getContext("webgl");
  fingerprintingFlags.font_fingerprinting =
    document.querySelectorAll('style, link[rel="stylesheet"]').length > 5; // Heuristic

  // Update detected methods array
  fingerprintingFlags.detected_methods = [];
  if (fingerprintingFlags.canvas_fingerprinting)
    fingerprintingFlags.detected_methods.push("canvas");
  if (fingerprintingFlags.audio_fingerprinting)
    fingerprintingFlags.detected_methods.push("audio");
  if (fingerprintingFlags.webgl_fingerprinting)
    fingerprintingFlags.detected_methods.push("webgl");
  if (fingerprintingFlags.font_fingerprinting)
    fingerprintingFlags.detected_methods.push("font");

  return {
    page_url: window.location.href,
    page_title: document.title,
    page_domain: currentDomain,
    timestamp: new Date().toISOString(),
    raw_cookies: rawCookies,
    scripts: scripts,
    network_requests: networkRequests.map((req) => ({
      ...req,
      domain: getDomainFromUrl(req.url),
    })),
    analytics_flags: analyticsFlags,
    fingerprinting_flags: fingerprintingFlags,
  };
}
