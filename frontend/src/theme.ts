import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#8ab4f8', // Authentic Google Material Dark Blue
    },
    secondary: {
      main: '#f28b82', // Authentic Google Material Dark Red/Pink
    },
    background: {
      default: '#202124', // Google standard dark mode background
      paper: '#292a2d',   // Google elevated surface
    },
    text: {
      primary: '#e8eaed', // Standard Google light text
      secondary: '#9aa0a6',
    },
    divider: 'rgba(255, 255, 255, 0.12)',
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h3: {
      fontWeight: 600,
      letterSpacing: '-0.02em', // Premium, tight heading
    },
    h6: {
      fontWeight: 500,
    },
    button: {
      textTransform: 'none',
      fontWeight: 500,
      letterSpacing: '0.25px',
    },
    subtitle1: {
      fontWeight: 500,
    }
  },
  shape: {
    borderRadius: 16,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          padding: '8px 24px',
        },
        containedPrimary: {
          color: '#202124', // Dark text on light blue, very Google
          fontWeight: 600,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none', // Strip default MUI overlay
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 12,
        },
        notchedOutline: {
          borderColor: '#5f6368',
        }
      },
    },
  },
});

export default theme;
