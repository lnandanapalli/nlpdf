import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import CommandInput from './CommandInput';

function setup(props: Partial<Parameters<typeof CommandInput>[0]> = {}) {
  const onProcess = vi.fn();
  render(<CommandInput onProcess={onProcess} hasFiles {...props} />);
  return { onProcess, user: userEvent.setup(), box: screen.getByPlaceholderText('Message NLPDF…') };
}

describe('CommandInput', () => {
  it('submits the trimmed command on Enter', async () => {
    const { onProcess, user, box } = setup();
    await user.type(box, '  compress this  {Enter}');
    expect(onProcess).toHaveBeenCalledWith('compress this');
  });

  it('Shift+Enter adds a new line instead of submitting', async () => {
    const { onProcess, user, box } = setup();
    await user.type(box, 'merge{Shift>}{Enter}{/Shift}then compress');
    expect(onProcess).not.toHaveBeenCalled();
    expect(box).toHaveValue('merge\nthen compress');
  });

  it('does not submit a blank command', async () => {
    const { onProcess, user, box } = setup();
    await user.type(box, '   {Enter}');
    expect(onProcess).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Send command' })).toBeDisabled();
  });

  it('asks for a file when none is uploaded', async () => {
    const { onProcess, user, box } = setup({ hasFiles: false });
    await user.type(box, 'compress{Enter}');
    expect(onProcess).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog', { name: 'No files uploaded' })).toBeInTheDocument();
  });

  it('a suggestion chip fills the box', async () => {
    const { user, box } = setup();
    await user.click(screen.getByRole('button', { name: 'Merge these PDFs' }));
    expect(box).toHaveValue('Merge these PDFs');
  });

  it('is inert while processing', async () => {
    const { onProcess, box } = setup({ disabled: true });
    expect(box).toBeDisabled();
    expect(onProcess).not.toHaveBeenCalled();
  });
});
