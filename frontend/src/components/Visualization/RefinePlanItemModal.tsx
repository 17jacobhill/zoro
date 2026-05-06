import { useState } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Box, Typography, Alert } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import { TextField } from '../../design-system/TextField';
import { CompactIconButton } from '../../design-system/CompactIconButton';
import { colors } from '../../design-system/colors';

interface RefinePlanItemModalProps {
  open: boolean;
  onClose: () => void;
  itemTitle: string;
  onSubmit: (guidance: string) => Promise<void>;
}

export function RefinePlanItemModal({ open, onClose, itemTitle, onSubmit }: RefinePlanItemModalProps) {
  const [guidance, setGuidance] = useState('');
  const [loading, setLoading] = useState(false);
  const [alert, setAlert] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const handleSubmit = async () => {
    if (!guidance.trim()) return;
    
    setLoading(true);
    setAlert(null);
    try {
      await onSubmit(guidance);
      setAlert({ type: 'success', message: 'Substeps refined successfully!' });
      setTimeout(() => {
        setGuidance('');
        setAlert(null);
        onClose();
      }, 2000);
    } catch (error) {
      console.error('Failed to refine substeps:', error);
      setAlert({ type: 'error', message: 'Failed to refine substeps. Please try again.' });
      setTimeout(() => setAlert(null), 3000);
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setGuidance('');
      setAlert(null);
      onClose();
    }
  };

  return (
    <Dialog 
      open={open} 
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
          border: `1px solid ${colors.green}`
        }
      }}
    >
      <DialogTitle>
        <Typography variant="h6" sx={{ color: colors.green, fontWeight: 'bold' }}>
          Refine & Enrich Substeps
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {itemTitle}
        </Typography>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 1 }}>
          {alert && (
            <Alert severity={alert.type} sx={{ mb: 2 }}>
              {alert.message}
            </Alert>
          )}
          <TextField
            fullWidth
            multiline
            rows={6}
            label="Guidance"
            placeholder="Describe how you want to refine the substeps..."
            value={guidance}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGuidance(e.target.value)}
            disabled={loading}
            autoFocus
          />
        </Box>
      </DialogContent>
      <DialogActions sx={{ p: 2, gap: 1 }}>
        <CompactIconButton
          label="Cancel refine substeps"
          icon={<CloseIcon sx={{ fontSize: 17 }} />}
          tone="grey"
          onClick={handleClose}
          disabled={loading}
        />
        <CompactIconButton
          label="Refine substeps"
          icon={<AutoFixHighIcon sx={{ fontSize: 17 }} />}
          tone="green"
          onClick={handleSubmit}
          disabled={!guidance.trim() || loading}
          loading={loading}
        />
      </DialogActions>
    </Dialog>
  );
}
