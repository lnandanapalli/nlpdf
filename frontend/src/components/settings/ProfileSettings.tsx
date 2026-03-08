import { useState, useEffect } from 'react';
import { Box, TextField, Button, Alert, Paper, Typography } from '@mui/material';
import { fetchCurrentUser, updateProfile } from '../../services/api';

export default function ProfileSettings() {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    fetchCurrentUser().then((user) => {
      setFirstName(user.first_name || '');
      setLastName(user.last_name || '');
      setEmail(user.email);
    });
  }, []);

  const handleSave = async () => {
    if (!firstName.trim() || !lastName.trim()) {
      setError('Both fields are required');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await updateProfile(firstName.trim(), lastName.trim());
      setSuccess('Profile updated successfully');
    } catch {
      setError('Failed to update profile. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper sx={{ p: 3, borderRadius: 2 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>Profile</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>{success}</Alert>}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <TextField label="Email" value={email} disabled fullWidth />
        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField
            label="First Name"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            fullWidth
          />
          <TextField
            label="Last Name"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            fullWidth
          />
        </Box>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={loading}
          sx={{ alignSelf: 'flex-start' }}
        >
          {loading ? 'Saving...' : 'Save Changes'}
        </Button>
      </Box>
    </Paper>
  );
}
