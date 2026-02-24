import { Box, Typography, CircularProgress, Fade } from '@mui/material';
import { Bot } from 'lucide-react';

interface ProcessingStateProps {
  isVisible: boolean;
}

export default function ProcessingState({ isVisible }: ProcessingStateProps) {
  if (!isVisible) return null;

  return (
    <Fade in={isVisible} timeout={800}>
      <Box 
        sx={{ 
          display: 'flex', 
          flexDirection: 'column', 
          alignItems: 'center', 
          justifyContent: 'center',
          py: 8
        }}
      >
        <Box sx={{ position: 'relative', display: 'inline-flex', mb: 4 }}>
          <CircularProgress size={80} thickness={4} color="primary" />
          <Box
            sx={{
              top: 0,
              left: 0,
              bottom: 0,
              right: 0,
              position: 'absolute',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              animation: 'pulse 1.5s infinite ease-in-out',
              '@keyframes pulse': {
                '0%': { opacity: 0.6 },
                '50%': { opacity: 1 },
                '100%': { opacity: 0.6 }
              }
            }}
          >
            <Bot size={32} color="#90caf9" />
          </Box>
        </Box>
        
        <Typography variant="h6" color="primary.light" gutterBottom sx={{ fontWeight: 500 }}>
          Analyzing your request...
        </Typography>
        <Typography variant="body2" color="text.secondary">
          The AI is currently processing the PDFs. This usually takes a few seconds.
        </Typography>
      </Box>
    </Fade>
  );
}
