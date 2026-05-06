import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Radio,
  RadioGroup,
  FormControlLabel,
  Chip,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CheckIcon from '@mui/icons-material/Check';
import { alpha } from '@mui/material/styles';
import { CompactIconButton } from '../../design-system/CompactIconButton';
import { colors } from '../../design-system/colors';
import { api } from '../../services/api';

interface Rule {
  category: string;
  text: string;
  context?: string;
  evidence?: string;
  confidence?: number;
  decay?: number;
  reasoning?: string;
  context_match?: number;
  relevance_score?: number;
}

interface RuleConflict {
  conflict_id: string;
  rule_item_ids: string[];
  rule_indices: { [key: string]: number[] };
  explanation: string;
  severity: 'low' | 'medium' | 'high';
  resolved: boolean;
  chosen_rule_index?: number;
  resolved_at?: string;
}

interface ConflictResolutionModalProps {
  open: boolean;
  onClose: () => void;
  chatId: string;
  itemId: string;
  conflict: RuleConflict;
  rules: Rule[];
  onResolved: () => void;
}

export function ConflictResolutionModal({
  open,
  onClose,
  chatId,
  itemId,
  conflict,
  rules,
  onResolved,
}: ConflictResolutionModalProps) {
  const [selectedRuleIndex, setSelectedRuleIndex] = useState<number | null>(null);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const conflictRuleIndices = conflict.rule_indices[itemId] || [];
  const conflictingRules = conflictRuleIndices.map(idx => rules[idx]).filter(Boolean);

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return colors.red;
      case 'medium': return colors.gold;
      case 'low': return colors.blue;
      default: return colors.grey;
    }
  };

  const handleResolve = async () => {
    if (selectedRuleIndex === null) {
      setError('Please select a rule to keep');
      return;
    }

    setResolving(true);
    setError(null);

    try {
      const result = await api.resolveConflict(
        chatId,
        itemId,
        conflict.conflict_id,
        selectedRuleIndex
      );

      if (result.success) {
        onResolved();
        onClose();
      } else {
        setError('Failed to resolve conflict');
      }
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to resolve conflict');
    } finally {
      setResolving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: colors.surfaceDark,
          color: colors.textOnDark,
        }
      }}
    >
      <DialogTitle sx={{ borderBottom: `1px solid ${colors.grey}` }}>
        <Box display="flex" alignItems="center" gap={1}>
          <Typography variant="h6">⚠️ Resolve Rule Conflict</Typography>
          <Chip
            label={conflict.severity.toUpperCase()}
            size="small"
            sx={{
              bgcolor: getSeverityColor(conflict.severity),
              color: colors.white,
              fontWeight: 'bold',
            }}
          />
        </Box>
      </DialogTitle>

      <DialogContent sx={{ mt: 2 }}>
        <Box mb={3}>
          <Typography variant="subtitle2" color={colors.gold} gutterBottom>
            Why these rules conflict:
          </Typography>
          <Typography variant="body2" sx={{ color: colors.textMutedOnDark }}>
            {conflict.explanation}
          </Typography>
        </Box>

        <Typography variant="subtitle2" color={colors.green} gutterBottom>
          Select which rule to keep:
        </Typography>

        <RadioGroup
          value={selectedRuleIndex !== null ? selectedRuleIndex : ''}
          onChange={(e) => setSelectedRuleIndex(Number(e.target.value))}
        >
          {conflictingRules.map((rule, idx) => {
            const actualIndex = conflictRuleIndices[idx];
            return (
              <Box
                key={actualIndex}
                sx={{
                  border: `1px solid ${selectedRuleIndex === actualIndex ? colors.green : colors.grey}`,
                  borderRadius: 1,
                  p: 2,
                  mb: 2,
                  bgcolor: selectedRuleIndex === actualIndex ? alpha(colors.green, 0.1) : 'transparent',
                  cursor: 'pointer',
                }}
                onClick={() => setSelectedRuleIndex(actualIndex)}
              >
                <FormControlLabel
                  value={actualIndex}
                  control={
                    <Radio
                      sx={{
                        color: colors.grey,
                        '&.Mui-checked': { color: colors.green },
                      }}
                    />
                  }
                  label={
                    <Box>
                      <Box display="flex" alignItems="center" gap={1} mb={1}>
                        <Chip
                          label={rule.category}
                          size="small"
                          sx={{
                            bgcolor: colors.blue,
                            color: colors.white,
                            fontSize: '0.75rem',
                          }}
                        />
                        {rule.confidence !== undefined && (
                          <Typography variant="caption" color={colors.grey}>
                            Confidence: {(rule.confidence * 100).toFixed(0)}%
                          </Typography>
                        )}
                        {rule.decay !== undefined && (
                          <Typography variant="caption" color={colors.grey}>
                            Specificity: {rule.decay > 0.6 ? 'High' : 'General'}
                          </Typography>
                        )}
                      </Box>

                      <Typography variant="body2" sx={{ mb: 1 }}>
                        {rule.text}
                      </Typography>

                      {rule.reasoning && (
                        <Box mt={1} p={1} bgcolor={alpha(colors.black, 0.2)} borderRadius={1}>
                          <Typography variant="caption" color={colors.gold}>
                            Why this rule was selected:
                          </Typography>
                          <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                            {rule.reasoning}
                          </Typography>
                        </Box>
                      )}

                      {rule.context && (
                        <Box mt={1}>
                          <Typography variant="caption" color={colors.grey}>
                            Context: {rule.context}
                          </Typography>
                        </Box>
                      )}

                      {rule.evidence && (
                        <Box mt={1}>
                          <Typography variant="caption" color={colors.grey}>
                            Evidence: {rule.evidence}
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  }
                  sx={{ width: '100%', m: 0 }}
                />
              </Box>
            );
          })}
        </RadioGroup>

        {error && (
          <Box mt={2} p={2} bgcolor={`${colors.red}20`} borderRadius={1}>
            <Typography variant="body2" color={colors.red}>
              {error}
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ borderTop: `1px solid ${colors.grey}`, p: 2 }}>
        <CompactIconButton
          label="Cancel conflict resolution"
          icon={<CloseIcon sx={{ fontSize: 17 }} />}
          tone="grey"
          onClick={onClose}
          disabled={resolving}
        />
        <CompactIconButton
          label="Resolve rule conflict"
          icon={<CheckIcon sx={{ fontSize: 17 }} />}
          tone="green"
          onClick={handleResolve}
          disabled={selectedRuleIndex === null || resolving}
          loading={resolving}
        />
      </DialogActions>
    </Dialog>
  );
}
