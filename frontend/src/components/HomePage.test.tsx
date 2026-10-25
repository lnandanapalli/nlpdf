import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HomePage from './HomePage';
import * as api from '../services/api';

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/api')>()),
  processPDFs: vi.fn(),
}));

const pdf = () => new File(['%PDF-1.7'], 'report.pdf', { type: 'application/pdf' });

/** The PDF endpoint is called with responseType "blob", so errors arrive as blobs. */
function blobError(status: number, detail: unknown) {
  const config = { headers: {} } as InternalAxiosRequestConfig;
  const data = new Blob([JSON.stringify({ detail })], { type: 'application/json' });
  return new AxiosError('fail', AxiosError.ERR_BAD_REQUEST, config, {}, {
    data, status, statusText: '', headers: {}, config,
  } as AxiosResponse);
}

async function uploadAndSend(command = 'compress this') {
  const user = userEvent.setup();
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await user.upload(input, pdf());
  await user.type(screen.getByPlaceholderText('Message NLPDF…'), command);
  await user.click(screen.getByRole('button', { name: 'Send command' }));
  return user;
}

beforeEach(() => {
  vi.mocked(api.processPDFs).mockReset();
});

describe('HomePage', () => {
  it('sends the files and command, then offers the download', async () => {
    vi.mocked(api.processPDFs).mockResolvedValue({ blob: new Blob(['%PDF']), filename: 'compress_report.pdf' });
    render(<HomePage />);
    await uploadAndSend();

    expect(api.processPDFs).toHaveBeenCalledWith([expect.objectContaining({ name: 'report.pdf' })], 'compress this');
    expect(await screen.findByText('Processing Complete!')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download Result' })).toBeInTheDocument();
  });

  it('shows the backend message from a blob error body', async () => {
    vi.mocked(api.processPDFs).mockRejectedValue(blobError(400, 'Rotate and split work on one PDF at a time.'));
    render(<HomePage />);
    await uploadAndSend();
    expect(await screen.findByText('Rotate and split work on one PDF at a time.')).toBeInTheDocument();
  });

  it('turns a validation list into a sentence instead of raw JSON', async () => {
    vi.mocked(api.processPDFs).mockRejectedValue(
      blobError(422, [{ type: 'string_too_long', loc: ['body', 'message'], msg: 'String should have at most 2000 characters' }]),
    );
    render(<HomePage />);
    await uploadAndSend();

    expect(await screen.findByText('Instruction must be at most 2000 characters.')).toBeInTheDocument();
    expect(screen.queryByText(/"loc"/)).not.toBeInTheDocument();
  });

  it('says the server is unreachable on a network failure', async () => {
    vi.mocked(api.processPDFs).mockRejectedValue(
      new AxiosError('Network Error', AxiosError.ERR_NETWORK, { headers: {} } as InternalAxiosRequestConfig),
    );
    render(<HomePage />);
    await uploadAndSend();
    expect(await screen.findByText(/Can't reach the server/)).toBeInTheDocument();
  });

  it('keeps the files after an error so the user can retry', async () => {
    vi.mocked(api.processPDFs).mockRejectedValue(blobError(400, 'Nope'));
    render(<HomePage />);
    await uploadAndSend();
    await screen.findByText('Nope');
    expect(screen.getByText('report.pdf')).toBeInTheDocument();
  });
});
