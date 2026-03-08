import { useState, useEffect, useCallback } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import AuthScreen from './components/AuthScreen';
import AppShell from './components/AppShell';
import HomePage from './components/HomePage';
import SettingsPage from './components/settings/SettingsPage';
import TermsOfService from './components/TermsOfService';
import PrivacyPolicy from './components/PrivacyPolicy';
import CookieConsent from './components/CookieConsent';
import { validateSession, logout } from './services/api';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState<boolean>(true);

  const handleLogout = useCallback(async () => {
    await logout();
    setIsAuthenticated(false);
  }, []);

  const handleLogin = () => {
    setIsAuthenticated(true);
  };

  // Validate session on mount
  useEffect(() => {
    validateSession()
      .then((valid) => {
        if (valid) setIsAuthenticated(true);
      })
      .finally(() => setIsCheckingAuth(false));
  }, []);

  // Listen for session-expired events from the axios interceptor
  useEffect(() => {
    const onExpired = () => setIsAuthenticated(false);
    window.addEventListener('session-expired', onExpired);
    return () => window.removeEventListener('session-expired', onExpired);
  }, []);

  // Proactive session guard: re-validate when user returns to the tab
  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible' && isAuthenticated) {
        validateSession().then((valid) => {
          if (!valid) setIsAuthenticated(false);
        });
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [isAuthenticated]);

  if (isCheckingAuth) {
    return (
      <Box sx={{ display: 'flex', minHeight: '100dvh', alignItems: 'center', justifyContent: 'center' }}>
        <Typography variant="h6" color="text.secondary">Loading...</Typography>
      </Box>
    );
  }

  return (
    <>
      <Routes>
        {/* Public pages — accessible regardless of auth */}
        <Route path="terms" element={<TermsOfService />} />
        <Route path="privacy" element={<PrivacyPolicy />} />

        {/* Everything else requires authentication */}
        {!isAuthenticated ? (
          <Route path="*" element={<AuthScreen onLogin={handleLogin} />} />
        ) : (
          <>
            <Route element={<AppShell onLogout={handleLogout} />}>
              <Route index element={<HomePage />} />
              <Route path="settings" element={<SettingsPage onAccountDeleted={handleLogout} />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </>
        )}
      </Routes>
      <CookieConsent />
    </>
  );
}

export default App;
