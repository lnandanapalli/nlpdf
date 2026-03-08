import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Container, List, ListItemButton, ListItemIcon, ListItemText,
  Paper, Typography, IconButton, useMediaQuery, useTheme,
} from '@mui/material';
import { User, Shield, ArrowLeft } from 'lucide-react';
import ProfileSettings from './ProfileSettings';
import SecuritySettings from './SecuritySettings';

type Section = 'profile' | 'security';

interface SettingsPageProps {
  onAccountDeleted: () => void;
}

export default function SettingsPage({ onAccountDeleted }: SettingsPageProps) {
  const [activeSection, setActiveSection] = useState<Section>('profile');
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();

  const sections = [
    { id: 'profile' as Section, label: 'Profile', icon: <User size={20} /> },
    { id: 'security' as Section, label: 'Security', icon: <Shield size={20} /> },
  ];

  return (
    <Box sx={{ flex: 1, py: { xs: 2, md: 4 }, px: { xs: 2, md: 0 } }}>
      <Container maxWidth="md">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
          <IconButton onClick={() => navigate('/')} size="small">
            <ArrowLeft size={20} />
          </IconButton>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>Settings</Typography>
        </Box>

        <Box sx={{ display: 'flex', gap: 3, flexDirection: isMobile ? 'column' : 'row' }}>
          {/* Sidebar */}
          <Paper sx={{ minWidth: isMobile ? 'auto' : 200, p: 1, borderRadius: 2, alignSelf: 'flex-start' }}>
            <List disablePadding>
              {sections.map((s) => (
                <ListItemButton
                  key={s.id}
                  selected={activeSection === s.id}
                  onClick={() => setActiveSection(s.id)}
                  sx={{ borderRadius: 1.5 }}
                >
                  <ListItemIcon sx={{ minWidth: 36 }}>{s.icon}</ListItemIcon>
                  <ListItemText primary={s.label} />
                </ListItemButton>
              ))}
            </List>
          </Paper>

          {/* Content */}
          <Box sx={{ flex: 1 }}>
            {activeSection === 'profile' && <ProfileSettings />}
            {activeSection === 'security' && <SecuritySettings onAccountDeleted={onAccountDeleted} />}
          </Box>
        </Box>
      </Container>
    </Box>
  );
}
