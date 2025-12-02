// Known tracker domains based on TrackerRadar data
// This is a subset for demo purposes - in production you'd use the full dataset
export const KNOWN_TRACKERS = new Set([
  // Analytics trackers
  "google-analytics.com",
  "googletagmanager.com",
  "googleadservices.com",
  "doubleclick.net",
  "facebook.com",
  "facebook.net",
  "fbcdn.net",
  "connect.facebook.net",

  // Ad networks
  "googlesyndication.com",
  "adsystem.amazon.com",
  "amazon-adsystem.com",
  "adsymptotic.com",

  // Social media trackers
  "twitter.com",
  "t.co",
  "linkedin.com",
  "instagram.com",

  // Other common trackers
  "hotjar.com",
  "mixpanel.com",
  "segment.com",
  "amplitude.com",
  "fullstory.com",
  "loggly.com",
  "newrelic.com",
  "pingdom.net",
  "quantserve.com",
  "scorecardresearch.com",
  "comscore.com",
  "bing.com",
  "yahoo.com",
  "yandex.ru",
  "baidu.com",

  // CDNs often used for tracking
  "cdnjs.cloudflare.com",
  "ajax.googleapis.com",
  "maxcdn.bootstrapcdn.com",
]);

export function getDomainFromUrl(url: string): string {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return "";
  }
}

function extractDomainKeywords(domain: string): Set<string> {
  // Remove common prefixes and TLD
  const cleanDomain = domain
    .replace(/^www\./, "")
    .replace(
      /\.(com|org|net|edu|gov|io|co|uk|de|fr|jp|au|ca|br|in|ru|cn|mx|it|es|nl|se|no|dk|fi|pl|be|at|ch|cz|hu|gr|pt|ro|bg|hr|sk|si|ee|lv|lt|lu|mt|cy)(\.|$).*/,
      ""
    );

  // Split by dots and hyphens to get keywords
  const parts = cleanDomain.split(/[.\-_]/);

  // Filter out common generic words and keep meaningful keywords
  const genericWords = new Set([
    "www",
    "cdn",
    "static",
    "assets",
    "api",
    "img",
    "images",
    "js",
    "css",
    "media",
    "content",
    "data",
    "files",
    "docs",
    "blog",
    "news",
    "store",
    "shop",
    "mail",
    "email",
    "support",
    "help",
    "admin",
    "secure",
  ]);

  const keywords = new Set<string>();

  for (const part of parts) {
    if (part.length >= 3 && !genericWords.has(part)) {
      keywords.add(part);

      // Also add longer common stems (e.g., "github" from "githubassets")
      if (part.length >= 6) {
        // Check for common patterns
        for (const existingKeyword of keywords) {
          if (existingKeyword.length >= 4) {
            // If one contains the other as a substring, consider them related
            if (
              part.includes(existingKeyword) ||
              existingKeyword.includes(part)
            ) {
              keywords.add(existingKeyword);
              keywords.add(part);
            }
          }
        }
      }
    }
  }

  return keywords;
}

export function isThirdPartyDomain(
  requestDomain: string,
  pageDomain: string
): boolean {
  // Remove www. prefix for comparison
  const cleanRequestDomain = requestDomain.replace(/^www\./, "");
  const cleanPageDomain = pageDomain.replace(/^www\./, "");

  // If domains are exactly the same, it's first-party
  if (cleanRequestDomain === cleanPageDomain) {
    return false;
  }

  // Check if request domain is a subdomain of page domain (traditional first-party)
  if (cleanRequestDomain.endsWith(`.${cleanPageDomain}`)) {
    return false;
  }

  // Check if page domain is a subdomain of request domain
  if (cleanPageDomain.endsWith(`.${cleanRequestDomain}`)) {
    return false;
  }

  // Extract the base domain (e.g., "mail.google.com" -> "google.com")
  function getBaseDomain(domain: string): string {
    const parts = domain.split('.');
    if (parts.length >= 2) {
      // For common cases, return the last two parts (domain.tld)
      return parts.slice(-2).join('.');
    }
    return domain;
  }

  // Check if they share the same base domain
  const baseRequestDomain = getBaseDomain(cleanRequestDomain);
  const basePageDomain = getBaseDomain(cleanPageDomain);
  
  if (baseRequestDomain === basePageDomain) {
    return false; // Same base domain = first-party
  }

  // Extract keywords from both domains
  const pageKeywords = extractDomainKeywords(cleanPageDomain);
  const requestKeywords = extractDomainKeywords(cleanRequestDomain);

  // If they share significant keywords, consider them first-party
  for (const pageKeyword of pageKeywords) {
    if (pageKeyword.length >= 4) {
      // Only consider meaningful keywords
      for (const requestKeyword of requestKeywords) {
        if (requestKeyword.length >= 4) {
          // Check for exact match or one contains the other
          if (
            pageKeyword === requestKeyword ||
            pageKeyword.includes(requestKeyword) ||
            requestKeyword.includes(pageKeyword)
          ) {
            return false; // First-party
          }
        }
      }
    }
  }

  // If no keyword match, it's third-party
  return true;
}

export function isKnownTracker(domain: string): boolean {
  return KNOWN_TRACKERS.has(domain.toLowerCase());
}
