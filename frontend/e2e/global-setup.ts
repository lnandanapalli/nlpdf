import { request } from '@playwright/test';
import { BACKEND_URL } from './support/constants';

/** Start from a clean slate: remove e2e accounts left by an interrupted run. */
export default async function globalSetup() {
  const api = await request.newContext({ baseURL: BACKEND_URL });
  await api.get('/__e2e__/cleanup');
  await api.dispose();
}
