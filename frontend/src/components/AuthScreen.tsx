import React, { useRef, useState } from 'react';
import axios from 'axios';
import { Turnstile, type TurnstileInstance } from '@marsidev/react-turnstile';
import { 
  Box, Container, Typography, TextField, Button, 
  Alert, Paper, InputAdornment, IconButton
} from '@mui/material';
import { Mail, Lock, Sparkles, Eye, EyeOff, KeyRound } from 'lucide-react';

const TURNSTILE_SITE_KEY = '0x4AAAAAACiFftjXsZL0PTZp';

interface AuthScreenProps {
  onLogin: (token: string) => void;
}

const API_BASE_URL = 'http://127.0.0.1:8000';

export default function AuthScreen({ onLogin }: AuthScreenProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [cfToken, setCfToken] = useState('');
  const turnstileRef = useRef<TurnstileInstance>(null);
  
  // OTP states
  const [showOTP, setShowOTP] = useState(false);
  const [otpCode, setOtpCode] = useState('');

  const handleError = (err: unknown, defaultMessage: string) => {
    if (axios.isAxiosError(err) && err.response?.data?.detail) {
      setError(
        typeof err.response.data.detail === 'string'
          ? err.response.data.detail
          : JSON.stringify(err.response.data.detail)
      );
    } else {
      setError(defaultMessage);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    if (!isLogin && password !== confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    if (!cfToken) {
      setError('Please complete the CAPTCHA');
      setLoading(false);
      return;
    }

    try {
      if (isLogin) {
        const response = await axios.post(`${API_BASE_URL}/auth/login`, {
          email,
          password,
          cf_token: cfToken,
        });
        const { access_token } = response.data;
        if (access_token) {
          onLogin(access_token);
        } else {
          setError('Authentication failed: No token received');
        }
      } else {
        // Signup
        await axios.post(`${API_BASE_URL}/auth/signup`, {
          email,
          password,
          cf_token: cfToken,
        });
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
    if (!otpCode) {
      setError('Please enter the verification code');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await axios.post(`${API_BASE_URL}/auth/verify_otp`, {
        email,
        otp_code: otpCode
      });
      const { access_token } = response.data;
      if (access_token) {
        onLogin(access_token);
      } else {
        setError('Verification failed: No token received');
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
    <Box sx={{ 
      display: 'flex', 
      height: '100vh', 
      width: '100vw',
      alignItems: 'center', 
      justifyContent: 'center',
      bgcolor: 'background.default' 
    }}>
      <Container maxWidth="xs">
        <Paper elevation={4} sx={{ p: 4, borderRadius: 3, bgcolor: '#1e1e1e' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 3 }}>
            <Sparkles color="#8ab4f8" size={32} style={{ marginRight: '12px' }} />
            <Typography variant="h4" color="primary.main" sx={{ fontWeight: 700, letterSpacing: 0.5 }}>
              NLPDF
            </Typography>
          </Box>

          <Typography variant="h6" align="center" sx={{ mb: 3, fontWeight: 500 }}>
            {showOTP ? 'Verify your email' : (isLogin ? 'Welcome back' : 'Create an account')}
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>{error}</Alert>
          )}
          {success && (
            <Alert severity="success" sx={{ mb: 3, borderRadius: 2 }}>{success}</Alert>
          )}

          {!showOTP ? (
            <>
              <form onSubmit={handleSubmit}>
                <TextField
                  fullWidth
                  variant="outlined"
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  sx={{ mb: 2 }}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Mail size={20} color="#888" />
                      </InputAdornment>
                    ),
                  }}
                />
                
                <TextField
                  fullWidth
                  variant="outlined"
                  label="Password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  sx={{ mb: !isLogin ? 2 : 3 }}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Lock size={20} color="#888" />
                      </InputAdornment>
                    ),
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton 
                          onClick={() => setShowPassword(!showPassword)}
                          edge="end"
                          size="small"
                        >
                          {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                        </IconButton>
                      </InputAdornment>
                    )
                  }}
                />

                {!isLogin && (
                  <TextField
                    fullWidth
                    variant="outlined"
                    label="Confirm Password"
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    sx={{ mb: 3 }}
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <Lock size={20} color="#888" />
                        </InputAdornment>
                      ),
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton 
                            onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                            edge="end"
                            size="small"
                          >
                            {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                          </IconButton>
                        </InputAdornment>
                      )
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
                    options={{ theme: 'light' }}
                  />
                </Box>

                <Button
                  fullWidth
                  type="submit"
                  variant="contained"
                  color="primary"
                  size="large"
                  disabled={loading}
                  sx={{ py: 1.5, mb: 2, borderRadius: 2, fontSize: '1rem' }}
                >
                  {loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Sign Up')}
                </Button>
              </form>

              <Box sx={{ textAlign: 'center', mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  {isLogin ? "Don't have an account? " : "Already have an account? "}
                  <Button 
                    variant="text" 
                    size="small" 
                    onClick={switchMode}
                    sx={{ ml: 0.5, p: 0, minWidth: 'auto', textTransform: 'none', fontWeight: 600 }}
                  >
                    {isLogin ? 'Sign up' : 'Log in'}
                  </Button>
                </Typography>
              </Box>
            </>
          ) : (
            <>
              <form onSubmit={handleVerifyOTP}>
                <TextField
                  fullWidth
                  variant="outlined"
                  label="6-digit Verification Code"
                  type="text"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  sx={{ mb: 3 }}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <KeyRound size={20} color="#888" />
                      </InputAdornment>
                    ),
                  }}
                />

                <Button
                  fullWidth
                  type="submit"
                  variant="contained"
                  color="primary"
                  size="large"
                  disabled={loading}
                  sx={{ py: 1.5, mb: 2, borderRadius: 2, fontSize: '1rem' }}
                >
                  {loading ? 'Verifying...' : 'Verify Email'}
                </Button>
              </form>
              
              <Box sx={{ textAlign: 'center', mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Didn't receive the code? 
                  <Button 
                    variant="text" 
                    size="small" 
                    onClick={handleResendOTP}
                    disabled={loading}
                    sx={{ ml: 0.5, p: 0, minWidth: 'auto', textTransform: 'none', fontWeight: 600 }}
                  >
                    Resend
                  </Button>
                </Typography>
                
                <Box sx={{ mt: 2 }}>
                  <Button 
                    variant="text" 
                    size="small" 
                    onClick={() => {
                      setShowOTP(false);
                      setIsLogin(true);
                      setError('');
                      setSuccess('');
                    }}
                    sx={{ textTransform: 'none' }}
                  >
                    Back to Login
                  </Button>
                </Box>
              </Box>
            </>
          )}
        </Paper>
      </Container>
    </Box>
  );
}
