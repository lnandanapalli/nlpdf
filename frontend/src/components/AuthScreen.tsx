import React, { useRef, useState } from 'react';
import axios from 'axios';
import { Turnstile, type TurnstileInstance } from '@marsidev/react-turnstile';
import {
  Box, Container, Typography, TextField, Button,
  Alert, Paper, InputAdornment, IconButton, Link, useTheme,
} from '@mui/material';
import { Mail, Lock, Sparkles, Eye, EyeOff, KeyRound } from 'lucide-react';
import { API_BASE_URL } from '../services/api';
import { config } from '../config';

const TURNSTILE_SITE_KEY = config.turnstileSiteKey;

interface AuthScreenProps {
  onLogin: (token: string) => void;
}

export default function AuthScreen({ onLogin }: AuthScreenProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [cfToken, setCfToken] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [showOTP, setShowOTP] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const turnstileRef = useRef<TurnstileInstance>(null);
  const theme = useTheme();
  const iconColor = theme.palette.text.secondary;

  const handleError = (err: unknown, defaultMessage: string) => {
    if (axios.isAxiosError(err) && err.response?.data?.detail) {
      const { detail } = err.response.data;
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } else {
      setError(defaultMessage);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }
    if (!isLogin && password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (!cfToken) {
      setError('Please complete the CAPTCHA');
      return;
    }

    setLoading(true);
    try {
      if (isLogin) {
        const { data } = await axios.post(`${API_BASE_URL}/auth/login`, { email, password, cf_token: cfToken });
        if (data.access_token) {
          onLogin(data.access_token);
        } else {
          setError('Authentication failed: no token received');
        }
      } else {
        await axios.post(`${API_BASE_URL}/auth/signup`, { email, password, cf_token: cfToken });
        setSuccess('Verification code sent to your email.');
        setShowOTP(true);
      }
    } catch (err) {
      handleError(err, 'An unexpected error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpCode) { setError('Please enter the verification code'); return; }

    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const { data } = await axios.post(`${API_BASE_URL}/auth/verify_otp`, { email, otp_code: otpCode });
      if (data.access_token) {
        onLogin(data.access_token);
      } else {
        setError('Verification failed: no token received');
      }
    } catch (err) {
      handleError(err, 'Verification failed. Please check the code and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOTP = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await axios.post(`${API_BASE_URL}/auth/resend_otp`, { email });
      setSuccess('A new verification code has been sent to your email.');
    } catch (err) {
      handleError(err, 'Failed to resend verification code.');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setIsLogin(!isLogin);
    setError('');
    setSuccess('');
    setShowOTP(false);
    setConfirmPassword('');
    setShowConfirmPassword(false);
    setCfToken('');
    turnstileRef.current?.reset();
  };

  return (
    <Box sx={{ display: 'flex', minHeight: '100dvh', alignItems: 'center', justifyContent: 'center' }}>
      <Container maxWidth="xs">
        <Paper elevation={4} sx={{ p: 4, borderRadius: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.5, mb: 3 }}>
            <Sparkles color={theme.palette.primary.main} size={32} />
            <Typography variant="h4" color="primary.main" sx={{ fontWeight: 700, letterSpacing: 0.5 }}>
              NLPDF
            </Typography>
          </Box>

          <Typography variant="h6" align="center" sx={{ mb: 3, fontWeight: 500 }}>
            {showOTP ? 'Verify your email' : (isLogin ? 'Welcome back' : 'Create an account')}
          </Typography>

          {error && <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>{error}</Alert>}
          {success && <Alert severity="success" sx={{ mb: 2, borderRadius: 2 }}>{success}</Alert>}

          {!showOTP ? (
            <>
              <form onSubmit={handleSubmit}>
                <TextField
                  fullWidth label="Email" type="email" value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  sx={{ mb: 2 }}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Mail size={20} color={iconColor} />
                      </InputAdornment>
                    ),
                  }}
                />

                <TextField
                  fullWidth label="Password" type={showPassword ? 'text' : 'password'}
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  sx={{ mb: !isLogin ? 2 : 3 }}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Lock size={20} color={iconColor} />
                      </InputAdornment>
                    ),
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton onClick={() => setShowPassword(!showPassword)} edge="end" size="small">
                          {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />

                {!isLogin && (
                  <TextField
                    fullWidth label="Confirm Password"
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                    sx={{ mb: 3 }}
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <Lock size={20} color={iconColor} />
                        </InputAdornment>
                      ),
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton onClick={() => setShowConfirmPassword(!showConfirmPassword)} edge="end" size="small">
                            {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }}
                  />
                )}

                <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
                  <Turnstile
                    ref={turnstileRef}
                    siteKey={TURNSTILE_SITE_KEY}
                    onSuccess={(token) => setCfToken(token)}
                    onError={() => setCfToken('')}
                    onExpire={() => setCfToken('')}
                    options={{ theme: 'dark' }}
                  />
                </Box>

                <Button
                  fullWidth type="submit" variant="contained" color="primary" size="large"
                  disabled={loading} sx={{ py: 1.5, mb: 2 }}
                >
                  {loading ? 'Processing…' : (isLogin ? 'Sign In' : 'Sign Up')}
                </Button>
              </form>

              <Typography variant="body2" color="text.secondary" align="center">
                {isLogin ? "Don't have an account? " : 'Already have an account? '}
                <Link component="button" variant="body2" onClick={switchMode} sx={{ fontWeight: 600 }}>
                  {isLogin ? 'Sign up' : 'Log in'}
                </Link>
              </Typography>
            </>
          ) : (
            <>
              <form onSubmit={handleVerifyOTP}>
                <TextField
                  fullWidth label="6-digit Verification Code" type="text"
                  value={otpCode} onChange={(e) => setOtpCode(e.target.value)}
                  sx={{ mb: 3 }}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <KeyRound size={20} color={iconColor} />
                      </InputAdornment>
                    ),
                  }}
                />

                <Button
                  fullWidth type="submit" variant="contained" color="primary" size="large"
                  disabled={loading} sx={{ py: 1.5, mb: 2 }}
                >
                  {loading ? 'Verifying…' : 'Verify Email'}
                </Button>
              </form>

              <Typography variant="body2" color="text.secondary" align="center">
                Didn't receive the code?{' '}
                <Link component="button" variant="body2" onClick={handleResendOTP} disabled={loading} sx={{ fontWeight: 600 }}>
                  Resend
                </Link>
              </Typography>

              <Box sx={{ mt: 1, textAlign: 'center' }}>
                <Link
                  component="button" variant="body2" color="text.secondary"
                  onClick={() => { setShowOTP(false); setIsLogin(true); setError(''); setSuccess(''); }}
                >
                  Back to Login
                </Link>
              </Box>
            </>
          )}
        </Paper>
      </Container>
    </Box>
  );
}
