import axios from 'axios';
import { config } from '../config';

export const API_BASE_URL = config.apiBaseUrl;

const PDF_PROCESSING_TIMEOUT_MS = 3 * 60 * 1000; // 3 minutes

// Shared axios instance with credentials (cookies sent automatically)
const api = axios.create({ baseURL: API_BASE_URL, withCredentials: true });

let isRefreshing = false;
let pendingRequests: Array<{
  resolve: () => void;
  reject: (err: unknown) => void;
}> = [];

function onRefreshed() {
  pendingRequests.forEach((p) => p.resolve());
  pendingRequests = [];
}

function onRefreshFailed(err: unknown) {
  pendingRequests.forEach((p) => p.reject(err));
  pendingRequests = [];
}

function getCookie(name: string): string | undefined {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : undefined;
}

// Attach CSRF token header on mutating requests
api.interceptors.request.use((cfg) => {
  if (cfg.method && cfg.method !== 'get') {
    const csrfToken = getCookie('csrf_token');
    if (csrfToken && cfg.headers) {
      cfg.headers['X-CSRF-Token'] = csrfToken;
    }
  }
  return cfg;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;

    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }

    // Don't try to refresh if this was the refresh call itself
    if (original.url === '/auth/refresh') {
      dispatchSessionExpired();
      return Promise.reject(error);
    }

    original._retry = true;

    if (isRefreshing) {
      // Another refresh is in flight — queue this request
      return new Promise((resolve, reject) => {
        pendingRequests.push({
          resolve: () => resolve(api(original)),
          reject,
        });
      });
    }

    isRefreshing = true;

    try {
      await api.post('/auth/refresh');

      isRefreshing = false;
      onRefreshed();

      return api(original);
    } catch {
      isRefreshing = false;
      onRefreshFailed(error);
      dispatchSessionExpired();
      return Promise.reject(error);
    }
  },
);

function dispatchSessionExpired() {
  window.dispatchEvent(new Event('session-expired'));
}

/**
 * Check if the current session is valid.
 * Tries GET /auth/me, falls back to refresh if 401.
 * Returns true if session is valid, false otherwise.
 */
export async function validateSession(): Promise<boolean> {
  try {
    await api.get('/auth/me');
    return true;
  } catch {
    // The interceptor will have attempted a refresh on 401.
    // If we still got an error, session is invalid.
    return false;
  }
}

/**
 * Log out the current user (revokes tokens and clears cookies server-side).
 */
export async function logout(): Promise<void> {
  try {
    await api.post('/auth/logout');
  } catch {
    // Even if the call fails, we still want the frontend to reset
  }
}

export interface UserData {
  id: number;
  email: string;
  first_name: string | null;
  last_name: string | null;
  created_at: string | null;
}

export async function fetchCurrentUser(): Promise<UserData> {
  const response = await api.get<UserData>('/auth/me');
  return response.data;
}

export async function updateProfile(firstName: string, lastName: string): Promise<UserData> {
  const response = await api.put<UserData>('/auth/profile', {
    first_name: firstName,
    last_name: lastName,
  });
  return response.data;
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await api.post('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function requestAccountDeletion(password: string): Promise<void> {
  await api.post('/auth/delete-account/request', { password });
}

export async function confirmAccountDeletion(otpCode: string): Promise<void> {
  await api.post('/auth/delete-account/confirm', { otp_code: otpCode });
}

export interface ProcessPDFResponse {
  blob: Blob;
  filename: string;
}

export const processPDFs = async (
  files: File[],
  command: string,
): Promise<ProcessPDFResponse> => {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  formData.append('message', command);

  const response = await api.post('/pdf/process', formData, {
    responseType: 'blob',
    timeout: PDF_PROCESSING_TIMEOUT_MS,
  });

  // Extract filename from Content-Disposition header if present
  let filename = 'result_document.pdf';
  const disposition: string | undefined = response.headers['content-disposition'];
  if (disposition) {
    const match = /filename\*?=(?:UTF-8'')?["']?([^"';\n]+)["']?/i.exec(disposition);
    if (match?.[1]) {
      filename = decodeURIComponent(match[1].trim());
    }
  }

  return { blob: response.data, filename };
};
