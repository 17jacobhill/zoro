import { useState, useEffect } from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
import { api } from '../../services/api';
import { FileCard } from './FileCard';
import { Button } from '../../design-system/Button';
import { colors } from '../../design-system/colors';
import type { FileInfo } from '../../types/knowledge';

export const FileManagementPanel: React.FC = () => {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);

  const loadFiles = async () => {
    setLoading(true);
    try {
      const data = await api.fetchPendingFiles();
      setFiles(data.files || []);
    } catch (error) {
      console.error('Failed to load files:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  const handleProcessAll = async () => {
    const pendingFiles = files.filter(f => f.pending > 0);
    if (pendingFiles.length === 0) return;

    setProcessing(true);
    try {
      const filenames = pendingFiles.map(f => f.filename);
      const response = await api.processKBFiles(filenames);
      
      if (response.success && response.newly_added_ids) {
        window.dispatchEvent(new CustomEvent('kb-process-complete', {
          detail: {
            newly_added_ids: response.newly_added_ids,
            total_added: response.total_added
          }
        }));
      }
      
      await loadFiles();
    } catch (error) {
      console.error('Failed to process files:', error);
    } finally {
      setProcessing(false);
    }
  };

  const hasPending = files.some(f => f.pending > 0);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Typography
        variant="body1"
        sx={{
          color: '#000',
          pb: 0.25,
          mb: 2,
          fontSize: '0.95rem',
          fontWeight: 600,
          lineHeight: 1.2,
        }}
      >
        Unstructured Files
      </Typography>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress size={24} sx={{ color: colors.green }} />
        </Box>
      ) : (
        <>
          <Box sx={{ flex: 1, overflow: 'auto', mb: 2 }}>
            {files.length === 0 ? (
              <Typography sx={{ color: colors.grey, textAlign: 'center', py: 3 }}>
                No unstructured files found
              </Typography>
            ) : (
              files.map(file => (
                <FileCard key={file.filename} file={file} onProcess={loadFiles} />
              ))
            )}
          </Box>

          {hasPending && (
            <Button
              onClick={handleProcessAll}
              disabled={processing}
              sx={{ width: '100%' }}
            >
              {processing ? 'Processing...' : 'Structure All Pending'}
            </Button>
          )}
        </>
      )}
    </Box>
  );
};
