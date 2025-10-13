/**
 * Popup Script for Privacy Inspector Demo
 * Handles the extension popup UI and interactions
 */

console.log("Popup script running - Privacy Inspector Demo");

// Initialize popup when DOM is loaded
document.addEventListener("DOMContentLoaded", initializePopup);

async function initializePopup() {
  console.log("Initializing popup interface");

  // Get and display extension ID
  const extensionId = chrome.runtime.id;
  document.getElementById("extension-id").textContent = extensionId;

  // Test background script communication
  testBackgroundCommunication();

  // Load current page information
  await loadCurrentPageInfo();

  // Set up button event listeners
  setupEventListeners();

  // Check permissions status
  checkPermissions();

  console.log("Popup initialization complete");
}

function testBackgroundCommunication() {
  chrome.runtime.sendMessage({ type: "PING" }, (response) => {
    const statusElement = document.getElementById("background-status");

    if (chrome.runtime.lastError) {
      console.error(
        "Background communication error:",
        chrome.runtime.lastError
      );
      statusElement.textContent = "Error";
      statusElement.style.color = "red";
    } else if (response && response.status) {
      console.log("Background communication successful");
      statusElement.textContent = "Active";
      statusElement.style.color = "green";
    } else {
      console.log("Background communication failed");
      statusElement.textContent = "Inactive";
      statusElement.style.color = "orange";
    }
  });
}

async function loadCurrentPageInfo() {
  try {
    // Get current active tab
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });

    if (tab) {
      // Update basic tab info
      document.getElementById("current-url").textContent = tab.url || "Unknown";
      document.getElementById("page-title").textContent =
        tab.title || "Unknown";

      // Try to get more detailed info from content script
      chrome.tabs.sendMessage(tab.id, { type: "GET_PAGE_INFO" }, (response) => {
        if (chrome.runtime.lastError) {
          console.log("Content script not available on this page");
          return;
        }

        if (response) {
          document.getElementById("cookie-count").textContent =
            response.cookieCount || 0;
          document.getElementById("script-count").textContent =
            response.scriptCount || 0;
        }
      });
    }
  } catch (error) {
    console.error("Error loading page info:", error);
  }
}

function setupEventListeners() {
  // Test background button
  document.getElementById("test-background").addEventListener("click", () => {
    console.log("Testing background communication...");
    testBackgroundCommunication();
  });

  // Refresh page info button
  document.getElementById("refresh-info").addEventListener("click", () => {
    console.log("Refreshing page info...");
    loadCurrentPageInfo();
  });

  // Clear storage button
  document.getElementById("clear-storage").addEventListener("click", () => {
    console.log("Clearing test data...");
    chrome.storage.local.clear(() => {
      console.log("Storage cleared");
      alert("Test data cleared!");
    });
  });
}

async function checkPermissions() {
  const requiredPermissions = [
    "activeTab",
    "scripting",
    "cookies",
    "storage",
    "webRequest",
    "webNavigation",
  ];

  const hostPermissions = ["<all_urls>"];

  try {
    const hasPermissions = await chrome.permissions.contains({
      permissions: requiredPermissions,
      origins: hostPermissions,
    });

    const statusElement = document.getElementById("permissions-status");

    if (hasPermissions) {
      statusElement.textContent = "All granted";
      statusElement.style.color = "green";
    } else {
      statusElement.textContent = "Some missing";
      statusElement.style.color = "orange";
    }
  } catch (error) {
    console.error("Error checking permissions:", error);
    document.getElementById("permissions-status").textContent = "Error";
  }
}

// Log popup closure (for debugging)
window.addEventListener("beforeunload", () => {
  console.log("Popup closing");
});
