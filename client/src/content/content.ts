// Initialize when page loads
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeContentScript);
} else {
  initializeContentScript();
}

function initializeContentScript() {
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

  chrome.storage.local.get(["pageAnalysis"], (result) => {
    const existingData = result.pageAnalysis || [];
    existingData.push(pageInfo);
    const recentData = existingData.slice(-10);
    chrome.storage.local.set({ pageAnalysis: recentData });
  });
}

// Handle popup requests
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) {
    console.warn("Rejected message from foreign extension:", sender.id);
    return; // Ignore the message
  }

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
      sendResponse(collectPrivacyData());
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
    trackers: [],
    permissions: [],
    timestamp: new Date().toISOString(),
  };
}
