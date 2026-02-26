import { Box, Typography, CircularProgress, Fade, useTheme } from '@mui/material';
import { Bot } from 'lucide-react';

interface ProcessingStateProps {
  isVisible: boolean;
}

export default function ProcessingState({ isVisible }: ProcessingStateProps) {
  const theme = useTheme();

  if (!isVisible) return null;

  return (
    <Fade in={isVisible} timeout={800}>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          flex: 1,
          gap: 2,
        }}
      >
        <Box sx={{ position: 'relative', display: 'inline-flex' }}>
          <CircularProgress size={72} thickness={4} color="primary" />
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              '@keyframes pulse': {
                '0%, 100%': { opacity: 0.6 },
                '50%': { opacity: 1 },
              },
              animation: 'pulse 1.5s ease-in-out infinite',
            }}
          >
            <Bot size={28} color={theme.palette.primary.main} />
          </Box>
        </Box>

        <Typography variant="h6" color="primary.main" sx={{ fontWeight: 500 }}>
          Analyzing your request…
        </Typography>
        <Typography variant="body2" color="text.secondary">
          The AI is processing your PDFs. This usually takes a few seconds.
        </Typography>
      </Box>
    </Fade>
  );
}
