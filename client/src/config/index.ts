// Configuration module for environment-based settings
interface AppConfig {
  API_BASE_URL: string;
  EXTENSION_CLIENT_HEADER: string;
  APP_ENV: string;
}

// Validate that all required environment variables are present
const validateConfig = (): AppConfig => {
  const config = {
    API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
    EXTENSION_CLIENT_HEADER: import.meta.env.VITE_EXTENSION_CLIENT_HEADER,
    APP_ENV: import.meta.env.VITE_APP_ENV || "development",
  };

  // Ensure all required config values are present
  if (!config.API_BASE_URL) {
    throw new Error("VITE_API_BASE_URL environment variable is required");
  }

  if (!config.EXTENSION_CLIENT_HEADER) {
    throw new Error(
      "VITE_EXTENSION_CLIENT_HEADER environment variable is required",
    );
  }

  return config;
};

// Export validated configuration
export const config = validateConfig();

// Export individual values for convenience
export const { API_BASE_URL, EXTENSION_CLIENT_HEADER, APP_ENV } = config;

// Type guard to check if we're in development
export const isDevelopment = () => APP_ENV === "development";

// Type guard to check if we're in production
export const isProduction = () => APP_ENV === "production";

console.log(`🔧 App initialized in ${APP_ENV} mode`);
console.log(`🌐 API Base URL: ${API_BASE_URL}`);
