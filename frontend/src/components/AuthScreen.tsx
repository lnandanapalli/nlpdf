import React, { useState } from 'react';
import axios from 'axios';
import { 
  Box, Container, Typography, TextField, Button, 
  Alert, Paper, InputAdornment, IconButton
} from '@mui/material';
import { Mail, Lock, Sparkles, Eye, EyeOff } from 'lucide-react';

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
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const endpoint = isLogin ? '/auth/login' : '/auth/signup';
      const response = await axios.post(`${API_BASE_URL}${endpoint}`, {
        email,
        password
      });
      
      const { access_token } = response.data;
      if (access_token) {
        onLogin(access_token);
      } else {
        setError('Authentication failed: No token received');
      }
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        setError(
          typeof err.response.data.detail === 'string'
            ? err.response.data.detail
            : JSON.stringify(err.response.data.detail)
        );
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setLoading(false);
    }
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
            {isLogin ? 'Welcome back' : 'Create an account'}
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>
              {error}
            </Alert>
          )}

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
                onClick={() => {
                  setIsLogin(!isLogin);
                  setError('');
                }}
                sx={{ ml: 0.5, p: 0, minWidth: 'auto', textTransform: 'none', fontWeight: 600 }}
              >
                {isLogin ? 'Sign up' : 'Log in'}
              </Button>
            </Typography>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
}
