/**
 * Centralised application configuration.
 * Values are read from environment variables set in the .env file.
 * See .env.example for the required variables.
 */

export const config = {
  /** Base URL of the backend API */
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL as string,

  /** Cloudflare Turnstile site key for CAPTCHA */
  turnstileSiteKey: import.meta.env.VITE_TURNSTILE_SITE_KEY as string,
} as const;
