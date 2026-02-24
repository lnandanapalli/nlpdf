import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { 
  Container, Typography, Box, Alert, Slide, 
  AppBar, Toolbar, Button as MuiButton 
} from '@mui/material';
import { Sparkles, Github } from 'lucide-react';
import DragDropZone from './components/DragDropZone';
import CommandInput from './components/CommandInput';
import ProcessingState from './components/ProcessingState';
import ResultCard from './components/ResultCard';
import { processPDFs } from './services/api';

type AppState = 'IDLE' | 'PROCESSING' | 'SUCCESS' | 'ERROR';

function App() {
  const [appState, setAppState] = useState<AppState>('IDLE');
  const [files, setFiles] = useState<File[]>([]);
  const [resultBlob, setResultBlob] = useState<Blob | null>(null);
  const [resultFilename, setResultFilename] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of content area when state changes
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [appState, resultBlob]);

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
      if (axios.isAxiosError(error) && error.response?.data?.detail) {
        setErrorMessage(
          typeof error.response.data.detail === 'string' 
            ? error.response.data.detail 
            : JSON.stringify(error.response.data.detail)
        );
      } else {
        setErrorMessage('An unexpected error occurred while communicating with the server.');
      }
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', bgcolor: 'background.default', overflow: 'hidden' }}>
      {/* Header */}
      <AppBar position="static" elevation={0} sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.default' }}>
        <Toolbar sx={{ justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Sparkles color="#8ab4f8" size={24} style={{ marginRight: '12px' }} />
            <Typography variant="h6" color="primary.main" sx={{ fontWeight: 600, letterSpacing: 0.5 }}>
              NLPDF
            </Typography>
          </Box>
          <MuiButton 
            startIcon={<Github size={18} />} 
            sx={{ color: 'text.secondary', '&:hover': { color: 'text.primary' } }}
            href="https://github.com"
            target="_blank"
          >
            Source
          </MuiButton>
        </Toolbar>
      </AppBar>

      {/* Scrollable Content Area */}
      <Box 
        ref={scrollRef}
        sx={{ 
          flexGrow: 1, 
          overflowY: 'auto', 
          display: 'flex', 
          flexDirection: 'column', 
          py: { xs: 4, md: 6 }, 
          px: { xs: 2, md: 0 } 
        }}
      >
        <Container maxWidth="md" sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {appState === 'IDLE' && files.length === 0 && (
            <Box sx={{ textAlign: 'center', mb: 2, mt: 4 }}>
              <Typography variant="h3" color="text.primary" sx={{ mb: 2 }}>
                What can I help you process?
              </Typography>
              <Typography variant="h6" color="text.secondary" sx={{ maxWidth: 600, mx: 'auto' }}>
                Upload your PDFs and use natural language to compress, merge, split, or rotate them instantly.
              </Typography>
            </Box>
          )}

          {appState === 'ERROR' && (
            <Slide direction="down" in={appState === 'ERROR'}>
              <Alert severity="error" sx={{ borderRadius: 2 }} onClose={() => setAppState('IDLE')}>
                {errorMessage}
              </Alert>
            </Slide>
          )}

          {(appState === 'IDLE' || appState === 'ERROR') && (
            <Slide direction="up" in={true}>
              <Box>
                <DragDropZone 
                  files={files}
                  onFilesAdded={(newFiles) => setFiles((prev) => [...prev, ...newFiles])}
                  onFileRemoved={(fileToRemove) => setFiles((prev) => prev.filter(f => f !== fileToRemove))}
                />
              </Box>
            </Slide>
          )}

          <ProcessingState isVisible={appState === 'PROCESSING'} />
          
          {appState === 'SUCCESS' && (
            <ResultCard 
              blob={resultBlob} 
              filename={resultFilename} 
              onReset={handleReset} 
            />
          )}

          {/* Spacer to ensure scrolling can go past the last item comfortably */}
          <Box sx={{ height: 40 }} />
        </Container>
      </Box>

      {/* Pinned Input Area at the Bottom */}
      <Box sx={{ 
        flexShrink: 0, 
        bgcolor: 'transparent',
        backgroundImage: 'linear-gradient(to top, #202124 85%, transparent)',
        pb: 4,
        pt: 3,
        px: { xs: 2, md: 0 }
      }}>
        <Container maxWidth="md">
          <CommandInput 
            onProcess={handleProcess}
            disabled={files.length === 0 || appState === 'PROCESSING'}
          />
        </Container>
      </Box>
    </Box>
  );
}

export default App;
