import { useState } from 'react';
import { Box, Typography, TextField, Button, InputAdornment, IconButton } from '@mui/material';
import { Send } from 'lucide-react';

interface CommandInputProps {
  onProcess: (command: string) => void;
  disabled?: boolean;
}

const SUGGESTIONS = [
  "Merge these PDFs",
  "Compress this file heavily",
  "Extract the first 5 pages",
  "Rotate page 1 by 90 degrees"
];

export default function CommandInput({ onProcess, disabled }: CommandInputProps) {
  const [command, setCommand] = useState('');

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (command.trim() && !disabled) {
      onProcess(command.trim());
    }
  };

  return (
    <Box sx={{ width: '100%', position: 'relative' }}>
      <Box sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', gap: 1, justifyContent: 'center' }}>
        {SUGGESTIONS.map((suggestion) => (
          <Button
            key={suggestion}
            variant="outlined"
            size="small"
            disabled={disabled}
            onClick={() => setCommand(suggestion)}
            sx={{ 
              borderRadius: 20, 
              textTransform: 'none', 
              fontSize: '0.8rem',
              borderColor: 'divider',
              color: 'text.secondary',
              bgcolor: 'background.paper',
              '&:hover': {
                borderColor: 'primary.main',
                color: 'primary.main',
                bgcolor: 'rgba(138, 180, 248, 0.08)'
              }
            }}
          >
            {suggestion}
          </Button>
        ))}
      </Box>

      <form onSubmit={handleSubmit}>
        <TextField
          fullWidth
          multiline
          minRows={1}
          maxRows={6}
          disabled={disabled}
          placeholder={disabled ? "Please upload a PDF first..." : "Message NLPDF..."}
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
              borderRadius: 6, /* Very round like ChatGPT */
              backgroundColor: 'background.paper',
              transition: 'all 0.2s',
              fontSize: '1rem',
              p: '12px 20px',
              fontFamily: 'Inter, sans-serif',
              boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
              '&.Mui-focused': {
                boxShadow: '0 4px 16px rgba(138, 180, 248, 0.15)',
              },
              '& fieldset': { border: '1px solid rgba(255,255,255,0.1)' },
              '&:hover fieldset': { border: '1px solid rgba(255,255,255,0.2)' },
              '&.Mui-focused fieldset': { border: '1px solid #8ab4f8' },
            }
          }}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end" sx={{ alignSelf: 'flex-end', mb: 0.5 }}>
                <IconButton
                  type="submit"
                  disabled={disabled || !command.trim()}
                  color="primary"
                  sx={{ 
                    bgcolor: command.trim() && !disabled ? 'primary.main' : 'action.disabledBackground',
                    color: command.trim() && !disabled ? '#202124' : 'text.disabled',
                    borderRadius: 2,
                    p: 1,
                    '&:hover': {
                      bgcolor: command.trim() && !disabled ? 'primary.light' : 'action.disabledBackground',
                    }
                  }}
                >
                  <Send size={18} />
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
      </form>
      
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 1.5 }}>
        NLPDF can make mistakes. Please verify important documents.
      </Typography>
    </Box>
  );
}
