import { test as base, expect, type APIRequestContext, type Page } from '@playwright/test';
import { BACKEND_URL } from './constants';

export { expect };

export const DEFAULT_PASSWORD = 'E2e-password-123';

/**
 * Stand-in for Cloudflare's Turnstile script: renders nothing and hands the
 * widget a token straight away, so tests don't depend on Cloudflare being
 * reachable. The backend's check is stubbed in tests/e2e_support/app.py.
 */
const FAKE_TURNSTILE = `
  (() => {
    const widgets = new Map();
    let next = 0;
    const issue = (opts) => setTimeout(() => opts.callback && opts.callback('e2e-turnstile-token'), 0);
    window.turnstile = {
      render(el, opts) {
        const id = 'e2e-widget-' + (next += 1);
        widgets.set(id, opts);
        issue(opts);
        return id;
      },
      // The app resets the widget after every failed submit and expects a new token.
      reset(id) {
        const opts = id ? widgets.get(id) : [...widgets.values()].pop();
        if (opts) issue(opts);
      },
      remove(id) { widgets.delete(id); },
      execute() {},
      getResponse() { return 'e2e-turnstile-token'; },
      isExpired() { return false; },
      ready(cb) { cb(); },
    };
  })();
`;

async function stubTurnstile(page: Page) {
  await page.route('https://challenges.cloudflare.com/turnstile/**', async (route) => {
    const onload = new URL(route.request().url()).searchParams.get('onload');
    const body = onload ? `${FAKE_TURNSTILE}\nwindow[${JSON.stringify(onload)}]?.();` : FAKE_TURNSTILE;
    await route.fulfill({ contentType: 'application/javascript', body });
  });
}

export function uniqueEmail(tag = 'user'): string {
  const rand = Math.random().toString(36).slice(2, 8);
  return `e2e-${tag}-${Date.now().toString(36)}-${rand}@example.com`.toLowerCase();
}

/** Read the last code "emailed" to a test address. */
export async function readEmailedCode(api: APIRequestContext, email: string): Promise<string> {
  let lastStatus = 0;
  // Emails go out as background tasks, so give the backend a moment.
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const res = await api.get(`${BACKEND_URL}/__e2e__/outbox/${encodeURIComponent(email)}`);
    lastStatus = res.status();
    if (res.ok()) return (await res.json()).code as string;
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error(`No code was emailed to ${email} (last status ${lastStatus})`);
}

export interface Account {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
}

/** Sign up without verifying. */
export async function signUpUnverified(
  api: APIRequestContext,
  overrides: Partial<Account> = {},
): Promise<Account> {
  const account: Account = {
    email: uniqueEmail(),
    password: DEFAULT_PASSWORD,
    firstName: 'Ada',
    lastName: 'Lovelace',
    ...overrides,
  };
  const res = await api.post(`${BACKEND_URL}/auth/signup`, {
    data: {
      email: account.email,
      password: account.password,
      first_name: account.firstName,
      last_name: account.lastName,
      cf_token: 'e2e',
    },
  });
  expect(res.status()).toBe(201);
  return account;
}

/**
 * Create a verified account. Pass `page.context().request` to have the auth
 * cookies land in that browser context (the page is then signed in), or the
 * isolated `request` fixture to leave the browser signed out.
 */
export async function createAccount(
  api: APIRequestContext,
  overrides: Partial<Account> = {},
): Promise<Account> {
  const account = await signUpUnverified(api, overrides);
  const code = await readEmailedCode(api, account.email);
  const res = await api.post(`${BACKEND_URL}/auth/verify_otp`, {
    data: { email: account.email, otp_code: code, password: account.password, cf_token: 'e2e' },
  });
  expect(res.status()).toBe(200);
  return account;
}

/** Fill the login form and submit it. */
export async function loginViaUi(page: Page, email: string, password: string) {
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign In', exact: true }).click();
}

export async function expectSignedIn(page: Page) {
  await expect(page.getByText('What can I help you process?')).toBeVisible();
}

export async function expectSignedOut(page: Page) {
  await expect(page.getByText('Welcome back')).toBeVisible();
}

export async function openAccountMenu(page: Page) {
  await page.getByRole('button', { name: 'Account menu' }).click();
}

interface Fixtures {
  /** A page already signed in to a fresh verified account. */
  signedIn: { page: Page; account: Account };
}

export const test = base.extend<Fixtures>({
  page: async ({ page }, use) => {
    await stubTurnstile(page);
    // Dismiss the cookie banner up front; it overlays the bottom of the page.
    await page.addInitScript(() => localStorage.setItem('nlpdf_cookie_consent', 'accepted'));
    await use(page);
  },
  signedIn: async ({ page }, use) => {
    const account = await createAccount(page.context().request);
    await page.goto('/');
    await expectSignedIn(page);
    await use({ page, account });
  },
});
