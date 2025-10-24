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
    case "ANALYZE_PAGE":
      // Future: Connect to your FastAPI backend
      sendResponse({ status: "Analysis queued" });
      break;
    default:
      sendResponse({ error: "Unknown message type" });
  }
  return true;
});
