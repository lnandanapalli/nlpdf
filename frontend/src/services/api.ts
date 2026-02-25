import axios from 'axios';

// Ensure the local dev server is pointing to the FastAPI backend
const API_BASE_URL = 'http://127.0.0.1:8000';

export interface ProcessPDFResponse {
  blob: Blob;
  filename: string;
}

export const processPDFs = async (files: File[], command: string, token: string | null = null): Promise<ProcessPDFResponse> => {
  const formData = new FormData();
  
  // Attach all files
  files.forEach((file) => {
    formData.append('files', file);
  });
  
  // Attach the natural language instruction
  formData.append('message', command);

  const headers: Record<string, string> = {
    'Content-Type': 'multipart/form-data',
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await axios.post(`${API_BASE_URL}/pdf/process`, formData, {
    headers,
    // We expect a binary blob in return (PDF or ZIP)
    responseType: 'blob',
    // 3 minute timeout for potentially long LLM processing / huge PDFs
    timeout: 180000, 
  });

  // Extract filename from the Content-Disposition header if available
  let filename = 'result_document.pdf';
  const disposition = response.headers['content-disposition'];
  if (disposition && disposition.indexOf('attachment') !== -1) {
    const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
    const matches = filenameRegex.exec(disposition);
    if (matches != null && matches[1]) { 
      filename = matches[1].replace(/['"]/g, '');
    }
  }

  return {
    blob: response.data,
    filename,
  };
};
