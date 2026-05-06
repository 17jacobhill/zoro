import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Tooltip,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CheckIcon from '@mui/icons-material/Check';
import StarIcon from '@mui/icons-material/Star';
import BoltIcon from '@mui/icons-material/Bolt';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ScienceIcon from '@mui/icons-material/Science';
import { ToggleOn, ToggleOff } from '@mui/icons-material';

import { CompactIconButton } from '../../design-system/CompactIconButton';
import { FormControl } from '../../design-system/FormControl';
import { InputLabel } from '../../design-system/InputLabel';
import { MenuItem } from '../../design-system/MenuItem';
import { TextField } from '../../design-system/TextField';
import { Select } from '../../design-system/Select';
import { colors } from '../../design-system/colors';
import { api } from '../../services/api';
import type { KnowledgeItem } from '../../types/knowledge';

interface AddRuleModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (item?: KnowledgeItem) => void;
  mode?: 'create' | 'edit';
  initialRule?: KnowledgeItem | null;
}

interface RefinedRule {
  title: string;
  content: string;
  confidence: number;
  decay: number;
  confidence_reasoning: string;
  decay_reasoning: string;
  context: string | null;
  evidence: string | null;
}

function toNullableText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function buildRefinedFromItem(item: KnowledgeItem | null | undefined): RefinedRule | null {
  if (!item) return null;
  return {
    title: item.title || '',
    content: item.content || '',
    confidence: item.confidence ?? 0.5,
    decay: item.decay ?? 0.5,
    confidence_reasoning: item.confidence_reasoning || '',
    decay_reasoning: item.decay_reasoning || '',
    context: item.context ?? null,
    evidence: item.evidence ?? null,
  };
}

export function AddRuleModal({
  open,
  onClose,
  onSuccess,
  mode = 'create',
  initialRule = null,
}: AddRuleModalProps) {
  const isEditMode = mode === 'edit' && !!initialRule;

  const [category, setCategory] = useState('');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [context, setContext] = useState('');
  const [evidence, setEvidence] = useState('');
  const [isStrict, setIsStrict] = useState(false);
  const [isTestable, setIsTestable] = useState(false);

  const [categories, setCategories] = useState<string[]>([]);
  const [isRefining, setIsRefining] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [refined, setRefined] = useState<RefinedRule | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applyInitialRule = (rule: KnowledgeItem | null | undefined) => {
    setCategory(rule?.category || '');
    setTitle(rule?.title || '');
    setContent(rule?.content || '');
    setContext(rule?.context || '');
    setEvidence(rule?.evidence || '');
    setIsStrict(Boolean(rule?.is_strict));
    setIsTestable(Boolean(rule?.is_strict && rule?.is_testable));
    setRefined(null);
    setError(null);
  };

  const resetForm = () => {
    if (isEditMode && initialRule) {
      applyInitialRule(initialRule);
      return;
    }

    setCategory('');
    setTitle('');
    setContent('');
    setContext('');
    setEvidence('');
    setIsStrict(false);
    setIsTestable(false);
    setRefined(null);
    setError(null);
  };

  useEffect(() => {
    if (!open) return;
    resetForm();
  }, [open, initialRule, mode]);

  useEffect(() => {
    if (!open) return;

    const loadCategories = async () => {
      try {
        const data = await api.fetchKBCategories();
        if (data.success && Array.isArray(data.categories)) {
          const next = Array.from(
            new Set(
              [...data.categories, initialRule?.category]
                .map((value) => String(value || '').trim())
                .filter(Boolean)
            )
          ).sort((a, b) => a.localeCompare(b));
          setCategories(next);
        } else {
          setCategories(initialRule?.category ? [initialRule.category] : []);
        }
      } catch (err) {
        console.error('Failed to load categories:', err);
        setCategories(initialRule?.category ? [initialRule.category] : []);
      }
    };

    loadCategories();
  }, [open, initialRule?.category]);

  const handleClose = () => {
    if (!isRefining && !isSaving) {
      onClose();
    }
  };

  const handleRefine = async () => {
    if (!title.trim() || !content.trim() || !category.trim()) {
      setError('Title, content, and category are required');
      return;
    }

    setIsRefining(true);
    setError(null);

    try {
      const data = await api.refineRule({
        rule_type: 'rule',
        category: category.trim(),
        title: title.trim(),
        content: content.trim(),
        context: toNullableText(context),
        evidence: toNullableText(evidence),
      });

      if (data.success && data.refined) {
        setRefined(data.refined);
      } else {
        setError(data.error || 'Failed to refine rule');
      }
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || 'Failed to refine rule');
    } finally {
      setIsRefining(false);
    }
  };

  const handleSave = async () => {
    if (!title.trim() || !content.trim() || !category.trim()) {
      setError('Title, content, and category are required');
      return;
    }

    if (!isEditMode && !refined) {
      setError('Please refine the rule before saving');
      return;
    }

    const payload = {
      type: 'rule',
      category: category.trim(),
      title: (refined?.title ?? title).trim(),
      content: (refined?.content ?? content).trim(),
      context: refined ? refined.context : toNullableText(context),
      evidence: refined ? refined.evidence : toNullableText(evidence),
      confidence: refined?.confidence ?? initialRule?.confidence ?? 0.5,
      decay: refined?.decay ?? initialRule?.decay ?? 0.5,
      confidence_reasoning: refined?.confidence_reasoning ?? initialRule?.confidence_reasoning ?? null,
      decay_reasoning: refined?.decay_reasoning ?? initialRule?.decay_reasoning ?? null,
      is_strict: isStrict,
      is_testable: isStrict && isTestable,
      is_favorite: initialRule?.is_favorite || false,
    };

    setIsSaving(true);
    setError(null);

    try {
      const response = isEditMode && initialRule?.item_id
        ? await api.updateKBItem(initialRule.item_id, payload)
        : await api.createKBItem(payload);

      if (!response.success || !response.item) {
        throw new Error(isEditMode ? 'Failed to update rule' : 'Failed to save rule');
      }

      const savedItem = response.item as KnowledgeItem;
      window.dispatchEvent(new CustomEvent('kb-process-complete', {
        detail: {
          newly_added_ids: isEditMode ? [] : [savedItem.item_id],
          total_added: isEditMode ? 0 : 1,
        },
      }));

      onSuccess(savedItem);
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || (isEditMode ? 'Failed to update rule' : 'Failed to save rule'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleRefinedFieldChange = (field: keyof RefinedRule, value: string) => {
    setRefined((prev) => {
      const baseline = prev || buildRefinedFromItem(initialRule) || {
        title: title.trim(),
        content: content.trim(),
        confidence: initialRule?.confidence ?? 0.5,
        decay: initialRule?.decay ?? 0.5,
        confidence_reasoning: initialRule?.confidence_reasoning || '',
        decay_reasoning: initialRule?.decay_reasoning || '',
        context: toNullableText(context),
        evidence: toNullableText(evidence),
      };

      if (field === 'context' || field === 'evidence') {
        return { ...baseline, [field]: value.trim() ? value : null };
      }

      return { ...baseline, [field]: value };
    });
  };

  const saveLabel = isEditMode ? 'Save Changes' : 'Save';
  const saveDisabled = isSaving || isRefining || !title.trim() || !content.trim() || !category.trim() || (!isEditMode && !refined);
  const modalTitle = isEditMode ? 'Edit Rule in Rules Management' : 'Add Rule to Rules Management';
  const modalSubtitle = isEditMode
    ? 'Edit rule details directly, optionally refine with AI, then save the updated rule.'
    : 'Enter rule details, refine with AI, then save.';
  const previewTitle = isEditMode ? 'Save Draft (Editable)' : 'Refined Rule (Editable)';

  const availableCategories = useMemo(
    () =>
      Array.from(
        new Set(
          [...categories, category]
            .map((value) => String(value || '').trim())
            .filter(Boolean)
        )
      ),
    [categories, category]
  );

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
          maxHeight: '90vh',
          borderRadius: 2,
        },
      }}
    >
      <DialogTitle sx={{ borderBottom: `1px solid ${colors.divider}`, pb: 1.25 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                width: 26,
                height: 26,
                borderRadius: '50%',
                bgcolor: colors.surfaceGreenSoft,
                color: colors.green,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <AutoAwesomeIcon sx={{ fontSize: 15 }} />
            </Box>
            <Typography variant="h6" sx={{ color: colors.text, fontWeight: 700, fontSize: '1rem' }}>
              {modalTitle}
            </Typography>
          </Box>
          <IconButton
            onClick={handleClose}
            disabled={isRefining || isSaving}
            size="small"
            disableRipple
            sx={{ color: colors.grey, mt: -0.25, mr: -0.5, '&:focus': { outline: 'none' } }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
        <Typography variant="caption" sx={{ color: colors.grey, mt: 0.6, display: 'block', fontSize: '0.72rem' }}>
          {modalSubtitle}
        </Typography>
      </DialogTitle>

      <DialogContent sx={{ mt: 0.5, overflow: 'auto', pt: 1.5 }}>
        <Box sx={{ mb: 2 }}>
          <Typography sx={{ fontWeight: 700, mb: 1.25, color: colors.grey, fontSize: '0.76rem', textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Rule Fields
          </Typography>

          <Box sx={{ display: 'flex', gap: 1.25, mb: 1.25 }}>
            <FormControl size="small" sx={{ flex: 1 }}>
              <InputLabel>Category</InputLabel>
              <Select
                value={category}
                label="Category"
                onChange={(e) => setCategory(e.target.value as string)}
                disabled={isRefining || isSaving}
              >
                {availableCategories.map((cat) => (
                  <MenuItem key={cat} value={cat}>
                    {cat}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <TextField
              fullWidth
              size="small"
              label="Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isRefining || isSaving}
              sx={{ flex: 2 }}
            />
          </Box>

          <Box sx={{ mb: 1.25, display: 'flex', alignItems: 'center', gap: 1.25, flexWrap: 'wrap' }}>
            <Tooltip title={isStrict ? 'Remove strict enforcement' : 'Mark for strict enforcement'}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                <IconButton
                  size="small"
                  disableRipple
                  disabled={isRefining || isSaving}
                  onClick={() => {
                    const next = !isStrict;
                    setIsStrict(next);
                    if (!next) setIsTestable(false);
                  }}
                  sx={{
                    color: isStrict ? colors.green : colors.grey,
                    padding: '2px',
                    '&:focus': { outline: 'none' },
                  }}
                >
                  {isStrict ? <ToggleOn fontSize="small" /> : <ToggleOff fontSize="small" />}
                </IconButton>
                <Typography sx={{ fontSize: '11.5px', color: isStrict ? colors.green : colors.grey, fontWeight: 500 }}>
                  Strict
                </Typography>
              </Box>
            </Tooltip>
            <Tooltip title={!isStrict ? 'Mark as strict first to enable testing' : isTestable ? 'Remove testable marking' : 'Mark as testable (requires test evidence)'}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                <span>
                  <IconButton
                    size="small"
                    disableRipple
                    disabled={!isStrict || isRefining || isSaving}
                    onClick={() => setIsTestable(!isTestable)}
                    sx={{
                      color: isTestable ? colors.blue : colors.grey,
                      padding: '2px',
                      opacity: !isStrict ? 0.3 : 1,
                      '&:focus': { outline: 'none' },
                    }}
                  >
                    <ScienceIcon fontSize="small" />
                  </IconButton>
                </span>
                <Typography sx={{ fontSize: '11.5px', color: isTestable ? colors.blue : colors.grey, fontWeight: 500, opacity: !isStrict ? 0.6 : 1 }}>
                  Testable
                </Typography>
              </Box>
            </Tooltip>
          </Box>

          <TextField
            fullWidth
            multiline
            minRows={3}
            maxRows={6}
            label="Content"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            disabled={isRefining || isSaving}
            sx={{
              mb: 1.25,
              '& .MuiInputBase-inputMultiline': { lineHeight: 1.4 },
            }}
          />

          <TextField
            fullWidth
            multiline
            minRows={2}
            maxRows={4}
            label="Context (optional)"
            placeholder="What was being built..."
            value={context}
            onChange={(e) => setContext(e.target.value)}
            disabled={isRefining || isSaving}
            sx={{ mb: 1.25 }}
          />

          <TextField
            fullWidth
            multiline
            minRows={2}
            maxRows={4}
            label="Evidence (optional)"
            placeholder="Supporting quotes or examples..."
            value={evidence}
            onChange={(e) => setEvidence(e.target.value)}
            disabled={isRefining || isSaving}
            sx={{ mb: 1.5 }}
          />

          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 0.5 }}>
            <CompactIconButton
              label={isEditMode ? 'Refine draft with AI' : 'Refine rule with AI'}
              icon={<AutoAwesomeIcon sx={{ fontSize: 16 }} />}
              tone="green"
              onClick={handleRefine}
              disabled={isSaving || !title.trim() || !content.trim() || !category.trim()}
              loading={isRefining}
            />
            <CompactIconButton
              label={saveLabel}
              icon={<CheckIcon sx={{ fontSize: 16 }} />}
              tone="green"
              onClick={handleSave}
              disabled={saveDisabled}
              loading={isSaving}
            />
          </Box>
        </Box>

        {(refined || isEditMode) && (
          <Box sx={{ mt: 1 }}>
            <Divider sx={{ mb: 1.5 }} />
            <Typography sx={{ fontWeight: 700, mb: 1.25, color: colors.green, fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: 0.4 }}>
              {previewTitle}
            </Typography>

            <TextField
              fullWidth
              size="small"
              label={isEditMode ? 'Saved Title' : 'Refined Title'}
              value={(refined?.title ?? title)}
              onChange={(e) => {
                setTitle(e.target.value);
                handleRefinedFieldChange('title', e.target.value);
              }}
              disabled={isSaving}
              sx={{ mb: 1.25 }}
            />

            <TextField
              fullWidth
              multiline
              rows={4}
              label={isEditMode ? 'Saved Content' : 'Refined Content'}
              value={(refined?.content ?? content)}
              onChange={(e) => {
                setContent(e.target.value);
                handleRefinedFieldChange('content', e.target.value);
              }}
              disabled={isSaving}
              sx={{
                mb: 1.25,
                '& .MuiInputBase-inputMultiline': { lineHeight: 1.4 },
              }}
            />

            <Box sx={{ display: 'flex', gap: 1.25, mb: 1.25, flexWrap: 'wrap' }}>
              <Box>
                <Chip
                  icon={<StarIcon sx={{ fontSize: '14px !important', color: `${colors.white} !important` }} />}
                  label={`Confidence: ${(((refined?.confidence ?? initialRule?.confidence ?? 0.5) || 0) * 100).toFixed(0)}%`}
                  sx={{
                    backgroundColor: (refined?.confidence ?? initialRule?.confidence ?? 0.5) >= 0.8
                      ? colors.green
                      : (refined?.confidence ?? initialRule?.confidence ?? 0.5) >= 0.6
                        ? colors.confidenceMedium
                        : colors.confidenceLow,
                    color: colors.white,
                    fontSize: '11px',
                  }}
                />
                <Typography sx={{ fontSize: '10.5px', color: colors.grey, mt: 0.5, maxWidth: 280 }}>
                  {refined?.confidence_reasoning || initialRule?.confidence_reasoning || 'Manual draft saved without refreshed confidence reasoning.'}
                </Typography>
              </Box>

              <Box>
                <Chip
                  icon={<BoltIcon sx={{ fontSize: '14px !important', color: `${colors.white} !important` }} />}
                  label={`Specificity: ${(((refined?.decay ?? initialRule?.decay ?? 0.5) || 0) * 100).toFixed(0)}%`}
                  sx={{
                    backgroundColor: (refined?.decay ?? initialRule?.decay ?? 0.5) > 0.6 ? colors.green : colors.grey,
                    color: colors.white,
                    fontSize: '11px',
                  }}
                />
                <Typography sx={{ fontSize: '10.5px', color: colors.grey, mt: 0.5, maxWidth: 280 }}>
                  {refined?.decay_reasoning || initialRule?.decay_reasoning || 'Manual draft saved without refreshed specificity reasoning.'}
                </Typography>
              </Box>
            </Box>

            {(refined?.context ?? context) && (
              <Box sx={{ mb: 1.25 }}>
                <Typography sx={{ fontSize: '10.5px', fontWeight: 700, color: colors.grey }}>Context:</Typography>
                <Typography sx={{ fontSize: '12px', lineHeight: 1.4 }}>
                  {refined?.context ?? context}
                </Typography>
              </Box>
            )}

            {(refined?.evidence ?? evidence) && (
              <Box>
                <Typography sx={{ fontSize: '10.5px', fontWeight: 700, color: colors.grey }}>Evidence:</Typography>
                <Typography sx={{ fontSize: '11.5px', fontFamily: 'monospace', bgcolor: colors.surface, p: 1, borderRadius: '6px', border: `1px solid ${colors.divider}` }}>
                  {refined?.evidence ?? evidence}
                </Typography>
              </Box>
            )}
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
      </DialogContent>
    </Dialog>
  );
}
