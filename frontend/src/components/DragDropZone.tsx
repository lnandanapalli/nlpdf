import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Box, Typography, Paper, Chip, useTheme } from '@mui/material';
import { CloudUpload, FileText, X } from 'lucide-react';

interface DragDropZoneProps {
  files: File[];
  onFilesAdded: (newFiles: File[]) => void;
  onFileRemoved: (fileToRemove: File) => void;
  disabled?: boolean;
}

export default function DragDropZone({ files, onFilesAdded, onFileRemoved, disabled }: DragDropZoneProps) {
  const theme = useTheme();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    onFilesAdded(acceptedFiles);
  }, [onFilesAdded]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    disabled,
  });

  return (
    <Box sx={{ width: '100%' }}>
      <Paper
        {...getRootProps()}
        variant="outlined"
        sx={{
          p: 3,
          textAlign: 'center',
          cursor: disabled ? 'default' : 'pointer',
          bgcolor: isDragActive ? 'action.hover' : 'transparent',
          borderColor: isDragActive ? 'primary.main' : 'divider',
          borderStyle: 'dashed',
          borderWidth: 2,
          transition: 'border-color 0.2s, background-color 0.2s',
          opacity: disabled ? 0.6 : 1,
          '&:hover': disabled ? {} : {
            borderColor: 'primary.main',
            bgcolor: 'action.hover',
          },
        }}
      >
        <input {...getInputProps()} />
        <CloudUpload
          size={32}
          color={isDragActive ? theme.palette.primary.main : theme.palette.text.secondary}
          style={{ marginBottom: 8 }}
        />
        <Typography variant="body1" color="text.primary" sx={{ fontWeight: 500 }}>
          {isDragActive ? 'Drop PDFs here' : 'Drag & Drop PDFs or click to browse'}
        </Typography>
      </Paper>

      {files.length > 0 && (
        <Box sx={{ mt: 1.5, display: 'flex', flexWrap: 'wrap', gap: 1, justifyContent: 'center' }}>
          {files.map((file, idx) => (
            <Chip
              key={`${file.name}-${idx}`}
              icon={<FileText size={16} />}
              label={
                <Typography noWrap sx={{ maxWidth: 220, fontSize: '0.85rem' }}>
                  {file.name}
                </Typography>
              }
              onDelete={disabled ? undefined : () => onFileRemoved(file)}
              deleteIcon={<X size={16} />}
              variant="outlined"
              color="primary"
              sx={{
                borderRadius: 2,
                pl: 1,
                py: 2.5,
                bgcolor: (t) => `${t.palette.primary.main}14`,
                borderColor: (t) => `${t.palette.primary.main}4D`,
              }}
            />
          ))}
        </Box>
      )}
    </Box>
  );
}
