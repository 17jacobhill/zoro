import { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Typography, Alert } from '@mui/material';
import ManageSearchOutlinedIcon from '@mui/icons-material/ManageSearchOutlined';
import DownloadDoneOutlinedIcon from '@mui/icons-material/DownloadDoneOutlined';
import { api } from '../../services/api';
import { colors } from '../../design-system/colors';
import { CompactIconButton } from '../../design-system/CompactIconButton';

interface RuleLearningPanelProps {
  chatId: string;
  visualizationStatus?: string;
}

interface LearnedRule {
  id?: string;
  title?: string;
  name?: string;
  rule?: string;
  content?: string;
  text?: string;
  description?: string;
  rationale?: string;
  category?: string;
  context?: string | null;
  evidence?: string | null;
  confidence?: number;
  decay?: number;
  confidence_reasoning?: string | null;
  decay_reasoning?: string | null;
}

function normalizeRuleSignature(rule: LearnedRule, index: number): string {
  const category = (rule.category || 'uncategorized').trim().toLowerCase();
  const text = (
    rule.text ||
    rule.content ||
    rule.description ||
    rule.rationale ||
    rule.rule ||
    rule.title ||
    rule.name ||
    `learned-rule-${index + 1}`
  ).trim().toLowerCase();
  return `${category}::${text}`;
}

export function RuleLearningPanel({ chatId, visualizationStatus = 'paused' }: RuleLearningPanelProps) {
  const [rules, setRules] = useState<LearnedRule[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [savingRuleKey, setSavingRuleKey] = useState<string | null>(null);
  const [savedRuleKeys, setSavedRuleKeys] = useState<string[]>([]);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [analysisState, setAnalysisState] = useState<{
    analyzed_tokens: number;
    analyzed_from_token: number;
    analyzed_to_token: number;
    remaining_tokens: number;
    total_clean_tokens: number;
    all_analyzed: boolean;
    can_analyze_more: boolean;
    updated_at?: string;
  } | null>(null);
  const autoAnalyzeKeyRef = useRef('');

  const loadRuleLearning = useCallback(async () => {
    try {
      const result = await api.getRuleLearning(chatId);
      if (result.success) {
        setRules(Array.isArray(result.rules) ? result.rules : []);
        setAnalysisState({
          analyzed_tokens: Number(result.analyzed_tokens || 0),
          analyzed_from_token: Number(result.analyzed_from_token || 0),
          analyzed_to_token: Number(result.analyzed_to_token || 0),
          remaining_tokens: Number(result.remaining_tokens || 0),
          total_clean_tokens: Number(result.total_clean_tokens || 0),
          all_analyzed: Boolean(result.all_analyzed),
          can_analyze_more: Boolean(result.can_analyze_more),
          updated_at: result.updated_at,
        });
        setError(null);
      } else {
        setError('Unable to load rule learning status');
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load rule learning status');
    } finally {
      setLoading(false);
    }
  }, [chatId]);

  const loadSavedRules = useCallback(async () => {
    try {
      const result = await api.fetchKBItems({ type: 'rule' });
      const items = Array.isArray(result.items) ? result.items : [];
      const signatures = items.map((item: any, index: number) =>
        normalizeRuleSignature(
          {
            category: item.category,
            content: item.content,
            title: item.title,
          },
          index
        )
      );
      setSavedRuleKeys(signatures);
    } catch (err) {
      console.error('Failed to load saved rules for learned-rule saving:', err);
    }
  }, []);

  useEffect(() => {
    autoAnalyzeKeyRef.current = '';
  }, [chatId]);

  useEffect(() => {
    void loadRuleLearning();
    const interval = window.setInterval(() => {
      void loadRuleLearning();
    }, 3000);
    return () => window.clearInterval(interval);
  }, [loadRuleLearning]);

  useEffect(() => {
    void loadSavedRules();

    const handleProcessComplete = () => {
      void loadSavedRules();
    };

    window.addEventListener('kb-process-complete', handleProcessComplete);
    return () => {
      window.removeEventListener('kb-process-complete', handleProcessComplete);
    };
  }, [loadSavedRules]);

  const getRuleTitle = (rule: any, index: number) =>
    rule?.title || rule?.name || rule?.rule || `Learned Rule ${index + 1}`;

  const getRuleBody = (rule: any) =>
    rule?.content || rule?.text || rule?.description || rule?.rationale || '';

  const handleAnalyze = useCallback(async () => {
    setAnalyzing(true);
    try {
      const result = await api.analyzeChatVisualization(chatId);
      if (!result.success) {
        throw new Error('Unable to analyze chat history');
      }
      setRules(Array.isArray(result.rules) ? result.rules : []);
      setAnalysisState({
        analyzed_tokens: Number(result.analyzed_tokens || 0),
        analyzed_from_token: Number(result.analyzed_from_token || 0),
        analyzed_to_token: Number(result.analyzed_to_token || 0),
        remaining_tokens: Number(result.remaining_tokens || 0),
        total_clean_tokens: Number(result.total_clean_tokens || 0),
        all_analyzed: Boolean(result.all_analyzed),
        can_analyze_more: !result.all_analyzed,
        updated_at: result.updated_at,
      });
      setError(null);
    } catch (err: any) {
      setError(err?.message || 'Failed to analyze rule learning state');
    } finally {
      setAnalyzing(false);
    }
  }, [chatId]);

  useEffect(() => {
    if (visualizationStatus !== 'polling' || analyzing || !analysisState?.can_analyze_more) return;
    if ((analysisState.total_clean_tokens || 0) <= 0) return;

    const requestKey = `${analysisState.analyzed_tokens}:${analysisState.total_clean_tokens}`;
    if (autoAnalyzeKeyRef.current === requestKey) return;

    autoAnalyzeKeyRef.current = requestKey;
    void handleAnalyze();
  }, [analysisState, analyzing, handleAnalyze, visualizationStatus]);

  const handleAcceptRule = async (rule: LearnedRule, index: number) => {
    const ruleKey = normalizeRuleSignature(rule, index);
    if (savedRuleKeys.includes(ruleKey)) return;

    const title = getRuleTitle(rule, index);
    const body = getRuleBody(rule) || title;
    setSavingRuleKey(ruleKey);
    setSaveMessage(null);
    try {
      const response = await api.createKBItem({
        type: 'rule',
        content: body,
        category: rule.category || 'workflow',
        title,
        context: rule.context ?? 'Accepted from the Rule Learning panel for future sessions.',
        evidence: rule.evidence ?? null,
        confidence: rule.confidence,
        decay: rule.decay,
        confidence_reasoning: rule.confidence_reasoning ?? null,
        decay_reasoning: rule.decay_reasoning ?? null,
        is_favorite: true,
      });

      const savedItemId = response?.item?.item_id;
      setSavedRuleKeys((prev) => Array.from(new Set([...prev, ruleKey])));
      setSaveMessage(`Saved "${title}" into Rules Management.`);
      await loadSavedRules();

      if (savedItemId) {
        window.dispatchEvent(new CustomEvent('kb-process-complete', {
          detail: {
            newly_added_ids: [savedItemId],
            total_added: 1,
          }
        }));
      }
    } catch (err: any) {
      console.error('Failed to save learned rule:', err);
      setError(err?.response?.data?.error || err?.message || 'Failed to save learned rule');
    } finally {
      setSavingRuleKey(null);
    }
  };

  const totalTokens = analysisState?.total_clean_tokens || 0;
  const analyzedTokens = analysisState?.analyzed_tokens || 0;
  const progressPercent =
    totalTokens > 0 ? Math.min(Math.round((analyzedTokens / totalTokens) * 100), 100) : 0;

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
          Rule Learning
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.25 }}>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            {visualizationStatus === 'polling' ? 'Auto during live run' : 'Auto resumes on Run'}
          </Typography>
          <CompactIconButton
            label={
              analyzing
                ? 'Analyzing latest transcript window'
                : analysisState?.can_analyze_more
                  ? 'Analyze next transcript window'
                  : 'Analyze rule learning now'
            }
            icon={<ManageSearchOutlinedIcon sx={{ fontSize: 18 }} />}
            tone="green"
            onClick={handleAnalyze}
            loading={analyzing}
          />
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 1.25 }}>
            {error}
          </Alert>
        )}

        {saveMessage && (
          <Alert severity="success" sx={{ mb: 1.25 }}>
            {saveMessage}
          </Alert>
        )}

        <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', mb: 0.8 }}>
          {totalTokens > 0
            ? `Analyzed ${analyzedTokens}/${totalTokens} tokens (${progressPercent}%)`
            : 'Waiting for transcript'}
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.9 }}>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 700 }}>
            Learned Rules ({rules.length})
          </Typography>
          {analysisState?.all_analyzed && totalTokens > 0 && (
            <Typography variant="caption" sx={{ color: colors.successText }}>
              Up to date
            </Typography>
          )}
        </Box>

        {loading && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.8 }}>
            Refreshing learning signal...
          </Typography>
        )}

        {rules.length === 0 ? (
          <Box sx={{ p: 1.4, border: '1px solid', borderColor: 'divider', borderRadius: 1, backgroundColor: colors.surfaceSubtle }}>
            <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
              {visualizationStatus === 'polling'
                ? 'No learned rules yet. Keep the run active or use Analyze now.'
                : 'No learned rules yet. Start a run or click Analyze now.'}
            </Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {rules.map((rule, index) => {
              const ruleKey = String(rule?.id || `${index}-${getRuleTitle(rule, index)}`);
              const normalizedRuleKey = normalizeRuleSignature(rule, index);
              const alreadySaved = savedRuleKeys.includes(normalizedRuleKey);
              return (
                <Box
                  key={ruleKey}
                  sx={{
                    p: 1.1,
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    backgroundColor: colors.surface,
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.9 }}>
                    <Box
                      sx={{
                        width: 26,
                        height: 26,
                        border: '1px solid',
                        borderColor: 'divider',
                        borderRadius: 0.8,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: alreadySaved ? colors.successText : colors.grey,
                        fontSize: '0.85rem',
                        fontWeight: 700,
                        flexShrink: 0,
                      }}
                    >
                      {alreadySaved ? '✓' : '•'}
                    </Box>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="caption" sx={{ display: 'block', fontWeight: 700 }}>
                        {getRuleTitle(rule, index)}
                      </Typography>
                      {rule.category && (
                        <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', fontSize: '0.66rem', mb: 0.35 }}>
                          {rule.category}
                        </Typography>
                      )}
                      <Typography variant="caption" sx={{ display: 'block', whiteSpace: 'pre-wrap', lineHeight: 1.35 }}>
                        {getRuleBody(rule) || 'No detail provided.'}
                      </Typography>
                      {rule.confidence_reasoning && (
                        <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', mt: 0.4, lineHeight: 1.35 }}>
                          Reasoning: {rule.confidence_reasoning}
                        </Typography>
                      )}
                    </Box>
                    <CompactIconButton
                      label={alreadySaved ? 'Already saved in Rules Management' : `Accept ${getRuleTitle(rule, index)}`}
                      icon={<DownloadDoneOutlinedIcon sx={{ fontSize: 17 }} />}
                      tone={alreadySaved ? 'grey' : 'green'}
                      onClick={() => handleAcceptRule(rule, index)}
                      disabled={alreadySaved}
                      loading={savingRuleKey === normalizedRuleKey}
                    />
                  </Box>
                </Box>
              );
            })}
          </Box>
        )}
      </Box>
    </Box>
  );
}
