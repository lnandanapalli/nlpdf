import type { Page } from '@playwright/test';
import {
  downloadBytes, inspectPdf, isZip, makeFakePdf, makeMarkdown, makePdf, type UploadFile,
} from './support/files';
import { expect, test } from './support/fixtures';

async function upload(page: Page, files: UploadFile[]) {
  await page.locator('input[type="file"]').setInputFiles(files);
  for (const file of files) {
    await expect(page.getByText(file.name, { exact: true })).toBeVisible();
  }
}

async function send(page: Page, command: string) {
  await page.getByPlaceholder('Message NLPDF…').fill(command);
  await page.getByRole('button', { name: 'Send command' }).click();
}

/** Run a command and return the downloaded result. */
async function runAndDownload(page: Page, command: string) {
  await send(page, command);
  await expect(page.getByText('Processing Complete!')).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download Result' }).click();
  const download = await downloadPromise;
  return { filename: download.suggestedFilename(), bytes: await downloadBytes(download) };
}

async function expectError(page: Page, text: string | RegExp) {
  await expect(page.getByRole('alert')).toContainText(text);
}

test.describe('Processing PDFs', () => {
  test('compress keeps every page and names the result after the input', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('report.pdf', 3)]);
    const { filename, bytes } = await runAndDownload(page, 'compress this');

    expect(filename).toBe('compress_report.pdf');
    expect((await inspectPdf(bytes)).pageCount).toBe(3);
  });

  test('extract pages returns just that range', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('book.pdf', 5)]);
    const { bytes } = await runAndDownload(page, 'extract pages 2-3');
    expect((await inspectPdf(bytes)).pageCount).toBe(2);
  });

  test('splitting into separate files returns a zip', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('book.pdf', 4)]);
    const { filename, bytes } = await runAndDownload(page, 'split pages 1-2 and 3-4 separately');
    expect(filename).toMatch(/\.zip$/);
    expect(isZip(bytes)).toBe(true);
  });

  test('merge combines the files in upload order', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('a.pdf', 3), await makePdf('b.pdf', 2)]);
    const { bytes } = await runAndDownload(page, 'merge these');
    expect((await inspectPdf(bytes)).pageCount).toBe(5);
  });

  test('merge then rotate rotates the right page of the merged file', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('a.pdf', 1), await makePdf('b.pdf', 2)]);
    const { bytes } = await runAndDownload(page, 'merge these then rotate page 2');
    const pdf = await inspectPdf(bytes);
    expect(pdf.pageCount).toBe(3);
    expect(pdf.rotations).toEqual([0, 90, 0]);
  });

  test('compressing several files returns a zip with one result per file', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('a.pdf', 1), await makePdf('b.pdf', 1)]);
    const { bytes } = await runAndDownload(page, 'compress these');
    expect(isZip(bytes)).toBe(true);
  });

  test('markdown converts to a PDF', async ({ signedIn: { page } }) => {
    await upload(page, [makeMarkdown('notes.md', '# Notes\n\n- one\n- two\n')]);
    const { filename, bytes } = await runAndDownload(page, 'convert to pdf');
    expect(filename).toMatch(/\.pdf$/);
    expect((await inspectPdf(bytes)).pageCount).toBeGreaterThanOrEqual(1);
  });

  test('"process another document" returns to an empty upload area', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('one.pdf', 1)]);
    await send(page, 'compress this');
    await expect(page.getByText('Processing Complete!')).toBeVisible();
    await page.getByRole('button', { name: 'Process another document' }).click();
    await expect(page.getByText('What can I help you process?')).toBeVisible();
    await expect(page.getByText('one.pdf', { exact: true })).toBeHidden();
  });
});

test.describe('Rejected requests explain what went wrong', () => {
  test('rotating several files without merging is refused', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('a.pdf', 2), await makePdf('b.pdf', 2)]);
    await send(page, 'rotate page 1');
    await expectError(page, 'Rotate and split work on one PDF at a time');
  });

  test('a step after splitting into separate files is refused', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('a.pdf', 4)]);
    await send(page, 'split pages 1-2 and 3-4 separately then compress');
    await expectError(page, 'Splitting into separate files has to be the last step.');
  });

  test('pages beyond the end of the document are refused', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('short.pdf', 2)]);
    await send(page, 'extract pages 5-9');
    await expectError(page, 'check that your page numbers and ranges are valid');
  });

  test('an instruction the assistant cannot map is refused', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('a.pdf', 1)]);
    await send(page, 'write me a poem');
    await expectError(page, 'Please describe a valid PDF operation.');
  });

  test('an LLM outage gives a retry message', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('a.pdf', 1)]);
    await send(page, 'simulate llm outage');
    await expectError(page, 'LLM service unavailable. Please try again later.');
  });

  test('a file that only pretends to be a PDF is refused', async ({ signedIn: { page } }) => {
    await upload(page, [makeFakePdf('fake.pdf')]);
    await send(page, 'compress this');
    await expectError(page, "File 'fake.pdf' is not a valid PDF");
  });

  test('mixing PDFs and markdown is refused', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('a.pdf', 1), makeMarkdown('b.md', '# hi')]);
    await send(page, 'compress these');
    await expectError(page, 'Mixed file types are not supported.');
  });

  test('sending a command without files asks for a file first', async ({ signedIn: { page } }) => {
    await send(page, 'compress this');
    await expect(page.getByRole('dialog', { name: 'No files uploaded' })).toBeVisible();
    await page.getByRole('button', { name: 'OK' }).click();
    await expect(page.getByRole('dialog')).toBeHidden();
  });

  test('the error can be dismissed and the files are still there to retry', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('a.pdf', 1)]);
    await send(page, 'write me a poem');
    await expectError(page, 'Please describe a valid PDF operation.');
    await page.getByRole('button', { name: 'Close' }).click();
    await expect(page.getByRole('alert')).toBeHidden();

    const { bytes } = await runAndDownload(page, 'compress this');
    expect((await inspectPdf(bytes)).pageCount).toBe(1);
  });
});

test.describe('Upload area and suggestions', () => {
  test('a file can be removed before processing', async ({ signedIn: { page } }) => {
    await upload(page, [await makePdf('keep.pdf', 1), await makePdf('drop.pdf', 1)]);
    const chip = page.locator('.MuiChip-root', { hasText: 'drop.pdf' });
    await chip.locator('.MuiChip-deleteIcon').click();
    await expect(page.getByText('drop.pdf', { exact: true })).toBeHidden();
    await expect(page.getByText('keep.pdf', { exact: true })).toBeVisible();
  });

  test('picking an example fills in the command box', async ({ signedIn: { page } }) => {
    await page.getByRole('button', { name: 'View all' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Flip page 2 upside down' }).click();
    await expect(page.getByPlaceholder('Message NLPDF…')).toHaveValue('Flip page 2 upside down');
  });
});
