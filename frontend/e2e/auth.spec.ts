import { BACKEND_URL } from './support/constants';
import {
  DEFAULT_PASSWORD, createAccount, expect, expectSignedIn, expectSignedOut, loginViaUi,
  openAccountMenu, readEmailedCode, signUpUnverified, test, uniqueEmail,
} from './support/fixtures';

const GENERIC_LOGIN_ERROR = /Invalid email or password/;

test.describe('Sign up', () => {
  test('new user signs up, verifies the emailed code and lands on the home page', async ({ page }) => {
    const email = uniqueEmail('signup');
    await page.goto('/');
    await page.getByRole('button', { name: 'Sign up', exact: true }).click();
    await expect(page.getByText('Create an account')).toBeVisible();

    await page.getByLabel('First').fill('Grace');
    await page.getByLabel('Last').fill('Hopper');
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password', { exact: true }).fill(DEFAULT_PASSWORD);
    await page.getByLabel('Confirm Password').fill(DEFAULT_PASSWORD);
    await page.getByRole('checkbox').check();
    await page.getByRole('button', { name: 'Sign Up', exact: true }).click();

    await expect(page.getByText('Verify your email')).toBeVisible();
    const code = await readEmailedCode(page.context().request, email);
    await page.getByLabel('6-digit Verification Code').fill(code);
    await page.getByRole('button', { name: 'Verify Email' }).click();

    await expectSignedIn(page);
    await openAccountMenu(page);
    await expect(page.getByText('Grace Hopper')).toBeVisible();
    await expect(page.getByText(email)).toBeVisible();
  });

  test('client-side checks catch a short password, a mismatch and unticked terms', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Sign up', exact: true }).click();
    await page.getByLabel('First').fill('A');
    await page.getByLabel('Last').fill('B');
    await page.getByLabel('Email').fill(uniqueEmail());
    const submit = page.getByRole('button', { name: 'Sign Up', exact: true });

    await page.getByLabel('Password', { exact: true }).fill('short');
    await page.getByLabel('Confirm Password').fill('short');
    await submit.click();
    await expect(page.getByText('Password must be at least 8 characters.')).toBeVisible();

    await page.getByLabel('Password', { exact: true }).fill(DEFAULT_PASSWORD);
    await page.getByLabel('Confirm Password').fill(`${DEFAULT_PASSWORD}x`);
    await submit.click();
    await expect(page.getByText('Passwords do not match')).toBeVisible();

    await page.getByLabel('Confirm Password').fill(DEFAULT_PASSWORD);
    await submit.click();
    await expect(page.getByText('You must agree to the Terms of Service and Privacy Policy')).toBeVisible();
  });

  test('a wrong verification code is rejected', async ({ page, request }) => {
    const account = await signUpUnverified(request);
    await page.goto('/');
    await loginViaUi(page, account.email, account.password);
    await page.getByRole('button', { name: 'Send code' }).click();

    const real = await readEmailedCode(request, account.email);
    const wrong = real === '000000' ? '111111' : '000000';
    await page.getByLabel('6-digit Verification Code').fill(wrong);
    await page.getByRole('button', { name: 'Verify Email' }).click();
    await expect(page.getByText('Invalid or expired verification code')).toBeVisible();
  });
});

test.describe('Log in and out', () => {
  test('existing user logs in, stays signed in across reloads, then logs out', async ({ page, request }) => {
    const account = await createAccount(request);
    await page.goto('/');
    await expectSignedOut(page);

    await loginViaUi(page, account.email, account.password);
    await expectSignedIn(page);

    await page.reload();
    await expectSignedIn(page);

    await openAccountMenu(page);
    await page.getByRole('menuitem', { name: 'Log Out' }).click();
    await expectSignedOut(page);

    await page.reload();
    await expectSignedOut(page);
  });

  test('a wrong password and an unknown email get the same message', async ({ page, request }) => {
    const account = await createAccount(request);
    await page.goto('/');

    await loginViaUi(page, account.email, 'not-the-password');
    const wrongPassword = await page.getByRole('alert').textContent();
    expect(wrongPassword).toMatch(GENERIC_LOGIN_ERROR);

    await loginViaUi(page, uniqueEmail('nobody'), 'not-the-password');
    await expect(page.getByRole('alert')).toHaveText(wrongPassword ?? '');
  });

  test('after five wrong passwords even the right one is refused', async ({ page, request }) => {
    const account = await createAccount(request);
    for (let i = 0; i < 5; i += 1) {
      const res = await request.post(`${BACKEND_URL}/auth/login`, {
        data: { email: account.email, password: 'wrong-password', cf_token: 'e2e' },
      });
      expect(res.status()).toBe(401);
    }

    await page.goto('/');
    await loginViaUi(page, account.email, account.password);
    await expect(page.getByRole('alert')).toContainText('sign-in is paused for 15 minutes');
    await expectSignedOut(page);
  });

  test('an unverified user is offered a code and can finish signing up from the login screen', async ({ page, request }) => {
    const account = await signUpUnverified(request);
    await page.goto('/');
    await loginViaUi(page, account.email, account.password);

    await expect(page.getByText("Your email isn't verified yet.")).toBeVisible();
    await page.getByRole('button', { name: 'Send code' }).click();
    await expect(page.getByText('Verify your email')).toBeVisible();

    const code = await readEmailedCode(request, account.email);
    await page.getByLabel('6-digit Verification Code').fill(code);
    await page.getByRole('button', { name: 'Verify Email' }).click();
    await expectSignedIn(page);
  });

  test('losing the session cookies sends the user back to the login screen', async ({ signedIn }) => {
    const { page } = signedIn;
    await page.context().clearCookies();
    await page.reload();
    await expectSignedOut(page);
  });
});

test.describe('Forgot password', () => {
  test('user resets the password with the emailed code and logs in with the new one', async ({ page, request }) => {
    const account = await createAccount(request);
    const newPassword = 'Brand-new-pass-456';

    await page.goto('/');
    await page.getByRole('button', { name: 'Forgot password?' }).click();
    await page.getByLabel('Email').fill(account.email);
    await page.getByRole('button', { name: 'Send Reset Code' }).click();
    await expect(page.getByText('If that email is valid, a reset code was sent.')).toBeVisible();

    const code = await readEmailedCode(request, account.email);
    await page.getByLabel('Verification Code').fill(code);
    await page.getByLabel('New Password').fill(newPassword);
    await page.getByLabel('Confirm').fill(newPassword);
    await page.getByRole('button', { name: 'Reset Password' }).click();
    await expect(page.getByText('Password reset successfully. You can now log in.')).toBeVisible();

    await loginViaUi(page, account.email, account.password);
    await expect(page.getByRole('alert')).toContainText(GENERIC_LOGIN_ERROR);

    await loginViaUi(page, account.email, newPassword);
    await expectSignedIn(page);
  });

  test('an unknown email gets the same response as a real one', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Forgot password?' }).click();
    await page.getByLabel('Email').fill(uniqueEmail('ghost'));
    await page.getByRole('button', { name: 'Send Reset Code' }).click();
    await expect(page.getByText('If that email is valid, a reset code was sent.')).toBeVisible();
  });
});
