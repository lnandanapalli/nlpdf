import { readFile } from 'node:fs/promises';
import type { Download } from '@playwright/test';
import { PDFDocument, StandardFonts } from 'pdf-lib';

export interface UploadFile {
  name: string;
  mimeType: string;
  buffer: Buffer;
}

/** A real PDF with `pages` pages, each labelled with its number. */
export async function makePdf(name: string, pages: number): Promise<UploadFile> {
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  for (let i = 1; i <= pages; i += 1) {
    const page = doc.addPage([612, 792]);
    page.drawText(`${name} page ${i}`, { x: 72, y: 700, size: 24, font });
  }
  return { name, mimeType: 'application/pdf', buffer: Buffer.from(await doc.save()) };
}

export function makeMarkdown(name: string, body: string): UploadFile {
  return { name, mimeType: 'text/markdown', buffer: Buffer.from(body, 'utf-8') };
}

/** Bytes that claim to be a PDF by name only. */
export function makeFakePdf(name: string): UploadFile {
  return { name, mimeType: 'application/pdf', buffer: Buffer.from('this is not a pdf at all') };
}

export async function downloadBytes(download: Download): Promise<Buffer> {
  const path = await download.path();
  return readFile(path);
}

export interface PdfSummary {
  pageCount: number;
  rotations: number[];
}

export async function inspectPdf(bytes: Buffer): Promise<PdfSummary> {
  expect4Bytes(bytes, '%PDF');
  const doc = await PDFDocument.load(bytes);
  return {
    pageCount: doc.getPageCount(),
    rotations: doc.getPages().map((p) => p.getRotation().angle),
  };
}

export function isZip(bytes: Buffer): boolean {
  return bytes.subarray(0, 2).toString('latin1') === 'PK';
}

function expect4Bytes(bytes: Buffer, magic: string) {
  const head = bytes.subarray(0, magic.length).toString('latin1');
  if (head !== magic) throw new Error(`Expected file to start with ${magic}, got ${JSON.stringify(head)}`);
}

