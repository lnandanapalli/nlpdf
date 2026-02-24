import { Box, Button, Fade, Alert, AlertTitle } from '@mui/material';
import { Download, RefreshCcw, CheckCircle2 } from 'lucide-react';

interface ResultCardProps {
  blob: Blob | null;
  filename: string;
  onReset: () => void;
}

export default function ResultCard({ blob, filename, onReset }: ResultCardProps) {
  if (!blob) return null;

  const handleDownload = () => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename || 'nlpdf_output.pdf');
    document.body.appendChild(link);
    link.click();
    if (link.parentNode) {
      link.parentNode.removeChild(link);
    }
  };

  return (
    <Fade in={!!blob} timeout={800}>
      <Box sx={{ py: 4, width: '100%' }}>
        <Alert 
          icon={<CheckCircle2 size={24} />} 
          severity="success"
          sx={{ mb: 4, borderRadius: 2, alignItems: 'center' }}
        >
          <AlertTitle sx={{ fontSize: '1.1rem', mb: 0.5 }}>Processing Complete!</AlertTitle>
          Your requested operation has been executed successfully.
        </Alert>

        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
          <Button
            variant="contained"
            color="primary"
            size="large"
            startIcon={<Download />}
            onClick={handleDownload}
            sx={{ px: 6, py: 1.5, borderRadius: 8, fontSize: '1.1rem' }}
            disableElevation
          >
            Download Result
          </Button>
          
          <Button
            variant="text"
            color="secondary"
            startIcon={<RefreshCcw size={18} />}
            onClick={onReset}
            sx={{ textTransform: 'none' }}
          >
            Process another document
          </Button>
        </Box>
      </Box>
    </Fade>
  );
}
