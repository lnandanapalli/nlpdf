import { useState, useEffect } from 'react';
import { Box, Typography, Button, Link, Slide } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { Cookie } from 'lucide-react';

const CONSENT_KEY = 'nlpdf_cookie_consent';

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem(CONSENT_KEY);
    if (!consent) {
      // Small delay so it doesn't flash on mount
      const timer = setTimeout(() => setVisible(true), 800);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem(CONSENT_KEY, 'accepted');
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <Slide direction="up" in={visible}>
      <Box
        sx={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 9999,
          bgcolor: 'background.paper',
          borderTop: 1,
          borderColor: 'divider',
          px: { xs: 2, md: 4 },
          py: 2,
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          alignItems: { xs: 'stretch', sm: 'center' },
          gap: 2,
          boxShadow: '0 -4px 20px rgba(0,0,0,0.3)',
        }}
      >
        <Cookie size={20} style={{ flexShrink: 0, opacity: 0.7 }} />
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          This site uses cookies and third-party services that may collect data to operate.
          By continuing to use this site, you consent to our{' '}
          <Link component={RouterLink} to="/privacy" variant="body2">Privacy Policy</Link>.
        </Typography>
        <Button
          variant="contained"
          size="small"
          onClick={handleAccept}
          sx={{ whiteSpace: 'nowrap', minWidth: 100 }}
        >
          Got it
        </Button>
      </Box>
    </Slide>
  );
}
