import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SessionSettings from './SessionSettings';
import * as api from '../../services/api';
import type { SessionRecord } from '../../services/api';

vi.mock('../../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/api')>()),
  fetchSessions: vi.fn(),
  terminateSession: vi.fn(),
  logoutAllOtherSessions: vi.fn(),
}));

function session(overrides: Partial<SessionRecord>): SessionRecord {
  return {
    id: 1,
    ip_address: '203.0.113.5',
    device_name: 'Windows 11',
    browser: 'Chrome 140',
    os: 'Windows 11',
    is_mobile: false,
    created_at: '2026-10-20T10:00:00',
    last_used_at: '2026-10-25T09:00:00Z',
    is_current: false,
    ...overrides,
  };
}

const CURRENT = session({ id: 1, is_current: true });
const PHONE = session({ id: 2, device_name: 'iPhone', browser: 'Mobile Safari 17', os: 'iOS 17', is_mobile: true });

beforeEach(() => {
  vi.mocked(api.terminateSession).mockResolvedValue();
  vi.mocked(api.logoutAllOtherSessions).mockResolvedValue();
});

describe('SessionSettings', () => {
  it('lists every session and marks this device', async () => {
    vi.mocked(api.fetchSessions).mockResolvedValue([CURRENT, PHONE]);
    render(<SessionSettings />);

    const items = await screen.findAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText('This device')).toBeInTheDocument();
    expect(within(items[1]).getByText(/Mobile Safari 17 on iOS 17 · 203\.0\.113\.5/)).toBeInTheDocument();
    // The current session cannot sign itself out from here.
    expect(within(items[0]).queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  });

  it('signs out one other device and removes it from the list', async () => {
    vi.mocked(api.fetchSessions).mockResolvedValue([CURRENT, PHONE]);
    const user = userEvent.setup();
    render(<SessionSettings />);

    await user.click(await screen.findByRole('button', { name: 'Sign out' }));

    expect(api.terminateSession).toHaveBeenCalledWith(2);
    expect(await screen.findByText('That device has been signed out.')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
  });

  it('asks before signing out every other device', async () => {
    vi.mocked(api.fetchSessions)
      .mockResolvedValueOnce([CURRENT, PHONE])
      .mockResolvedValueOnce([CURRENT]);
    const user = userEvent.setup();
    render(<SessionSettings />);

    await user.click(await screen.findByRole('button', { name: 'Sign out all other devices' }));
    const dialog = screen.getByRole('dialog');
    expect(api.logoutAllOtherSessions).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole('button', { name: 'Sign out' }));

    expect(api.logoutAllOtherSessions).toHaveBeenCalled();
    expect(await screen.findByText('All other devices have been signed out.')).toBeInTheDocument();
    // The page is aria-hidden until the dialog finishes closing.
    await waitFor(() => expect(screen.getAllByRole('listitem')).toHaveLength(1));
  });

  it('disables the bulk sign-out when this is the only session', async () => {
    vi.mocked(api.fetchSessions).mockResolvedValue([CURRENT]);
    render(<SessionSettings />);
    expect(await screen.findByRole('button', { name: 'Sign out all other devices' })).toBeDisabled();
  });

  it('shows an error if the sessions cannot be loaded', async () => {
    vi.mocked(api.fetchSessions).mockRejectedValue(new Error('down'));
    render(<SessionSettings />);
    expect(await screen.findByText('Could not load your sessions.')).toBeInTheDocument();
  });

  it('keeps the row and explains when signing out fails', async () => {
    vi.mocked(api.fetchSessions).mockResolvedValue([CURRENT, PHONE]);
    vi.mocked(api.terminateSession).mockRejectedValue(new Error('down'));
    const user = userEvent.setup();
    render(<SessionSettings />);

    await user.click(await screen.findByRole('button', { name: 'Sign out' }));
    expect(await screen.findByText('Could not sign out that device.')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });
});
