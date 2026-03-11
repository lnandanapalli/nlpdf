import { useRef, useState, type SubmitEvent } from 'react';
import { Turnstile, type TurnstileInstance } from '@marsidev/react-turnstile';
import {
  Box, Container, Typography, TextField, Button,
  Alert, Paper, InputAdornment, IconButton, Link, useTheme,
  Checkbox, FormControlLabel,
} from '@mui/material';
import { Mail, Lock, Eye, EyeOff, KeyRound, User } from 'lucide-react';
import { Link as RouterLink } from 'react-router-dom';
import {
  login as apiLogin, signup as apiSignup, verifyOtp, resendOtp, extractErrorMessage,
} from '../services/api';
import { config } from '../config';

const TURNSTILE_SITE_KEY = config.turnstileSiteKey;

interface AuthScreenProps {
  onLogin: () => void;
}

export default function AuthScreen({ onLogin }: AuthScreenProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [cfToken, setCfToken] = useState('');
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [showOTP, setShowOTP] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const turnstileRef = useRef<TurnstileInstance>(null);
  const theme = useTheme();
  const iconColor = theme.palette.text.secondary;

  const handleError = (err: unknown, defaultMessage: string) => {
    setError(extractErrorMessage(err, defaultMessage));
  };

  const handleSubmit = async (e: SubmitEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }
    if (!isLogin && (!firstName.trim() || !lastName.trim())) {
      setError('Please fill in all fields');
      return;
    }
    if (!isLogin && password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (!isLogin && !agreedToTerms) {
      setError('You must agree to the Terms of Service and Privacy Policy');
      return;
    }
    if (!cfToken) {
      setError('Please complete the CAPTCHA');
      return;
    }

    setLoading(true);
    try {
      if (isLogin) {
        await apiLogin(email, password, cfToken);
        onLogin();
      } else {
        await apiSignup(email, password, firstName.trim(), lastName.trim(), cfToken);
        setSuccess('Verification code sent to your email.');
        setShowOTP(true);
      }
    } catch (err) {
      handleError(err, 'An unexpected error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e: SubmitEvent) => {
    e.preventDefault();
    if (!otpCode) { setError('Please enter the verification code'); return; }

    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await verifyOtp(email, otpCode);
      onLogin();
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
      await resendOtp(email);
      setSuccess('A new verification code has been sent to your email.');
    } catch (err) {
      handleError(err, 'Failed to resend verification code.');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setIsLogin(!isLogin);
    setFirstName('');
    setLastName('');
    setError('');
    setSuccess('');
    setShowOTP(false);
    setConfirmPassword('');
    setShowConfirmPassword(false);
    setAgreedToTerms(false);
    setCfToken('');
    turnstileRef.current?.reset();
  };

  return (
    <Box sx={{ display: 'flex', minHeight: '100dvh', alignItems: 'center', justifyContent: 'center' }}>
      <Container maxWidth="xs">
        <Paper elevation={4} sx={{ p: 4, borderRadius: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.5, mb: 3 }}>
            <img src="/nlpdficon.svg" alt="NLPDF logo" style={{ width: 40, height: 40 }} />
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
                {!isLogin && (
                  <>
                    <TextField
                      fullWidth label="First Name" value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      sx={{ mb: 2 }}
                      slotProps={{
                        input: {
                          startAdornment: (
                            <InputAdornment position="start">
                              <User size={20} color={iconColor} />
                            </InputAdornment>
                          ),
                        },
                      }}
                    />
                    <TextField
                      fullWidth label="Last Name" value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      sx={{ mb: 2 }}
                      slotProps={{
                        input: {
                          startAdornment: (
                            <InputAdornment position="start">
                              <User size={20} color={iconColor} />
                            </InputAdornment>
                          ),
                        },
                      }}
                    />
                  </>
                )}

                <TextField
                  fullWidth label="Email" type="email" value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  sx={{ mb: 2 }}
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start">
                          <Mail size={20} color={iconColor} />
                        </InputAdornment>
                      ),
                    },
                  }}
                />

                <TextField
                  fullWidth label="Password" type={showPassword ? 'text' : 'password'}
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  sx={{ mb: !isLogin ? 2 : 3 }}
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start">
                          <Lock size={20} color={iconColor} />
                        </InputAdornment>
                      ),
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton onClick={() => setShowPassword(!showPassword)} edge="end" size="small" aria-label={showPassword ? 'Hide password' : 'Show password'}>
                            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    },
                  }}
                />

                {!isLogin && (
                  <TextField
                    fullWidth label="Confirm Password"
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                    sx={{ mb: 3 }}
                    slotProps={{
                      input: {
                        startAdornment: (
                          <InputAdornment position="start">
                            <Lock size={20} color={iconColor} />
                          </InputAdornment>
                        ),
                        endAdornment: (
                          <InputAdornment position="end">
                            <IconButton onClick={() => setShowConfirmPassword(!showConfirmPassword)} edge="end" size="small" aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}>
                              {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </IconButton>
                          </InputAdornment>
                        ),
                      },
                    }}
                  />
                )}

                {!isLogin && (
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={agreedToTerms}
                        onChange={(e) => setAgreedToTerms(e.target.checked)}
                        size="small"
                      />
                    }
                    label={
                      <Typography variant="body2" color="text.secondary">
                        I agree to the{' '}
                        <Link component={RouterLink} to="/terms" target="_blank" variant="body2">Terms of Service</Link>
                        {' '}and{' '}
                        <Link component={RouterLink} to="/privacy" target="_blank" variant="body2">Privacy Policy</Link>
                      </Typography>
                    }
                    sx={{ mb: 1, alignItems: 'flex-start', '& .MuiCheckbox-root': { pt: 0.5 } }}
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
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start">
                          <KeyRound size={20} color={iconColor} />
                        </InputAdornment>
                      ),
                    },
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
