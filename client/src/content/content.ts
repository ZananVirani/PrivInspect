// Track network requests
const networkRequests: Array<{
  url: string;
  method: string;
  type: string;
  timestamp: string;
}> = [];

// Override fetch to monitor network requests
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
  console.log(
    "Network request tracked (fetch):",
    requestData.url,
    "Total requests:",
    networkRequests.length
  );

  return originalFetch.apply(this, args);
};

// Override XMLHttpRequest to monitor AJAX requests
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
  console.log(
    "Network request tracked (XHR):",
    requestData.url,
    "Total requests:",
    networkRequests.length
  );

  return originalXHROpen.call(this, method, url, async, username, password);
};

// Initialize when page loads
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeContentScript);
} else {
  initializeContentScript();
}

function initializeContentScript() {
  logBasicPageInfo();
}

async function getCookiesUsingChromeAPI(): Promise<
  Array<{ name: string; value: string; domain: string }>
> {
  const currentDomain = new URL(window.location.href).hostname;
  console.log("Attempting to get cookies for domain:", currentDomain);

  try {
    // Content scripts cannot access chrome.cookies directly
    // We need to send a message to the background script or popup
    return new Promise((resolve) => {
      if (chrome.runtime && chrome.runtime.sendMessage) {
        console.log("Sending message to background script for cookies");
        chrome.runtime.sendMessage(
          { type: "GET_COOKIES", domain: currentDomain },
          (response) => {
            if (chrome.runtime.lastError) {
              console.warn(
                "Chrome API not available in content script, falling back to document.cookie:",
                chrome.runtime.lastError
              );
              // Fallback to document.cookie parsing
              resolve(parseCookiesFromDocument());
            } else if (response && response.cookies) {
              console.log(
                "Received cookies from background script:",
                response.cookies
              );
              resolve(response.cookies);
            } else {
              console.log("No response from background script, using fallback");
              resolve(parseCookiesFromDocument());
            }
          }
        );
      } else {
        console.log(
          "Chrome runtime not available, using document.cookie fallback"
        );
        resolve(parseCookiesFromDocument());
      }
    });
  } catch (error) {
    console.warn(
      "Error accessing Chrome API, falling back to document.cookie:",
      error
    );
    return parseCookiesFromDocument();
  }
}

function parseCookiesFromDocument(): Array<{
  name: string;
  value: string;
  domain: string;
}> {
  const currentDomain = new URL(window.location.href).hostname;
  const cookieString = document.cookie;

  console.log("Parsing cookies from document.cookie:", cookieString);

  if (!cookieString) {
    console.log("No cookies found in document.cookie");
    return [];
  }

  const parsedCookies = cookieString
    .split(";")
    .map((cookie) => cookie.trim())
    .filter(Boolean)
    .map((cookie) => {
      const [name, ...valueParts] = cookie.split("=");
      return {
        name: name?.trim() || "",
        value: valueParts.join("=")?.trim() || "",
        domain: currentDomain,
      };
    });

  console.log("Parsed cookies from document:", parsedCookies);
  return parsedCookies;
}

async function logBasicPageInfo() {
  try {
    const cookies = await getCookiesUsingChromeAPI();
    console.log("Collected cookies:", cookies.length, cookies);

    const pageInfo = {
      url: window.location.href,
      title: document.title,
      cookieCount: cookies.length,
      scriptCount: document.querySelectorAll("script").length,
      timestamp: new Date().toISOString(),
    };

    chrome.storage.local.get(["pageAnalysis"], (result) => {
      const existingData = result.pageAnalysis || [];
      existingData.push(pageInfo);
      const recentData = existingData.slice(-10);
      chrome.storage.local.set({ pageAnalysis: recentData });
    });
  } catch (error) {
    console.error("Error collecting page info:", error);
  }
}

// Handle popup requests
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) {
    console.warn("Rejected message from foreign extension:", sender.id);
    return; // Ignore the message
  }

  switch (message.type) {
    case "GET_PAGE_INFO":
      getCookiesUsingChromeAPI()
        .then((cookies) => {
          sendResponse({
            url: window.location.href,
            title: document.title,
            cookieCount: cookies.length,
            scriptCount: document.querySelectorAll("script").length,
            webRequestCount: networkRequests.length,
          });
        })
        .catch((error) => {
          console.error("Error getting page info:", error);
          sendResponse({
            url: window.location.href,
            title: document.title,
            cookieCount: 0,
            scriptCount: document.querySelectorAll("script").length,
            webRequestCount: networkRequests.length,
          });
        });
      return true; // Keep message channel open for async response

    case "COLLECT_PRIVACY_DATA":
      collectPrivacyData()
        .then((data) => {
          sendResponse(data);
        })
        .catch((error) => {
          console.error("Error collecting privacy data:", error);
          sendResponse({ error: "Failed to collect privacy data" });
        });
      return true; // Keep message channel open for async response

    case "GET_WEB_REQUEST_COUNT":
      sendResponse({ webRequestCount: networkRequests.length });
      break;

    default:
      sendResponse({ error: "Unknown message type" });
  }
  return true;
});

async function collectPrivacyData() {
  try {
    const cookies = await getCookiesUsingChromeAPI();

    return {
      page_url: window.location.href,
      page_title: document.title,
      cookies: cookies.map((cookie) => `${cookie.name}=${cookie.value}`), // Convert to string format for compatibility
      raw_cookies: cookies, // Include structured cookie data
      scripts: Array.from(document.querySelectorAll("script")).map(
        (script) => ({
          src: script.src || null,
          inline: !script.src,
          type: script.type || "text/javascript",
          content_preview: script.src
            ? null
            : script.textContent?.substring(0, 500), // Increased for better ML analysis
        })
      ),
      forms: Array.from(document.querySelectorAll("form")).map((form) => ({
        action: form.action || "",
        method: form.method || "get",
        inputs: Array.from(form.querySelectorAll("input")).map((input) => ({
          type: input.type,
          name: input.name,
          required: input.required,
        })),
      })),
      network_requests: networkRequests.slice(-50), // Include last 50 network requests
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.error("Error collecting privacy data:", error);
    // Fallback to document.cookie if Chrome API fails
    return {
      page_url: window.location.href,
      page_title: document.title,
      cookies: document.cookie
        .split(";")
        .map((c) => c.trim())
        .filter(Boolean),
      raw_cookies: [],
      scripts: Array.from(document.querySelectorAll("script")).map(
        (script) => ({
          src: script.src || null,
          inline: !script.src,
          type: script.type || "text/javascript",
          content_preview: script.src
            ? null
            : script.textContent?.substring(0, 500),
        })
      ),
      forms: Array.from(document.querySelectorAll("form")).map((form) => ({
        action: form.action || "",
        method: form.method || "get",
        inputs: Array.from(form.querySelectorAll("input")).map((input) => ({
          type: input.type,
          name: input.name,
          required: input.required,
        })),
      })),
      network_requests: networkRequests.slice(-50),
      timestamp: new Date().toISOString(),
    };
  }
}
