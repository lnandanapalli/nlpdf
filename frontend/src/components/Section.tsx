import { Box, Typography } from '@mui/material';

export default function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>{title}</Typography>
      {typeof children === 'string' ? (
        <Typography variant="body1" color="text.secondary" sx={{ lineHeight: 1.8 }}>
          {children}
        </Typography>
      ) : (
        children
      )}
    </Box>
  );
}
