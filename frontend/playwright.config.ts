import { defineConfig, devices } from '@playwright/test';
import {
  BACKEND_URL, FRONTEND_PORT, FRONTEND_URL, TURNSTILE_TEST_SITE_KEY,
} from './e2e/support/constants';

/**
 * Full-stack end-to-end suite.
 *
 * Starts the real backend through tests/e2e_support/app.py (real database,
 * auth and PDF pipeline; fake LLM, captured email) and a Vite dev server
 * pointed at it. Both use their own ports so they never collide with, or
 * reuse, a normal dev setup. Needs the SQL Server database to be up and
 * migrated (`docker compose up -d sqlserver && poetry run alembic upgrade head`).
 */

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list'], ['html', { open: 'never' }]],
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: FRONTEND_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'poetry run uvicorn tests.e2e_support.app:app --port 8001',
      cwd: '..',
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        APP_ENV: 'development',
        CORS_ALLOW_ORIGINS: JSON.stringify([FRONTEND_URL]),
      },
    },
    {
      command: `npx vite --port ${FRONTEND_PORT} --strictPort`,
      url: FRONTEND_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        VITE_API_BASE_URL: BACKEND_URL,
        VITE_TURNSTILE_SITE_KEY: TURNSTILE_TEST_SITE_KEY,
      },
    },
  ],
});
