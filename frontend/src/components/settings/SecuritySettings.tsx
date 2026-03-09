import { useState } from 'react';
import {
  Box, TextField, Button, Alert, Paper, Typography,
  Dialog, DialogTitle, DialogContent, DialogActions, DialogContentText,
  InputAdornment, IconButton,
} from '@mui/material';
import { Eye, EyeOff } from 'lucide-react';
import {
  changePassword, requestAccountDeletion, confirmAccountDeletion, extractErrorMessage,
} from '../../services/api';

interface SecuritySettingsProps {
  onAccountDeleted: () => void;
}

export default function SecuritySettings({ onAccountDeleted }: SecuritySettingsProps) {
  // Password change state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [pwLoading, setPwLoading] = useState(false);
  const [pwSuccess, setPwSuccess] = useState('');
  const [pwError, setPwError] = useState('');

  // Delete account state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteStep, setDeleteStep] = useState<'password' | 'otp'>('password');
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteOtp, setDeleteOtp] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const handleChangePassword = async () => {
    setPwError('');
    setPwSuccess('');

    if (!currentPassword || !newPassword || !confirmPw) {
      setPwError('Please fill in all fields');
      return;
    }
    if (newPassword !== confirmPw) {
      setPwError('New passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      setPwError('New password must be at least 8 characters');
      return;
    }

    setPwLoading(true);
    try {
      await changePassword(currentPassword, newPassword);
      setPwSuccess('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPw('');
    } catch (err) {
      setPwError(extractErrorMessage(err, 'Failed to change password. Please try again.'));
    } finally {
      setPwLoading(false);
    }
  };

  const handleDeleteRequest = async () => {
    setDeleteError('');
    if (!deletePassword) {
      setDeleteError('Please enter your password');
      return;
    }

    setDeleteLoading(true);
    try {
      await requestAccountDeletion(deletePassword);
      setDeleteStep('otp');
    } catch (err) {
      setDeleteError(extractErrorMessage(err, 'Failed to initiate account deletion.'));
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleDeleteConfirm = async () => {
    setDeleteError('');
    if (!deleteOtp) {
      setDeleteError('Please enter the confirmation code');
      return;
    }

    setDeleteLoading(true);
    try {
      await confirmAccountDeletion(deleteOtp);
      onAccountDeleted();
    } catch (err) {
      setDeleteError(extractErrorMessage(err, 'Failed to delete account.'));
    } finally {
      setDeleteLoading(false);
    }
  };

  const closeDeleteDialog = () => {
    setDeleteDialogOpen(false);
    setDeleteStep('password');
    setDeletePassword('');
    setDeleteOtp('');
    setDeleteError('');
  };

  const passwordToggle = (show: boolean, setShow: (v: boolean) => void) => (
    <InputAdornment position="end">
      <IconButton onClick={() => setShow(!show)} edge="end" size="small" aria-label={show ? 'Hide password' : 'Show password'}>
        {show ? <EyeOff size={18} /> : <Eye size={18} />}
      </IconButton>
    </InputAdornment>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Change Password */}
      <Paper sx={{ p: 3, borderRadius: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>Change Password</Typography>
        {pwError && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setPwError('')}>{pwError}</Alert>}
        {pwSuccess && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setPwSuccess('')}>{pwSuccess}</Alert>}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            label="Current Password"
            type={showCurrentPw ? 'text' : 'password'}
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            fullWidth
            slotProps={{
              input: { endAdornment: passwordToggle(showCurrentPw, setShowCurrentPw) },
            }}
          />
          <TextField
            label="New Password"
            type={showNewPw ? 'text' : 'password'}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            fullWidth
            slotProps={{
              input: { endAdornment: passwordToggle(showNewPw, setShowNewPw) },
            }}
          />
          <TextField
            label="Confirm New Password"
            type={showNewPw ? 'text' : 'password'}
            value={confirmPw}
            onChange={(e) => setConfirmPw(e.target.value)}
            fullWidth
          />
          <Button
            variant="contained"
            onClick={handleChangePassword}
            disabled={pwLoading}
            sx={{ alignSelf: 'flex-start' }}
          >
            {pwLoading ? 'Changing...' : 'Change Password'}
          </Button>
        </Box>
      </Paper>

      {/* Delete Account */}
      <Paper
        sx={{
          p: 3, borderRadius: 2,
          borderColor: 'error.main', borderWidth: 1, borderStyle: 'solid',
        }}
      >
        <Typography variant="h6" color="error" sx={{ mb: 1 }}>Delete Account</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Permanently delete your account and all associated data. This action cannot be undone.
        </Typography>
        <Button variant="outlined" color="error" onClick={() => setDeleteDialogOpen(true)}>
          Delete Account
        </Button>
      </Paper>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={closeDeleteDialog} maxWidth="xs" fullWidth>
        <DialogTitle color="error">
          {deleteStep === 'password' ? 'Confirm Account Deletion' : 'Enter Confirmation Code'}
        </DialogTitle>
        <DialogContent>
          {deleteError && <Alert severity="error" sx={{ mb: 2 }}>{deleteError}</Alert>}

          {deleteStep === 'password' ? (
            <>
              <DialogContentText sx={{ mb: 2 }}>
                Enter your password to confirm. A verification code will be sent to your email.
              </DialogContentText>
              <TextField
                label="Password"
                type="password"
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                fullWidth
                autoFocus
              />
            </>
          ) : (
            <>
              <DialogContentText sx={{ mb: 2 }}>
                A 6-digit confirmation code has been sent to your email. Enter it below to permanently delete your account.
              </DialogContentText>
              <TextField
                label="6-digit Confirmation Code"
                value={deleteOtp}
                onChange={(e) => setDeleteOtp(e.target.value)}
                fullWidth
                autoFocus
              />
            </>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={closeDeleteDialog} disabled={deleteLoading}>Cancel</Button>
          {deleteStep === 'password' ? (
            <Button
              variant="contained"
              color="error"
              onClick={handleDeleteRequest}
              disabled={deleteLoading}
            >
              {deleteLoading ? 'Verifying...' : 'Continue'}
            </Button>
          ) : (
            <Button
              variant="contained"
              color="error"
              onClick={handleDeleteConfirm}
              disabled={deleteLoading}
            >
              {deleteLoading ? 'Deleting...' : 'Delete My Account'}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
}
