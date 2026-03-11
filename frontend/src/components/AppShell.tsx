import { Outlet, Link } from 'react-router-dom';
import { Box, AppBar, Toolbar, Typography, Button as MuiButton } from '@mui/material';

import GitHubIcon from '@mui/icons-material/GitHub';
import ProfileMenu from './ProfileMenu';

interface AppShellProps {
  onLogout: () => void;
}

export default function AppShell({ onLogout }: AppShellProps) {


  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100dvh' }}>
      <AppBar
        position="static"
        elevation={0}
        sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.default' }}
      >
        <Toolbar sx={{ justifyContent: 'space-between' }}>
          <Box
            component={Link}
            to="/"
            sx={{
              display: 'flex', alignItems: 'center', gap: 1.5,
              textDecoration: 'none', color: 'inherit',
            }}
          >
            <img src="/nlpdficon.svg" alt="NLPDF logo" style={{ width: 28, height: 28 }} />
            <Typography variant="h6" color="primary.main" sx={{ fontWeight: 600, letterSpacing: 0.5 }}>
              NLPDF
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MuiButton
              startIcon={<GitHubIcon fontSize="small" />}
              sx={{ color: 'text.secondary' }}
              href="https://github.com/lnandanapalli/nlpdf"
              target="_blank"
              aria-label="View source on GitHub"
            >
              GitHub
            </MuiButton>
            <ProfileMenu onLogout={onLogout} />
          </Box>
        </Toolbar>
      </AppBar>
      <Outlet />
    </Box>
  );
}
