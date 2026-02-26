import { useState } from 'react';
import { Box, Typography, TextField, InputAdornment, IconButton, Chip } from '@mui/material';
import { Send } from 'lucide-react';

interface CommandInputProps {
  onProcess: (command: string) => void;
  disabled?: boolean;
}

const SUGGESTIONS = [
  'Merge these PDFs',
  'Compress this file heavily',
  'Extract the first 5 pages',
  'Rotate page 1 by 90 degrees',
];

export default function CommandInput({ onProcess, disabled }: CommandInputProps) {
  const [command, setCommand] = useState('');

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (command.trim() && !disabled) {
      onProcess(command.trim());
    }
  };

  const canSubmit = !!command.trim() && !disabled;

  return (
    <Box sx={{ width: '100%' }}>
      {/* Suggestion chips */}
      <Box sx={{ mb: 1.5, display: 'flex', flexWrap: 'wrap', gap: 1, justifyContent: 'center' }}>
        {SUGGESTIONS.map((suggestion) => (
          <Chip
            key={suggestion}
            label={suggestion}
            size="small"
            variant="outlined"
            disabled={disabled}
            onClick={() => setCommand(suggestion)}
            sx={{
              borderColor: 'divider',
              color: 'text.secondary',
              fontSize: '0.8rem',
              '&:hover': { borderColor: 'primary.main', color: 'primary.main' },
            }}
          />
        ))}
      </Box>

      {/* Command text field */}
      <form onSubmit={handleSubmit}>
        <TextField
          fullWidth
          multiline
          minRows={1}
          maxRows={6}
          disabled={disabled}
          placeholder={disabled ? 'Upload a PDF first…' : 'Message NLPDF…'}
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          sx={{
            '& .MuiOutlinedInput-root': {
              borderRadius: 6,
              bgcolor: 'background.paper',
              fontSize: '1rem',
              px: '20px',
              py: '12px',
              transition: 'box-shadow 0.2s',
              boxShadow: (t) => t.shadows[2],
              '&.Mui-focused': {
                boxShadow: (t) => `0 4px 16px ${t.palette.primary.main}26`,
              },
              '& fieldset': { borderColor: 'divider' },
              '&:hover fieldset': { borderColor: 'text.disabled' },
              '&.Mui-focused fieldset': { borderColor: 'primary.main' },
            },
          }}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end" sx={{ alignSelf: 'flex-end', mb: 0.5 }}>
                <IconButton
                  type="submit"
                  disabled={!canSubmit}
                  color="primary"
                  sx={{
                    bgcolor: canSubmit ? 'primary.main' : 'action.disabledBackground',
                    color: canSubmit ? 'background.default' : 'text.disabled',
                    borderRadius: 2,
                    p: 1,
                    '&:hover': { bgcolor: canSubmit ? 'primary.light' : 'action.disabledBackground' },
                  }}
                >
                  <Send size={18} />
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
      </form>

      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 1 }}>
        NLPDF can make mistakes. Please verify important documents.
      </Typography>
    </Box>
  );
}
