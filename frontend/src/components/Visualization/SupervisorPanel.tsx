import { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Typography, Chip, Alert } from '@mui/material';
import { colors } from '../../design-system/colors';
import { api } from '../../services/api';
import { Button } from '../../design-system/Button';

interface SupervisorPanelProps {
  chatId: string;
  visualizationStatus?: string;
}

interface SupervisionData {
  status: 'on_track' | 'needs_attention' | 'blocked';
  summary: string;
  current_step: string | null;
  expected_step: string | null;
  blocker?: {
    title: string;
    description: string;
  } | null;
  action_required: string[];
  timestamp: string;
  resolved?: boolean;
}

export function SupervisorPanel({
  chatId,
  visualizationStatus = 'paused',
}: SupervisorPanelProps) {
  const [supervisionHistory, setSupervisionHistory] = useState<SupervisionData[]>([]);
  const [supervisionError, setSupervisionError] = useState<string | null>(null);
  const [supervising, setSupervising] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [tokenStats, setTokenStats] = useState<{
    current_tokens: number;
    last_supervised_tokens: number;
    tokens_since_last: number;
    threshold: number;
    progress_percent: number;
  } | null>(null);
  const autoSupervisionKeyRef = useRef('');

  const loadSupervision = useCallback(async () => {
    try {
      const result = await api.getSupervision(chatId);
      if (result.success) {
        setSupervisionHistory(result.supervision_history || []);
        setTokenStats(result.token_stats || null);
        setSupervisionError(null);
      }
    } catch (error: any) {
      console.error('Failed to load supervision:', error);
      setSupervisionError(error?.message || 'Failed to load supervision');
    }
  }, [chatId]);

  useEffect(() => {
    autoSupervisionKeyRef.current = '';
  }, [chatId]);

  useEffect(() => {
    loadSupervision();
    const interval = window.setInterval(() => {
      void loadSupervision();
    }, 3000);
    return () => window.clearInterval(interval);
  }, [loadSupervision]);

  const getStatusColor = (status: SupervisionData['status']) => {
    switch (status) {
      case 'on_track':
        return colors.green;
      case 'needs_attention':
        return colors.gold;
      case 'blocked':
        return colors.red;
      default:
        return colors.grey;
    }
  };

  const latestSupervision =
    supervisionHistory.length > 0
      ? supervisionHistory[supervisionHistory.length - 1]
      : null;

  const handleSupervise = useCallback(async () => {
    setSupervising(true);
    try {
      await api.superviseChatVisualization(chatId);
      await loadSupervision();
    } catch (error: any) {
      console.error('Failed to supervise:', error);
      setSupervisionError(error?.message || 'Failed to supervise');
    } finally {
      setSupervising(false);
    }
  }, [chatId, loadSupervision]);

  const handleResolve = async () => {
    if (!latestSupervision?.timestamp) return;
    setResolving(true);
    try {
      const result = await api.resolveSupervision(chatId, latestSupervision.timestamp);
      if (!result.success) {
        throw new Error(result.error || 'Failed to resolve supervisor signal');
      }
      await loadSupervision();
    } catch (error: any) {
      console.error('Failed to resolve supervision:', error);
      setSupervisionError(error?.message || 'Failed to resolve supervision');
    } finally {
      setResolving(false);
    }
  };

  useEffect(() => {
    if (visualizationStatus !== 'polling' || supervising || !tokenStats) return;
    if (tokenStats.threshold <= 0 || tokenStats.tokens_since_last < tokenStats.threshold) return;

    const requestKey = `${tokenStats.current_tokens}:${tokenStats.last_supervised_tokens}`;
    if (autoSupervisionKeyRef.current === requestKey) return;

    autoSupervisionKeyRef.current = requestKey;
    void handleSupervise();
  }, [handleSupervise, supervising, tokenStats, visualizationStatus]);

  return (
    <Box
      sx={{
        flex: 1,
        height: '100%',
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        p: 2,
        pb: 3,
        boxSizing: 'border-box',
        borderLeft: `1px solid ${colors.dividerStrong}`,
      }}
    >
      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          overflowX: 'hidden',
          pr: 0.5,
          mr: -0.25,
          scrollbarWidth: 'thin',
          scrollbarColor: `${colors.dividerStrong} transparent`,
          '&::-webkit-scrollbar': {
            width: 8,
          },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: colors.dividerStrong,
            borderRadius: 8,
          },
          '&::-webkit-scrollbar-track': {
            backgroundColor: 'transparent',
          },
        }}
      >
        <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 700 }}>
          Supervisor
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.25 }}>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            {visualizationStatus === 'polling' ? 'Auto during live run' : 'Auto resumes on Run'}
          </Typography>
          <Button
            size="small"
            variant="outlined"
            onClick={handleSupervise}
            disabled={supervising}
            sx={{ fontSize: '0.7rem', px: 1.1, py: 0.25 }}
          >
            {supervising ? 'Running...' : 'Run Now'}
          </Button>
        </Box>

        {supervisionError && (
          <Alert severity="error" sx={{ mb: 1.25 }}>
            {supervisionError}
          </Alert>
        )}

        {!latestSupervision ? (
          <Box
            sx={{
              p: 1.5,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              backgroundColor: colors.surfaceSubtle,
            }}
          >
            <Typography variant="body2" color="text.secondary">
              No supervisor signal yet.
            </Typography>
          </Box>
        ) : (
          <Box
            sx={{
              p: 1.5,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              backgroundColor: colors.surfaceSubtle,
              mb: 1.1,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Box
                sx={{
                  width: 9,
                  height: 9,
                  borderRadius: '50%',
                  backgroundColor: getStatusColor(latestSupervision.status),
                }}
              />
              <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
                STATUS
              </Typography>
              <Chip
                label={latestSupervision.status.replace('_', ' ').toUpperCase()}
                size="small"
                sx={{
                  ml: 'auto',
                  fontSize: '0.65rem',
                  height: 22,
                  color: colors.white,
                  backgroundColor: getStatusColor(latestSupervision.status),
                  fontWeight: 700,
                }}
              />
            </Box>

            <Typography variant="body2" sx={{ mb: 1.1, fontWeight: 700, lineHeight: 1.35 }}>
              {latestSupervision.summary}
            </Typography>

            {(latestSupervision.current_step || latestSupervision.expected_step) && (
              <Box
                sx={{
                  p: 1,
                  border: '1px solid',
                  borderColor: colors.surfaceInfoBorder,
                  borderRadius: 0.75,
                  backgroundColor: colors.surfaceInfo,
                }}
              >
                {latestSupervision.current_step && (
                  <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', mb: 0.2 }}>
                    Current: {latestSupervision.current_step}
                  </Typography>
                )}
                {latestSupervision.expected_step && (
                  <Typography variant="caption" sx={{ display: 'block', color: colors.warningTextStrong }}>
                    Next expected: {latestSupervision.expected_step}
                  </Typography>
                )}
              </Box>
            )}

            {!latestSupervision.resolved && (
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 0.8 }}>
                <Button
                  size="small"
                  variant="text"
                  onClick={handleResolve}
                  disabled={resolving}
                  sx={{ fontSize: '0.68rem', minWidth: 'unset', px: 0.2, py: 0.15 }}
                >
                  {resolving ? 'Resolving...' : 'Mark resolved'}
                </Button>
              </Box>
            )}
          </Box>
        )}

        {latestSupervision?.blocker && (
          <Alert severity="error" sx={{ mb: 1.1 }}>
            <Typography variant="caption" sx={{ fontWeight: 700, display: 'block' }}>
              {latestSupervision.blocker.title}
            </Typography>
            <Typography variant="caption">
              {latestSupervision.blocker.description}
            </Typography>
          </Alert>
        )}

        {latestSupervision?.action_required && latestSupervision.action_required.length > 0 && (
          <Box
            sx={{
              p: 1.1,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              backgroundColor: colors.surface,
              mb: 1.1,
            }}
          >
            <Typography variant="caption" sx={{ display: 'block', fontWeight: 700, mb: 0.3, color: 'text.secondary' }}>
              Action required
            </Typography>
            {latestSupervision.action_required.slice(0, 2).map((action, idx) => (
              <Typography key={idx} variant="caption" sx={{ display: 'block' }}>
                {action}
              </Typography>
            ))}
          </Box>
        )}

        {tokenStats && (
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Coverage: {tokenStats.tokens_since_last}/{tokenStats.threshold} tokens since last supervision
          </Typography>
        )}
      </Box>
    </Box>
  );
}
