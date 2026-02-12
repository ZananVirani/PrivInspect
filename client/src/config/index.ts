// Configuration module for environment-based settings
interface AppConfig {
  API_BASE_URL: string;
  EXTENSION_CLIENT_HEADER: string;
}

// Validate that all required environment variables are present
const validateConfig = (): AppConfig => {
  const config = {
    API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
    EXTENSION_CLIENT_HEADER: import.meta.env.VITE_EXTENSION_CLIENT_HEADER,
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

// Export individual values for convenience
export const { API_BASE_URL, EXTENSION_CLIENT_HEADER } = validateConfig();
