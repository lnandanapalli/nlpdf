import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Box, Typography, Button, Paper, Chip } from '@mui/material';
import { CloudUpload, FileText, X } from 'lucide-react';

interface DragDropZoneProps {
  files: File[];
  onFilesAdded: (newFiles: File[]) => void;
  onFileRemoved: (fileToRemove: File) => void;
  disabled?: boolean;
}

export default function DragDropZone({ files, onFilesAdded, onFileRemoved, disabled }: DragDropZoneProps) {
  const onDrop = useCallback((acceptedFiles: File[]) => {
    onFilesAdded(acceptedFiles);
  }, [onFilesAdded]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    disabled,
  });

  return (
    <Box sx={{ width: '100%', mb: 2 }}>
      <Paper
        {...getRootProps()}
        variant="outlined"
        sx={{
          p: 6,
          textAlign: 'center',
          cursor: disabled ? 'default' : 'pointer',
          bgcolor: isDragActive ? 'rgba(138, 180, 248, 0.08)' : 'transparent',
          borderColor: isDragActive ? 'primary.main' : 'divider',
          borderStyle: 'dashed',
          borderWidth: 2,
          borderRadius: 4,
          transition: 'all 0.2s ease-in-out',
          opacity: disabled ? 0.6 : 1,
          '&:hover': {
            borderColor: disabled ? 'divider' : 'primary.main',
            bgcolor: disabled ? 'transparent' : 'rgba(138, 180, 248, 0.04)',
          }
        }}
      >
        <input {...getInputProps()} />
        <CloudUpload size={48} color={isDragActive ? '#8ab4f8' : '#9aa0a6'} style={{ marginBottom: 16 }} />
        <Typography variant="h6" color="text.primary" gutterBottom sx={{ fontWeight: 500 }}>
          {isDragActive ? 'Drop PDFs here' : 'Drag & Drop PDFs'}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Or click to browse your files
        </Typography>
        
        {!disabled && (
          <Button variant="outlined" color="primary" sx={{ borderRadius: 2, px: 3 }}>
            Choose Files
          </Button>
        )}
      </Paper>

      {files.length > 0 && (
        <Box sx={{ mt: 3, display: 'flex', flexWrap: 'wrap', gap: 1.5, justifyContent: 'center' }}>
          {files.map((file, idx) => (
            <Chip
              key={`${file.name}-${idx}`}
              icon={<FileText size={16} />}
              label={<Typography noWrap sx={{ maxWidth: 220, fontSize: '0.85rem' }}>{file.name}</Typography>}
              onDelete={disabled ? undefined : () => onFileRemoved(file)}
              deleteIcon={<X size={16} />}
              variant="outlined"
              color="primary"
              sx={{ 
                borderRadius: 2, 
                pl: 1, 
                py: 2.5,
                bgcolor: 'rgba(138, 180, 248, 0.08)',
                borderColor: 'rgba(138, 180, 248, 0.3)'
              }}
            />
          ))}
        </Box>
      )}
    </Box>
  );
}
