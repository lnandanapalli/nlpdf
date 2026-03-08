import { useState } from 'react';
import axios from 'axios';
import { Container, Typography, Box, Alert, Slide } from '@mui/material';
import DragDropZone from './DragDropZone';
import CommandInput from './CommandInput';
import ProcessingState from './ProcessingState';
import ResultCard from './ResultCard';
import { processPDFs } from '../services/api';

type AppState = 'IDLE' | 'PROCESSING' | 'SUCCESS' | 'ERROR';

export default function HomePage() {
  const [appState, setAppState] = useState<AppState>('IDLE');
  const [files, setFiles] = useState<File[]>([]);
  const [resultBlob, setResultBlob] = useState<Blob | null>(null);
  const [resultFilename, setResultFilename] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');

  const handleReset = () => {
    setAppState('IDLE');
    setFiles([]);
    setResultBlob(null);
    setResultFilename('');
    setErrorMessage('');
  };

  const handleProcess = async (command: string) => {
    if (files.length === 0) return;
    setAppState('PROCESSING');
    setErrorMessage('');

    try {
      const { blob, filename } = await processPDFs(files, command);
      setResultBlob(blob);
      setResultFilename(filename);
      setAppState('SUCCESS');
    } catch (error: unknown) {
      setAppState('ERROR');
      let detail: string | null = null;

      if (axios.isAxiosError(error) && error.response?.data) {
        const data = error.response.data;
        if (data instanceof Blob) {
          try {
            const json = JSON.parse(await data.text());
            detail = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
          } catch {
            // ignore parse errors
          }
        } else if (typeof data.detail === 'string') {
          detail = data.detail;
        }
      }

      setErrorMessage(detail ?? 'An unexpected error occurred while communicating with the server.');
    }
  };

  return (
    <>
      {/* Main content */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', py: { xs: 2, md: 3 }, px: { xs: 2, md: 0 } }}>
        <Container maxWidth="md" sx={{ display: 'flex', flexDirection: 'column', gap: 3, flex: 1 }}>

          {appState === 'IDLE' && files.length === 0 && (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" color="text.primary" sx={{ mb: 1 }}>
                What can I help you process?
              </Typography>
              <Typography variant="h6" color="text.secondary" sx={{ maxWidth: 600, mx: 'auto' }}>
                Upload your PDFs and use natural language to compress, merge, split, or rotate them instantly.
              </Typography>
            </Box>
          )}

          {appState === 'ERROR' && (
            <Slide direction="down" in>
              <Alert severity="error" sx={{ borderRadius: 2 }} onClose={() => setAppState('IDLE')}>
                {errorMessage}
              </Alert>
            </Slide>
          )}

          {(appState === 'IDLE' || appState === 'ERROR') && (
            <Slide direction="up" in>
              <Box>
                <DragDropZone
                  files={files}
                  onFilesAdded={(newFiles) => setFiles((prev) => [...prev, ...newFiles])}
                  onFileRemoved={(fileToRemove) => setFiles((prev) => prev.filter((f) => f !== fileToRemove))}
                />
              </Box>
            </Slide>
          )}

          <ProcessingState isVisible={appState === 'PROCESSING'} />

          {appState === 'SUCCESS' && (
            <ResultCard blob={resultBlob} filename={resultFilename} onReset={handleReset} />
          )}

        </Container>
      </Box>

      {/* Command input */}
      <Box
        sx={{
          flexShrink: 0,
          pb: 3,
          pt: 2,
          px: { xs: 2, md: 0 },
          backgroundImage: (t) => `linear-gradient(to top, ${t.palette.background.default} 85%, transparent)`,
        }}
      >
        <Container maxWidth="md">
          <CommandInput
            onProcess={handleProcess}
            disabled={appState === 'PROCESSING'}
            hasFiles={files.length > 0}
          />
        </Container>
      </Box>
    </>
  );
}
