import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

type Handler = (config: InternalAxiosRequestConfig) => Promise<AxiosResponse>;

let handler: Handler;
const calls: { method?: string; url?: string; headers: Record<string, unknown> }[] = [];
let api: typeof import('./api');

function respond(config: InternalAxiosRequestConfig, status: number, data: unknown = {}, headers: Record<string, string> = {}) {
  const response = { data, status, statusText: '', headers, config, request: {} } as AxiosResponse;
  if (status >= 200 && status < 300) return Promise.resolve(response);
  return Promise.reject(new AxiosError(`HTTP ${status}`, AxiosError.ERR_BAD_REQUEST, config, {}, response));
}

function routes(table: Record<string, (config: InternalAxiosRequestConfig) => Promise<AxiosResponse>>): Handler {
  return (config) => {
    const route = table[`${config.method?.toUpperCase()} ${config.url}`];
    if (!route) throw new Error(`Unexpected request ${config.method} ${config.url}`);
    return route(config);
  };
}

function axiosErrorWith(status: number, data: unknown): AxiosError {
  const config = { headers: {} } as InternalAxiosRequestConfig;
  return new AxiosError('fail', AxiosError.ERR_BAD_REQUEST, config, {}, {
    data, status, statusText: '', headers: {}, config,
  } as AxiosResponse);
}

beforeAll(async () => {
  // axios.create copies the defaults, so the adapter has to be in place
  // before the api module builds its instance.
  axios.defaults.adapter = (config) => {
    calls.push({ method: config.method, url: config.url, headers: { ...config.headers } });
    return handler(config);
  };
  api = await import('./api');
});

afterEach(() => {
  calls.length = 0;
});

function urls() {
  return calls.map((c) => `${c.method?.toUpperCase()} ${c.url}`);
}

describe('token refresh interceptor', () => {
  it('refreshes once and retries when a protected call gets a 401', async () => {
    let meCalls = 0;
    handler = routes({
      'GET /auth/me': (c) => (meCalls++ === 0 ? respond(c, 401) : respond(c, 200, { id: 1 })),
      'POST /auth/refresh': (c) => respond(c, 200),
    });

    await expect(api.fetchCurrentUser()).resolves.toEqual({ id: 1 });
    expect(urls()).toEqual(['GET /auth/me', 'POST /auth/refresh', 'GET /auth/me']);
  });

  it.each(['/auth/login', '/auth/verify_otp', '/auth/reset-password'])(
    'does not refresh or expire the session when %s rejects credentials',
    async (url) => {
      const expired = vi.fn();
      window.addEventListener('session-expired', expired);
      handler = routes({ [`POST ${url}`]: (c) => respond(c, 401, { detail: 'nope' }) });

      const call = url === '/auth/login'
        ? api.login('a@b.co', 'pw', 't')
        : url === '/auth/verify_otp'
          ? api.verifyOtp('a@b.co', '123456', 'pw', 't')
          : api.resetPassword('a@b.co', '123456', 'pw', 't');
      await expect(call).rejects.toBeInstanceOf(AxiosError);

      expect(urls()).toEqual([`POST ${url}`]);
      expect(expired).not.toHaveBeenCalled();
      window.removeEventListener('session-expired', expired);
    },
  );

  it('announces an expired session when the refresh itself fails', async () => {
    const expired = vi.fn();
    window.addEventListener('session-expired', expired);
    handler = routes({
      'GET /auth/me': (c) => respond(c, 401),
      'POST /auth/refresh': (c) => respond(c, 401),
    });

    await expect(api.validateSession()).resolves.toBe(false);
    expect(expired).toHaveBeenCalled();
    window.removeEventListener('session-expired', expired);
  });

  it('shares one refresh between requests that fail together', async () => {
    let resolveRefresh!: () => void;
    const seen = new Set<string>();
    handler = routes({
      'GET /auth/me': (c) => (seen.has('me') ? respond(c, 200, { id: 1 }) : (seen.add('me'), respond(c, 401))),
      'GET /documents': (c) => (seen.has('docs') ? respond(c, 200, { items: [] }) : (seen.add('docs'), respond(c, 401))),
      'POST /auth/refresh': (c) => new Promise((resolve) => { resolveRefresh = () => resolve(respond(c, 200)); }),
    });

    const both = Promise.all([api.fetchCurrentUser(), api.fetchDocuments()]);
    await vi.waitFor(() => expect(resolveRefresh).toBeTypeOf('function'));
    resolveRefresh();
    await both;

    expect(urls().filter((u) => u === 'POST /auth/refresh')).toHaveLength(1);
  });
});

describe('CSRF header', () => {
  it('copies the csrf cookie into X-CSRF-Token on mutating requests only', async () => {
    document.cookie = 'csrf_token=abc123; path=/';
    handler = routes({
      'PUT /auth/profile': (c) => respond(c, 200, {}),
      'GET /auth/me': (c) => respond(c, 200, {}),
    });

    await api.updateProfile('A', 'B');
    await api.fetchCurrentUser();

    expect(calls[0].headers['X-CSRF-Token']).toBe('abc123');
    expect(calls[1].headers['X-CSRF-Token']).toBeUndefined();
  });
});

describe('verifyOtp', () => {
  it('sends the password along with the code', async () => {
    let body: unknown;
    handler = routes({
      'POST /auth/verify_otp': (c) => {
        body = JSON.parse(c.data as string);
        return respond(c, 200);
      },
    });

    await api.verifyOtp('a@b.co', '123456', 'secret-pw', 'tok');
    expect(body).toEqual({ email: 'a@b.co', otp_code: '123456', password: 'secret-pw', cf_token: 'tok' });
  });
});

describe('processPDFs', () => {
  it.each([
    ['attachment; filename="compress_report.pdf"', 'compress_report.pdf'],
    ["attachment; filename*=UTF-8''split_r%C3%A9sum%C3%A9.zip", 'split_résumé.zip'],
  ])('reads the filename from %s', async (disposition, expected) => {
    handler = routes({
      'POST /pdf/process': (c) => respond(c, 200, new Blob(['%PDF']), { 'content-disposition': disposition }),
    });
    const file = new File(['%PDF'], 'report.pdf', { type: 'application/pdf' });
    const result = await api.processPDFs([file], 'compress');
    expect(result.filename).toBe(expected);
  });

  it('falls back to a default name without a header', async () => {
    handler = routes({ 'POST /pdf/process': (c) => respond(c, 200, new Blob(['%PDF'])) });
    const result = await api.processPDFs([new File(['x'], 'a.pdf')], 'compress');
    expect(result.filename).toBe('result_document.pdf');
  });
});

describe('formatErrorDetail', () => {
  const issue = (type: string, field: string, msg = '') => ({ type, loc: ['body', field], msg });

  it('passes backend sentences through', () => {
    expect(api.formatErrorDetail('Merge needs at least two files.', 'x')).toBe('Merge needs at least two files.');
  });

  it.each([
    [issue('missing', 'email'), 'Email is required.'],
    [issue('string_too_short', 'password', 'String should have at least 8 characters'), 'Password must be at least 8 characters.'],
    [issue('string_too_long', 'first_name', 'String should have at most 50 characters'), 'First name must be at most 50 characters.'],
    [issue('string_pattern_mismatch', 'otp_code', "String should match pattern '^\\d{6}$'"), 'The code must be 6 digits.'],
    [issue('value_error', 'email', 'value is not a valid email address: bad'), 'Enter a valid email address.'],
    [issue('weird_type', 'secret_internal_field'), 'A field is invalid.'],
  ])('turns %o into a sentence', (detail, expected) => {
    expect(api.formatErrorDetail([detail], 'fallback')).toBe(expected);
  });

  it('joins several problems and drops duplicates', () => {
    const detail = [issue('missing', 'email'), issue('missing', 'email'), issue('missing', 'password')];
    expect(api.formatErrorDetail(detail, 'x')).toBe('Email is required. Password is required.');
  });

  it('never echoes submitted values, even if a server sent them', () => {
    const leaky = [{ ...issue('string_too_short', 'password', 'too short'), input: 'hunter2' }];
    expect(api.formatErrorDetail(leaky, 'x')).not.toContain('hunter2');
  });

  it.each([undefined, null, '', [], { odd: true }])('uses the fallback for %o', (detail) => {
    expect(api.formatErrorDetail(detail, 'fallback')).toBe('fallback');
  });
});

describe('extractErrorMessage', () => {
  it('uses the fallback for non-HTTP errors', () => {
    expect(api.extractErrorMessage(new Error('boom'), 'fallback')).toBe('fallback');
  });

  it('says the server is unreachable when there is no response', () => {
    const err = new AxiosError('Network Error', AxiosError.ERR_NETWORK, { headers: {} } as InternalAxiosRequestConfig);
    expect(api.extractErrorMessage(err, 'fallback')).toMatch(/Can't reach the server/);
  });

  it('formats the response detail', () => {
    expect(api.extractErrorMessage(axiosErrorWith(400, { detail: 'Bad thing' }), 'x')).toBe('Bad thing');
  });
});

describe('isUnverifiedEmailError', () => {
  it('recognises the unverified-email 403', () => {
    const err = axiosErrorWith(403, { detail: 'Unverified email. Please verify your account.' });
    expect(api.isUnverifiedEmailError(err)).toBe(true);
  });

  it.each([
    [403, 'CAPTCHA verification failed'],
    [401, 'Unverified email'],
  ])('ignores %i "%s"', (status, detail) => {
    expect(api.isUnverifiedEmailError(axiosErrorWith(status, { detail }))).toBe(false);
  });
});
