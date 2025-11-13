// Import hot reload for development
import "../utils/hotReload";

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
// This captures ALL network requests, not just fetch/xhr
chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    // Skip chrome:// and extension:// URLs
    if (
      details.url.startsWith("chrome://") ||
      details.url.startsWith("chrome-extension://")
    ) {
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

    // Keep only last 500 requests per tab to prevent memory issues
    const requests = tabNetworkRequests.get(details.tabId)!;
    if (requests.length > 500) {
      requests.splice(0, requests.length - 500);
    }
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
      // Handle cookie requests from content script - supports all 10 features
      if (message.domain) {
        chrome.cookies.getAll({ domain: message.domain }, (cookies) => {
          // Include full cookie data for persistent cookie detection
          const cookieData = cookies.map((cookie) => ({
            name: cookie.name,
            value: cookie.value,
            domain: cookie.domain,
            path: cookie.path,
            secure: cookie.secure,
            httpOnly: cookie.httpOnly,
            sameSite: cookie.sameSite,
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
