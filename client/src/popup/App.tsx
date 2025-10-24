import { useState, useEffect } from "react";
import {
  Shield,
  RefreshCw,
  Activity,
  Globe,
  Cookie,
  Code,
  CheckCircle,
  XCircle,
  AlertCircle,
  Info,
} from "lucide-react";

interface PageInfo {
  url: string;
  title: string;
  cookieCount: number;
  scriptCount: number;
}

interface ExtensionStatus {
  backgroundActive: boolean;
  permissionsGranted: boolean;
}

function App() {
  const [pageInfo, setPageInfo] = useState<PageInfo>({
    url: "Loading...",
    title: "Loading...",
    cookieCount: 0,
    scriptCount: 0,
  });

  const [extensionStatus, setExtensionStatus] = useState<ExtensionStatus>({
    backgroundActive: false,
    permissionsGranted: false,
  });

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    initializePopup();
  }, []);

  const initializePopup = async () => {
    setLoading(true);

    try {
      // Test background communication
      const backgroundActive = await testBackgroundCommunication();

      // Check permissions
      const permissionsGranted = await checkPermissions();

      setExtensionStatus({
        backgroundActive,
        permissionsGranted,
      });

      // Load page info
      await loadCurrentPageInfo(backgroundActive, permissionsGranted);
    } catch (error) {
      console.error("Error initializing popup:", error);
    }

    setLoading(false);
  };

  const testBackgroundCommunication = (): Promise<boolean> => {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ type: "PING" }, (response) => {
          if (chrome.runtime.lastError) resolve(false);
          else resolve(response && response.status);
        });
      } catch (error) {
        console.error("Error testing background:", error);
        resolve(false);
      }
    });
  };

  const loadCurrentPageInfo = async (
    backgroundActive: boolean,
    permissionsGranted: boolean
  ) => {
    try {
      // Check if extension is ready for analysis
      if (!backgroundActive || !permissionsGranted) {
        // Set default values when extension isn't ready
        setPageInfo({
          url: "Analysis unavailable",
          title: "Analysis unavailable",
          cookieCount: 0,
          scriptCount: 0,
        });
        return;
      }

      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });

      if (tab) {
        const basicInfo = {
          url: tab.url || "Unknown",
          title: tab.title || "Unknown",
          cookieCount: 0,
          scriptCount: 0,
        };

        setPageInfo(basicInfo);

        // Try to get detailed info from content script
        if (tab.id) {
          chrome.tabs.sendMessage(
            tab.id,
            { type: "GET_PAGE_INFO" },
            (response) => {
              if (!chrome.runtime.lastError && response) {
                setPageInfo((prev) => ({
                  ...prev,
                  cookieCount: response.cookieCount || 0,
                  scriptCount: response.scriptCount || 0,
                }));
              }
            }
          );
        }
      }
    } catch (error) {
      console.error("Error loading page info:", error);
      // Set error state
      setPageInfo({
        url: "Error loading data",
        title: "Error loading data",
        cookieCount: 0,
        scriptCount: 0,
      });
    }
  };

  const checkPermissions = async (): Promise<boolean> => {
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
      return await chrome.permissions.contains({
        permissions: requiredPermissions,
        origins: hostPermissions,
      });
    } catch (error) {
      console.error("Error checking permissions:", error);
      return false;
    }
  };

  const requestPermissions = async () => {
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
      const granted = await chrome.permissions.request({
        permissions: requiredPermissions,
        origins: hostPermissions,
      });

      if (granted) {
        // Update extension status after granting permissions
        const permissionsGranted = await checkPermissions();
        setExtensionStatus((prev) => ({ ...prev, permissionsGranted }));

        // If permissions are now granted and background is active, reload page info
        if (permissionsGranted && extensionStatus.backgroundActive) {
          loadCurrentPageInfo(
            extensionStatus.backgroundActive,
            permissionsGranted
          );
        }
      }

      return granted;
    } catch (error) {
      console.error("Error requesting permissions:", error);
      return false;
    }
  };

  const truncateText = (text: string, maxLength: number = 30) => {
    return text.length > maxLength
      ? `${text.substring(0, maxLength)}...`
      : text;
  };

  return (
    <div className="w-96 min-h-[500px] max-w-96 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 text-white custom-scrollbar">
      {/* Main Content */}
      <div className="bg-white text-gray-800 p-5 flex-1 min-h-[400px]">
        {/* Hello World Section */}
        <div className="text-center mb-6">
          <div className="text-4xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent mb-2 animate-pulse flex items-center justify-center gap-3">
            <Shield className="w-10 h-10 text-blue-600" />
            PrivInspect
          </div>
          <div className="text-sm font-medium text-gray-600">
            ML-Powered Privacy Inspector
          </div>
        </div>

        {/* Extension Status */}
        <div className="mb-4 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200">
          <h3 className="text-sm font-semibold text-blue-700 mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Extension Status
          </h3>
          <div className="space-y-3">
            {/* Status Indicators */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-600">
                  Background Worker:
                </span>
                <div className="flex items-center gap-1">
                  {extensionStatus.backgroundActive ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500" />
                  )}
                  <span
                    className={`text-xs font-medium ${
                      extensionStatus.backgroundActive
                        ? "text-green-600"
                        : "text-red-600"
                    }`}
                  >
                    {extensionStatus.backgroundActive ? "Active" : "Inactive"}
                  </span>
                </div>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-600">Permissions:</span>
                <div className="flex items-center gap-1">
                  {extensionStatus.permissionsGranted ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-orange-500" />
                  )}
                  <span
                    className={`text-xs font-medium ${
                      extensionStatus.permissionsGranted
                        ? "text-green-600"
                        : "text-orange-600"
                    }`}
                  >
                    {extensionStatus.permissionsGranted
                      ? "All Granted"
                      : "Some Missing"}
                  </span>
                </div>
              </div>
            </div>

            {/* User-Friendly Messages */}
            <div className="space-y-2">
              {/* Show success message if everything is working */}
              {extensionStatus.backgroundActive &&
                extensionStatus.permissionsGranted && (
                  <div className="flex items-center gap-2 p-3 bg-green-50 rounded-lg border border-green-200">
                    <CheckCircle className="w-5 h-5 text-green-500" />
                    <span className="text-sm font-medium text-green-700">
                      Setup is ready for analysis
                    </span>
                  </div>
                )}

              {/* Show background worker error */}
              {!extensionStatus.backgroundActive && (
                <div className="flex items-center gap-2 p-3 bg-red-50 rounded-lg border border-red-200">
                  <XCircle className="w-5 h-5 text-red-500" />
                  <span className="text-sm font-medium text-red-700">
                    Unable to analyze this page. Please refresh and try again.
                  </span>
                </div>
              )}

              {/* Show permissions error */}
              {!extensionStatus.permissionsGranted && (
                <div className="flex items-center gap-2 p-3 bg-orange-50 rounded-lg border border-orange-200">
                  <AlertCircle className="w-5 h-5 text-orange-500" />
                  <button
                    className="text-sm font-medium text-orange-700 hover:text-orange-800 hover:underline transition-colors duration-200"
                    onClick={requestPermissions}
                  >
                    Not all permissions are granted; click here to grant
                    permissions
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Current Page Info */}
        <div className="mb-4 p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200">
          <h3 className="text-sm font-semibold text-purple-700 mb-3 flex items-center gap-2">
            <Globe className="w-4 h-4" />
            Current Page Analysis
          </h3>

          {/* Show warning if extension isn't ready */}
          {(!extensionStatus.backgroundActive ||
            !extensionStatus.permissionsGranted) && (
            <div className="mb-3 p-3 bg-yellow-50 rounded-lg border border-yellow-200">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-yellow-600" />
                <span className="text-sm text-yellow-700 font-medium">
                  Data unavailable - Extension status failed
                </span>
              </div>
            </div>
          )}

          <div className="space-y-2">
            <div className="flex justify-between items-start">
              <span className="text-xs text-gray-600">URL:</span>
              <span
                className={`text-xs text-right max-w-48 truncate font-mono ${
                  !extensionStatus.backgroundActive ||
                  !extensionStatus.permissionsGranted
                    ? "text-gray-400 italic"
                    : ""
                }`}
              >
                {truncateText(pageInfo.url, 25)}
              </span>
            </div>
            <div className="flex justify-between items-start">
              <span className="text-xs text-gray-600">Title:</span>
              <span
                className={`text-xs text-right max-w-48 truncate ${
                  !extensionStatus.backgroundActive ||
                  !extensionStatus.permissionsGranted
                    ? "text-gray-400 italic"
                    : ""
                }`}
              >
                {truncateText(pageInfo.title, 20)}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 mt-3">
              <div
                className={`flex items-center justify-center gap-2 p-2 bg-white rounded-lg border ${
                  !extensionStatus.backgroundActive ||
                  !extensionStatus.permissionsGranted
                    ? "opacity-50"
                    : ""
                }`}
              >
                <Cookie className="w-4 h-4 text-orange-500" />
                <div className="text-center">
                  <div className="text-lg font-bold text-orange-600">
                    {pageInfo.cookieCount}
                  </div>
                  <div className="text-xs text-gray-500">Cookies</div>
                </div>
              </div>
              <div
                className={`flex items-center justify-center gap-2 p-2 bg-white rounded-lg border ${
                  !extensionStatus.backgroundActive ||
                  !extensionStatus.permissionsGranted
                    ? "opacity-50"
                    : ""
                }`}
              >
                <Code className="w-4 h-4 text-blue-500" />
                <div className="text-center">
                  <div className="text-lg font-bold text-blue-600">
                    {pageInfo.scriptCount}
                  </div>
                  <div className="text-xs text-gray-500">Scripts</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mb-4">
          <button
            onClick={async () => initializePopup()}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg hover:from-green-600 hover:to-green-700 transition-all duration-200 text-xs font-medium shadow-md hover:shadow-lg transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
            Refresh Info
          </button>
        </div>

        {/* Footer */}
        <div className="text-center pt-4 border-t border-gray-200">
          <p className="text-xs text-blue-600 italic flex items-center justify-center">
            <button
              className="flex items-center gap-1"
              onClick={() => console.log("Disclaimer clicked")}
            >
              <Info className="w-3 h-3" />
              Click here for disclaimer
            </button>
          </p>
          <p className="text-xs text-gray-400 mt-1">
            <a
              href="https://www.flaticon.com/free-icons/fraud"
              title="Fraud Icon"
            >
              Browser Extension icon created by Smashicons - Flaticon
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;
