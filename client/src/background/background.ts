// Import hot reload for development
import "../utils/hotReload";

// Essential message handling only
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) {
    console.warn("Rejected message from foreign extension:", sender.id);
    return; // Ignore the message
  }

  switch (message.type) {
    case "PING":
      sendResponse({ status: "Background service worker is active" });
      break;
    case "GET_COOKIES":
      // Handle cookie requests from content script
      if (message.domain) {
        chrome.cookies.getAll({ domain: message.domain }, (cookies) => {
          const cookieData = cookies.map((cookie) => ({
            name: cookie.name,
            value: cookie.value,
            domain: cookie.domain,
          }));
          sendResponse({ cookies: cookieData });
        });
        return true; // Keep message channel open for async response
      } else {
        sendResponse({ cookies: [] });
      }
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
