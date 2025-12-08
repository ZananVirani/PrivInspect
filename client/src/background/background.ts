// Import hot reload for development
import "../utils/hotReload";

// Function to determine if a network request is privacy-relevant
function isPrivacyRelevantRequest(
  details: chrome.webRequest.WebRequestBodyDetails
): boolean {
  const url = details.url.toLowerCase();

  // Skip common static resources that don't provide privacy insights
  const staticExtensions = [
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".bmp",
    ".css",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".webm",
    ".mp3",
    ".wav",
    ".ogg",
  ];

  // Skip if it's a static resource
  if (staticExtensions.some((ext) => url.includes(ext))) {
    return false;
  }

  // Include these privacy-relevant request types:
  const relevantTypes = [
    "xmlhttprequest", // API calls, AJAX
    "script", // JavaScript files (may contain tracking)
    "sub_frame", // Iframes (often used for tracking)
    "ping", // Beacon/ping requests (tracking)
    "other", // Catch-all for API calls
  ];

  // Include if it's a relevant type
  if (relevantTypes.includes(details.type)) {
    return true;
  }

  // Include requests to known tracking/analytics domains
  const trackingKeywords = [
    "analytics",
    "tracking",
    "tracker",
    "ads",
    "doubleclick",
    "googletagmanager",
    "facebook",
    "twitter",
    "linkedin",
    "hotjar",
    "mixpanel",
    "segment",
    "amplitude",
    "intercom",
  ];

  if (trackingKeywords.some((keyword) => url.includes(keyword))) {
    return true;
  }

  // Include third-party API calls (cross-origin requests)
  if (details.type === "main_frame") {
    return false; // Skip main page loads
  }

  return false;
}

// Track network requests per tab for privacy analysis
const tabNetworkRequests = new Map<
  number,
  Array<{
    url: string;
    method: string;
    type: string;
    timestamp: string;
    tabId: number;
  }>
>();

// Listen for network requests using webRequest API
// This captures privacy-relevant requests, filtering out static resources
chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    // Skip chrome:// and extension:// URLs
    if (
      details.url.startsWith("chrome://") ||
      details.url.startsWith("chrome-extension://")
    ) {
      return;
    }

    // Only store privacy-relevant requests to reduce payload size
    if (!isPrivacyRelevantRequest(details)) {
      return;
    }

    const requestData = {
      url: details.url,
      method: details.method,
      type: details.type,
      timestamp: new Date().toISOString(),
      tabId: details.tabId,
    };

    // Store request for the specific tab
    if (!tabNetworkRequests.has(details.tabId)) {
      tabNetworkRequests.set(details.tabId, []);
    }
    tabNetworkRequests.get(details.tabId)!.push(requestData);
  },
  { urls: ["<all_urls>"] },
  ["requestBody"]
);

// Clear requests when tab is closed
chrome.tabs.onRemoved.addListener((tabId) => {
  tabNetworkRequests.delete(tabId);
});

// Essential message handling
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) {
    console.warn("Rejected message from foreign extension:", sender.id);
    return;
  }

  switch (message.type) {
    case "PING":
      sendResponse({ status: "Background service worker is active" });
      break;

    case "GET_COOKIES":
    case "GET_DETAILED_COOKIES":
      // Handle cookie requests from content script - supports all 10 features
      const url = message.url || message.domain;
      if (url) {
        chrome.cookies.getAll({ url: url }, (cookies) => {
          // Include full cookie data for persistent cookie detection
          const cookieData = cookies.map((cookie) => ({
            domain: cookie.domain,
            secure: cookie.secure,
            expirationDate: cookie.expirationDate, // For num_persistent_cookies feature
            session: cookie.session,
          }));
          sendResponse({ cookies: cookieData });
        });
        return true;
      } else {
        sendResponse({ cookies: [] });
      }
      break;

    case "GET_NETWORK_REQUESTS":
      // Return network requests for specific tab - supports features 1, 4, 5, 10
      const tabId = sender.tab?.id || message.tabId;
      const requests = tabNetworkRequests.get(tabId) || [];
      sendResponse({ requests: requests });
      break;

    case "CLEAR_TAB_DATA":
      // Clear stored data for tab
      const clearTabId = sender.tab?.id || message.tabId;
      tabNetworkRequests.delete(clearTabId);
      sendResponse({ status: "cleared" });
      break;

    case "ANALYZE_PAGE":
      // Future: Connect to your FastAPI backend
      sendResponse({ status: "Analysis queued" });
      break;

    default:
      sendResponse({ error: "Unknown message type" });
  }
  return true;
});
