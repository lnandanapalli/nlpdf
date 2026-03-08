import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { IconButton, Menu, MenuItem, ListItemIcon, ListItemText, Avatar } from '@mui/material';
import { Settings, LogOut } from 'lucide-react';

interface ProfileMenuProps {
  onLogout: () => void;
}

export default function ProfileMenu({ onLogout }: ProfileMenuProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const navigate = useNavigate();

  return (
    <>
      <IconButton
        onClick={(e) => setAnchorEl(e.currentTarget)}
        size="small"
        sx={{ ml: 1 }}
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
        />
      </IconButton>
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={() => setAnchorEl(null)}
        onClick={() => setAnchorEl(null)}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        slotProps={{ paper: { sx: { mt: 1, minWidth: 180 } } }}
      >
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
