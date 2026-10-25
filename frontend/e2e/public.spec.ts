import { BACKEND_URL } from './support/constants';
import { expect, expectSignedOut, test } from './support/fixtures';

test.describe('Public pages', () => {
  test('the login screen loads', async ({ page }) => {
    await page.goto('/');
    await expectSignedOut(page);
    await expect(page.getByText('NLPDF', { exact: true })).toBeVisible();
  });

  test('empty login fields are caught before anything is sent', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Sign In', exact: true }).click();
    await expect(page.getByText('Please fill in all fields')).toBeVisible();
  });

  test('terms and privacy are readable while signed out', async ({ page }) => {
    await page.goto('/terms');
    await expect(page.getByRole('heading', { name: /Terms of Service/i }).first()).toBeVisible();
    await page.goto('/privacy');
    await expect(page.getByRole('heading', { name: /Privacy Policy/i }).first()).toBeVisible();
  });

  test('a protected URL shows the login screen when signed out', async ({ page }) => {
    await page.goto('/settings/sessions');
    await expectSignedOut(page);
  });

  test('an unknown URL sends a signed-in user home', async ({ signedIn: { page } }) => {
    await page.goto('/no-such-page');
    await expect(page).toHaveURL(/\/$/);
  });
});

test.describe('Cookie banner', () => {
  test('appears on a first visit and stays dismissed', async ({ browser }) => {
    // A fresh context without the fixture's pre-accepted consent.
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('/terms');
    await expect(page.getByText(/This site uses cookies/)).toBeVisible();
    await page.getByRole('button', { name: 'Got it' }).click();
    await expect(page.getByText(/This site uses cookies/)).toBeHidden();

    await page.reload();
    await page.waitForTimeout(1200); // the banner appears after an 800 ms delay
    await expect(page.getByText(/This site uses cookies/)).toBeHidden();
    await context.close();
  });
});

test.describe('Browser-level protections', () => {
  test('auth cookies are not readable by page scripts', async ({ signedIn: { page } }) => {
    const visible = await page.evaluate(() => document.cookie);
    expect(visible).not.toContain('access_token');
    expect(visible).not.toContain('refresh_token');
    // The CSRF token has to be readable: the app copies it into a header.
    expect(visible).toContain('csrf_token');
  });

  test('a state-changing request without the CSRF header is refused, readably', async ({ signedIn: { page } }) => {
    // The 403 must carry CORS headers; otherwise the browser hides it and the
    // app can only report a network failure.
    const result = await page.evaluate(async (api) => {
      const res = await fetch(`${api}/documents`, { method: 'DELETE', credentials: 'include' });
      return { status: res.status, body: await res.json() };
    }, BACKEND_URL);
    expect(result.status).toBe(403);
    expect(result.body.detail).toBe('Missing CSRF token');
  });

  test('API responses carry the security headers', async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/health`);
    const headers = res.headers();
    expect(headers['x-content-type-options']).toBe('nosniff');
    expect(headers['x-frame-options']).toBe('DENY');
    expect(headers['content-security-policy']).toContain("frame-ancestors 'none'");
  });
});
