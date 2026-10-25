import { request } from '@playwright/test';
import { BACKEND_URL } from './support/constants';

/** Remove every e2e account so test runs never pile up in the database. */
export default async function globalTeardown() {
  const api = await request.newContext({ baseURL: BACKEND_URL });
  await api.get('/__e2e__/cleanup');
  await api.dispose();
}
