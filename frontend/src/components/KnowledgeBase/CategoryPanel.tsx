import { useState, useEffect, useMemo } from 'react';
import { Box, Typography, Chip, CircularProgress, IconButton, Tooltip } from '@mui/material';
import DoneAllIcon from '@mui/icons-material/DoneAll';
import ClearAllIcon from '@mui/icons-material/ClearAll';
import { api } from '../../services/api';
import { Button } from '../../design-system/Button';
import { TextField } from '../../design-system/TextField';
import { colors } from '../../design-system/colors';
import type { KnowledgeItem } from '../../types/knowledge';
import type { DuplicateSuggestion } from '../../types/knowledge';

type DemoMergeSuggestion = {
  id: string;
  merge_from: string[];
  merge_to: string;
  reasoning: string;
};

const demoRuleA: KnowledgeItem = {
  item_id: 'demo-rule-a',
  type: 'rule',
  category: 'visual-style',
  title: 'Use default green for new icons',
  content: 'Prefer the default interface green for newly introduced icon accents.',
  context: null,
  evidence: null,
  confidence: 0.92,
  decay: 0.18,
  confidence_reasoning: null,
  decay_reasoning: null,
  source_file: 'demo-fixture',
  usage_count: 7,
  is_favorite: true,
  is_strict: true,
  is_testable: false,
  created_at: '2026-03-28T00:00:00Z',
};

const demoRuleB: KnowledgeItem = {
  item_id: 'demo-rule-b',
  type: 'rule',
  category: 'visual-style',
  title: 'Keep icon colors aligned to brand green',
  content: 'When adding icons, align accent colors with the established brand green palette.',
  context: null,
  evidence: null,
  confidence: 0.88,
  decay: 0.21,
  confidence_reasoning: null,
  decay_reasoning: null,
  source_file: 'demo-fixture',
  usage_count: 5,
  is_favorite: false,
  is_strict: true,
  is_testable: false,
  created_at: '2026-03-28T00:00:00Z',
};

const demoRuleC: KnowledgeItem = {
  item_id: 'demo-rule-c',
  type: 'rule',
  category: 'review-workflow',
  title: 'Batch refine must show verification evidence',
  content: 'Batch rule refine review should display linked code and test snippets from verification notes.',
  context: null,
  evidence: null,
  confidence: 0.94,
  decay: 0.14,
  confidence_reasoning: null,
  decay_reasoning: null,
  source_file: 'demo-fixture',
  usage_count: 4,
  is_favorite: true,
  is_strict: false,
  is_testable: false,
  created_at: '2026-03-28T00:00:00Z',
};

const demoRuleD: KnowledgeItem = {
  item_id: 'demo-rule-d',
  type: 'rule',
  category: 'review-ux',
  title: 'Notes carousel should support arrow navigation',
  content: 'For Notes Used in Refine, provide previous/next controls for quick review.',
  context: null,
  evidence: null,
  confidence: 0.78,
  decay: 0.34,
  confidence_reasoning: null,
  decay_reasoning: null,
  source_file: 'demo-fixture',
  usage_count: 3,
  is_favorite: false,
  is_strict: false,
  is_testable: false,
  created_at: '2026-03-28T00:00:00Z',
};

const DEMO_MERGE_SUGGESTIONS: DemoMergeSuggestion[] = [
  {
    id: 'demo-merge-2',
    merge_from: ['visual-style', 'icon-style'],
    merge_to: 'design-system',
    reasoning: 'Both capture icon/color presentation guidance and are easier to manage as one style bucket.',
  },
];

const DEMO_DUPLICATE_SUGGESTIONS: DuplicateSuggestion[] = [
  {
    suggestion_id: 'demo-dup-1',
    item_ids: [demoRuleA.item_id, demoRuleB.item_id],
    items: [demoRuleA, demoRuleB],
    similarity_score: 0.93,
    reasoning: 'These rules are near duplicates and can be merged into one strict visual style rule.',
    suggested_merged: 'Prefer default interface green for new icons and icon accents.',
    merged_title: 'Prefer default green for new icons',
    merged_context: null,
    merged_evidence: null,
    is_conflict: false,
    merged_confidence: 0.91,
    merged_decay: 0.19,
    scoring_explanation: 'High semantic overlap on icon color guidance and same UI scope.',
    dismissed: false,
  },
  {
    suggestion_id: 'demo-dup-2',
    item_ids: [demoRuleC.item_id, demoRuleD.item_id],
    items: [demoRuleC, demoRuleD],
    similarity_score: 0.81,
    reasoning: 'These both govern refinement review UX and can likely be merged after wording cleanup.',
    suggested_merged: 'Batch refine review should include verification evidence and navigable note controls.',
    merged_title: 'Batch refine must show evidence and note navigation',
    merged_context: null,
    merged_evidence: null,
    is_conflict: false,
    merged_confidence: 0.86,
    merged_decay: 0.22,
    scoring_explanation: 'Shared objective with slightly different emphasis (evidence vs navigation).',
    dismissed: false,
  },
];

export const CategoryPanel: React.FC = () => {
  const [categories, setCategories] = useState<Array<{ name: string; count: number }>>([]);
  const [duplicateSuggestions, setDuplicateSuggestions] = useState<DuplicateSuggestion[]>(DEMO_DUPLICATE_SUGGESTIONS);
  const [mergeSuggestions, setMergeSuggestions] = useState<DemoMergeSuggestion[]>(DEMO_MERGE_SUGGESTIONS);
  const [loading, setLoading] = useState(false);
  const [loadingDuplicates, setLoadingDuplicates] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [categoryQuery, setCategoryQuery] = useState('');

  const loadCategories = async () => {
    setLoading(true);
    try {
      const data = await api.fetchKBItems({});
      const categoryMap: Record<string, number> = {};
      data.items.forEach((item: any) => {
        categoryMap[item.category] = (categoryMap[item.category] || 0) + 1;
      });
      const cats = Object.entries(categoryMap)
        .map(([name, count]) => ({ name, count }))
        .sort((a, b) => a.name.localeCompare(b.name));
      setCategories(cats);
    } catch (error) {
      console.error('Failed to load categories:', error);
    } finally {
      setLoading(false);
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

  const handleFindDuplicates = async () => {
    setLoadingDuplicates(true);
    try {
      const data = await api.detectDuplicates();
      const all = data.duplicates || [];
      if (selectedCategories.length === 0) {
        setDuplicateSuggestions(all);
      } else {
        const selected = new Set(selectedCategories);
        const scoped = all.filter((s: DuplicateSuggestion) =>
          (s.items || []).some((item: any) => selected.has(item.category))
        );
        setDuplicateSuggestions(scoped);
      }
    } catch (error) {
      console.error('Failed to detect duplicates:', error);
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
      const removedIds = result.updated_ids || result.removed_ids || suggestion.item_ids;
      setDuplicateSuggestions((prev) => prev.filter((s) => !s.item_ids.some((id) => removedIds.includes(id))));
      await loadCategories();
    } catch (error) {
      console.error('Failed to merge duplicates:', error);
    }
  };

  const handleDismissDuplicate = (suggestionId: string) => {
    setDuplicateSuggestions((prev) => prev.filter((s) => s.suggestion_id !== suggestionId));
  };

  const toggleCategory = (name: string) => {
    setSelectedCategories((prev) => (prev.includes(name) ? prev.filter((c) => c !== name) : [...prev, name]));
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Typography
        variant="body1"
        sx={{
          color: '#000',
          pb: 0.25,
          mb: 1.5,
          fontSize: '0.95rem',
          fontWeight: 600,
          lineHeight: 1.2,
        }}
      >
        Categories & Duplicates
      </Typography>

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

        {loading ? (
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
                    backgroundColor: selected ? colors.green : '#f4f4f4',
                    color: selected ? 'white' : '#333',
                    border: '1px solid',
                    borderColor: selected ? colors.green : '#ddd',
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
        </Box>

        {mergeSuggestions.length === 0 ? (
          <Typography sx={{ fontSize: '11px', color: colors.grey }}>No merge suggestions pending.</Typography>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.8 }}>
            {mergeSuggestions.map((sug) => (
              <Box
                key={sug.id}
                sx={{
                  border: '1px solid #e2e2e2',
                  borderRadius: 1,
                  p: 0.9,
                  backgroundColor: '#fff',
                }}
                >
                  <Typography sx={{ fontSize: '11px', fontWeight: 700, mb: 0.35 }}>
                    {sug.merge_from.join(' + ')} {'->'} {sug.merge_to}
                  </Typography>
                <Typography sx={{ fontSize: '10px', color: colors.grey, mb: 0.75 }}>
                  {sug.reasoning}
                </Typography>
                <Box sx={{ display: 'flex', gap: 0.8 }}>
                  <Button
                    onClick={() => setMergeSuggestions((prev) => prev.filter((m) => m.id !== sug.id))}
                    colorVariant="green"
                    sx={{ flex: 1, fontSize: '10px', py: 0.35 }}
                  >
                    Apply
                  </Button>
                  <Button
                    onClick={() => setMergeSuggestions((prev) => prev.filter((m) => m.id !== sug.id))}
                    colorVariant="transparent"
                    sx={{ flex: 1, fontSize: '10px', py: 0.35 }}
                  >
                    Dismiss
                  </Button>
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
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Chip
              label="DEMO"
              size="small"
              sx={{ height: 18, fontSize: '9px', backgroundColor: '#eef7ee', color: colors.green, fontWeight: 700 }}
            />
            <Button
              onClick={handleFindDuplicates}
              disabled={loadingDuplicates}
              colorVariant="green"
              sx={{ fontSize: '0.72rem', py: 0.45, px: 1.1, minWidth: 114 }}
            >
              {loadingDuplicates ? 'Scanning...' : 'Find Duplicates'}
            </Button>
          </Box>
        </Box>

        <Typography sx={{ fontSize: '10px', color: colors.grey, mb: 1 }}>
          Scope: {selectedCategories.length ? `${selectedCategories.length} selected categories` : 'All categories'}
        </Typography>

        <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 0.8 }}>
          {loadingDuplicates ? (
            <Typography sx={{ fontSize: '12px', color: colors.grey }}>Searching for duplicates...</Typography>
          ) : duplicateSuggestions.length === 0 ? (
            <Typography sx={{ fontSize: '12px', color: colors.grey }}>No duplicate suggestions yet.</Typography>
          ) : (
            duplicateSuggestions.map((sug) => {
              const titles = (sug.items || []).map((i) => i.title).filter(Boolean);
              const categoryNames = Array.from(new Set((sug.items || []).map((i) => i.category).filter(Boolean)));
              return (
                <Box
                  key={sug.suggestion_id}
                  sx={{
                    border: '1px solid #e2e2e2',
                    borderRadius: 1,
                    p: 1,
                    backgroundColor: sug.is_conflict ? '#fffaf0' : '#fff',
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                    <Typography sx={{ fontSize: '11px', fontWeight: 700 }}>
                      {Math.round((sug.similarity_score || 0) * 100)}% match
                    </Typography>
                    {sug.is_conflict && (
                      <Chip
                        label="Conflict"
                        size="small"
                        sx={{ height: 18, fontSize: '9px', backgroundColor: colors.gold, color: '#000' }}
                      />
                    )}
                  </Box>

                  <Typography sx={{ fontSize: '11px', mb: 0.5 }}>
                    {titles.slice(0, 2).join('  •  ') || 'Untitled rules'}
                  </Typography>

                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
                    {categoryNames.map((name) => (
                      <Chip key={name} label={name} size="small" sx={{ height: 18, fontSize: '9px', backgroundColor: '#f0f7f0' }} />
                    ))}
                  </Box>

                  <Box sx={{ display: 'flex', gap: 0.8 }}>
                    <Button
                      onClick={() => handleAcceptDuplicate(sug)}
                      colorVariant="green"
                      sx={{ flex: 1, fontSize: '10px', py: 0.35 }}
                    >
                      Merge
                    </Button>
                    <Button
                      onClick={() => handleDismissDuplicate(sug.suggestion_id)}
                      colorVariant="transparent"
                      sx={{ flex: 1, fontSize: '10px', py: 0.35 }}
                    >
                      Dismiss
                    </Button>
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
