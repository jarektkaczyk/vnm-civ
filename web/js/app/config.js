// Site configuration, read by js/app/analytics.js.
// POSTHOG_KEY is the public project key of the PostHog EU project (it ships in the page by design). Empty = no analytics
// script loads. CF_BEACON_TOKEN is the public site token of Cloudflare Web Analytics (it ships in the page by design);
// empty = no beacon loads. analytics.js injects both scripts under the same guard.
export const POSTHOG_KEY = "phc_ucQEwFzGmuXRMkiZzvGF7ALEVQpxoU7BG75QVYh5Rjug";
export const POSTHOG_HOST = "https://eu.i.posthog.com";
export const POSTHOG_ASSETS = "https://eu-assets.i.posthog.com";
export const CF_BEACON_TOKEN = "fc15ccf0412446f9b7f0edf2e2123dc7";
export const CF_BEACON_SRC = "https://static.cloudflareinsights.com/beacon.min.js";
