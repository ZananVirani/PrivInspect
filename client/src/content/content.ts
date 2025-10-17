console.log("Content script loaded on:", window.location.href);

// Initialize content script
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeContentScript);
} else {
  initializeContentScript();
}

function initializeContentScript() {
  console.log(
    "Privacy Inspector Demo - Content script initialized (React + Vite version)"
  );
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

  // Collect and store basic page information
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

  // Store data locally for testing
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
  sender.documentId;
  switch (message.type) {
    case "GET_PAGE_INFO":
      sendResponse({
        url: window.location.href,
        title: document.title,
        cookieCount: document.cookie.split(";").filter((c) => c.trim()).length,
        scriptCount: document.querySelectorAll("script").length,
      });
      break;

    case "COLLECT_PRIVACY_DATA":
      const privacyData = collectPrivacyData();
      sendResponse(privacyData);
      break;

    default:
      sendResponse({ error: "Unknown message type" });
  }

  return true;
});

function collectPrivacyData() {
  return {
    cookies: document.cookie.split(";").filter((c) => c.trim()),
    scripts: Array.from(document.querySelectorAll("script")).map((script) => ({
      src: script.src,
      inline: !script.src,
      type: script.type || "text/javascript",
    })),
    trackers: [], // Future: Detect tracking scripts
    permissions: [], // Future: Check requested permissions
    timestamp: new Date().toISOString(),
  };
}
