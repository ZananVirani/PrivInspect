// Import hot reload for development
import "../utils/hotReload";

console.log(
  "Background service worker loaded - Privacy Inspector Demo v1.0 (React + Vite)"
);

// Listen for extension installation
chrome.runtime.onInstalled.addListener((details) => {
  console.log("Privacy Inspector Demo installed:", details.reason);

  if (details.reason === "install") {
    console.log("Extension installed for the first time");
  } else if (details.reason === "update") {
    console.log(
      "Extension updated to version:",
      chrome.runtime.getManifest().version
    );
  }
});

// Listen for extension startup
chrome.runtime.onStartup.addListener(() => {
  console.log("Privacy Inspector Demo started");
});

// Listen for messages from content scripts or popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log("Background received message:", message);
  console.log("Sender ID:", sender.id);

  // Handle different message types
  switch (message.type) {
    case "PING":
      sendResponse({ status: "Background service worker is active" });
      break;

    case "GET_EXTENSION_ID":
      sendResponse({ extensionId: chrome.runtime.id });
      break;

    case "ANALYZE_PAGE":
      console.log("Privacy analysis requested for:", message.url);
      sendResponse({ status: "Analysis queued" });
      break;

    default:
      console.log("Unknown message type:", message.type);
      sendResponse({ error: "Unknown message type" });
  }

  return true; // Keep message channel open for async responses
});

console.log(
  "Background service worker ready - Extension ID:",
  chrome.runtime.id
);
