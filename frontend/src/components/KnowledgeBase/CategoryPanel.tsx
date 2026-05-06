import { useState, useEffect, useMemo } from 'react';
import { Alert, Box, Typography, Chip, CircularProgress, IconButton, Tooltip } from '@mui/material';
import CallMergeIcon from '@mui/icons-material/CallMerge';
import SearchIcon from '@mui/icons-material/Search';
import DoneAllIcon from '@mui/icons-material/DoneAll';
import ClearAllIcon from '@mui/icons-material/ClearAll';

import { api } from '../../services/api';
import { CompactIconButton } from '../../design-system/CompactIconButton';
import { TextField } from '../../design-system/TextField';
import { colors } from '../../design-system/colors';
import type { DuplicateSuggestion, MergeSuggestion } from '../../types/knowledge';

type StatusMessage = {
  severity: 'success' | 'error';
  message: string;
} | null;

function emitKbUpdated() {
  window.dispatchEvent(
    new CustomEvent('kb-process-complete', {
      detail: {
        newly_added_ids: [],
        total_added: 0,
      },
    })
  );
}

export const CategoryPanel: React.FC = () => {
  const [categories, setCategories] = useState<Array<{ name: string; count: number }>>([]);
  const [duplicateSuggestions, setDuplicateSuggestions] = useState<DuplicateSuggestion[]>([]);
  const [mergeSuggestions, setMergeSuggestions] = useState<MergeSuggestion[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(false);
  const [loadingDuplicates, setLoadingDuplicates] = useState(false);
  const [loadingMerges, setLoadingMerges] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [categoryQuery, setCategoryQuery] = useState('');
  const [statusMessage, setStatusMessage] = useState<StatusMessage>(null);
  const [mergeScanStarted, setMergeScanStarted] = useState(false);
  const [duplicateScanStarted, setDuplicateScanStarted] = useState(false);

  const loadCategories = async () => {
    setLoadingCategories(true);
    try {
      const data = await api.fetchKBItems({ type: 'rule' });
      const categoryMap: Record<string, number> = {};
      (data.items || []).forEach((item: any) => {
        const category = String(item.category || 'uncategorized');
        categoryMap[category] = (categoryMap[category] || 0) + 1;
      });

      const nextCategories = Object.entries(categoryMap)
        .map(([name, count]) => ({ name, count }))
        .sort((a, b) => a.name.localeCompare(b.name));

      setCategories(nextCategories);
      setSelectedCategories((prev) => prev.filter((name) => nextCategories.some((cat) => cat.name === name)));
    } catch (error) {
      console.error('Failed to load categories:', error);
      setStatusMessage({
        severity: 'error',
        message: 'Failed to load category metadata.',
      });
    } finally {
      setLoadingCategories(false);
    }
  };

  useEffect(() => {
    loadCategories();
  }, []);

  useEffect(() => {
    const handleProcessComplete = () => {
      loadCategories();
    };

    window.addEventListener('kb-process-complete', handleProcessComplete);
    return () => window.removeEventListener('kb-process-complete', handleProcessComplete);
  }, []);

  const filteredCategories = useMemo(() => {
    const q = categoryQuery.trim().toLowerCase();
    if (!q) return categories;
    return categories.filter((c) => c.name.toLowerCase().includes(q));
  }, [categories, categoryQuery]);

  const visibleMergeSuggestions = useMemo(() => {
    if (selectedCategories.length === 0) return mergeSuggestions;
    const selected = new Set(selectedCategories);
    return mergeSuggestions.filter(
      (suggestion) =>
        suggestion.merge_from.some((name) => selected.has(name)) || selected.has(suggestion.merge_to)
    );
  }, [mergeSuggestions, selectedCategories]);

  const visibleDuplicateSuggestions = useMemo(() => {
    if (selectedCategories.length === 0) return duplicateSuggestions;
    const selected = new Set(selectedCategories);
    return duplicateSuggestions.filter((suggestion) =>
      (suggestion.items || []).some((item) => selected.has(item.category))
    );
  }, [duplicateSuggestions, selectedCategories]);

  const handleSuggestMerges = async () => {
    setLoadingMerges(true);
    setMergeScanStarted(true);
    setStatusMessage(null);
    try {
      const data = await api.suggestCategoryMerges();
      setMergeSuggestions(Array.isArray(data.suggestions) ? (data.suggestions as MergeSuggestion[]) : []);
    } catch (error: any) {
      console.error('Failed to suggest category merges:', error);
      setStatusMessage({
        severity: 'error',
        message: error?.response?.data?.error || error?.message || 'Failed to suggest category merges.',
      });
      setMergeSuggestions([]);
    } finally {
      setLoadingMerges(false);
    }
  };

  const handleAcceptMerge = async (suggestion: MergeSuggestion) => {
    try {
      const response = await api.acceptCategoryMerge(suggestion.merge_from, suggestion.merge_to);
      setMergeSuggestions((prev) => prev.filter((item) => item.suggestion_id !== suggestion.suggestion_id));
      setSelectedCategories((prev) => {
        const mapped = prev.map((category) =>
          suggestion.merge_from.includes(category) ? suggestion.merge_to : category
        );
        return Array.from(new Set(mapped));
      });
      await loadCategories();
      emitKbUpdated();
      setStatusMessage({
        severity: 'success',
        message: `Merged ${response.updated_items} rules into "${suggestion.merge_to}".`,
      });
    } catch (error: any) {
      console.error('Failed to accept category merge:', error);
      setStatusMessage({
        severity: 'error',
        message: error?.response?.data?.error || error?.message || 'Failed to merge categories.',
      });
    }
  };

  const handleDismissMerge = async (suggestion: MergeSuggestion) => {
    try {
      await api.dismissCategoryMerge(suggestion.suggestion_id);
    } catch (error) {
      console.error('Failed to dismiss category merge suggestion:', error);
    } finally {
      setMergeSuggestions((prev) => prev.filter((item) => item.suggestion_id !== suggestion.suggestion_id));
    }
  };

  const handleFindDuplicates = async () => {
    setLoadingDuplicates(true);
    setDuplicateScanStarted(true);
    setStatusMessage(null);
    try {
      const category = selectedCategories.length === 1 ? selectedCategories[0] : undefined;
      const data = await api.detectDuplicates(category);
      setDuplicateSuggestions(Array.isArray(data.duplicates) ? (data.duplicates as DuplicateSuggestion[]) : []);
    } catch (error: any) {
      console.error('Failed to detect duplicates:', error);
      setStatusMessage({
        severity: 'error',
        message: error?.response?.data?.error || error?.message || 'Failed to detect duplicate rules.',
      });
      setDuplicateSuggestions([]);
    } finally {
      setLoadingDuplicates(false);
    }
  };

  const handleAcceptDuplicate = async (suggestion: DuplicateSuggestion) => {
    try {
      const mergedTitle = suggestion.merged_title || suggestion.items[0]?.title || 'Merged Rule';
      const mergedContent = suggestion.suggested_merged || suggestion.items[0]?.content || '';
      const result = await api.mergeDuplicates(
        suggestion.item_ids,
        mergedContent,
        mergedTitle,
        suggestion.merged_confidence,
        suggestion.merged_decay,
        suggestion.scoring_explanation,
        suggestion.is_conflict
      );

      const removedIds = result.removed_item_ids || result.removed_ids || result.updated_ids || suggestion.item_ids.slice(1);
      setDuplicateSuggestions((prev) =>
        prev.filter(
          (item) =>
            item.suggestion_id !== suggestion.suggestion_id &&
            !item.item_ids.some((itemId) => removedIds.includes(itemId))
        )
      );
      await loadCategories();
      emitKbUpdated();
      setStatusMessage({
        severity: 'success',
        message: suggestion.is_conflict
          ? `Merged conflicting rules into "${mergedTitle}" for follow-up review.`
          : `Merged duplicate rules into "${mergedTitle}".`,
      });
    } catch (error: any) {
      console.error('Failed to merge duplicates:', error);
      setStatusMessage({
        severity: 'error',
        message: error?.response?.data?.error || error?.message || 'Failed to merge duplicate rules.',
      });
    }
  };

  const handleDismissDuplicate = (suggestionId: string) => {
    setDuplicateSuggestions((prev) => prev.filter((item) => item.suggestion_id !== suggestionId));
  };

  const toggleCategory = (name: string) => {
    setSelectedCategories((prev) => (prev.includes(name) ? prev.filter((c) => c !== name) : [...prev, name]));
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Typography
        variant="body1"
        sx={{
          color: colors.black,
          pb: 0.25,
          mb: 1.5,
          fontSize: '0.95rem',
          fontWeight: 600,
          lineHeight: 1.2,
        }}
      >
        Categories & Duplicates
      </Typography>

      {statusMessage && (
        <Alert severity={statusMessage.severity} sx={{ mb: 1.25 }}>
          {statusMessage.message}
        </Alert>
      )}

      <Box
        sx={{
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          p: 1.25,
          mb: 1.25,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, letterSpacing: '0.04em' }}>
            CATEGORY TAGS
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.25 }}>
            <Tooltip title="Select all">
              <span>
                <IconButton
                  size="small"
                  disableRipple
                  onClick={() => setSelectedCategories(categories.map((c) => c.name))}
                  disabled={categories.length === 0}
                  sx={{ color: colors.green, '&:focus': { outline: 'none' } }}
                >
                  <DoneAllIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Clear">
              <span>
                <IconButton
                  size="small"
                  disableRipple
                  onClick={() => setSelectedCategories([])}
                  disabled={selectedCategories.length === 0}
                  sx={{ color: colors.grey, '&:focus': { outline: 'none' } }}
                >
                  <ClearAllIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          </Box>
        </Box>

        <TextField
          size="small"
          placeholder="Search category tags..."
          value={categoryQuery}
          onChange={(e) => setCategoryQuery(e.target.value)}
          fullWidth
          sx={{
            mb: 1,
            '& .MuiInputBase-root': { height: 36 },
            '& .MuiInputBase-input': { fontSize: '11px' },
            '& .MuiInputBase-input::placeholder': { fontSize: '11px' },
          }}
        />

        {loadingCategories ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
            <CircularProgress size={18} sx={{ color: colors.green }} />
          </Box>
        ) : (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, maxHeight: 132, overflow: 'auto', pr: 0.5 }}>
            {filteredCategories.map((cat) => {
              const selected = selectedCategories.includes(cat.name);
              return (
                <Chip
                  key={cat.name}
                  label={`${cat.name} (${cat.count})`}
                  size="small"
                  onClick={() => toggleCategory(cat.name)}
                  sx={{
                    fontSize: '10px',
                    height: 24,
                    cursor: 'pointer',
                    backgroundColor: selected ? colors.green : colors.surfaceNeutral,
                    color: selected ? colors.white : colors.strongText,
                    border: '1px solid',
                    borderColor: selected ? colors.green : colors.divider,
                  }}
                />
              );
            })}
            {!filteredCategories.length && (
              <Typography sx={{ fontSize: '11px', color: colors.grey }}>No categories match your search.</Typography>
            )}
          </Box>
        )}
      </Box>

      <Box
        sx={{
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          p: 1.25,
          mb: 1.25,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, letterSpacing: '0.04em' }}>
            CATEGORY MERGES
          </Typography>
          <CompactIconButton
            label={loadingMerges ? 'Scanning for category merges' : 'Suggest category merges'}
            icon={<CallMergeIcon sx={{ fontSize: 18 }} />}
            tone="green"
            onClick={handleSuggestMerges}
            loading={loadingMerges}
          />
        </Box>

        <Typography sx={{ fontSize: '10px', color: colors.grey, mb: 1 }}>
          Scope: {selectedCategories.length ? `${selectedCategories.length} selected categories` : 'All categories'}
        </Typography>

        {loadingMerges ? (
          <Typography sx={{ fontSize: '12px', color: colors.grey }}>Looking for overlapping categories...</Typography>
        ) : visibleMergeSuggestions.length === 0 ? (
          <Typography sx={{ fontSize: '11px', color: colors.grey }}>
            {mergeScanStarted ? 'No category merge suggestions right now.' : 'Run merge suggestions to review category consolidation ideas.'}
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.8 }}>
            {visibleMergeSuggestions.map((suggestion) => (
              <Box
                key={suggestion.suggestion_id}
                sx={{
                  border: `1px solid ${colors.dividerMuted}`,
                  borderRadius: 1,
                  p: 0.9,
                  backgroundColor: colors.surface,
                }}
              >
                <Typography sx={{ fontSize: '11px', fontWeight: 700, mb: 0.35 }}>
                  {suggestion.merge_from.join(' + ')} {'->'} {suggestion.merge_to}
                </Typography>
                <Typography sx={{ fontSize: '10px', color: colors.grey, mb: 0.75 }}>
                  {suggestion.reasoning}
                </Typography>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.4 }}>
                  <CompactIconButton
                    label={`Apply merge into ${suggestion.merge_to}`}
                    icon={<DoneAllIcon sx={{ fontSize: 17 }} />}
                    tone="green"
                    onClick={() => handleAcceptMerge(suggestion)}
                  />
                  <CompactIconButton
                    label={`Dismiss merge suggestion for ${suggestion.merge_to}`}
                    icon={<ClearAllIcon sx={{ fontSize: 17 }} />}
                    tone="grey"
                    onClick={() => handleDismissMerge(suggestion)}
                  />
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </Box>

      <Box
        sx={{
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          p: 1.25,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, letterSpacing: '0.04em' }}>
            DUPLICATE REVIEW
          </Typography>
          <CompactIconButton
            label={loadingDuplicates ? 'Scanning for duplicates' : 'Find duplicate rules'}
            icon={<SearchIcon sx={{ fontSize: 18 }} />}
            tone="green"
            onClick={handleFindDuplicates}
            loading={loadingDuplicates}
          />
        </Box>

        <Typography sx={{ fontSize: '10px', color: colors.grey, mb: 1 }}>
          Scope: {selectedCategories.length ? `${selectedCategories.length} selected categories` : 'All categories'}
        </Typography>

        <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 0.8 }}>
          {loadingDuplicates ? (
            <Typography sx={{ fontSize: '12px', color: colors.grey }}>Searching for duplicates...</Typography>
          ) : visibleDuplicateSuggestions.length === 0 ? (
            <Typography sx={{ fontSize: '12px', color: colors.grey }}>
              {duplicateScanStarted ? 'No duplicate or conflict suggestions right now.' : 'Run duplicate review to see merge and conflict candidates.'}
            </Typography>
          ) : (
            visibleDuplicateSuggestions.map((suggestion) => {
              const titles = (suggestion.items || []).map((item) => item.title).filter(Boolean);
              const categoryNames = Array.from(new Set((suggestion.items || []).map((item) => item.category).filter(Boolean)));
              return (
                <Box
                  key={suggestion.suggestion_id}
                  sx={{
                    border: `1px solid ${colors.dividerMuted}`,
                    borderRadius: 1,
                    p: 1,
                    backgroundColor: suggestion.is_conflict ? colors.surfaceWarningMuted : colors.surface,
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                    <Typography sx={{ fontSize: '11px', fontWeight: 700 }}>
                      {Math.round((suggestion.similarity_score || 0) * 100)}% match
                    </Typography>
                    {suggestion.is_conflict && (
                      <Chip
                        label="Conflict"
                        size="small"
                        sx={{ height: 18, fontSize: '9px', backgroundColor: colors.gold, color: colors.black }}
                      />
                    )}
                  </Box>

                  <Typography sx={{ fontSize: '11px', mb: 0.35 }}>
                    {titles.slice(0, 2).join('  •  ') || 'Untitled rules'}
                  </Typography>

                  <Typography sx={{ fontSize: '10px', color: colors.grey, mb: 0.5 }}>
                    {suggestion.reasoning}
                  </Typography>

                  {suggestion.merged_title && (
                    <Typography sx={{ fontSize: '10px', color: colors.darkGreen, mb: 0.25 }}>
                      Proposed title: {suggestion.merged_title}
                    </Typography>
                  )}
                  {suggestion.suggested_merged && (
                    <Typography sx={{ fontSize: '10px', color: colors.darkGreen, mb: 0.6, whiteSpace: 'pre-wrap' }}>
                      Proposed rule: {suggestion.suggested_merged}
                    </Typography>
                  )}

                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
                    {categoryNames.map((name) => (
                      <Chip
                        key={name}
                        label={name}
                        size="small"
                        sx={{ height: 18, fontSize: '9px', backgroundColor: colors.surfaceSuccessTint }}
                      />
                    ))}
                  </Box>

                  <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.4 }}>
                    <CompactIconButton
                      label={suggestion.is_conflict ? 'Merge conflict suggestion' : 'Merge duplicate rules'}
                      icon={<DoneAllIcon sx={{ fontSize: 17 }} />}
                      tone="green"
                      onClick={() => handleAcceptDuplicate(suggestion)}
                    />
                    <CompactIconButton
                      label="Dismiss duplicate suggestion"
                      icon={<ClearAllIcon sx={{ fontSize: 17 }} />}
                      tone="grey"
                      onClick={() => handleDismissDuplicate(suggestion.suggestion_id)}
                    />
                  </Box>
                </Box>
              );
            })
          )}
        </Box>
      </Box>
    </Box>
  );
};
