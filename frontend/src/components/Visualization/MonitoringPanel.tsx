import { useState, useEffect } from 'react';
import { Box, Typography, Chip, Alert } from '@mui/material';
import { colors } from '../../design-system/colors';
import { api } from '../../services/api';

interface MonitoringPanelProps {
  chatId: string;
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
  saved_at?: string;
  resolved?: boolean;
}

export function MonitoringPanel({
  chatId,
}: MonitoringPanelProps) {
  const [supervisionHistory, setSupervisionHistory] = useState<SupervisionData[]>([]);
  const [supervisionError, setSupervisionError] = useState<string | null>(null);
  
  // Load existing supervision/enforcement data on mount
  useEffect(() => {
    const loadSupervision = async () => {
      try {
        const result = await api.getSupervision(chatId);
        if (result.success && result.supervision_history) {
          setSupervisionHistory(result.supervision_history);
        }
      } catch (error) {
        console.error('Failed to load supervision:', error);
      }
    };
    loadSupervision();
  }, [chatId]);

  const getPlanStatusColor = (status: string) => {
    switch (status) {
      case 'on_track': return colors.green;
      case 'needs_attention': return colors.gold;
      case 'blocked': return colors.red;
      default: return colors.grey;
    }
  };
  
  const latestSupervision =
    supervisionHistory.length > 0
      ? supervisionHistory[supervisionHistory.length - 1]
      : null;

  return (
    <Box sx={{ 
      flex: 1,
      minHeight: 0,
      display: 'flex', 
      flexDirection: 'column',
      p: 2,
      pb: 3,
      boxSizing: 'border-box',
      borderLeft: '1px solid #d0d0d0'
    }}>
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 'bold' }}>
          Supervisor
        </Typography>
        
        {/* Token Stats
        <Box sx={{ mb: 2 }}>
          ...
        </Box>
        */}

        {/* Error Messages */}
        {supervisionError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {supervisionError}
          </Alert>
        )}

        {!latestSupervision ? (
          <Box
            sx={{
              p: 2,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              backgroundColor: '#fafafa',
            }}
          >
            <Typography variant="body2" color="text.secondary">
              No supervisor signal yet. Click "Supervise" to begin.
            </Typography>
          </Box>
        ) : (
          <Box
            sx={{
              p: 2,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              backgroundColor: '#fafafa',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  backgroundColor: getPlanStatusColor(latestSupervision.status),
                  boxShadow: `0 0 0 4px ${getPlanStatusColor(latestSupervision.status)}22`,
                }}
              />
              <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
                STATUS
              </Typography>
              <Chip
                label={latestSupervision.status.replace('_', ' ').toUpperCase()}
                size="small"
                sx={{
                  backgroundColor: getPlanStatusColor(latestSupervision.status),
                  color: '#fff',
                  fontWeight: 'bold',
                  fontSize: '0.65rem',
                  ml: 'auto',
                }}
              />
            </Box>
            <Typography variant="body2" sx={{ mb: 1, fontWeight: 'bold' }}>
              {latestSupervision.summary}
            </Typography>
            {(latestSupervision.current_step || latestSupervision.expected_step) && (
              <Box sx={{ mb: 1, p: 1, backgroundColor: '#f0f7ff', borderRadius: 0.5, border: '1px solid #e3f2fd' }}>
                {latestSupervision.current_step && (
                  <Typography variant="caption" sx={{ display: 'block', fontSize: '0.7rem', mb: 0.25 }}>
                    Current: {latestSupervision.current_step}
                  </Typography>
                )}
                {latestSupervision.expected_step && (
                  <Typography variant="caption" sx={{ display: 'block', fontSize: '0.7rem', color: colors.gold }}>
                    Next expected: {latestSupervision.expected_step}
                  </Typography>
                )}
              </Box>
            )}
            {latestSupervision.blocker && (
              <Alert severity="error" sx={{ mb: 1, py: 0.5 }}>
                <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block' }}>
                  {latestSupervision.blocker.title}
                </Typography>
                <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
                  {latestSupervision.blocker.description}
                </Typography>
              </Alert>
            )}
            {latestSupervision.action_required && latestSupervision.action_required.length > 0 && (
              <Box sx={{ mt: 1, p: 1, backgroundColor: '#f5f5f5', borderRadius: 0.5 }}>
                <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block', mb: 0.5 }}>
                  Action required:
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
                  {latestSupervision.action_required.map((action, idx) => (
                    <Typography key={idx} variant="caption" sx={{ fontSize: '0.7rem' }}>
                      {action}
                    </Typography>
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
}
