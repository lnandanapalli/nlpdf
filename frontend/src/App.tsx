import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Container, Typography, Box, Alert, Slide,
  AppBar, Toolbar, Button as MuiButton, useTheme,
} from '@mui/material';
import { Sparkles } from 'lucide-react';
import GitHubIcon from '@mui/icons-material/GitHub';
import DragDropZone from './components/DragDropZone';
import CommandInput from './components/CommandInput';
import ProcessingState from './components/ProcessingState';
import ResultCard from './components/ResultCard';
import AuthScreen from './components/AuthScreen';
import { processPDFs, validateSession, logout } from './services/api';

type AppState = 'IDLE' | 'PROCESSING' | 'SUCCESS' | 'ERROR';

function App() {
  const [appState, setAppState] = useState<AppState>('IDLE');
  const [files, setFiles] = useState<File[]>([]);
  const [resultBlob, setResultBlob] = useState<Blob | null>(null);
  const [resultFilename, setResultFilename] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');

  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState<boolean>(true);

  const theme = useTheme();

  const handleReset = () => {
    setAppState('IDLE');
    setFiles([]);
    setResultBlob(null);
    setResultFilename('');
    setErrorMessage('');
  };

  const handleLogout = useCallback(async () => {
    await logout();
    setIsAuthenticated(false);
    handleReset();
  }, []);

  // Validate session on mount (cookie-based — no localStorage check needed)
  useEffect(() => {
    validateSession()
      .then((valid) => {
        if (valid) {
          setIsAuthenticated(true);
        }
      })
      .finally(() => setIsCheckingAuth(false));
  }, []);

  // Listen for session-expired events from the axios interceptor
  useEffect(() => {
    const onExpired = () => {
      setIsAuthenticated(false);
      handleReset();
    };
    window.addEventListener('session-expired', onExpired);
    return () => window.removeEventListener('session-expired', onExpired);
  }, []);

  // Proactive session guard: re-validate when user returns to the tab
  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible' && isAuthenticated) {
        validateSession().then((valid) => {
          if (!valid) {
            setIsAuthenticated(false);
            handleReset();
          }
        });
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [isAuthenticated]);

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

  const handleLogin = () => {
    setIsAuthenticated(true);
  };

  if (isCheckingAuth) {
    return (
      <Box sx={{ display: 'flex', minHeight: '100dvh', alignItems: 'center', justifyContent: 'center' }}>
        <Typography variant="h6" color="text.secondary">Loading...</Typography>
      </Box>
    );
  }

  if (!isAuthenticated) {
    return <AuthScreen onLogin={handleLogin} />;
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100dvh' }}>
      <AppBar position="static" elevation={0} sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.default' }}>
        <Toolbar sx={{ justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Sparkles color={theme.palette.primary.main} size={24} />
            <Typography variant="h6" color="primary.main" sx={{ fontWeight: 600, letterSpacing: 0.5 }}>
              NLPDF
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MuiButton
              startIcon={<GitHubIcon fontSize="small" />}
              sx={{ color: 'text.secondary' }}
              href="https://github.com/lnandanapalli/nlpdf"
              target="_blank"
            >
              GitHub
            </MuiButton>
            <MuiButton
              variant="outlined"
              size="small"
              onClick={handleLogout}
              sx={{ borderColor: 'divider', color: 'text.secondary' }}
            >
              Log Out
            </MuiButton>
          </Box>
        </Toolbar>
      </AppBar>

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
            disabled={files.length === 0 || appState === 'PROCESSING'}
          />
        </Container>
      </Box>
    </Box>
  );
}

export default App;
