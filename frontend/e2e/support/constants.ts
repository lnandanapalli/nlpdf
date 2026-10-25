/** Ports dedicated to the e2e run so it never reuses a normal dev server. */
export const BACKEND_URL = 'http://localhost:8001';
export const FRONTEND_PORT = 5174;
export const FRONTEND_URL = `http://localhost:${FRONTEND_PORT}`;

/** Cloudflare's always-pass Turnstile site key (the script itself is stubbed). */
export const TURNSTILE_TEST_SITE_KEY = '1x00000000000000000000AA';
