import { useState } from 'react';
import { Box, Typography } from '@mui/material';
import { api } from '../../services/api';
import { Button } from '../../design-system/Button';
import { colors } from '../../design-system/colors';
import type { FileInfo } from '../../types/knowledge';

interface FileCardProps {
  file: FileInfo;
  onProcess: () => void;
}

export const FileCard: React.FC<FileCardProps> = ({ file, onProcess }) => {
  const [processing, setProcessing] = useState(false);

  const handleProcess = async () => {
    setProcessing(true);
    try {
      const response = await api.processKBFiles([file.filename]);
      
      if (response.success && response.newly_added_ids) {
        window.dispatchEvent(new CustomEvent('kb-process-complete', {
          detail: {
            newly_added_ids: response.newly_added_ids,
            total_added: response.total_added
          }
        }));
      }
      
      onProcess();
    } catch (error) {
      console.error('Failed to process file:', error);
    } finally {
      setProcessing(false);
    }
  };

  const progress = file.total_items > 0 ? (file.processed / file.total_items) * 100 : 0;

  return (
    <Box
      sx={{
        border: '1px solid #ddd',
        padding: '12px',
        marginBottom: '8px',
        borderRadius: '4px',
      }}
    >
      <Typography sx={{ fontWeight: 'bold', marginBottom: '8px', fontSize: '11px' }}>
        {file.filename}
      </Typography>

      <Box
        sx={{
          height: '4px',
          background: '#f0f0f0',
          borderRadius: '2px',
          marginBottom: '8px',
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            width: `${progress}%`,
            height: '100%',
            background: colors.green,
            borderRadius: '2px',
            transition: 'width 0.3s',
          }}
        />
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography sx={{ fontSize: '12px', color: colors.grey }}>
          {file.processed} / {file.total_items}
        </Typography>
        {file.pending > 0 && (
          <Box
            sx={{
              background: colors.green,
              color: 'white',
              padding: '2px 8px',
              borderRadius: '12px',
              fontSize: '12px',
            }}
          >
            {file.pending} pending
          </Box>
        )}
      </Box>

      {file.pending > 0 && (
        <Button
          onClick={handleProcess}
          disabled={processing}
          sx={{ marginTop: '8px', width: '100%', fontSize: '12px' }}
        >
          {processing ? 'Processing...' : 'Structure'}
        </Button>
      )}
    </Box>
  );
};