import { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  CircularProgress,
} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import CloseIcon from '@mui/icons-material/Close';
import CheckIcon from '@mui/icons-material/Check';
import { CompactIconButton } from '../design-system/CompactIconButton';
import { colors } from '../design-system/colors';
import { api } from '../services/api';

interface DirectoryPickerModalProps {
  open: boolean;
  initialPath?: string | null;
  onClose: () => void;
  onSelect: (path: string) => void;
}

export function DirectoryPickerModal({ open, initialPath, onClose, onSelect }: DirectoryPickerModalProps) {
  const [currentPath, setCurrentPath] = useState<string | null>(null);
  const [parent, setParent] = useState<string | null>(null);
  const [directories, setDirectories] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((path?: string) => {
    setLoading(true);
    setError(null);
    api
      .browseDirectory(path)
      .then((res) => {
        if (res.success && res.path !== undefined) {
          setCurrentPath(res.path);
          setParent(res.parent ?? null);
          setDirectories(res.directories ?? []);
        } else {
          setError(res.error || 'Failed to browse directory');
        }
      })
      .catch((err) => {
        setError(err?.response?.data?.error || err?.message || 'Failed to browse directory');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (open) load(initialPath ?? undefined);
  }, [open, initialPath, load]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{ sx: { bgcolor: colors.surface, color: colors.text, height: 480 } }}
    >
      <DialogTitle sx={{ borderBottom: `1px solid ${colors.divider}` }}>
        <Typography variant="h6" sx={{ color: colors.text }}>
          Choose Project Directory
        </Typography>
        <Typography
          variant="caption"
          noWrap
          title={currentPath ?? undefined}
          sx={{ color: colors.grey, mt: 0.5, display: 'block', fontFamily: 'monospace' }}
        >
          {currentPath ?? 'Loading…'}
        </Typography>
      </DialogTitle>

      <DialogContent sx={{ p: 0, overflowY: 'auto' }}>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        )}

        {!loading && error && (
          <Box m={2} p={2} bgcolor={`${colors.red}20`} borderRadius={1}>
            <Typography variant="body2" color={colors.red}>
              {error}
            </Typography>
          </Box>
        )}

        {!loading && !error && (
          <List dense disablePadding>
            {parent && (
              <ListItemButton onClick={() => load(parent)}>
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <ArrowUpwardIcon fontSize="small" sx={{ color: colors.grey }} />
                </ListItemIcon>
                <ListItemText primary=".. (up one level)" />
              </ListItemButton>
            )}
            {directories.length === 0 && !parent && (
              <Box p={2}>
                <Typography variant="body2" sx={{ color: colors.grey }}>
                  No subdirectories here.
                </Typography>
              </Box>
            )}
            {directories.map((name) => (
              <ListItemButton
                key={name}
                onClick={() => load(currentPath ? `${currentPath}/${name}` : name)}
              >
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <FolderIcon fontSize="small" sx={{ color: colors.green }} />
                </ListItemIcon>
                <ListItemText primary={name} />
              </ListItemButton>
            ))}
          </List>
        )}
      </DialogContent>

      <DialogActions sx={{ borderTop: `1px solid ${colors.divider}`, p: 2 }}>
        <CompactIconButton label="Cancel" icon={<CloseIcon sx={{ fontSize: 17 }} />} tone="grey" onClick={onClose} />
        <CompactIconButton
          label="Select this folder"
          icon={<CheckIcon sx={{ fontSize: 17 }} />}
          tone="green"
          onClick={() => currentPath && onSelect(currentPath)}
          disabled={!currentPath || loading}
        />
      </DialogActions>
    </Dialog>
  );
}
