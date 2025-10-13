/**
 * Content Script for Privacy Inspector Demo
 * This runs on every webpage and will eventually collect privacy data
 */

console.log("Content script loaded on:", window.location.href);

// Simple test to verify content script is working
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeContentScript);
} else {
  initializeContentScript();
}

function initializeContentScript() {
  console.log("Privacy Inspector Demo - Content script initialized");
  console.log("Page title:", document.title);
  console.log("Current URL:", window.location.href);

  // Test message to background script
  chrome.runtime.sendMessage({ type: "PING" }, (response) => {
    if (response && response.status) {
      console.log("Background communication test successful:", response.status);
    } else {
      console.log("Background communication test failed");
    }
  });

  // Future privacy analysis will happen here
  // For now, just log basic page information
  logBasicPageInfo();
}

function logBasicPageInfo() {
  const pageInfo = {
    url: window.location.href,
    title: document.title,
    cookieCount: document.cookie.split(";").filter((c) => c.trim()).length,
    scriptCount: document.querySelectorAll("script").length,
    timestamp: new Date().toISOString(),
  };

  console.log("Basic page info collected:", pageInfo);

  // This is where we'll eventually send data to the privacy analysis API
  // For now, just store it locally for testing
  chrome.storage.local.get(["pageAnalysis"], (result) => {
    const existingData = result.pageAnalysis || [];
    existingData.push(pageInfo);

    // Keep only last 10 entries for testing
    const recentData = existingData.slice(-10);

    chrome.storage.local.set({ pageAnalysis: recentData }, () => {
      console.log("Page info saved to storage");
    });
  });
}

// Listen for messages from popup or background
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log("Content script received message:", message);

  switch (message.type) {
    case "GET_PAGE_INFO":
      sendResponse({
        url: window.location.href,
        title: document.title,
        cookieCount: document.cookie.split(";").filter((c) => c.trim()).length,
        scriptCount: document.querySelectorAll("script").length,
      });
      break;

    default:
      sendResponse({ error: "Unknown message type" });
  }

  return true;
});
