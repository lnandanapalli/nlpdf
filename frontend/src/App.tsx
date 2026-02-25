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
import AuthScreen from './components/AuthScreen';
import { processPDFs } from './services/api';

const API_BASE_URL = 'http://127.0.0.1:8000';

type AppState = 'IDLE' | 'PROCESSING' | 'SUCCESS' | 'ERROR';

function App() {
  const [appState, setAppState] = useState<AppState>('IDLE');
  const [files, setFiles] = useState<File[]>([]);
  const [resultBlob, setResultBlob] = useState<Blob | null>(null);
  const [resultFilename, setResultFilename] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  
  // Auth state
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState<boolean>(true);

  const scrollRef = useRef<HTMLDivElement>(null);

  // Check token validity on mount
  useEffect(() => {
    const checkAuth = async () => {
      if (!token) {
        setIsCheckingAuth(false);
        return;
      }

      try {
        await axios.get(`${API_BASE_URL}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setIsAuthenticated(true);
      } catch {
        // Token invalid or expired
        localStorage.removeItem('token');
        setToken(null);
        setIsAuthenticated(false);
      } finally {
        setIsCheckingAuth(false);
      }
    };

    checkAuth();
  }, [token]);

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
      const { blob, filename } = await processPDFs(files, command, token);
      setResultBlob(blob);
      setResultFilename(filename);
      setAppState('SUCCESS');
    } catch (error: unknown) {
      setAppState('ERROR');
      
      if (axios.isAxiosError(error) && error.response?.data) {
        let errorDetail = null;
        
        // When responseType is 'blob', axios returns the error JSON as a Blob
        if (error.response.data instanceof Blob) {
          try {
            const text = await error.response.data.text();
            const json = JSON.parse(text);
            errorDetail = json.detail;
          } catch (e) {
            console.error('Failed to parse error blob', e);
          }
        } else {
          errorDetail = error.response.data.detail;
        }

        if (errorDetail) {
          setErrorMessage(
            typeof errorDetail === 'string' 
              ? errorDetail 
              : JSON.stringify(errorDetail)
          );
          return;
        }
      }
      
      setErrorMessage('An unexpected error occurred while communicating with the server.');
    }
  };

  const handleLogin = (newToken: string) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setIsAuthenticated(false);
    handleReset();
  };

  if (isCheckingAuth) {
    return (
      <Box sx={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', bgcolor: 'background.default' }}>
        <Typography variant="h6" color="text.secondary">Loading...</Typography>
      </Box>
    );
  }

  if (!isAuthenticated) {
    return <AuthScreen onLogin={handleLogin} />;
  }

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
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <MuiButton 
              startIcon={<Github size={18} />} 
              sx={{ color: 'text.secondary', '&:hover': { color: 'text.primary' } }}
              href="https://github.com/lnandanapalli/nlpdf"
              target="_blank"
            >
              Source
            </MuiButton>
            <MuiButton 
              variant="outlined" 
              color="inherit" 
              size="small"
              onClick={handleLogout}
              sx={{ borderColor: 'divider', color: 'text.secondary' }}
            >
              Log Out
            </MuiButton>
          </Box>
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
