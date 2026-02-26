import { useCallback } from 'react';
import { Box, Button, Fade, Alert, AlertTitle } from '@mui/material';
import { Download, RefreshCcw, CheckCircle2 } from 'lucide-react';

interface ResultCardProps {
  blob: Blob | null;
  filename: string;
  onReset: () => void;
}

export default function ResultCard({ blob, filename, onReset }: ResultCardProps) {
  // Must be declared before any early returns to comply with Rules of Hooks
  const handleDownload = useCallback(() => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || 'nlpdf_output.pdf';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 100);
  }, [blob, filename]);

  if (!blob) return null;

  return (
    <Fade in={!!blob} timeout={800}>
      <Box sx={{ width: '100%' }}>
        <Alert
          icon={<CheckCircle2 size={22} />}
          severity="success"
          sx={{ mb: 3, borderRadius: 2, alignItems: 'center' }}
        >
          <AlertTitle sx={{ mb: 0.5 }}>Processing Complete!</AlertTitle>
          Your requested operation was executed successfully.
        </Alert>

        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
          <Button
            variant="contained"
            color="primary"
            size="large"
            startIcon={<Download />}
            onClick={handleDownload}
            disableElevation
          >
            Download Result
          </Button>

          <Button
            variant="text"
            color="inherit"
            startIcon={<RefreshCcw size={16} />}
            onClick={onReset}
            sx={{ color: 'text.secondary' }}
          >
            Process another document
          </Button>
        </Box>
      </Box>
    </Fade>
  );
}
