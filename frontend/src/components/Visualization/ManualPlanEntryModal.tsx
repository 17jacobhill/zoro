import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import { CompactIconButton } from '../../design-system/CompactIconButton';
import { TextField } from '../../design-system/TextField';
import { colors } from '../../design-system/colors';

interface ManualPlanEntryModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (content: string) => Promise<void>;
}

export function ManualPlanEntryModal({
  open,
  onClose,
  onSubmit,
}: ManualPlanEntryModalProps) {
  const [content, setContent] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClose = () => {
    if (!isExtracting) {
      setContent('');
      setError(null);
      onClose();
    }
  };

  const handleSubmit = async () => {
    if (content.trim().length < 50) {
      setError('Please enter at least 50 characters');
      return;
    }

    setIsExtracting(true);
    setError(null);

    try {
      await onSubmit(content);
      setContent('');
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve plan');
    } finally {
      setIsExtracting(false);
    }
  };

  const charCount = content.length;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: colors.surface,
          color: colors.text,
        }
      }}
    >
      <DialogTitle sx={{ borderBottom: `1px solid ${colors.divider}` }}>
        <Typography variant="h6" sx={{ color: colors.text }}>
          Manual Plan Entry
        </Typography>
        <Typography variant="caption" sx={{ color: colors.grey, mt: 0.5, display: 'block' }}>
          Paste your plan text below. The LLM will retrieve it for you.
        </Typography>
      </DialogTitle>

      <DialogContent sx={{ mt: 2 }}>
        <TextField
          multiline
          rows={12}
          fullWidth
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Paste your plan here..."
          disabled={isExtracting}
          sx={{
            '& .MuiInputBase-root': {
              fontFamily: 'monospace',
              fontSize: '12px',
            }
          }}
        />

        <Box sx={{ mt: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="caption" sx={{ color: colors.grey }}>
            {charCount} characters
          </Typography>
          {charCount > 0 && charCount < 50 && (
            <Typography variant="caption" sx={{ color: colors.red }}>
              Minimum 50 characters required
            </Typography>
          )}
        </Box>

        {error && (
          <Box mt={2} p={2} bgcolor={`${colors.red}20`} borderRadius={1}>
            <Typography variant="body2" color={colors.red}>
              {error}
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ borderTop: `1px solid ${colors.divider}`, p: 2 }}>
        <CompactIconButton
          label="Cancel manual plan entry"
          icon={<CloseIcon sx={{ fontSize: 17 }} />}
          tone="grey"
          onClick={handleClose}
          disabled={isExtracting}
        />
        <CompactIconButton
          label="Retrieve plan from pasted text"
          icon={<AutoFixHighIcon sx={{ fontSize: 17 }} />}
          tone="green"
          onClick={handleSubmit}
          disabled={isExtracting || content.trim().length < 50}
          loading={isExtracting}
        />
      </DialogActions>
    </Dialog>
  );
}
