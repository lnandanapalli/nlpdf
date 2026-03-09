import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  IconButton, Menu, MenuItem, ListItemIcon, ListItemText,
  Avatar, Typography, Divider, Box,
} from '@mui/material';
import { Settings, LogOut } from 'lucide-react';
import { fetchCurrentUser, type UserData } from '../services/api';

interface ProfileMenuProps {
  onLogout: () => void;
}

export default function ProfileMenu({ onLogout }: ProfileMenuProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [user, setUser] = useState<UserData | null>(null);
  const open = Boolean(anchorEl);
  const navigate = useNavigate();

  useEffect(() => {
    const loadUser = () => {
      fetchCurrentUser()
        .then(setUser)
        .catch(() => setUser(null));
    };
    loadUser();
    window.addEventListener('profile-updated', loadUser);
    return () => window.removeEventListener('profile-updated', loadUser);
  }, []);

  const initials = user
    ? `${(user.first_name ?? '')[0] ?? ''}${(user.last_name ?? '')[0] ?? ''}`.toUpperCase() || '?'
    : '?';

  const fullName = user
    ? [user.first_name, user.last_name].filter(Boolean).join(' ') || user.email
    : '';

  return (
    <>
      <IconButton
        onClick={(e) => setAnchorEl(e.currentTarget)}
        size="small"
        sx={{ ml: 1 }}
        aria-label="Account menu"
      >
        <Avatar
          sx={{
            width: 32,
            height: 32,
            bgcolor: 'primary.main',
            color: 'background.default',
            fontSize: '0.85rem',
            fontWeight: 600,
          }}
        >
          {initials}
        </Avatar>
      </IconButton>
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={() => setAnchorEl(null)}
        onClick={() => setAnchorEl(null)}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        slotProps={{ paper: { sx: { mt: 1, minWidth: 200 } } }}
      >
        <Box sx={{ px: 2, py: 1.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            {fullName}
          </Typography>
          {user && (
            <Typography variant="caption" color="text.secondary">
              {user.email}
            </Typography>
          )}
        </Box>
        <Divider />
        <MenuItem onClick={() => navigate('/settings')}>
          <ListItemIcon><Settings size={18} /></ListItemIcon>
          <ListItemText>Settings</ListItemText>
        </MenuItem>
        <MenuItem onClick={onLogout}>
          <ListItemIcon><LogOut size={18} /></ListItemIcon>
          <ListItemText>Log Out</ListItemText>
        </MenuItem>
      </Menu>
    </>
  );
}
