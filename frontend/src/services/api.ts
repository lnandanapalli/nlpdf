import axios from 'axios';
import { config } from '../config';

export const API_BASE_URL = config.apiBaseUrl;

const PDF_PROCESSING_TIMEOUT_MS = 3 * 60 * 1000; // 3 minutes

// Shared axios instance with credentials (cookies sent automatically)
const api = axios.create({ baseURL: API_BASE_URL, withCredentials: true });

// Endpoints whose 401 means "wrong credentials or code", not "session expired".
// Refreshing on those would be a wasted request and would wrongly announce an
// expired session on the login screen.
const CREDENTIAL_ENDPOINTS = new Set([
  '/auth/login',
  '/auth/signup',
  '/auth/verify_otp',
  '/auth/resend_otp',
  '/auth/forgot-password',
  '/auth/reset-password',
]);

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

    if (error.response?.status !== 401 || original._retry || CREDENTIAL_ENDPOINTS.has(original.url)) {
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
      await api.post('/auth/refresh', {});

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

// --- Auth API ---

export async function login(email: string, password: string, cfToken: string): Promise<void> {
  await api.post('/auth/login', { email, password, cf_token: cfToken });
}

export async function signup(
  email: string, password: string, firstName: string, lastName: string, cfToken: string,
): Promise<void> {
  await api.post('/auth/signup', {
    email, password, first_name: firstName, last_name: lastName, cf_token: cfToken,
  });
}

// The password is sent again with the code: whoever holds the emailed code
// sets the account's password, so an earlier signup by someone else can't.
export async function verifyOtp(
  email: string, otpCode: string, password: string, cfToken: string,
): Promise<void> {
  await api.post('/auth/verify_otp', {
    email, otp_code: otpCode, password, cf_token: cfToken,
  });
}

// Sent by /auth/login (403) only after the password was checked, so showing it
// reveals nothing to someone who doesn't already know the password.
const UNVERIFIED_EMAIL_DETAIL = 'Unverified email';

export function isUnverifiedEmailError(err: unknown): boolean {
  return (
    axios.isAxiosError(err)
    && err.response?.status === 403
    && typeof err.response.data?.detail === 'string'
    && err.response.data.detail.startsWith(UNVERIFIED_EMAIL_DETAIL)
  );
}

export async function resendOtp(email: string): Promise<void> {
  await api.post('/auth/resend_otp', { email });
}

export async function forgotPassword(email: string, cfToken: string): Promise<void> {
  await api.post('/auth/forgot-password', { email, cf_token: cfToken });
}

export async function resetPassword(
  email: string, otpCode: string, newPassword: string, cfToken: string,
): Promise<void> {
  await api.post('/auth/reset-password', {
    email, otp_code: otpCode, new_password: newPassword, cf_token: cfToken,
  });
}

// --- Error Handling ---

// Request fields the user can see, by the name the API uses for them.
const FIELD_LABELS: Record<string, string> = {
  email: 'Email',
  password: 'Password',
  new_password: 'New password',
  current_password: 'Current password',
  first_name: 'First name',
  last_name: 'Last name',
  otp_code: 'Verification code',
  message: 'Instruction',
  files: 'Files',
};

interface ValidationIssue {
  type?: string;
  loc?: (string | number)[];
  msg?: string;
}

/**
 * Turn one FastAPI 422 entry into a sentence about the field the user typed.
 *
 * Only the field name and the kind of problem are used, never echoed values
 * (the backend strips them), and the result depends only on what this user
 * submitted, so it can't reveal anything about other accounts.
 */
function describeValidationIssue(issue: ValidationIssue): string {
  const field = String(issue.loc?.[issue.loc.length - 1] ?? '');
  const label = FIELD_LABELS[field] ?? 'A field';
  const limit = /(\d+)/.exec(issue.msg ?? '')?.[1];

  switch (issue.type) {
    case 'missing':
      return `${label} is required.`;
    case 'string_too_short':
      return limit ? `${label} must be at least ${limit} characters.` : `${label} is too short.`;
    case 'string_too_long':
      return limit ? `${label} must be at most ${limit} characters.` : `${label} is too long.`;
    case 'string_pattern_mismatch':
      return field === 'otp_code' ? 'The code must be 6 digits.' : `${label} is not in the right format.`;
    case 'value_error':
      return field === 'email' ? 'Enter a valid email address.' : `${label} is invalid.`;
    default:
      return `${label} is invalid.`;
  }
}

/**
 * Turn an API error `detail` into text for the user.
 *
 * String details are written by the backend for users (and kept generic
 * wherever detail could leak account state); list details are 422 field
 * validation errors and are rewritten into plain sentences.
 */
export function formatErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = [...new Set(detail.map((d) => describeValidationIssue(d as ValidationIssue)))];
    return messages.join(' ');
  }
  return fallback;
}

export function extractErrorMessage(err: unknown, fallback: string): string {
  if (!axios.isAxiosError(err)) return fallback;
  if (!err.response) {
    return "Can't reach the server. Check your connection and try again.";
  }
  return formatErrorDetail(err.response.data?.detail, fallback);
}

// --- PDF Processing ---

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

// ---------- Sessions ----------

export interface SessionRecord {
  id: number;
  ip_address: string | null;
  device_name: string | null;
  browser: string | null;
  os: string | null;
  is_mobile: boolean;
  created_at: string | null;
  last_used_at: string | null;
  is_current: boolean;
}

export async function fetchSessions(): Promise<SessionRecord[]> {
  const res = await api.get<SessionRecord[]>('/auth/sessions');
  return res.data;
}

export async function terminateSession(sessionId: number): Promise<void> {
  await api.delete(`/auth/sessions/${sessionId}`);
}

export async function logoutAllOtherSessions(): Promise<void> {
  await api.post('/auth/sessions/logout-all');
}

// ---------- Document history ----------

export interface DocumentRecord {
  id: number;
  original_filename: string;
  operation_type: string;
  input_size_mb: string | null;
  output_size_mb: string | null;
  page_count: number | null;
  created_at: string | null;
}

export interface DocumentPage {
  items: DocumentRecord[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchDocuments(limit = 20, offset = 0): Promise<DocumentPage> {
  const res = await api.get<DocumentPage>('/documents', { params: { limit, offset } });
  return res.data;
}

export async function deleteDocument(documentId: number): Promise<void> {
  await api.delete(`/documents/${documentId}`);
}

export async function clearDocuments(): Promise<number> {
  const res = await api.delete<{ message: string; deleted: number }>('/documents');
  return res.data.deleted;
}
