import axios from 'axios';
import { config } from '../config';

export const API_BASE_URL = config.apiBaseUrl;

const PDF_PROCESSING_TIMEOUT_MS = 3 * 60 * 1000; // 3 minutes

export interface ProcessPDFResponse {
  blob: Blob;
  filename: string;
}

export const processPDFs = async (
  files: File[],
  command: string,
  token: string,
): Promise<ProcessPDFResponse> => {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  formData.append('message', command);

  const response = await axios.post(`${API_BASE_URL}/pdf/process`, formData, {
    headers: { Authorization: `Bearer ${token}` },
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
