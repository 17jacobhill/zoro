import { useState } from 'react';
import { Box, Typography } from '@mui/material';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import { api } from '../../services/api';
import { CompactIconButton } from '../../design-system/CompactIconButton';
import { colors } from '../../design-system/colors';
import type { FileInfo } from '../../types/knowledge';

interface FileCardProps {
  file: FileInfo;
  onProcess: () => void;
}

export const FileCard: React.FC<FileCardProps> = ({ file, onProcess }) => {
  const [processing, setProcessing] = useState(false);
  const totalChunks = file.total_chunks ?? file.total_items ?? 0;
  const processedChunks = file.processed_chunks ?? file.processed ?? 0;
  const pendingChunks = file.pending_chunks ?? file.pending ?? 0;
  const processedPercent = typeof file.processed_percent === 'number'
    ? file.processed_percent
    : (totalChunks > 0 ? (processedChunks / totalChunks) * 100 : 0);
  const unprocessedPercent = typeof file.unprocessed_percent === 'number'
    ? file.unprocessed_percent
    : Math.max(0, 100 - processedPercent);
  const hasPending = pendingChunks > 0 || unprocessedPercent > 0.01;

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

  return (
    <Box
      sx={{
        border: `1px solid ${colors.divider}`,
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
          background: colors.surfaceNeutral,
          borderRadius: '2px',
          marginBottom: '8px',
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            width: `${Math.max(0, Math.min(100, processedPercent))}%`,
            height: '100%',
            background: colors.green,
            borderRadius: '2px',
            transition: 'width 0.3s',
          }}
        />
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography sx={{ fontSize: '12px', color: colors.grey }}>
          {processedPercent.toFixed(0)}% structured ({processedChunks}/{totalChunks} chunks)
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          {hasPending && (
            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.5,
                border: `1px solid ${colors.divider}`,
                background: colors.surface,
                color: colors.secondaryText,
                padding: '2px 8px',
                borderRadius: '999px',
                fontSize: '11px',
                fontWeight: 600,
              }}
            >
              <Box
                sx={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: colors.green,
                  flexShrink: 0,
                }}
              />
              {unprocessedPercent.toFixed(0)}% left
            </Box>
          )}
          {hasPending && (
            <CompactIconButton
              label={processing ? `Structuring ${file.filename}` : `Structure ${file.filename}`}
              icon={<AccountTreeOutlinedIcon sx={{ fontSize: 18 }} />}
              tone="green"
              onClick={handleProcess}
              loading={processing}
            />
          )}
        </Box>
      </Box>
    </Box>
  );
};
