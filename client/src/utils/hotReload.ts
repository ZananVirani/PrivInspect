// Hot reload helper for Chrome extension development
// This script automatically reloads the extension when files change

/// <reference types="vite/client" />

// Listen for file changes and reload extension
if (import.meta.hot) {
  import.meta.hot.accept(() => {
    console.log("🔄 Hot reload triggered - reloading extension...");

    // Reload the extension
    if (chrome && chrome.runtime && chrome.runtime.reload) {
      chrome.runtime.reload();
    }
  });
}

export {};
