import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogContentText, DialogTitle, IconButton, Pagination, Paper, Stack, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import { FileText, Trash2 } from 'lucide-react';
import {
  clearDocuments, deleteDocument, extractErrorMessage, fetchDocuments,
  type DocumentRecord,
} from '../services/api';

const PAGE_SIZE = 20;

function formatWhen(value: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString();
}

function formatSize(value: string | null): string {
  return value ? `${value} MB` : '—';
}

export default function DocumentHistory() {
  const [items, setItems] = useState<DocumentRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [confirmClear, setConfirmClear] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async (targetPage: number) => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchDocuments(PAGE_SIZE, (targetPage - 1) * PAGE_SIZE);
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load your history.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(page);
  }, [load, page]);

  const handleDelete = async (id: number) => {
    setBusyId(id);
    setError('');
    try {
      await deleteDocument(id);
      // Stepping back a page when the last row on it is removed avoids
      // landing on an empty page.
      const isLastOnPage = items.length === 1 && page > 1;
      if (isLastOnPage) setPage(page - 1);
      else await load(page);
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not delete that item.'));
    } finally {
      setBusyId(null);
    }
  };

  const handleClear = async () => {
    setConfirmClear(false);
    setLoading(true);
    setError('');
    try {
      await clearDocuments();
      setPage(1);
      await load(1);
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not clear your history.'));
      setLoading(false);
    }
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Box sx={{ maxWidth: 960, mx: 'auto', width: '100%', p: { xs: 2, sm: 3 } }}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>History</Typography>
          <Typography variant="body2" color="text.secondary">
            Files you have processed. Only metadata is kept — never the files themselves.
          </Typography>
        </Box>
        <Button
          color="error"
          variant="outlined"
          size="small"
          startIcon={<Trash2 size={16} />}
          disabled={loading || total === 0}
          onClick={() => setConfirmClear(true)}
        >
          Clear all
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress />
        </Box>
      ) : items.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: 'center' }}>
          <FileText size={32} style={{ opacity: 0.4 }} />
          <Typography sx={{ mt: 1.5, fontWeight: 500 }}>Nothing here yet</Typography>
          <Typography variant="body2" color="text.secondary">
            Process a PDF and it will show up here.
          </Typography>
        </Paper>
      ) : (
        <>
          <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>File</TableCell>
                  <TableCell>Operation</TableCell>
                  <TableCell align="right">Pages</TableCell>
                  <TableCell align="right">In</TableCell>
                  <TableCell align="right">Out</TableCell>
                  <TableCell>When</TableCell>
                  <TableCell align="right" />
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((doc) => (
                  <TableRow key={doc.id} hover>
                    <TableCell sx={{ maxWidth: 260, wordBreak: 'break-all' }}>
                      {doc.original_filename}
                    </TableCell>
                    <TableCell>{doc.operation_type}</TableCell>
                    <TableCell align="right">{doc.page_count ?? '—'}</TableCell>
                    <TableCell align="right">{formatSize(doc.input_size_mb)}</TableCell>
                    <TableCell align="right">{formatSize(doc.output_size_mb)}</TableCell>
                    <TableCell>{formatWhen(doc.created_at)}</TableCell>
                    <TableCell align="right">
                      <Tooltip title="Remove from history">
                        <span>
                          <IconButton
                            size="small"
                            disabled={busyId === doc.id}
                            onClick={() => void handleDelete(doc.id)}
                            aria-label={`Remove ${doc.original_filename} from history`}
                          >
                            <Trash2 size={16} />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {pageCount > 1 && (
            <Stack sx={{ alignItems: 'center', mt: 2 }}>
              <Pagination
                count={pageCount}
                page={page}
                onChange={(_, value) => setPage(value)}
                size="small"
              />
            </Stack>
          )}
        </>
      )}

      <Dialog open={confirmClear} onClose={() => setConfirmClear(false)}>
        <DialogTitle>Clear your history?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This removes all {total} {total === 1 ? 'entry' : 'entries'} from your history.
            It cannot be undone. Your files are not affected — they were never stored.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmClear(false)}>Cancel</Button>
          <Button color="error" onClick={() => void handleClear()}>Clear all</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
