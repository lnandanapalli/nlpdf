import type { Browser, Page } from '@playwright/test';
import { BACKEND_URL } from './support/constants';
import {
  type Account, expect, expectSignedIn, expectSignedOut, loginViaUi, openAccountMenu,
  readEmailedCode, test,
} from './support/fixtures';

async function openSettings(page: Page, section: 'Profile' | 'Security' | 'Sessions') {
  await openAccountMenu(page);
  await page.getByRole('menuitem', { name: 'Settings' }).click();
  await page.getByRole('button', { name: section, exact: true }).click();
}

/** Sign the same account in from a second, independent browser. */
async function signInElsewhere(browser: Browser, account: Account) {
  const context = await browser.newContext({ userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
  const res = await context.request.post(`${BACKEND_URL}/auth/login`, {
    data: { email: account.email, password: account.password, cf_token: 'e2e' },
  });
  expect(res.status()).toBe(200);
  return context;
}

async function isSignedIn(context: Awaited<ReturnType<Browser['newContext']>>) {
  return (await context.request.get(`${BACKEND_URL}/auth/me`)).ok();
}

test.describe('Profile', () => {
  test('changing the name updates the account menu', async ({ signedIn: { page } }) => {
    await openSettings(page, 'Profile');
    await page.getByLabel('First Name').fill('Katherine');
    await page.getByLabel('Last Name').fill('Johnson');
    await page.getByRole('button', { name: 'Save Changes' }).click();
    await expect(page.getByText('Profile updated successfully')).toBeVisible();

    await page.reload();
    await openAccountMenu(page);
    await expect(page.getByText('Katherine Johnson')).toBeVisible();
  });
});

test.describe('Password', () => {
  test('a wrong current password is refused', async ({ signedIn: { page } }) => {
    await openSettings(page, 'Security');
    await page.getByLabel('Current Password').fill('not-my-password');
    await page.getByLabel('New Password', { exact: true }).fill('Another-pass-789');
    await page.getByLabel('Confirm New Password').fill('Another-pass-789');
    await page.getByRole('button', { name: 'Change Password' }).click();
    await expect(page.getByText('Current password is incorrect')).toBeVisible();
  });

  test('after a change the new password works and other devices are signed out', async ({ signedIn: { page, account }, browser }) => {
    const elsewhere = await signInElsewhere(browser, account);
    const newPassword = 'Another-pass-789';

    await openSettings(page, 'Security');
    await page.getByLabel('Current Password').fill(account.password);
    await page.getByLabel('New Password', { exact: true }).fill(newPassword);
    await page.getByLabel('Confirm New Password').fill(newPassword);
    await page.getByRole('button', { name: 'Change Password' }).click();
    await expect(page.getByText('Password changed successfully')).toBeVisible();

    // This device stays signed in; the other one is cut off immediately.
    await page.reload();
    await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();
    expect(await isSignedIn(elsewhere)).toBe(false);
    await elsewhere.close();

    await openAccountMenu(page);
    await page.getByRole('menuitem', { name: 'Log Out' }).click();
    await loginViaUi(page, account.email, newPassword);
    await expectSignedIn(page);
  });
});

test.describe('Sessions', () => {
  test('lists this device and another one, and can sign the other out', async ({ signedIn: { page, account }, browser }) => {
    const elsewhere = await signInElsewhere(browser, account);

    await openSettings(page, 'Sessions');
    const items = page.locator('li.MuiListItem-root');
    await expect(items).toHaveCount(2);
    await expect(items.filter({ hasText: 'This device' })).toHaveCount(1);

    const other = items.filter({ hasNotText: 'This device' });
    await expect(other).toContainText('iPhone');
    await other.getByRole('button', { name: 'Sign out' }).click();
    await expect(page.getByText('That device has been signed out.')).toBeVisible();
    await expect(items).toHaveCount(1);

    // Its refresh token is gone, so it can't renew its session.
    const refresh = await elsewhere.request.post(`${BACKEND_URL}/auth/refresh`, { data: {} });
    expect(refresh.status()).toBe(401);
    await elsewhere.close();
  });

  test('"sign out all other devices" cuts them off immediately', async ({ signedIn: { page, account }, browser }) => {
    const elsewhere = await signInElsewhere(browser, account);
    expect(await isSignedIn(elsewhere)).toBe(true);

    await openSettings(page, 'Sessions');
    await page.getByRole('button', { name: 'Sign out all other devices' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Sign out' }).click();
    await expect(page.getByText('All other devices have been signed out.')).toBeVisible();
    await expect(page.locator('li.MuiListItem-root')).toHaveCount(1);

    expect(await isSignedIn(elsewhere)).toBe(false);
    await elsewhere.close();

    await page.reload();
    await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();
  });

  test('with no other devices the bulk sign-out is disabled', async ({ signedIn: { page } }) => {
    await openSettings(page, 'Sessions');
    await expect(page.getByText('This device')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign out all other devices' })).toBeDisabled();
  });
});

test.describe('Delete account', () => {
  test('deleting with the emailed code removes the account for good', async ({ signedIn: { page, account }, request }) => {
    await openSettings(page, 'Security');
    await page.getByRole('button', { name: 'Delete Account' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Password').fill(account.password);
    await dialog.getByRole('button', { name: 'Continue' }).click();

    const code = await readEmailedCode(request, account.email);
    await dialog.getByLabel('6-digit Confirmation Code').fill(code);
    await dialog.getByRole('button', { name: 'Delete My Account' }).click();
    await expectSignedOut(page);

    await loginViaUi(page, account.email, account.password);
    await expect(page.getByRole('alert')).toContainText('Invalid email or password');
  });

  test('a wrong password stops the deletion at the first step', async ({ signedIn: { page } }) => {
    await openSettings(page, 'Security');
    await page.getByRole('button', { name: 'Delete Account' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Password').fill('not-my-password');
    await dialog.getByRole('button', { name: 'Continue' }).click();
    await expect(dialog.getByText('Password is incorrect')).toBeVisible();
  });
});
