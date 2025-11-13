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

export function isThirdPartyDomain(
  requestDomain: string,
  pageDomain: string
): boolean {
  // Remove www. prefix for comparison
  const cleanRequestDomain = requestDomain.replace(/^www\./, "");
  const cleanPageDomain = pageDomain.replace(/^www\./, "");

  // Check if domains match or if request domain is subdomain of page domain
  return (
    !cleanRequestDomain.endsWith(cleanPageDomain) &&
    cleanRequestDomain !== cleanPageDomain
  );
}

export function isKnownTracker(domain: string): boolean {
  return KNOWN_TRACKERS.has(domain.toLowerCase());
}
