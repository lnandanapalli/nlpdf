import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AuthScreen from './AuthScreen';
import * as api from '../services/api';

vi.mock('@marsidev/react-turnstile', () => import('../test/turnstileMock'));
vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/api')>()),
  login: vi.fn(),
  signup: vi.fn(),
  verifyOtp: vi.fn(),
  resendOtp: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
}));

const EMAIL = 'ada@example.com';
const PASSWORD = 'correct-horse-1';

function httpError(status: number, detail: unknown) {
  const config = { headers: {} } as InternalAxiosRequestConfig;
  return new AxiosError('fail', AxiosError.ERR_BAD_REQUEST, config, {}, {
    data: { detail }, status, statusText: '', headers: {}, config,
  } as AxiosResponse);
}

function renderScreen() {
  const onLogin = vi.fn();
  render(<MemoryRouter><AuthScreen onLogin={onLogin} /></MemoryRouter>);
  return { onLogin, user: userEvent.setup() };
}

async function fillLogin(user: ReturnType<typeof userEvent.setup>, password = PASSWORD) {
  await user.type(screen.getByLabelText('Email'), EMAIL);
  await user.type(screen.getByLabelText('Password'), password);
  await user.click(screen.getByRole('button', { name: 'Sign In' }));
}

async function openSignup(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Sign up' }));
  await user.type(screen.getByLabelText('First'), 'Ada');
  await user.type(screen.getByLabelText('Last'), 'Lovelace');
  await user.type(screen.getByLabelText('Email'), EMAIL);
}

beforeEach(() => {
  vi.mocked(api.login).mockResolvedValue();
  vi.mocked(api.signup).mockResolvedValue();
  vi.mocked(api.verifyOtp).mockResolvedValue();
  vi.mocked(api.resendOtp).mockResolvedValue();
});

describe('sign up', () => {
  it('rejects a short password before calling the API', async () => {
    const { user } = renderScreen();
    await openSignup(user);
    await user.type(screen.getByLabelText('Password'), 'short');
    await user.type(screen.getByLabelText('Confirm Password'), 'short');
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: 'Sign Up' }));

    expect(screen.getByText('Password must be at least 8 characters.')).toBeInTheDocument();
    expect(api.signup).not.toHaveBeenCalled();
  });

  it('verifies the code with the password typed at sign-up', async () => {
    const { user, onLogin } = renderScreen();
    await openSignup(user);
    await user.type(screen.getByLabelText('Password'), PASSWORD);
    await user.type(screen.getByLabelText('Confirm Password'), PASSWORD);
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: 'Sign Up' }));

    expect(api.signup).toHaveBeenCalledWith(EMAIL, PASSWORD, 'Ada', 'Lovelace', 'test-turnstile-token');
    await user.type(await screen.findByLabelText('6-digit Verification Code'), '123456');
    await user.click(screen.getByRole('button', { name: 'Verify Email' }));

    expect(api.verifyOtp).toHaveBeenCalledWith(EMAIL, '123456', PASSWORD, 'test-turnstile-token');
    expect(onLogin).toHaveBeenCalled();
  });

  it('shows server validation errors as sentences', async () => {
    vi.mocked(api.signup).mockRejectedValue(httpError(422, [
      { type: 'value_error', loc: ['body', 'email'], msg: 'value is not a valid email address' },
    ]));
    const { user } = renderScreen();
    await openSignup(user);
    await user.type(screen.getByLabelText('Password'), PASSWORD);
    await user.type(screen.getByLabelText('Confirm Password'), PASSWORD);
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: 'Sign Up' }));

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
  });
});

describe('log in', () => {
  it('signs in on success', async () => {
    const { user, onLogin } = renderScreen();
    await fillLogin(user);
    expect(api.login).toHaveBeenCalledWith(EMAIL, PASSWORD, 'test-turnstile-token');
    expect(onLogin).toHaveBeenCalled();
  });

  it("shows the server's message for a failed login", async () => {
    vi.mocked(api.login).mockRejectedValue(httpError(401, 'Invalid email or password.'));
    const { user, onLogin } = renderScreen();
    await fillLogin(user, 'wrong-password');

    expect(await screen.findByText('Invalid email or password.')).toBeInTheDocument();
    expect(onLogin).not.toHaveBeenCalled();
  });

  it('offers verification to an unverified account and uses the login password', async () => {
    vi.mocked(api.login).mockRejectedValue(httpError(403, 'Unverified email. Please verify your account.'));
    const { user, onLogin } = renderScreen();
    await fillLogin(user);

    expect(await screen.findByText(/isn't verified yet/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Send code' }));
    expect(api.resendOtp).toHaveBeenCalledWith(EMAIL);

    await user.type(await screen.findByLabelText('6-digit Verification Code'), '654321');
    await user.click(screen.getByRole('button', { name: 'Verify Email' }));
    expect(api.verifyOtp).toHaveBeenCalledWith(EMAIL, '654321', PASSWORD, 'test-turnstile-token');
    expect(onLogin).toHaveBeenCalled();
  });

  it('treats a CAPTCHA 403 as an ordinary error, not as unverified', async () => {
    vi.mocked(api.login).mockRejectedValue(httpError(403, 'CAPTCHA verification failed'));
    const { user } = renderScreen();
    await fillLogin(user);

    expect(await screen.findByText('CAPTCHA verification failed')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Send code' })).not.toBeInTheDocument();
  });

  it('asks for every field before calling the API', async () => {
    const { user } = renderScreen();
    await user.click(screen.getByRole('button', { name: 'Sign In' }));
    expect(screen.getByText('Please fill in all fields')).toBeInTheDocument();
    expect(api.login).not.toHaveBeenCalled();
  });
});
