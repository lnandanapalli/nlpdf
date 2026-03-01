import axios from 'axios';
import { config } from '../config';

export const API_BASE_URL = config.apiBaseUrl;

const PDF_PROCESSING_TIMEOUT_MS = 3 * 60 * 1000; // 3 minutes

// Shared axios instance with silent refresh interceptor
const api = axios.create({ baseURL: API_BASE_URL });

let isRefreshing = false;
let pendingRequests: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

function onRefreshed(token: string) {
  pendingRequests.forEach((p) => p.resolve(token));
  pendingRequests = [];
}

function onRefreshFailed(err: unknown) {
  pendingRequests.forEach((p) => p.reject(err));
  pendingRequests = [];
}

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('token');
  if (token && cfg.headers) {
    cfg.headers.Authorization = `Bearer ${token}`;
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
          resolve: (token: string) => {
            original.headers.Authorization = `Bearer ${token}`;
            resolve(api(original));
          },
          reject,
        });
      });
    }

    isRefreshing = true;
    const refreshToken = localStorage.getItem('refreshToken');

    if (!refreshToken) {
      isRefreshing = false;
      dispatchSessionExpired();
      return Promise.reject(error);
    }

    try {
      const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
        refresh_token: refreshToken,
      });

      localStorage.setItem('token', data.access_token);
      localStorage.setItem('refreshToken', data.refresh_token);

      isRefreshing = false;
      onRefreshed(data.access_token);

      original.headers.Authorization = `Bearer ${data.access_token}`;
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
  localStorage.removeItem('token');
  localStorage.removeItem('refreshToken');
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
