import { test, expect } from '@playwright/test';

test.describe('Smoke Tests', () => {
  test('should load the authentication screen', async ({ page }) => {
    // Navigate to the app root
    await page.goto('/');

    // Check for the "Loading..." state (optional, might be too fast)
    // await expect(page.getByText('Loading...')).toBeVisible();

    // Verify we landed on the Auth Screen
    await expect(page.getByText('NLPDF', { exact: true })).toBeVisible();
    await expect(page.getByText('Welcome back')).toBeVisible();
    await expect(page.getByLabel('Email')).toBeVisible();
    await expect(page.getByLabel('Password', { exact: true })).toBeVisible();
  });

  test('should show validation error when signing in with empty fields', async ({ page }) => {
    await page.goto('/');
    
    // Click Sign In without filling anything
    await page.getByRole('button', { name: 'Sign In' }).click();

    // We expect a validation error (either from browser or our app)
    // In our case, the app sets an error state: "Please fill in all fields"
    // But it also requires CAPTCHA first.
    await expect(page.getByText('Please fill in all fields')).toBeVisible();
  });
});
