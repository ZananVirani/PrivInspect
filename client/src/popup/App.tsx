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
  Eye,
  Target,
  AlertTriangle,
} from "lucide-react";
import { ApiService } from "../utils/apiService";

interface PageInfo {
  url: string;
  title: string;
  cookieCount: number;
  scriptCount: number;
  webRequestCount: number;
}

interface ExtensionStatus {
  extensionId: string;
  backgroundActive: boolean;
  permissionsGranted: boolean;
}

interface AnalysisResult {
  privacy_score: number;
  privacy_grade: string;
  privacy_level: string;
  findings: string[];
  recommendations: string[];
  third_party_domains: string[];
  known_trackers: string[];
  computed_features?: {
    num_third_party_domains: number;
    num_third_party_scripts: number;
    num_third_party_cookies: number;
    num_persistent_cookies: number;
    tracker_script_ratio: number;
    fingerprinting_flag: number;
  };
  score_breakdown?: any;
}

function App() {
  const [pageInfo, setPageInfo] = useState<PageInfo>({
    url: "Loading...",
    title: "Loading...",
    cookieCount: 0,
    scriptCount: 0,
    webRequestCount: 0,
  });

  const [extensionStatus, setExtensionStatus] = useState<ExtensionStatus>({
    extensionId: "Loading...",
    backgroundActive: false,
    permissionsGranted: false,
  });

  const [loading, setLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  useEffect(() => {
    initializePopup();

    // Set up periodic web request monitoring
    const interval = setInterval(() => {
      updateWebRequestCount();
    }, 3000); // Update every 3 seconds

    return () => clearInterval(interval);
  }, []);

  const updateWebRequestCount = async () => {
    try {
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });
      if (
        tab?.id &&
        tab.url &&
        !tab.url.startsWith("chrome://") &&
        !tab.url.startsWith("chrome-extension://")
      ) {
        // First try to ping the content script to see if it's ready
        chrome.tabs.sendMessage(tab.id, { type: "PING" }, (_pingResponse) => {
          if (chrome.runtime.lastError) {
            // Content script not ready yet, just skip this update
            return;
          }

          // Content script is ready, now get the web request count
          chrome.tabs.sendMessage(
            tab.id!,
            { type: "GET_WEB_REQUEST_COUNT" },
            (response) => {
              if (chrome.runtime.lastError) {
                console.warn(
                  "Failed to get web request count:",
                  chrome.runtime.lastError.message
                );
              } else if (response && response.webRequestCount !== undefined) {
                setPageInfo((prev) => ({
                  ...prev,
                  webRequestCount: response.webRequestCount,
                }));
              }
            }
          );
        });
      }
    } catch (error) {
      console.error("Error updating web request count:", error);
    }
  };

  const initializePopup = async () => {
    try {
      // Get extension ID
      const extensionId = chrome.runtime.id;

      // Test background communication
      const backgroundActive = await testBackgroundCommunication();

      // Check permissions
      const permissionsGranted = await checkPermissions();

      // Update extension status
      setExtensionStatus({
        extensionId,
        backgroundActive,
        permissionsGranted,
      });

      // Load page info
      await loadCurrentPageInfo(backgroundActive, permissionsGranted);

      // Authenticate and analyze if extension is ready
      if (backgroundActive && permissionsGranted) {
        await authenticateAndAnalyze();
      }
    } catch (error) {
      console.error("Error initializing popup:", error);
    }
  };

  const getValidToken = async (): Promise<string | null> => {
    try {
      // Check for existing token
      const existingToken = await ApiService.getStoredToken();

      if (existingToken && ApiService.isTokenValid(existingToken)) {
        return existingToken;
      }

      // Get new token if none exists or expired
      const authResponse = await ApiService.authenticate();
      await ApiService.storeToken(authResponse.access_token);

      return authResponse.access_token;
    } catch (error) {
      console.error("Authentication failed:", error);
      return null;
    }
  };

  const authenticateAndAnalyze = async () => {
    try {
      setLoading(true);
      setAnalysisError(null);

      // Get or refresh JWT token
      const token = await getValidToken();

      if (!token) {
        console.error("Authentication failed");
        setAnalysisError("Authentication failed");
        return;
      }

      // Collect data from current tab
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });
      if (!tab.id) {
        console.error("No active tab found");
        setAnalysisError("No active tab found");
        return;
      }

      const results = await chrome.tabs.sendMessage(tab.id, {
        type: "COLLECT_PRIVACY_DATA",
      });

      if (!results) {
        console.error("Failed to collect page data");
        setAnalysisError("Failed to collect page data");
        return;
      }

      // Send to backend for analysis using new comprehensive method
      const analysisResult = await ApiService.analyzeComprehensivePrivacy(
        results,
        token
      );
      console.log("Analysis Result:", analysisResult);
      setAnalysisResult(analysisResult);
    } catch (error) {
      console.error("Analysis failed:", error);
      setAnalysisError("Analysis failed: " + (error as Error).message);
    } finally {
      setLoading(false);
    }
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
          webRequestCount: 0,
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
          webRequestCount: 0,
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
                  webRequestCount: response.webRequestCount || 0,
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
        webRequestCount: 0,
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

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'A': return 'text-green-600 bg-green-50';
      case 'B': return 'text-blue-600 bg-blue-50';
      case 'C': return 'text-yellow-600 bg-yellow-50';
      case 'D': return 'text-orange-600 bg-orange-50';
      case 'F': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getPrivacyLevelIcon = (level: string) => {
    switch (level) {
      case 'high': return <Shield className="w-4 h-4 text-green-600" />;
      case 'medium': return <Eye className="w-4 h-4 text-yellow-600" />;
      case 'low': return <AlertTriangle className="w-4 h-4 text-red-600" />;
      default: return <Shield className="w-4 h-4 text-gray-600" />;
    }
  };

  const getTopTrackingDomains = (knownTrackers: string[]) => {
    // For now, return the first 5 known trackers
    // TODO: In the future, this could be enhanced with severity scores from the backend
    return knownTrackers.slice(0, 5);
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

        // If permissions are now granted and background is active, reload page info and authenticate
        if (permissionsGranted && extensionStatus.backgroundActive) {
          loadCurrentPageInfo(
            extensionStatus.backgroundActive,
            permissionsGranted
          );

          // Trigger authentication and analysis now that we have permissions
          await authenticateAndAnalyze();
        }
      }

      return granted;
    } catch (error) {
      console.error("Error requesting permissions:", error);
      return false;
    }
  };

  return (
    <div className="w-96 h-[600px] max-w-96 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 text-white overflow-hidden">
      {/* Main Content */}
      <div className="bg-white text-gray-800 p-5 h-full overflow-y-auto custom-scrollbar">
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

        {/* Privacy Score Section - Only show if we have analysis results */}
        {analysisResult && (
          <div className="mb-4 p-4 bg-gradient-to-r from-green-50 to-blue-50 rounded-lg border border-green-200">
            <h3 className="text-sm font-semibold text-green-700 mb-3 flex items-center gap-2">
              <Target className="w-4 h-4" />
              Privacy Analysis Results
            </h3>
            
            {/* Score and Grade */}
            <div className="flex items-center justify-between mb-3">
              <div className="text-center">
                <div className="text-3xl font-bold text-green-600">
                  {analysisResult.privacy_score}/100
                </div>
                <div className="text-xs text-gray-500">Privacy Score</div>
              </div>
              <div className={`px-4 py-2 rounded-full text-lg font-bold ${getGradeColor(analysisResult.privacy_grade)}`}>
                {analysisResult.privacy_grade}
              </div>
              <div className="flex items-center gap-1">
                {getPrivacyLevelIcon(analysisResult.privacy_level)}
                <span className="text-sm font-medium capitalize">
                  {analysisResult.privacy_level} Privacy
                </span>
              </div>
            </div>

            {/* Key Metrics */}
            {analysisResult.computed_features && (
              <div className="grid grid-cols-2 gap-2 mb-3">
                <div className="bg-white p-2 rounded border">
                  <div className="text-xs text-gray-600">Third-Party Domains</div>
                  <div className="text-lg font-bold text-blue-600">
                    {analysisResult.computed_features.num_third_party_domains}
                  </div>
                </div>
                <div className="bg-white p-2 rounded border">
                  <div className="text-xs text-gray-600">Persistent Cookies</div>
                  <div className="text-lg font-bold text-orange-600">
                    {analysisResult.computed_features.num_persistent_cookies}
                  </div>
                </div>
                <div className="bg-white p-2 rounded border">
                  <div className="text-xs text-gray-600">Known Trackers</div>
                  <div className="text-lg font-bold text-red-600">
                    {analysisResult.known_trackers.length}
                  </div>
                </div>
                <div className="bg-white p-2 rounded border">
                  <div className="text-xs text-gray-600">Tracker Ratio</div>
                  <div className="text-lg font-bold text-purple-600">
                    {analysisResult.computed_features.num_third_party_domains > 0 
                      ? Math.round((analysisResult.known_trackers.length / analysisResult.computed_features.num_third_party_domains) * 100)
                      : 0}%
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Top Tracking Domains - Only show if we have trackers */}
        {analysisResult && analysisResult.known_trackers.length > 0 && (
          <div className="mb-4 p-4 bg-gradient-to-r from-red-50 to-orange-50 rounded-lg border border-red-200">
            <h3 className="text-sm font-semibold text-red-700 mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              Top Tracking Domains ({analysisResult.known_trackers.length})
            </h3>
            <div className="space-y-2">
              {getTopTrackingDomains(analysisResult.known_trackers).map((domain, index) => (
                <div key={domain} className="flex items-center gap-2 p-2 bg-white rounded border">
                  <div className="w-6 h-6 bg-red-100 rounded-full flex items-center justify-center">
                    <span className="text-xs font-bold text-red-600">{index + 1}</span>
                  </div>
                  <div className="flex-1 text-sm font-mono text-gray-800 truncate">
                    {domain}
                  </div>
                  <Eye className="w-4 h-4 text-red-500" />
                </div>
              ))}
              {analysisResult.known_trackers.length > 5 && (
                <div className="text-xs text-center text-gray-500 italic">
                  +{analysisResult.known_trackers.length - 5} more tracking domains detected
                </div>
              )}
            </div>
          </div>
        )}

        {/* Findings and Recommendations */}
        {analysisResult && (analysisResult.findings.length > 0 || analysisResult.recommendations.length > 0) && (
          <div className="mb-4 p-4 bg-gradient-to-r from-yellow-50 to-orange-50 rounded-lg border border-yellow-200">
            <h3 className="text-sm font-semibold text-yellow-700 mb-3 flex items-center gap-2">
              <Info className="w-4 h-4" />
              Privacy Insights
            </h3>
            
            {/* Findings */}
            {analysisResult.findings.length > 0 && (
              <div className="mb-3">
                <h4 className="text-xs font-semibold text-orange-700 mb-2">Issues Found:</h4>
                <div className="space-y-1 max-h-24 overflow-y-auto">
                  {analysisResult.findings.slice(0, 3).map((finding, index) => (
                    <div key={index} className="flex items-start gap-2">
                      <AlertCircle className="w-3 h-3 text-orange-500 mt-0.5 flex-shrink-0" />
                      <span className="text-xs text-gray-700">{finding}</span>
                    </div>
                  ))}
                  {analysisResult.findings.length > 3 && (
                    <div className="text-xs text-center text-gray-500 italic">
                      +{analysisResult.findings.length - 3} more issues
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {analysisResult.recommendations.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-blue-700 mb-2">Recommendations:</h4>
                <div className="space-y-1 max-h-24 overflow-y-auto">
                  {analysisResult.recommendations.slice(0, 3).map((rec, index) => (
                    <div key={index} className="flex items-start gap-2">
                      <CheckCircle className="w-3 h-3 text-blue-500 mt-0.5 flex-shrink-0" />
                      <span className="text-xs text-gray-700">{rec}</span>
                    </div>
                  ))}
                  {analysisResult.recommendations.length > 3 && (
                    <div className="text-xs text-center text-gray-500 italic">
                      +{analysisResult.recommendations.length - 3} more recommendations
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Analysis Error */}
        {analysisError && (
          <div className="mb-4 p-4 bg-red-50 rounded-lg border border-red-200">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-500" />
              <span className="text-sm font-medium text-red-700">Analysis Failed</span>
            </div>
            <p className="text-xs text-red-600 mt-1">{analysisError}</p>
          </div>
        )}

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
              <span className="text-xs text-gray-600 mr-1 font-bold">URL:</span>
              <span
                className={`text-xs text-right truncate font-mono ${
                  !extensionStatus.backgroundActive ||
                  !extensionStatus.permissionsGranted
                    ? "text-gray-400 italic"
                    : ""
                }`}
              >
                {pageInfo.url}
              </span>
            </div>
            <div className="flex justify-between items-start">
              <span className="text-xs text-gray-600 mr-1 font-bold">
                Title:
              </span>
              <span
                className={`text-xs text-right truncate ${
                  !extensionStatus.backgroundActive ||
                  !extensionStatus.permissionsGranted
                    ? "text-gray-400 italic"
                    : ""
                }`}
              >
                {pageInfo.title}
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
            onClick={async () => {
              await initializePopup();
              // Trigger analysis if extension is ready
              if (extensionStatus.backgroundActive && extensionStatus.permissionsGranted) {
                await authenticateAndAnalyze();
              }
            }}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg hover:from-green-600 hover:to-green-700 transition-all duration-200 text-xs font-medium shadow-md hover:shadow-lg transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
            {loading ? "Analyzing..." : "Analyze Privacy"}
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
