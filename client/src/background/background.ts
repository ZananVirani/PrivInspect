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
      // Network requests are now tracked by content script directly
      // Return empty array for backward compatibility
      sendResponse({ requests: [] });
      break;

    default:
      sendResponse({ error: "Unknown message type" });
  }
  return true;
});
