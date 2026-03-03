import { useState, type SubmitEvent } from 'react';
import {
  Box, Typography, TextField, InputAdornment, IconButton, Chip,
  Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Button,
} from '@mui/material';
import { Send } from 'lucide-react';

interface CommandInputProps {
  onProcess: (command: string) => void;
  disabled?: boolean;
  hasFiles?: boolean;
}

const SUGGESTIONS = [
  'Merge these PDFs',
  'Compress this file heavily',
  'Extract the first 5 pages',
  'Rotate page 1 by 90 degrees',
];

const ALL_EXAMPLES: { category: string; examples: string[] }[] = [
  {
    category: 'Compress',
    examples: [
      'Compress this file',
      'Maximum compression',
      'Compress at high quality',
      'Compress both files',
    ],
  },
  {
    category: 'Split',
    examples: [
      'Extract pages 5-10',
      'Get pages 1-5 and 10-15 as separate files',
      'Extract the first 3 pages',
    ],
  },
  {
    category: 'Merge',
    examples: [
      'Merge these PDFs',
      'Merge these and compress the result',
      'Compress these and then merge',
    ],
  },
  {
    category: 'Rotate',
    examples: [
      'Rotate page 1 by 90 degrees',
      'Flip page 2 upside down',
      'Rotate page 1 by 90 and page 3 by 180',
    ],
  },
  {
    category: 'Markdown to PDF',
    examples: [
      'Convert this markdown to PDF',
      'Convert to PDF on letter paper',
      'Convert all these markdown files to PDF',
    ],
  },
];

export default function CommandInput({ onProcess, disabled, hasFiles }: CommandInputProps) {
  const [command, setCommand] = useState('');
  const [showFileAlert, setShowFileAlert] = useState(false);
  const [showExamples, setShowExamples] = useState(false);

  const handleSubmit = (e?: SubmitEvent) => {
    if (e) e.preventDefault();
    if (!command.trim() || disabled) return;
    if (!hasFiles) {
      setShowFileAlert(true);
      return;
    }
    onProcess(command.trim());
  };

  const handleExampleClick = (example: string) => {
    setCommand(example);
    setShowExamples(false);
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
        <Chip
          label="View all"
          size="small"
          variant="outlined"
          disabled={disabled}
          onClick={() => setShowExamples(true)}
          sx={{
            borderColor: 'divider',
            color: 'text.secondary',
            fontSize: '0.8rem',
            '&:hover': { borderColor: 'primary.main', color: 'primary.main' },
          }}
        />
      </Box>

      {/* Command text field */}
      <form onSubmit={handleSubmit}>
        <TextField
          fullWidth
          multiline
          minRows={1}
          maxRows={6}
          disabled={disabled}
          placeholder="Message NLPDF…"
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
          slotProps={{
            input: {
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
            },
          }}
        />
      </form>

      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 1 }}>
        NLPDF can make mistakes. Please verify important documents.
      </Typography>

      {/* No files alert */}
      <Dialog open={showFileAlert} onClose={() => setShowFileAlert(false)}>
        <DialogTitle>No files uploaded</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Please upload at least one PDF or markdown file before processing.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowFileAlert(false)} autoFocus>OK</Button>
        </DialogActions>
      </Dialog>

      {/* Examples dialog */}
      <Dialog
        open={showExamples}
        onClose={() => setShowExamples(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Example Commands</DialogTitle>
        <DialogContent dividers>
          {ALL_EXAMPLES.map(({ category, examples }) => (
            <Box key={category} sx={{ mb: 2, '&:last-child': { mb: 0 } }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
                {category}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                {examples.map((example) => (
                  <Chip
                    key={example}
                    label={example}
                    size="small"
                    variant="outlined"
                    onClick={() => handleExampleClick(example)}
                    sx={{
                      borderColor: 'divider',
                      color: 'text.primary',
                      fontSize: '0.8rem',
                      '&:hover': { borderColor: 'primary.main', color: 'primary.main' },
                    }}
                  />
                ))}
              </Box>
            </Box>
          ))}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowExamples(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
