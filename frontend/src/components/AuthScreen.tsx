import { useRef, useState, type FormEvent } from 'react';
import { Turnstile, type TurnstileInstance } from '@marsidev/react-turnstile';
import {
  Box, Container, Typography, TextField, Button,
  Alert, Paper, InputAdornment, IconButton, Link, useTheme,
  Checkbox, FormControlLabel,
} from '@mui/material';
import { Mail, Lock, Eye, EyeOff, KeyRound } from 'lucide-react';
import { Link as RouterLink } from 'react-router-dom';
import {
  login as apiLogin, signup as apiSignup, verifyOtp, resendOtp, extractErrorMessage,
  forgotPassword, resetPassword,
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
  const [isForgotPassword, setIsForgotPassword] = useState(false);
  const [showResetForm, setShowResetForm] = useState(false);
  const turnstileRef = useRef<TurnstileInstance>(null);
  const theme = useTheme();
  const iconColor = theme.palette.text.secondary;

  const handleError = (err: unknown, defaultMessage: string) => {
    setError(extractErrorMessage(err, defaultMessage));
  };

  const handleSubmit = async (e: FormEvent) => {
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
        setCfToken('');
        turnstileRef.current?.reset();
      }
    } catch (err) {
      handleError(err, 'An unexpected error occurred. Please try again.');
      setCfToken('');
      turnstileRef.current?.reset();
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e: FormEvent) => {
    e.preventDefault();
    if (!otpCode) { setError('Please enter the verification code'); return; }
    if (!cfToken) { setError('Please complete the CAPTCHA'); return; }

    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await verifyOtp(email, otpCode, cfToken);
      onLogin();
    } catch (err) {
      handleError(err, 'Verification failed. Please check the code and try again.');
      setCfToken('');
      turnstileRef.current?.reset();
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
    setIsForgotPassword(false);
    setShowResetForm(false);
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

  const handleForgotPassword = async (e: FormEvent) => {
    e.preventDefault();
    if (!email) { setError('Please enter your email'); return; }
    if (!cfToken) { setError('Please complete the CAPTCHA'); return; }

    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await forgotPassword(email, cfToken);
      setSuccess('If that email is valid, a reset code was sent.');
      setShowResetForm(true);
      setCfToken('');
      turnstileRef.current?.reset();
    } catch (err) {
      handleError(err, 'Failed to initiate password reset.');
      setCfToken('');
      turnstileRef.current?.reset();
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: FormEvent) => {
    e.preventDefault();
    if (!otpCode || !password || !confirmPassword) { setError('Please fill in all fields'); return; }
    if (password !== confirmPassword) { setError('Passwords do not match'); return; }
    if (!cfToken) { setError('Please complete the CAPTCHA'); return; }

    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await resetPassword(email, otpCode, password, cfToken);
      setSuccess('Password reset successfully. You can now log in.');
      setIsForgotPassword(false);
      setShowResetForm(false);
      setIsLogin(true);
      setPassword('');
      setConfirmPassword('');
      setOtpCode('');
      setCfToken('');
      turnstileRef.current?.reset();
    } catch (err) {
      handleError(err, 'Failed to reset password. Please check the code.');
      setCfToken('');
      turnstileRef.current?.reset();
    } finally {
      setLoading(false);
    }
  };

  // Determine the current "step" to force Turnstile reset on mode change
  const currentStep = showOTP ? 'otp' : isForgotPassword ? (showResetForm ? 'reset' : 'forgot') : (isLogin ? 'login' : 'signup');

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
            {showOTP ? 'Verify your email' :
             isForgotPassword ? (showResetForm ? 'Reset password' : 'Forgot password') :
             (isLogin ? 'Welcome back' : 'Create an account')}
          </Typography>

          {error && <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>{error}</Alert>}
          {success && <Alert severity="success" sx={{ mb: 2, borderRadius: 2 }}>{success}</Alert>}

          <Box sx={{ mb: 2 }}>
            {showOTP ? (
              /* --- PART 1: SIGNUP OTP VERIFICATION --- */
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
                    component="button" type="button" variant="body2" color="text.secondary"
                    onClick={() => { setShowOTP(false); setIsLogin(true); setError(''); setSuccess(''); }}
                  >
                    Back to Login
                  </Link>
                </Box>
              </>
            ) : isForgotPassword ? (
              /* --- PART 2: FORGOT PASSWORD FLOW --- */
              <>
                {!showResetForm ? (
                  <form onSubmit={handleForgotPassword}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3, textAlign: 'center' }}>
                      Enter your email address to receive a verification code.
                    </Typography>
                    <TextField
                      fullWidth label="Email" type="email" value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      sx={{ mb: 3 }}
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
                    <Button
                      fullWidth type="submit" variant="contained" color="primary" size="large"
                      disabled={loading} sx={{ py: 1.5, mb: 2 }}
                    >
                      {loading ? 'Sending code…' : 'Send Reset Code'}
                    </Button>
                  </form>
                ) : (
                  <form onSubmit={handleResetPassword}>
                    <TextField
                      fullWidth label="Verification Code" type="text"
                      value={otpCode} onChange={(e) => setOtpCode(e.target.value)}
                      sx={{ mb: 2 }}
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
                    <TextField
                      fullWidth label="New Password" type={showPassword ? 'text' : 'password'}
                      value={password} onChange={(e) => setPassword(e.target.value)}
                      sx={{ mb: 2 }}
                      slotProps={{
                        input: {
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
                        },
                      }}
                    />
                    <TextField
                      fullWidth label="Confirm" type={showConfirmPassword ? 'text' : 'password'}
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
                              <IconButton onClick={() => setShowConfirmPassword(!showConfirmPassword)} edge="end" size="small">
                                {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                              </IconButton>
                            </InputAdornment>
                          ),
                        },
                      }}
                    />
                    <Button
                      fullWidth type="submit" variant="contained" color="primary" size="large"
                      disabled={loading} sx={{ py: 1.5, mb: 2 }}
                    >
                      {loading ? 'Resetting…' : 'Reset Password'}
                    </Button>
                  </form>
                )}
                <Box sx={{ mt: 1, textAlign: 'center' }}>
                  <Link
                    component="button" variant="body2" color="text.secondary"
                    onClick={() => { setIsForgotPassword(false); setShowResetForm(false); setError(''); setSuccess(''); turnstileRef.current?.reset(); }}
                  >
                    Back to Login
                  </Link>
                </Box>
              </>
            ) : (
              /* --- PART 3: LOGIN / SIGNUP --- */
              <>
                <form onSubmit={handleSubmit}>
                  {!isLogin && (
                    <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                      <TextField fullWidth label="First" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
                      <TextField fullWidth label="Last" value={lastName} onChange={(e) => setLastName(e.target.value)} />
                    </Box>
                  )}
                  <TextField
                    fullWidth label="Email" type="email" value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    sx={{ mb: 2 }}
                    slotProps={{
                      input: {
                        startAdornment: <InputAdornment position="start"><Mail size={20} color={iconColor} /></InputAdornment>,
                      },
                    }}
                  />
                  <TextField
                    fullWidth label="Password" type={showPassword ? 'text' : 'password'}
                    value={password} onChange={(e) => setPassword(e.target.value)}
                    sx={{ mb: !isLogin ? 2 : 1 }}
                    slotProps={{
                      input: {
                        startAdornment: <InputAdornment position="start"><Lock size={20} color={iconColor} /></InputAdornment>,
                        endAdornment: (
                          <InputAdornment position="end">
                            <IconButton onClick={() => setShowPassword(!showPassword)} edge="end" size="small">
                              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </IconButton>
                          </InputAdornment>
                        ),
                      },
                    }}
                  />

                  {isLogin && (
                    <Box sx={{ textAlign: 'right', mb: 2 }}>
                      <Link
                        component="button" type="button" variant="body2"
                        onClick={() => { setIsForgotPassword(true); setError(''); setSuccess(''); turnstileRef.current?.reset(); }}
                      >
                        Forgot password?
                      </Link>
                    </Box>
                  )}

                  {!isLogin && (
                    <>
                      <TextField
                        fullWidth label="Confirm Password" type={showConfirmPassword ? 'text' : 'password'}
                        value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                        sx={{ mb: 2 }}
                      />
                      <FormControlLabel
                        control={<Checkbox checked={agreedToTerms} onChange={(e) => setAgreedToTerms(e.target.checked)} size="small" />}
                        label={<Typography variant="body2">I agree to the <Link component={RouterLink} to="/terms" target="_blank">Terms</Link> and <Link component={RouterLink} to="/privacy" target="_blank">Privacy Policy</Link></Typography>}
                        sx={{ mb: 2, alignItems: 'flex-start' }}
                      />
                    </>
                  )}

                  <Button
                    fullWidth type="submit" variant="contained" color="primary" size="large"
                    disabled={loading} sx={{ py: 1.5, mb: 2 }}
                  >
                    {loading ? 'Processing…' : (isLogin ? 'Sign In' : 'Sign Up')}
                  </Button>
                </form>

                <Typography variant="body2" color="text.secondary" align="center">
                  {isLogin ? "Don't have an account? " : 'Already have an account? '}
                  <Link component="button" type="button" variant="body2" onClick={switchMode} sx={{ fontWeight: 600 }}>
                    {isLogin ? 'Sign up' : 'Log in'}
                  </Link>
                </Typography>
              </>
            )}
          </Box>

          {/* SINGLE CONSOLIDATED TURNSTILE COMPONENT */}
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
            <Turnstile
              key={currentStep} // FORCE RESET ON MODE CHANGE
              ref={turnstileRef}
              siteKey={TURNSTILE_SITE_KEY}
              onSuccess={(token) => setCfToken(token)}
              onError={() => setCfToken('')}
              onExpire={() => setCfToken('')}
              options={{ theme: 'dark' }}
            />
          </Box>
        </Paper>
      </Container>
    </Box>
  );
}
