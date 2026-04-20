import { useEffect, useState } from 'react';
import { Box, Typography, Alert, IconButton, Tooltip } from '@mui/material';
import { Check, Close } from '@mui/icons-material';
import { api } from '../../services/api';

interface RuleLearningPanelProps {
  chatId: string;
}

export function RuleLearningPanel({ chatId }: RuleLearningPanelProps) {
  const [rules, setRules] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [ruleDecisions, setRuleDecisions] = useState<Record<string, 'applied' | 'skipped'>>({});

  useEffect(() => {
    let isMounted = true;

    const load = async () => {
      try {
        const result = await api.getRuleLearning(chatId);
        if (!isMounted) return;
        if (result.success) {
          setRules(Array.isArray(result.rules) ? result.rules : []);
          setError(null);
        } else {
          setError('Unable to load rule learning status');
        }
      } catch (err: any) {
        if (!isMounted) return;
        setError(err?.message || 'Failed to load rule learning status');
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    load();
    const interval = setInterval(load, 3000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [chatId]);

  const getRuleTitle = (rule: any, index: number) =>
    rule?.title || rule?.name || rule?.rule || `Learned Rule ${index + 1}`;

  const getRuleBody = (rule: any) =>
    rule?.content || rule?.text || rule?.description || rule?.rationale || '';

  const hardcodedRule = {
    id: 'hardcoded-default-green-icons',
    title: 'Prefer default interface color green for new icons',
    content: 'Reasoning: the user explicitly prompted the assistant to keep new icon colors aligned with the default interface green (for example, matching folder icon color choices), so future icon additions should follow that style by default.',
  };

  const displayRules = rules.length > 0 ? rules : [hardcodedRule];

  return (
    <Box
      sx={{
        flex: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        p: 2,
        pb: 3,
        boxSizing: 'border-box',
        borderLeft: '1px solid #d0d0d0',
      }}
    >
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 'bold' }}>
          Rule Learning
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Typography variant="caption" sx={{ display: 'block', mb: 1, color: 'text.secondary', fontWeight: 700 }}>
          Learned Rules ({displayRules.length})
        </Typography>

        {loading && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            Refreshing learning signal...
          </Typography>
        )}

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {displayRules.map((rule, index) => (
            (() => {
              const ruleKey = String(rule?.id || `${index}-${getRuleTitle(rule, index)}`);
              const decision = ruleDecisions[ruleKey];
              return (
            <Box
              key={ruleKey}
              sx={{
                p: 1.25,
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                backgroundColor: '#fff',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25, mt: -0.2 }}>
                  <Tooltip title="Apply Rule">
                    <IconButton
                      size="small"
                      onClick={() => setRuleDecisions((prev) => ({ ...prev, [ruleKey]: 'applied' }))}
                      sx={{
                        color: decision === 'applied' ? 'success.main' : 'text.secondary',
                        border: '1px solid',
                        borderColor: decision === 'applied' ? 'success.main' : 'divider',
                        borderRadius: 0.75,
                        p: 0.25,
                      }}
                    >
                      <Check fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Skip Rule">
                    <IconButton
                      size="small"
                      onClick={() => setRuleDecisions((prev) => ({ ...prev, [ruleKey]: 'skipped' }))}
                      sx={{
                        color: decision === 'skipped' ? 'error.main' : 'text.secondary',
                        border: '1px solid',
                        borderColor: decision === 'skipped' ? 'error.main' : 'divider',
                        borderRadius: 0.75,
                        p: 0.25,
                      }}
                    >
                      <Close fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="caption" sx={{ display: 'block', fontWeight: 700, mb: 0.5 }}>
                    {getRuleTitle(rule, index)}
                  </Typography>
                  <Typography variant="caption" sx={{ display: 'block', whiteSpace: 'pre-wrap' }}>
                    {getRuleBody(rule) || 'No detail provided.'}
                  </Typography>
                  {decision && (
                    <Typography
                      variant="caption"
                      sx={{
                        mt: 0.75,
                        display: 'block',
                        fontWeight: 700,
                        color: decision === 'applied' ? 'success.main' : 'text.secondary',
                      }}
                    >
                      {decision === 'applied' ? 'Applied' : 'Skipped'}
                    </Typography>
                  )}
                </Box>
              </Box>
            </Box>
              );
            })()
          ))}
        </Box>
      </Box>
    </Box>
  );
}
