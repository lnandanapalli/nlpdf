import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, Alert, Paper, Typography, Chip, CircularProgress,
  List, ListItem, ListItemIcon, ListItemText, Divider,
  Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions,
} from '@mui/material';
import { Laptop, Smartphone } from 'lucide-react';
import {
  fetchSessions, terminateSession, logoutAllOtherSessions, extractErrorMessage,
  type SessionRecord,
} from '../../services/api';

function formatWhen(iso: string | null): string {
  if (!iso) return 'Unknown';
  // The API sends UTC timestamps; some drivers omit the zone suffix.
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleString();
}

function describeDevice(s: SessionRecord): string {
  const parts = [s.browser, s.os].filter(Boolean);
  return parts.length > 0 ? parts.join(' on ') : 'Unknown browser';
}

export default function SessionSettings() {
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | 'all' | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [confirmAllOpen, setConfirmAllOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      setSessions(await fetchSessions());
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load your sessions.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleTerminate = async (sessionId: number) => {
    setError('');
    setSuccess('');
    setBusyId(sessionId);
    try {
      await terminateSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      setSuccess('That device has been signed out.');
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not sign out that device.'));
    } finally {
      setBusyId(null);
    }
  };

  const handleLogoutAll = async () => {
    setConfirmAllOpen(false);
    setError('');
    setSuccess('');
    setBusyId('all');
    try {
      await logoutAllOtherSessions();
      setSuccess('All other devices have been signed out.');
      await load();
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not sign out your other devices.'));
    } finally {
      setBusyId(null);
    }
  };

  const others = sessions.filter((s) => !s.is_current);

  return (
    <Paper sx={{ p: 3, borderRadius: 2 }}>
      <Typography variant="h6" sx={{ mb: 1 }}>Active Sessions</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Devices that are signed in to your account. A device you sign out here can keep
        access for up to 15 minutes; &ldquo;Sign out all other devices&rdquo; takes effect
        immediately.
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>{success}</Alert>}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
          <CircularProgress size={28} />
        </Box>
      ) : (
        <>
          <List disablePadding>
            {sessions.map((s, i) => (
              <Box key={s.id}>
                {i > 0 && <Divider component="li" />}
                <ListItem
                  sx={{ px: 0, gap: 1, flexWrap: 'wrap' }}
                  secondaryAction={!s.is_current && (
                    <Button
                      size="small" color="error"
                      onClick={() => handleTerminate(s.id)}
                      disabled={busyId !== null}
                    >
                      {busyId === s.id ? 'Signing out…' : 'Sign out'}
                    </Button>
                  )}
                >
                  <ListItemIcon sx={{ minWidth: 36 }}>
                    {s.is_mobile ? <Smartphone size={20} /> : <Laptop size={20} />}
                  </ListItemIcon>
                  <ListItemText
                    sx={{ pr: s.is_current ? 0 : 10 }}
                    primary={(
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <span>{s.device_name || 'Unknown device'}</span>
                        {s.is_current && <Chip label="This device" size="small" color="primary" />}
                      </Box>
                    )}
                    secondary={(
                      <>
                        {describeDevice(s)}
                        {s.ip_address ? ` · ${s.ip_address}` : ''}
                        <br />
                        {`Last active ${formatWhen(s.last_used_at)} · Signed in ${formatWhen(s.created_at)}`}
                      </>
                    )}
                  />
                </ListItem>
              </Box>
            ))}
          </List>

          <Button
            variant="outlined" color="error" sx={{ mt: 2 }}
            onClick={() => setConfirmAllOpen(true)}
            disabled={others.length === 0 || busyId !== null}
          >
            {busyId === 'all' ? 'Signing out…' : 'Sign out all other devices'}
          </Button>
        </>
      )}

      <Dialog open={confirmAllOpen} onClose={() => setConfirmAllOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Sign out all other devices?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Every other device will be signed out right away. This device stays signed in.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setConfirmAllOpen(false)}>Cancel</Button>
          <Button variant="contained" color="error" onClick={handleLogoutAll}>Sign out</Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
