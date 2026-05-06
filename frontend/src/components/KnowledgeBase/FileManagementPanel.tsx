import { useState, useEffect } from 'react';
import { Alert, Box, Typography, CircularProgress } from '@mui/material';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import { api } from '../../services/api';
import { FileCard } from './FileCard';
import { CompactIconButton } from '../../design-system/CompactIconButton';
import { colors } from '../../design-system/colors';
import { PanelHeader } from '../../design-system/PanelHeader';
import type { FileInfo } from '../../types/knowledge';

export const FileManagementPanel: React.FC = () => {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [importingRepoAgents, setImportingRepoAgents] = useState(false);
  const [totalUnprocessedPercent, setTotalUnprocessedPercent] = useState(0);
  const [repoAgentsStatus, setRepoAgentsStatus] = useState<{ severity: 'success' | 'error'; message: string } | null>(null);

  const hasPendingWork = (file: FileInfo): boolean => {
    const pendingChunks = file.pending_chunks ?? file.pending ?? 0;
    const unprocessedPercent = file.unprocessed_percent;
    if (typeof unprocessedPercent === 'number') {
      return unprocessedPercent > 0.01;
    }
    return pendingChunks > 0;
  };

  const loadFiles = async () => {
    setLoading(true);
    try {
      const data = await api.fetchPendingFiles();
      setFiles(data.files || []);
      setTotalUnprocessedPercent(typeof data.total_unprocessed_percent === 'number' ? data.total_unprocessed_percent : 0);
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
    const pendingFiles = files.filter(hasPendingWork);
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

  const handleImportRepoAgents = async () => {
    setImportingRepoAgents(true);
    setRepoAgentsStatus(null);
    try {
      const response = await api.importRepoAgents();
      if (response.success) {
        if (response.newly_added_ids?.length) {
          window.dispatchEvent(new CustomEvent('kb-process-complete', {
            detail: {
              newly_added_ids: response.newly_added_ids,
              total_added: response.items_added,
            }
          }));
        }
        setRepoAgentsStatus({
          severity: 'success',
          message: response.message || `Structured repo ${response.filename} into Rules Management.`,
        });
        await loadFiles();
        return;
      }

      setRepoAgentsStatus({
        severity: 'error',
        message: response.error || 'Failed to structure repo AGENTS.md.',
      });
    } catch (error: any) {
      console.error('Failed to import repo AGENTS.md:', error);
      setRepoAgentsStatus({
        severity: 'error',
        message: error?.response?.data?.error || error?.message || 'Failed to structure repo AGENTS.md.',
      });
    } finally {
      setImportingRepoAgents(false);
    }
  };

  const hasPending = files.some(hasPendingWork);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <PanelHeader title="Unstructured Files" />
      <Typography sx={{ fontSize: '0.7rem', color: colors.grey, mb: 1 }}>
        {totalUnprocessedPercent.toFixed(1)}% of unstructured content is still unstructured.
      </Typography>

      <Box
        sx={{
          mb: 1.5,
          p: 1.25,
          border: `1px dashed ${colors.dividerStrong}`,
          borderRadius: 1.5,
          backgroundColor: colors.surfaceSubtle,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1, mb: 0.35 }}>
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: colors.text }}>
            Repo Instructions
          </Typography>
          <CompactIconButton
            label={importingRepoAgents ? 'Structuring repo AGENTS.md' : 'Structure repo AGENTS.md'}
            icon={<DescriptionOutlinedIcon sx={{ fontSize: 18 }} />}
            tone="green"
            onClick={handleImportRepoAgents}
            loading={importingRepoAgents}
          />
        </Box>
        <Typography sx={{ fontSize: '0.7rem', color: colors.grey, mb: 1 }}>
          Structure the current repo-root `AGENTS.md` directly into Rules Management without copying it into the unstructured staging area first.
        </Typography>
      </Box>

      {repoAgentsStatus && (
        <Alert severity={repoAgentsStatus.severity} sx={{ mb: 1.5 }}>
          {repoAgentsStatus.message}
        </Alert>
      )}

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
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <CompactIconButton
                label={processing ? 'Structuring all pending files' : 'Structure all pending files'}
                icon={<AccountTreeOutlinedIcon sx={{ fontSize: 18 }} />}
                tone="green"
                onClick={handleProcessAll}
                loading={processing}
              />
            </Box>
          )}
        </>
      )}
    </Box>
  );
};
