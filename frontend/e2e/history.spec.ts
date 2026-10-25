import type { Page } from '@playwright/test';
import { makePdf } from './support/files';
import { createAccount, expect, openAccountMenu, test } from './support/fixtures';

async function processFile(page: Page, name: string, command: string) {
  await page.locator('input[type="file"]').setInputFiles([await makePdf(name, 2)]);
  await page.getByPlaceholder('Message NLPDF…').fill(command);
  await page.getByRole('button', { name: 'Send command' }).click();
  await expect(page.getByText('Processing Complete!')).toBeVisible();
  await page.getByRole('button', { name: 'Process another document' }).click();
}

async function openHistory(page: Page) {
  await openAccountMenu(page);
  await page.getByRole('menuitem', { name: 'History' }).click();
  await expect(page.getByRole('heading', { name: 'History' })).toBeVisible();
}

test.describe('History', () => {
  test('a new account starts with an empty history', async ({ signedIn: { page } }) => {
    await openHistory(page);
    await expect(page.getByText('Nothing here yet')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Clear all' })).toBeDisabled();
  });

  test('processed files are listed, and can be removed one by one or all at once', async ({ signedIn: { page } }) => {
    await processFile(page, 'first.pdf', 'compress this');
    await processFile(page, 'second.pdf', 'rotate page 1');

    await openHistory(page);
    const rows = page.locator('tbody tr');
    await expect(rows).toHaveCount(2);
    await expect(rows.filter({ hasText: 'first' })).toContainText('compress');
    await expect(rows.filter({ hasText: 'second' })).toContainText('rotate');

    await page.getByRole('button', { name: 'Remove first from history' }).click();
    await expect(rows).toHaveCount(1);
    await expect(rows).toContainText('second');

    await page.getByRole('button', { name: 'Clear all' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Clear all' }).click();
    await expect(page.getByText('Nothing here yet')).toBeVisible();
  });

  test("one user never sees another user's history", async ({ signedIn: { page }, browser }) => {
    await processFile(page, 'private.pdf', 'compress this');

    const otherContext = await browser.newContext();
    const other = await otherContext.newPage();
    await other.addInitScript(() => localStorage.setItem('nlpdf_cookie_consent', 'accepted'));
    await createAccount(otherContext.request);
    await other.goto('/history');
    await expect(other.getByText('Nothing here yet')).toBeVisible();
    await expect(other.getByText('private')).toBeHidden();
    await otherContext.close();
  });
});
