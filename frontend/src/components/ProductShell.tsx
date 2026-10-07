import { useEffect, useMemo, useState } from 'react';
import { Box, IconButton, Tab, Tabs, TextField, Tooltip, Typography } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';

import { colors } from '../design-system/colors';
import zoroIcon from '../assets/sword.png';
import { api } from '../services/api';
import { DirectoryPickerModal } from './DirectoryPickerModal';
import { KnowledgeBaseTab } from './KnowledgeBase/KnowledgeBaseTab';
import { VisualizationTab } from './Visualization/VisualizationTab';

function ProjectRootControl() {
  const [path, setPath] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getProjectRoot()
      .then((res) => {
        if (res.success && res.path) setPath(res.path);
      })
      .catch(() => {
        /* non-fatal — control just stays blank */
      });
  }, []);

  const startEditing = () => {
    setDraft(path ?? '');
    setError(null);
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setError(null);
  };

  const applyNewPath = async (newPath: string) => {
    setSaving(true);
    setError(null);
    try {
      const res = await api.setProjectRoot(newPath);
      if (res.success && res.path) {
        setPath(res.path);
        setIsEditing(false);
        setPickerOpen(false);
        // Every list/session in the app is scoped to the project root —
        // reload so all of it (sessions, plan, rules) re-fetches fresh
        // against the new project instead of trying to patch each piece
        // of state that implicitly depended on the old one.
        window.location.reload();
      } else {
        setError(res.error || 'Failed to switch project');
      }
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || 'Failed to switch project');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      {isEditing ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flex: 1, minWidth: 0 }}>
          <TextField
            size="small"
            autoFocus
            fullWidth
            placeholder="/absolute/path/to/project"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') applyNewPath(draft.trim());
              if (e.key === 'Escape') cancelEditing();
            }}
            error={Boolean(error)}
            helperText={error ?? undefined}
            disabled={saving}
            sx={{ '& .MuiInputBase-input': { fontSize: '0.8rem', fontFamily: 'monospace' } }}
          />
          <IconButton size="small" onClick={() => applyNewPath(draft.trim())} disabled={saving} aria-label="Save project directory">
            <CheckIcon fontSize="small" sx={{ color: colors.green }} />
          </IconButton>
          <IconButton size="small" onClick={cancelEditing} disabled={saving} aria-label="Cancel">
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0 }}>
          <Typography
            noWrap
            title={path ?? undefined}
            sx={{ fontSize: '0.8rem', fontFamily: 'monospace', color: colors.grey, maxWidth: 380 }}
          >
            {path ?? 'Loading project directory…'}
          </Typography>
          <Tooltip title="Choose project directory">
            <IconButton size="small" onClick={() => setPickerOpen(true)} aria-label="Choose project directory">
              <FolderOpenIcon fontSize="small" sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Type project directory">
            <IconButton size="small" onClick={startEditing} aria-label="Type project directory">
              <EditIcon fontSize="small" sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      <DirectoryPickerModal
        open={pickerOpen}
        initialPath={path}
        onClose={() => setPickerOpen(false)}
        onSelect={applyNewPath}
      />
    </>
  );
}

export function ProductShell() {
  const [tabIndex, setTabIndex] = useState(0);
  const visibleTabs = useMemo(
    () => [
      { key: 'visualization', label: 'Visualization' },
      { key: 'knowledge-base', label: 'Rules Management' },
    ],
    []
  );

  return (
    <Box
      sx={{
        height: '100vh',
        width: '100vw',
        display: 'flex',
        flexDirection: 'column',
        m: 0,
        p: 0,
        bgcolor: colors.surface,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, pt: 2, px: 2, pb: 1, flexShrink: 0 }}>
        <img src={zoroIcon} alt="ZORO" style={{ width: 44, height: 44 }} />
        <Typography
          sx={{
            fontFamily: '"SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
            fontWeight: 800,
            fontSize: '1.7rem',
            letterSpacing: '0.04em',
            lineHeight: 1,
          }}
        >
          ZORO
        </Typography>
        <Box sx={{ flex: 1 }} />
        <ProjectRootControl />
      </Box>

      <Tabs
        value={tabIndex}
        onChange={(_, nextValue) => setTabIndex(nextValue)}
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          flexShrink: 0,
          '& .MuiTab-root': {
            color: colors.grey,
            minHeight: 48,
            textTransform: 'none',
            fontWeight: 600,
            '&:focus': {
              outline: 'none',
            },
            '&.Mui-focusVisible': {
              outline: 'none',
              backgroundColor: 'transparent',
            },
          },
          '& .Mui-selected': {
            color: `${colors.green} !important`,
          },
          '& .MuiTabs-indicator': {
            backgroundColor: colors.green,
          },
        }}
      >
        {visibleTabs.map((tab) => (
          <Tab key={tab.key} label={tab.label} disableRipple />
        ))}
      </Tabs>

      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {visibleTabs[tabIndex]?.key === 'visualization' && <VisualizationTab />}
        {visibleTabs[tabIndex]?.key === 'knowledge-base' && <KnowledgeBaseTab />}
      </Box>
    </Box>
  );
}
