import { useEffect, useMemo, useState } from 'react';
import { Box, Typography, Chip, Stack, Dialog, DialogTitle, DialogContent, DialogActions, Alert, IconButton, Tooltip } from '@mui/material';
import { Close as CloseIcon, ChevronLeft as ChevronLeftIcon, ChevronRight as ChevronRightIcon, EditOutlined as EditOutlinedIcon, EditNoteOutlined as EditNoteOutlinedIcon, Check as CheckIcon, AutoFixHigh as AutoFixHighIcon } from '@mui/icons-material';
import { Accordion } from '../../design-system/Accordion';
import { CompactIconButton } from '../../design-system/CompactIconButton';
import { TextField } from '../../design-system/TextField';
import { colors } from '../../design-system/colors';
import { api } from '../../services/api';
import { createRuleNoteKey, toRuleNoteRecord } from './ruleNotes';
import type { RuleNoteRecord } from './ruleNotes';
import type { EvidenceRecord } from './evidence';
import { makeEvidenceRuleKey } from './evidence';

interface RuleReviewPanelProps {
  chatId: string;
  plan: any;
  evidence: EvidenceRecord[];
  onItemSelect?: (itemId: string) => void;
  onPlanUpdate?: (updatedPlan: any) => void;
  notesRefreshKey?: number;
  onRuleNotesSaved?: () => void;
}

interface FavoriteRule {
  item_id: string;
  title: string;
  content: string;
  category: string;
  context?: string;
  evidence?: string;
  is_favorite?: boolean;
  is_strict?: boolean;
  is_testable?: boolean;
}

interface ReviewRule {
  key: string;
  kb_item_id?: string;
  title: string;
  content: string;
  category: string;
  context?: string;
  evidence?: string;
  is_favorite: boolean;
  is_strict: boolean;
  is_testable: boolean;
}

interface VerificationEntry {
  evidenceRecordId: string;
  noteKey: string;
  itemId: string;
  itemLabel: string;
  itemDescription?: string;
  verdict: string;
  explanation: string;
  timestamp: string;
  codeBlocks: Array<{ file_path?: string; line_range?: string; code_snippet?: string }>;
  testEvidence?: {
    name?: string;
    command?: string;
    result?: string;
    output?: string;
    test_file?: string;
    test_code?: string;
  };
  noteMeta: Omit<RuleNoteRecord, 'note_key' | 'chat_id' | 'note_text'>;
}

interface RuleUsage {
  rule: ReviewRule;
  entries: VerificationEntry[];
}

interface RefinedRuleDraft {
  title: string;
  content: string;
  confidence: number;
  decay: number;
  confidence_reasoning: string;
  decay_reasoning: string;
  context: string | null;
  evidence: string | null;
}

interface BatchRefineResult {
  ruleUsage: RuleUsage;
  refined: RefinedRuleDraft | null;
  status: 'pending' | 'ready' | 'error' | 'approved' | 'skipped' | 'updated';
  error?: string;
  notesUsed?: Array<{
    itemLabel: string;
    verdict: string;
    noteText: string;
    verificationIndex: number | null;
    verificationTimestamp: string | null;
    explanation?: string;
    codeEvidence?: string;
    testEvidence?: string;
    codeSnippet?: string;
    testCommand?: string;
    testOutput?: string;
    testCode?: string;
  }>;
}

type DiffPart = {
  text: string;
  kind: 'same' | 'add' | 'del';
};

function safeNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function hasFieldChange(before: string | null | undefined, after: string | null | undefined): boolean {
  return (before || '').trim() !== (after || '').trim();
}

function makeRuleKey(rule: { kb_item_id?: string; text?: string; content?: string }): string {
  return makeEvidenceRuleKey(rule);
}

function isPersistedRuleInKnowledgeBase(rule: { kb_item_id?: string }): boolean {
  return Boolean(rule.kb_item_id && !String(rule.kb_item_id).startsWith('manual-'));
}

function emitKnowledgeBaseRefresh(newlyAddedIds: string[] = []) {
  window.dispatchEvent(new CustomEvent('kb-process-complete', {
    detail: {
      newly_added_ids: newlyAddedIds,
      total_added: newlyAddedIds.length,
    },
  }));
}

function tokenizeForDiff(text: string): string[] {
  return (text || '').match(/\S+|\s+/g) || [];
}

function computeInlineDiff(before: string, after: string): DiffPart[] {
  if (before === after) return [{ text: after || '', kind: 'same' }];
  const a = tokenizeForDiff(before || '');
  const b = tokenizeForDiff(after || '');
  if (!a.length && !b.length) return [{ text: '', kind: 'same' }];

  // Guard against pathological DP sizes.
  if (a.length * b.length > 120000) {
    return [
      ...(before ? [{ text: before, kind: 'del' as const }] : []),
      ...(after ? [{ text: after, kind: 'add' as const }] : []),
    ];
  }

  const dp: number[][] = Array.from({ length: a.length + 1 }, () => Array(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      if (a[i] === b[j]) dp[i][j] = dp[i + 1][j + 1] + 1;
      else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const out: DiffPart[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ text: a[i], kind: 'same' });
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ text: a[i], kind: 'del' });
      i += 1;
    } else {
      out.push({ text: b[j], kind: 'add' });
      j += 1;
    }
  }
  while (i < a.length) {
    out.push({ text: a[i], kind: 'del' });
    i += 1;
  }
  while (j < b.length) {
    out.push({ text: b[j], kind: 'add' });
    j += 1;
  }

  // Merge adjacent chunks with same kind to avoid overly fragmented rendering.
  const merged: DiffPart[] = [];
  for (const piece of out) {
    const prev = merged[merged.length - 1];
    if (prev && prev.kind === piece.kind) prev.text += piece.text;
    else merged.push({ ...piece });
  }
  return merged;
}

function InlineDiffText({ before, after }: { before: string; after: string }) {
  const parts = computeInlineDiff(before || '', after || '');
  return (
    <Box sx={{ fontSize: '0.6rem', whiteSpace: 'pre-wrap', lineHeight: 1.28 }}>
      {parts.map((part, idx) => (
        <Box
          key={idx}
          component="span"
          sx={
            part.kind === 'add'
              ? { bgcolor: colors.surfaceSuccessStrong, color: colors.successText, borderRadius: 0.45, px: 0.08 }
              : part.kind === 'del'
                ? { bgcolor: colors.surfaceDanger, color: colors.dangerText, textDecoration: 'line-through', borderRadius: 0.45, px: 0.08 }
                : undefined
          }
        >
          {part.text}
        </Box>
      ))}
    </Box>
  );
}

export function RuleReviewPanel({ chatId, plan, evidence, onItemSelect, onPlanUpdate, notesRefreshKey, onRuleNotesSaved }: RuleReviewPanelProps) {
  const [favorites, setFavorites] = useState<FavoriteRule[]>([]);
  const [noteRecords, setNoteRecords] = useState<Record<string, RuleNoteRecord>>({});
  const [reviewRuleKeys, setReviewRuleKeys] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [noteSaveState, setNoteSaveState] = useState<Record<string, 'idle' | 'saving' | 'saved' | 'error'>>({});
  const [noteEditorOpen, setNoteEditorOpen] = useState<Record<string, boolean>>({});
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [verificationCursorByRule, setVerificationCursorByRule] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [refineTarget, setRefineTarget] = useState<RuleUsage | null>(null);
  const [isRefining, setIsRefining] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [refined, setRefined] = useState<RefinedRuleDraft | null>(null);
  const [refineError, setRefineError] = useState<string>('');
  const [refineNoteIndex, setRefineNoteIndex] = useState(0);
  const [editingDiffField, setEditingDiffField] = useState<string | null>(null);
  const [diffDrafts, setDiffDrafts] = useState<Record<string, string>>({});
  const [refinedRuleStatusByKey, setRefinedRuleStatusByKey] = useState<Record<string, 'refined' | 'updated'>>({});
  const [batchReviewOpen, setBatchReviewOpen] = useState(false);
  const [batchRefineResults, setBatchRefineResults] = useState<BatchRefineResult[]>([]);
  const [batchRefineIndex, setBatchRefineIndex] = useState(0);
  const [batchNoteCursorByRule, setBatchNoteCursorByRule] = useState<Record<string, number>>({});
  const [isBatchRefining, setIsBatchRefining] = useState(false);
  const [isBatchApplying, setIsBatchApplying] = useState(false);
  const [batchError, setBatchError] = useState<string>('');

  useEffect(() => {
    const loadInitialData = async () => {
      setLoading(true);
      try {
        const [favoritesRes, notesRes] = await Promise.all([
          api.getFavorites(),
          api.getRuleNotes(chatId),
        ]);
        const loadedFavorites = (favoritesRes.favorites || []) as FavoriteRule[];
        setFavorites(loadedFavorites);
        setNoteRecords((notesRes.notes || {}) as Record<string, RuleNoteRecord>);

        // Favorites are always included in Rules Review; preserve user-added review rules.
        const favoriteKeys = loadedFavorites.map((f) => `kb:${f.item_id}`);

        setReviewRuleKeys((prev) => {
          if (!prev.length) return favoriteKeys;
          return Array.from(new Set([...favoriteKeys, ...prev]));
        });
      } catch (error) {
        console.error('Failed loading rules review data:', error);
      } finally {
        setLoading(false);
      }
    };
    loadInitialData();
  }, [chatId]);

  useEffect(() => {
    const refreshNotesOnly = async () => {
      if (!chatId) return;
      try {
        const notesRes = await api.getRuleNotes(chatId);
        setNoteRecords((notesRes.notes || {}) as Record<string, RuleNoteRecord>);
      } catch (error) {
        console.error('Failed refreshing rule notes:', error);
      }
    };
    refreshNotesOnly();
  }, [chatId, notesRefreshKey]);

  const sessionRules = useMemo(() => {
    const byKey = new Map<string, ReviewRule>();
    const favoritesById = new Map<string, FavoriteRule>();
    for (const favorite of favorites) favoritesById.set(favorite.item_id, favorite);

    const upsert = (rule: any) => {
      const key = makeRuleKey(rule);
      if (!key || key === 'txt:') return;
      if (byKey.has(key)) return;
      const favorite = rule.kb_item_id ? favoritesById.get(rule.kb_item_id) : undefined;
      byKey.set(key, {
        key,
        kb_item_id: rule.kb_item_id,
        title: favorite?.title || rule.text || 'Rule',
        content: favorite?.content || rule.text || '',
        category: favorite?.category || rule.category || 'uncategorized',
        context: favorite?.context ?? rule.context,
        evidence: favorite?.evidence ?? rule.evidence,
        is_favorite: !!favorite,
        is_strict: !!(favorite?.is_strict ?? rule.needs_strict_enforcement),
        is_testable: !!(favorite?.is_testable ?? rule.is_testable),
      });
    };

    const walk = (items: any[]) => {
      for (const item of items || []) {
        (item.rules || []).forEach(upsert);
        (item.inherited_rules || []).forEach((ir: any) => upsert(ir.rule || {}));
        if (item.children?.length) walk(item.children);
      }
    };

    walk(plan?.plan?.items || []);

    // Include favorites even if not currently attached to any plan node.
    favorites.forEach((favorite) => {
      const key = `kb:${favorite.item_id}`;
      if (byKey.has(key)) return;
      byKey.set(key, {
        key,
        kb_item_id: favorite.item_id,
        title: favorite.title || favorite.content || 'Favorite Rule',
        content: favorite.content || '',
        category: favorite.category || 'uncategorized',
        context: favorite.context,
        evidence: favorite.evidence,
        is_favorite: true,
        is_strict: !!favorite.is_strict,
        is_testable: !!favorite.is_testable,
      });
    });

    return Array.from(byKey.values());
  }, [favorites, plan]);

  const reviewRules = useMemo(
    () => reviewRuleKeys.map((key) => sessionRules.find((rule) => rule.key === key)).filter(Boolean) as ReviewRule[],
    [reviewRuleKeys, sessionRules]
  );

  const usage = useMemo(() => {
    const usageMap = new Map<string, RuleUsage>();
    const itemLabelById = new Map<string, string>();
    const itemDescriptionById = new Map<string, string>();
    const reviewRuleByKey = new Map<string, ReviewRule>();
    reviewRules.forEach((rule) => usageMap.set(rule.key, { rule, entries: [] }));
    reviewRules.forEach((rule) => reviewRuleByKey.set(rule.key, rule));

    const indexItems = (items: any[]) => {
      for (const item of items || []) {
        if (item?.id) {
          itemLabelById.set(item.id, `${item.number || ''} ${item.title || ''}`.trim());
          itemDescriptionById.set(item.id, (item.description || '').trim());
        }
        if (item.children?.length) indexItems(item.children);
      }
    };

    indexItems(plan?.plan?.items || []);

    for (const record of evidence || []) {
      if (record.source !== 'rule-verification') continue;
      const rawRuleKey = makeRuleKey({
        kb_item_id: record.rule_kb_item_id || undefined,
        text: record.rule_text,
      });
      const targetRule = reviewRuleByKey.get(rawRuleKey);
      if (!targetRule) continue;
      const target = usageMap.get(targetRule.key);
      if (!target) continue;

      const scopedItemId = String(record.item_id || '');
      const noteKey = createRuleNoteKey({
        source: 'rule-verification',
        evidenceRecordId: record.record_id,
        itemId: scopedItemId,
        ruleKbItemId: record.rule_kb_item_id || targetRule.kb_item_id,
        ruleText: record.rule_text || targetRule.content,
        timestamp: record.timestamp || '',
        index: record.record_index,
      });

      target.entries.push({
        evidenceRecordId: record.record_id,
        noteKey,
        itemId: scopedItemId,
        itemLabel: itemLabelById.get(scopedItemId) || scopedItemId,
        itemDescription: itemDescriptionById.get(scopedItemId) || '',
        verdict: record.verdict || 'unclear',
        explanation: record.explanation || '',
        timestamp: record.timestamp || '',
        codeBlocks: record.artifacts || [],
        testEvidence: record.tests || undefined,
        noteMeta: {
          rule_kb_item_id: record.rule_kb_item_id || targetRule.kb_item_id || null,
          rule_text: record.rule_text || targetRule.content || '',
          plan_item_id: scopedItemId || null,
          evidence_record_id: record.record_id,
          verification_timestamp: record.timestamp || null,
          verification_index: record.record_index,
          source: 'rule-verification',
          verdict: record.verdict || 'unclear',
          explanation: record.explanation || '',
        },
      });
    }
    return Array.from(usageMap.values());
  }, [evidence, plan, reviewRules]);

  const filteredSessionRules = useMemo(() => {
    const q = search.trim().toLowerCase();
    const current = new Set(reviewRuleKeys);
    return sessionRules.filter((rule) => {
      if (current.has(rule.key)) return false;
      if (!q) return true;
      return (
        rule.title.toLowerCase().includes(q) ||
        rule.content.toLowerCase().includes(q) ||
        rule.category.toLowerCase().includes(q)
      );
    }).slice(0, 20);
  }, [search, sessionRules, reviewRuleKeys]);

  const displayedSessionRules = useMemo(() => filteredSessionRules.slice(0, 8), [filteredSessionRules]);
  const hiddenSessionRuleCount = Math.max(0, filteredSessionRules.length - displayedSessionRules.length);

  const verifiedStepsByRuleKey = useMemo(() => {
    const byRuleKey = new Map<string, Set<string>>();
    const itemLabelById = new Map<string, string>();

    const indexItems = (items: any[]) => {
      for (const item of items || []) {
        if (item?.id) itemLabelById.set(item.id, `${item.number || ''} ${item.title || ''}`.trim());
        if (item.children?.length) indexItems(item.children);
      }
    };

    indexItems(plan?.plan?.items || []);
    for (const record of evidence || []) {
      if (record.source !== 'rule-verification') continue;
      const ruleKey = makeRuleKey({
        kb_item_id: record.rule_kb_item_id || undefined,
        text: record.rule_text,
      });
      if (!ruleKey) continue;
      if (!byRuleKey.has(ruleKey)) byRuleKey.set(ruleKey, new Set<string>());
      const bucket = byRuleKey.get(ruleKey)!;
      const scopedItemId = String(record.item_id || '');
      const stepLabel = itemLabelById.get(scopedItemId) || scopedItemId;
      if (stepLabel) bucket.add(stepLabel);
    }
    return byRuleKey;
  }, [evidence, plan]);

  const persistAllNotes = async (): Promise<boolean> => {
    try {
      const result = await api.updateRuleNotes(chatId, noteRecords);
      if (!result.success) throw new Error(result.error || 'Failed to save notes');
      return true;
    } catch (error: any) {
      console.error('Failed to save notes:', error);
      return false;
    }
  };

  const saveSingleNote = async (
    noteKey: string,
    noteText: string,
    noteMeta: Omit<RuleNoteRecord, 'note_key' | 'chat_id' | 'note_text'>
  ) => {
    setNoteSaveState((prev) => ({ ...prev, [noteKey]: 'saving' }));
    try {
      const nextRecords = {
        ...noteRecords,
        [noteKey]: toRuleNoteRecord(chatId, noteKey, noteText, noteMeta),
      };
      setNoteRecords(nextRecords);
      const result = await api.updateRuleNotes(chatId, nextRecords);
      if (!result.success) throw new Error(result.error || 'Failed to save note');
      setNoteSaveState((prev) => ({ ...prev, [noteKey]: 'saved' }));
      onRuleNotesSaved?.();
      setTimeout(() => {
        setNoteSaveState((prev) => ({ ...prev, [noteKey]: 'idle' }));
      }, 1200);
    } catch (error) {
      console.error('Failed to save note:', error);
      setNoteSaveState((prev) => ({ ...prev, [noteKey]: 'error' }));
    }
  };

  const resolveExistingNote = (entry: VerificationEntry): { key: string; note: RuleNoteRecord } | null => {
    const direct = noteRecords[entry.noteKey];
    if (direct) return { key: entry.noteKey, note: direct };
    const byEvidenceRecordId = Object.values(noteRecords).find(
      (note) => (note.evidence_record_id || null) === entry.evidenceRecordId
    );
    if (byEvidenceRecordId) {
      return { key: byEvidenceRecordId.note_key, note: byEvidenceRecordId };
    }
    return null;
  };

  const getRefineNotes = (target: RuleUsage) =>
    target.entries
      .map((entry) => {
        const resolved = resolveExistingNote(entry);
        const noteText = (resolved?.note?.note_text || '').trim();
        if (!noteText) return null;
        const codeEvidence = (entry.codeBlocks || [])
          .map((cb) => {
            const path = cb.file_path || 'unknown file';
            const line = cb.line_range ? ` (${cb.line_range})` : '';
            return `${path}${line}`;
          })
          .filter(Boolean)
          .join('; ');
        const testEvidence = entry.testEvidence
          ? [
              entry.testEvidence.name || 'test',
              entry.testEvidence.result ? `result=${entry.testEvidence.result}` : '',
              entry.testEvidence.test_file || '',
            ]
              .filter(Boolean)
              .join(' | ')
          : '';
        const codeSnippet = (entry.codeBlocks || [])
          .map((cb) => {
            const header = [cb.file_path || 'unknown file', cb.line_range ? `(${cb.line_range})` : '']
              .filter(Boolean)
              .join(' ');
            const snippet = cb.code_snippet || '';
            return header || snippet ? `${header}\n${snippet}`.trim() : '';
          })
          .filter(Boolean)
          .join('\n\n');
        return {
          itemLabel: entry.itemLabel,
          verdict: entry.verdict,
          noteText,
          verificationIndex: safeNumber(entry.noteMeta.verification_index),
          verificationTimestamp: entry.noteMeta.verification_timestamp || entry.timestamp || null,
          explanation: entry.explanation || '',
          codeEvidence,
          testEvidence,
          codeSnippet,
          testCommand: entry.testEvidence?.command || '',
          testOutput: entry.testEvidence?.output || '',
          testCode: entry.testEvidence?.test_code || '',
        };
      })
      .filter(Boolean) as Array<{
      itemLabel: string;
      verdict: string;
      noteText: string;
      verificationIndex: number | null;
      verificationTimestamp: string | null;
      explanation: string;
      codeEvidence: string;
      testEvidence: string;
      codeSnippet: string;
      testCommand: string;
      testOutput: string;
      testCode: string;
    }>;

  const buildNotesUsedForRuleUsage = (target: RuleUsage) =>
    getRefineNotes(target).map((n) => ({
      itemLabel: n.itemLabel,
      verdict: n.verdict,
      noteText: n.noteText,
      verificationIndex: n.verificationIndex,
      verificationTimestamp: n.verificationTimestamp,
      explanation: n.explanation,
      codeEvidence: n.codeEvidence,
      testEvidence: n.testEvidence,
      codeSnippet: n.codeSnippet,
      testCommand: n.testCommand,
      testOutput: n.testOutput,
      testCode: n.testCode,
    }));

  const noteCoverageByRuleKey = useMemo(() => {
    const coverage = new Map<string, { withNotes: number; total: number }>();
    for (const ruleUsage of usage) {
      let withNotes = 0;
      for (const entry of ruleUsage.entries) {
        const resolved = resolveExistingNote(entry);
        const noteText = (resolved?.note?.note_text || '').trim();
        if (noteText) withNotes += 1;
      }
      coverage.set(ruleUsage.rule.key, {
        withNotes,
        total: ruleUsage.entries.length,
      });
    }
    return coverage;
  }, [usage, noteRecords]);

  const startRefine = (target: RuleUsage) => {
    setRefineTarget(target);
    setRefined(null);
    setRefineError('');
    setRefineNoteIndex(0);
    setEditingDiffField(null);
    setDiffDrafts({});
  };

  const buildRefineContext = (target: RuleUsage): string => {
    const noteLines = getRefineNotes(target).map(
      (n) =>
        [
          `- [${n.itemLabel}] verdict=${n.verdict}`,
          n.explanation ? `explanation=${n.explanation}` : '',
          n.codeEvidence ? `code_evidence=${n.codeEvidence}` : '',
          n.testEvidence ? `test_evidence=${n.testEvidence}` : '',
          `note=${n.noteText}`,
        ]
          .filter(Boolean)
          .join('; ')
    );

    const contextParts = [
      target.rule.context || '',
      'Refine this rule based on user notes tied to concrete task proof records.',
      noteLines.length ? `Proof review notes:\n${noteLines.join('\n')}` : 'No notes were provided.',
    ].filter(Boolean);

    return contextParts.join('\n\n');
  };

  const refineRuleUsage = async (target: RuleUsage): Promise<RefinedRuleDraft> => {
    const result = await api.refineRule({
      rule_type: 'rule',
      category: target.rule.category,
      title: target.rule.title || 'Rule',
      content: target.rule.content,
      context: buildRefineContext(target),
      evidence: target.rule.evidence || null,
    });
    if (!result.success || !result.refined) {
      throw new Error(result.error || 'Refine failed');
    }
    return result.refined as RefinedRuleDraft;
  };

  const persistRuleToKnowledgeBase = async (
    target: RuleUsage,
    draft: RefinedRuleDraft
  ): Promise<{ itemId: string | null; created: boolean }> => {
    const payload = {
      type: 'rule' as const,
      category: target.rule.category,
      title: draft.title,
      content: draft.content,
      context: draft.context,
      evidence: draft.evidence,
      confidence: draft.confidence,
      decay: draft.decay,
      confidence_reasoning: draft.confidence_reasoning,
      decay_reasoning: draft.decay_reasoning,
      is_strict: target.rule.is_strict,
      is_testable: target.rule.is_strict && target.rule.is_testable,
      // Avoid duplicating old manual favorites if this save is the first KB-backed copy.
      is_favorite: isPersistedRuleInKnowledgeBase(target.rule) ? target.rule.is_favorite : false,
    };

    if (isPersistedRuleInKnowledgeBase(target.rule) && target.rule.kb_item_id) {
      const result = await api.updateKBItem(target.rule.kb_item_id, payload);
      if (!result.success) {
        throw new Error('Failed to update rule in Rules Management.');
      }
      return { itemId: target.rule.kb_item_id, created: false };
    }

    const result = await api.createKBItem(payload);
    if (!result.success || !result.item) {
      throw new Error('Failed to save rule into Rules Management.');
    }
    return { itemId: result.item.item_id || null, created: true };
  };

  const runRefine = async () => {
    if (!refineTarget) return;
    setIsRefining(true);
    setRefineError('');
    try {
      // Persist latest note edits before refining.
      const saved = await persistAllNotes();
      if (!saved) {
        throw new Error('Save notes failed. Fix note save and retry refine.');
      }
      const refinedResult = await refineRuleUsage(refineTarget);
      setRefined(refinedResult);
      setRefinedRuleStatusByKey((prev) => ({ ...prev, [refineTarget.rule.key]: 'refined' }));
    } catch (error: any) {
      setRefineError(error.message || 'Refine failed');
    } finally {
      setIsRefining(false);
    }
  };

  const updateRule = async () => {
    if (!refineTarget || !refined) return;
    setIsUpdating(true);
    setRefineError('');
    try {
      const saveResult = await persistRuleToKnowledgeBase(refineTarget, refined);
      emitKnowledgeBaseRefresh(saveResult.created && saveResult.itemId ? [saveResult.itemId] : []);
      setRefinedRuleStatusByKey((prev) => ({ ...prev, [refineTarget.rule.key]: 'updated' }));
      setRefineTarget(null);
      setRefined(null);
      if (onPlanUpdate) {
        const result = await api.getVisualizationPlan(chatId);
        if (result.success && result.plan) onPlanUpdate(result.plan);
      }
    } catch (error: any) {
      setRefineError(error.message || 'Update failed');
    } finally {
      setIsUpdating(false);
    }
  };

  const startBatchRefine = async () => {
    setBatchError('');
    setIsBatchRefining(true);
    setBatchReviewOpen(true);
    setBatchRefineIndex(0);
    setBatchNoteCursorByRule({});
    try {
      const saved = await persistAllNotes();
      if (!saved) {
        throw new Error('Save notes failed. Fix note save and retry batch refine.');
      }

      const eligible = usage.filter((ruleUsage) => {
        const coverage = noteCoverageByRuleKey.get(ruleUsage.rule.key);
        return (coverage?.withNotes || 0) > 0;
      });

      if (!eligible.length) {
        throw new Error('No rules with notes are available for batch refine.');
      }

      const pending: BatchRefineResult[] = eligible.map((ruleUsage) => ({
        ruleUsage,
        refined: null,
        status: 'pending',
        notesUsed: buildNotesUsedForRuleUsage(ruleUsage),
      }));
      setBatchRefineResults(pending);
      setBatchRefineIndex(0);

      const next: BatchRefineResult[] = [];
      for (let idx = 0; idx < eligible.length; idx += 1) {
        const target = eligible[idx];
        setBatchRefineIndex(idx);
        try {
          const refinedResult = await refineRuleUsage(target);
          next.push({
            ruleUsage: target,
            refined: refinedResult,
            status: 'ready',
            notesUsed: buildNotesUsedForRuleUsage(target),
          });
          setRefinedRuleStatusByKey((prev) => ({ ...prev, [target.rule.key]: 'refined' }));
        } catch (error: any) {
          next.push({
            ruleUsage: target,
            refined: null,
            status: 'error',
            error: error?.message || 'Refine failed',
            notesUsed: buildNotesUsedForRuleUsage(target),
          });
        }
        setBatchRefineResults([...next]);
      }
    } catch (error: any) {
      setBatchError(error?.message || 'Batch refine failed');
      setBatchRefineResults([]);
    } finally {
      setIsBatchRefining(false);
    }
  };

  const applyBatchApproved = async () => {
    setBatchError('');
    setIsBatchApplying(true);
    try {
      const updatedKeys: string[] = [];
      const newlyAddedIds: string[] = [];
      const next = [...batchRefineResults];
      for (let i = 0; i < next.length; i += 1) {
        const item = next[i];
        if (item.status !== 'approved' || !item.refined) continue;
        try {
          const saveResult = await persistRuleToKnowledgeBase(item.ruleUsage, item.refined);
          if (saveResult.created && saveResult.itemId) {
            newlyAddedIds.push(saveResult.itemId);
          }
          next[i] = { ...item, status: 'updated', error: undefined };
          updatedKeys.push(item.ruleUsage.rule.key);
        } catch (error: any) {
          next[i] = { ...item, status: 'error', error: error?.message || 'Update failed' };
        }
        setBatchRefineResults([...next]);
      }

      if (updatedKeys.length) {
        emitKnowledgeBaseRefresh(newlyAddedIds);
        setRefinedRuleStatusByKey((prev) => {
          const copy = { ...prev };
          updatedKeys.forEach((key) => {
            copy[key] = 'updated';
          });
          return copy;
        });
      }

      if (updatedKeys.length && onPlanUpdate) {
        const result = await api.getVisualizationPlan(chatId);
        if (result.success && result.plan) onPlanUpdate(result.plan);
      }
    } catch (error: any) {
      setBatchError(error?.message || 'Batch apply failed');
    } finally {
      setIsBatchApplying(false);
    }
  };

  const batchCounts = useMemo(() => {
    const summary = {
      total: batchRefineResults.length,
      ready: 0,
      approved: 0,
      updated: 0,
      error: 0,
      skipped: 0,
      pending: 0,
    };
    for (const item of batchRefineResults) {
      summary[item.status] += 1;
    }
    return summary;
  }, [batchRefineResults]);

  return (
    <>
      <Accordion
        title={
          <Typography variant="body1" sx={{ fontWeight: 'bold' }}>Rules Review</Typography>
        }
        defaultOpen={true}
      >
        <Box sx={{ px: 2, pt: 1.25, pb: 1 }}>
          {loading ? (
            <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>Loading rules...</Typography>
          ) : (
            <Stack spacing={2}>
              <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1, position: 'relative' }}>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, mb: 0.7 }}>Add Rules from This Session</Typography>
                <TextField
                  fullWidth
                  size="small"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search rules to add to review..."
                  sx={{
                    mb: 0.2,
                    '& .MuiInputBase-root': { minHeight: 32 },
                    '& .MuiInputBase-input': { fontSize: '0.72rem', py: 0.55 },
                    '& .MuiInputBase-input::placeholder': { fontSize: '0.7rem', opacity: 0.9 },
                  }}
                />
                {search.trim() ? (
                  <Box
                    sx={{
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1,
                      bgcolor: 'background.paper',
                      maxHeight: 140,
                      overflowY: 'auto',
                    }}
                  >
                    {displayedSessionRules.length === 0 ? (
                      <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', px: 1, py: 0.8 }}>
                        No matching rules.
                      </Typography>
                    ) : (
                      displayedSessionRules.map((rule) => (
                      <Box
                        key={rule.key}
                        onClick={() => {
                          setReviewRuleKeys((prev) => Array.from(new Set([...prev, rule.key])));
                          setSearch('');
                        }}
                        sx={{
                          px: 1,
                          py: 0.7,
                          cursor: 'pointer',
                          borderBottom: '1px solid',
                          borderColor: 'divider',
                          '&:hover': { bgcolor: `${colors.green}14` },
                        }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 0.6 }}>
                          <Typography sx={{ fontSize: '0.62rem', fontWeight: 600 }}>
                            {rule.title || 'Rule'}
                          </Typography>
                          {(() => {
                            const steps = Array.from(verifiedStepsByRuleKey.get(rule.key) || []);
                            if (!steps.length) return null;
                            return (
                              <Typography sx={{ fontSize: '0.56rem', color: 'text.secondary', whiteSpace: 'nowrap' }}>
                                {steps.length === 1 ? `Verified: ${steps[0]}` : `Verified: ${steps.length} steps`}
                              </Typography>
                            );
                          })()}
                        </Box>
                        <Box sx={{ display: 'flex', gap: 0.45, alignItems: 'center', flexWrap: 'wrap', mt: 0.25 }}>
                          <Chip
                            label={rule.category}
                            size="small"
                            sx={{ bgcolor: `${colors.green}1f`, color: colors.darkGreen, fontSize: '0.62rem', height: 16 }}
                          />
                          {rule.is_favorite && (
                            <Chip
                              label="★ Favorite"
                              size="small"
                              sx={{ bgcolor: colors.surfaceWarningAlt, color: colors.warningTextStrong, fontSize: '0.6rem', height: 16 }}
                            />
                          )}
                          {rule.is_strict && (
                            <Chip
                              label="⚡ Strict"
                              size="small"
                              sx={{ bgcolor: colors.surfaceDanger, color: colors.dangerText, fontSize: '0.6rem', height: 16 }}
                            />
                          )}
                          {rule.is_testable && (
                            <Chip
                              label="🧪 Testable"
                              size="small"
                              sx={{ bgcolor: colors.surfaceInfoAlt, color: colors.infoText, fontSize: '0.6rem', height: 16 }}
                            />
                          )}
                        </Box>
                        <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary' }}>
                          {rule.content}
                        </Typography>
                      </Box>
                      ))
                    )}
                    {hiddenSessionRuleCount > 0 && (
                      <Typography sx={{ fontSize: '0.64rem', color: 'text.secondary', px: 1, py: 0.55, borderTop: '1px solid', borderColor: 'divider' }}>
                        + {hiddenSessionRuleCount} more results. Narrow your search.
                      </Typography>
                    )}
                  </Box>
                ) : (
                  <Typography sx={{ fontSize: '0.66rem', color: 'text.secondary', px: 0.2, py: 0.35 }}>
                    Type to search and add additional rules.
                  </Typography>
                )}
              </Box>

              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
                <Typography sx={{ fontSize: '0.66rem', color: 'text.secondary' }}>
                  Batch refine rules with notes, then review diffs before applying.
                </Typography>
                <CompactIconButton
                  label={isBatchRefining ? 'Evolving rules with notes' : 'Evolve rules with notes'}
                  icon={<AutoFixHighIcon sx={{ fontSize: '0.8rem' }} />}
                  tone="green"
                  onClick={startBatchRefine}
                  disabled={isBatchApplying || usage.length === 0}
                  loading={isBatchRefining}
                />
              </Box>

              {usage.length === 0 ? (
                <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>No rules selected for review.</Typography>
              ) : (
                usage.map((ruleUsage) => (
                  <Accordion
                    key={ruleUsage.rule.key}
                    defaultOpen={false}
                    title={
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 0.75, width: '100%' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6, flexWrap: 'wrap' }}>
                          <Typography sx={{ fontSize: '0.74rem', fontWeight: 700 }}>
                            {ruleUsage.rule.title || 'Rule'}
                          </Typography>
                          <Chip label={ruleUsage.rule.category} size="small" sx={{ bgcolor: colors.green, color: 'white', fontSize: '0.68rem', height: 18 }} />
                          {ruleUsage.rule.is_favorite && (
                            <Chip label="★ Favorite" size="small" sx={{ bgcolor: colors.gold, color: 'white', fontSize: '0.66rem', height: 18 }} />
                          )}
                          {ruleUsage.rule.is_strict && (
                            <Chip label="⚡ Strict" size="small" sx={{ bgcolor: colors.red, color: 'white', fontSize: '0.66rem', height: 18 }} />
                          )}
                          {ruleUsage.rule.is_testable && (
                            <Chip label="🧪 Testable" size="small" sx={{ bgcolor: colors.blue, color: 'white', fontSize: '0.66rem', height: 18 }} />
                          )}
                          <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary' }}>
                            {ruleUsage.entries.length} verification{ruleUsage.entries.length === 1 ? '' : 's'}
                          </Typography>
                          {(() => {
                            const coverage = noteCoverageByRuleKey.get(ruleUsage.rule.key);
                            if (!coverage) return null;
                            if (coverage.total === 0 || coverage.withNotes === 0) {
                              return (
                                <Chip
                                  label="No notes"
                                  size="small"
                                  sx={{ bgcolor: colors.surfaceMuted, color: colors.secondaryText, fontSize: '0.62rem', height: 17 }}
                                />
                              );
                            }
                            return (
                              <Chip
                                label={`Notes ${coverage.withNotes}/${coverage.total}`}
                                size="small"
                                sx={{ bgcolor: colors.surfaceSuccess, color: colors.successText, fontSize: '0.62rem', height: 17 }}
                              />
                            );
                          })()}
                          {refinedRuleStatusByKey[ruleUsage.rule.key] && (
                            <Chip
                              label={refinedRuleStatusByKey[ruleUsage.rule.key] === 'updated' ? 'Refined + Saved' : 'Refined'}
                              size="small"
                              sx={{ bgcolor: colors.surfaceSuccessAlt, color: colors.successText, fontSize: '0.62rem', height: 17 }}
                            />
                          )}
                        </Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.35 }}>
                          <Tooltip title="Refine Rule">
                            <IconButton
                              size="small"
                              disableRipple
                              sx={{
                                p: 0.25,
                                color: colors.darkGreen,
                                '&:hover': { bgcolor: 'rgba(76, 111, 59, 0.08)' },
                                '&:focus, &.Mui-focusVisible': { outline: 'none', bgcolor: 'rgba(76, 111, 59, 0.08)' },
                              }}
                              onClick={(e) => {
                                e.stopPropagation();
                                startRefine(ruleUsage);
                              }}
                            >
                              <AutoFixHighIcon sx={{ fontSize: '0.9rem' }} />
                            </IconButton>
                          </Tooltip>
                          {!ruleUsage.rule.is_favorite && (
                            <IconButton
                              size="small"
                              sx={{ p: 0.2, color: colors.grey }}
                              onClick={(e) => {
                                e.stopPropagation();
                                setReviewRuleKeys((prev) => prev.filter((k) => k !== ruleUsage.rule.key));
                              }}
                            >
                              <CloseIcon fontSize="small" />
                            </IconButton>
                          )}
                        </Box>
                      </Box>
                    }
                  >
                    <Box sx={{ p: 1.25 }}>

                    <Typography sx={{ fontSize: '0.76rem', fontWeight: 600, mb: 0.5 }}>
                      {ruleUsage.rule.title || ruleUsage.rule.content}
                    </Typography>
                    <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mb: 1 }}>
                      {ruleUsage.rule.content}
                    </Typography>

                    {ruleUsage.entries.length === 0 ? (
                      <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', fontStyle: 'italic' }}>
                        No proof records yet for this task.
                      </Typography>
                    ) : (
                      <Stack spacing={1}>
                        {(() => {
                          const total = ruleUsage.entries.length;
                          const rawIndex = verificationCursorByRule[ruleUsage.rule.key] ?? 0;
                          const currentIndex = Math.min(Math.max(rawIndex, 0), total - 1);
                          const entry = ruleUsage.entries[currentIndex];
                          const resolved = resolveExistingNote(entry);
                          const effectiveKey = resolved?.key || entry.noteKey;
                          const savedText = resolved?.note?.note_text || '';
                          const isOpen = !!noteEditorOpen[effectiveKey];
                          const draft = noteDrafts[effectiveKey] ?? savedText;
                          return (
                              <Box key={entry.noteKey} sx={{ border: '1px dashed', borderColor: 'divider', borderRadius: 1, p: 0.9 }}>
                                <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1, mb: 0.55 }}>
                                  <Box sx={{ minWidth: 0 }}>
                                    <Typography sx={{ fontSize: '0.64rem', color: 'text.secondary' }}>
                                      Proof {currentIndex + 1} of {total}
                                    </Typography>
                                    <Typography
                                      sx={{ fontSize: '0.7rem', color: colors.darkGreen, fontWeight: 600, cursor: entry.itemId ? 'pointer' : 'default' }}
                                      onClick={() => entry.itemId && onItemSelect?.(entry.itemId)}
                                    >
                                      {entry.itemLabel || 'Unknown item'}
                                    </Typography>
                                  </Box>
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.2, ml: 'auto' }}>
                                    {total > 1 && (
                                      <>
                                        <IconButton
                                          size="small"
                                          disableRipple
                                          disabled={currentIndex === 0}
                                          onClick={() =>
                                            setVerificationCursorByRule((prev) => ({
                                              ...prev,
                                              [ruleUsage.rule.key]: Math.max(0, currentIndex - 1),
                                            }))
                                          }
                                          sx={{ p: 0.2, color: colors.grey, '&:focus': { outline: 'none' } }}
                                        >
                                          <ChevronLeftIcon fontSize="small" />
                                        </IconButton>
                                        <IconButton
                                          size="small"
                                          disableRipple
                                          disabled={currentIndex >= total - 1}
                                          onClick={() =>
                                            setVerificationCursorByRule((prev) => ({
                                              ...prev,
                                              [ruleUsage.rule.key]: Math.min(total - 1, currentIndex + 1),
                                            }))
                                          }
                                          sx={{ p: 0.2, color: colors.grey, '&:focus': { outline: 'none' } }}
                                        >
                                          <ChevronRightIcon fontSize="small" />
                                        </IconButton>
                                      </>
                                    )}
                                    <Chip
                                      label={entry.verdict.toUpperCase()}
                                      size="small"
                                      sx={{
                                        bgcolor: entry.verdict === 'pass' ? colors.green : entry.verdict === 'fail' ? colors.red : colors.gold,
                                        color: 'white',
                                        fontSize: '0.63rem',
                                        height: 17,
                                      }}
                                    />
                                  </Box>
                                </Box>
                                {entry.itemDescription && (
                                  <Typography sx={{ mt: 0.2, mb: 0.5, fontSize: '0.62rem', color: 'text.secondary', whiteSpace: 'pre-wrap' }}>
                                    {entry.itemDescription}
                                  </Typography>
                                )}
                                <Box sx={{ mt: 0.15, minWidth: 0 }}>
                                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 0.8, mb: 0.2 }}>
                                    <Typography sx={{ fontSize: '0.64rem', color: 'text.secondary', mt: 0.1 }}>
                                      Pass/Fail Reason
                                    </Typography>
                                    <CompactIconButton
                                      label={savedText.trim() ? 'Edit note' : 'Add note'}
                                      icon={
                                        savedText.trim()
                                          ? <EditOutlinedIcon sx={{ fontSize: '0.72rem' }} />
                                          : <EditNoteOutlinedIcon sx={{ fontSize: '0.8rem' }} />
                                      }
                                      tone="dark-green"
                                      onClick={() => {
                                        setNoteEditorOpen((prev) => ({ ...prev, [effectiveKey]: true }));
                                        setNoteDrafts((prev) => ({
                                          ...prev,
                                          [effectiveKey]: prev[effectiveKey] ?? savedText ?? '',
                                        }));
                                      }}
                                      sx={{ ml: 'auto' }}
                                    />
                                  </Box>
                                  <Box
                                    sx={{
                                      display: 'grid',
                                      gridTemplateColumns: {
                                        xs: '1fr',
                                        md: isOpen || !!savedText.trim() ? 'minmax(0, 1fr) 320px' : '1fr',
                                      },
                                      gap: 0.55,
                                      mb: 0.45,
                                      alignItems: 'start',
                                    }}
                                  >
                                    <Typography sx={{ fontSize: '0.68rem', color: 'text.primary', whiteSpace: 'pre-wrap' }}>
                                      {entry.explanation || 'No explanation'}
                                    </Typography>
                                    {(isOpen || savedText.trim()) && (
                                      <Box sx={{ minWidth: 0 }}>
                                        {!isOpen ? (
                                          <Typography
                                            sx={{
                                              fontSize: '0.6rem',
                                              color: 'text.secondary',
                                              whiteSpace: 'pre-wrap',
                                              lineHeight: 1.25,
                                              textAlign: 'right',
                                            }}
                                          >
                                            {savedText}
                                          </Typography>
                                        ) : (
                                          <Box>
                                            <TextField
                                              fullWidth
                                              multiline
                                              minRows={2}
                                              maxRows={4}
                                              placeholder="Review note for this verification..."
                                              value={draft}
                                              onChange={(e) => setNoteDrafts((prev) => ({ ...prev, [effectiveKey]: e.target.value }))}
                                              inputProps={{ 'aria-label': 'Proof Note' }}
                                              sx={{
                                                '& .MuiInputBase-root': { py: 0 },
                                                '& .MuiInputBase-input': { fontSize: '0.64rem' },
                                                '& textarea.MuiInputBase-input': { py: 0.25, px: 0.4 },
                                                '& .MuiInputBase-input::placeholder': { fontSize: '0.62rem' },
                                              }}
                                            />
                                            <Box sx={{ mt: 0.35, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.3, flexWrap: 'wrap' }}>
                                              <Tooltip title={noteSaveState[effectiveKey] === 'saving' ? 'Saving...' : 'Save note'}>
                                                <span>
                                                  <IconButton
                                                    size="small"
                                                    disableRipple
                                                    onClick={async () => {
                                                      await saveSingleNote(effectiveKey, draft, entry.noteMeta);
                                                      setNoteEditorOpen((prev) => ({ ...prev, [effectiveKey]: false }));
                                                    }}
                                                    disabled={noteSaveState[effectiveKey] === 'saving'}
                                                    sx={{
                                                      p: 0.35,
                                                      color: noteSaveState[effectiveKey] === 'saving' ? 'text.disabled' : colors.green,
                                                      '&:hover': { bgcolor: 'rgba(124, 179, 66, 0.12)' },
                                                      '&:focus, &.Mui-focusVisible': { outline: 'none', bgcolor: 'rgba(124, 179, 66, 0.12)' },
                                                    }}
                                                  >
                                                    <CheckIcon sx={{ fontSize: '0.9rem' }} />
                                                  </IconButton>
                                                </span>
                                              </Tooltip>
                                              <Tooltip title="Cancel">
                                                <IconButton
                                                  size="small"
                                                  disableRipple
                                                  onClick={() => setNoteEditorOpen((prev) => ({ ...prev, [effectiveKey]: false }))}
                                                  sx={{
                                                    p: 0.35,
                                                    color: colors.grey,
                                                    '&:hover': { bgcolor: 'rgba(120, 120, 120, 0.1)' },
                                                    '&:focus, &.Mui-focusVisible': { outline: 'none', bgcolor: 'rgba(120, 120, 120, 0.1)' },
                                                  }}
                                                >
                                                  <CloseIcon sx={{ fontSize: '0.9rem' }} />
                                                </IconButton>
                                              </Tooltip>
                                              {noteSaveState[effectiveKey] === 'saved' && (
                                                <Typography sx={{ fontSize: '0.62rem', color: colors.green }}>
                                                  Saved
                                                </Typography>
                                              )}
                                              {noteSaveState[effectiveKey] === 'error' && (
                                                <Typography sx={{ fontSize: '0.62rem', color: colors.red }}>
                                                  Failed to save
                                                </Typography>
                                              )}
                                            </Box>
                                          </Box>
                                        )}
                                      </Box>
                                    )}
                                  </Box>

                                  {(entry.codeBlocks.length > 0 || entry.testEvidence) ? (
                                    <Box
                                      sx={{
                                        display: 'grid',
                                        gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
                                        gap: 0.55,
                                        mt: 0.45,
                                      }}
                                    >
                                      <Box sx={{ minWidth: 0 }}>
                                        <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', mb: 0.22 }}>
                                          Code Evidence
                                        </Typography>
                                        {entry.codeBlocks.length > 0 ? (
                                          <Stack spacing={0.45}>
                                            {entry.codeBlocks.map((cb, cbIdx) => (
                                              <Box key={cbIdx} sx={{ p: 0.5, bgcolor: colors.surfaceMutedAlt, borderRadius: 1 }}>
                                                <Typography sx={{ fontSize: '0.58rem', color: colors.darkGreen, mb: 0.2 }}>
                                                  {cb.file_path || 'Unknown file'}{cb.line_range ? ` (${cb.line_range})` : ''}
                                                </Typography>
                                                <Box sx={{ fontSize: '0.57rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                                  {cb.code_snippet || ''}
                                                </Box>
                                              </Box>
                                            ))}
                                          </Stack>
                                        ) : (
                                          <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', fontStyle: 'italic' }}>
                                            None
                                          </Typography>
                                        )}
                                      </Box>

                                      <Box sx={{ minWidth: 0 }}>
                                        <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', mb: 0.22 }}>
                                          Test Evidence
                                        </Typography>
                                        {entry.testEvidence ? (
                                          <Box sx={{ p: 0.5, bgcolor: colors.surfaceMutedAlt, borderRadius: 1 }}>
                                            <Typography sx={{ fontSize: '0.58rem', mb: 0.2 }}>
                                              {entry.testEvidence.name || 'Unnamed test'} • {String(entry.testEvidence.result || 'unknown').toUpperCase()}
                                            </Typography>
                                            {entry.testEvidence.command && (
                                              <Box sx={{ mt: 0.25, fontSize: '0.57rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                                {entry.testEvidence.command}
                                              </Box>
                                            )}
                                            {entry.testEvidence.output && (
                                              <Box sx={{ mt: 0.25, fontSize: '0.57rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                                {entry.testEvidence.output}
                                              </Box>
                                            )}
                                            {entry.testEvidence.test_file && (
                                              <Typography sx={{ mt: 0.25, fontSize: '0.58rem', color: colors.darkGreen }}>
                                                {entry.testEvidence.test_file}
                                              </Typography>
                                            )}
                                            {entry.testEvidence.test_code && (
                                              <Box sx={{ mt: 0.25, fontSize: '0.57rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                                {entry.testEvidence.test_code}
                                              </Box>
                                            )}
                                          </Box>
                                        ) : (
                                          <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', fontStyle: 'italic' }}>
                                            None
                                          </Typography>
                                        )}
                                      </Box>
                                    </Box>
                                  ) : null}
                                </Box>
                              </Box>
                          );
                        })()}
                      </Stack>
                    )}
                    </Box>
                  </Accordion>
                ))
              )}

            </Stack>
          )}
        </Box>
      </Accordion>

      <Dialog
        open={batchReviewOpen}
        onClose={() => !isBatchRefining && !isBatchApplying && setBatchReviewOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle sx={{ fontSize: '0.86rem', fontWeight: 700, py: 1.1 }}>
          Batch Refine Review
        </DialogTitle>
        <DialogContent>
          <Stack spacing={1} sx={{ mt: 0.4 }}>
            {batchError && <Alert severity="error">{batchError}</Alert>}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
              <Chip size="small" label={`Total ${batchCounts.total}`} sx={{ fontSize: '0.62rem', height: 18 }} />
              <Chip size="small" label={`Ready ${batchCounts.ready}`} sx={{ fontSize: '0.62rem', height: 18, bgcolor: colors.surfaceSuccessSoft, color: colors.successText }} />
              <Chip size="small" label={`Approved ${batchCounts.approved}`} sx={{ fontSize: '0.62rem', height: 18, bgcolor: colors.surfaceSuccess, color: colors.successText }} />
              <Chip size="small" label={`Applied ${batchCounts.updated}`} sx={{ fontSize: '0.62rem', height: 18, bgcolor: colors.surfaceSuccessStrong, color: colors.successText }} />
              {batchCounts.error > 0 && (
                <Chip size="small" label={`Errors ${batchCounts.error}`} sx={{ fontSize: '0.62rem', height: 18, bgcolor: colors.surfaceDanger, color: colors.dangerText }} />
              )}
            </Box>

            {batchRefineResults.length === 0 ? (
              <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>
                {isBatchRefining ? 'Running batch refine...' : 'No batch results yet.'}
              </Typography>
            ) : (
              (() => {
                const currentIndex = Math.min(Math.max(batchRefineIndex, 0), batchRefineResults.length - 1);
                const current = batchRefineResults[currentIndex];
                const rule = current.ruleUsage.rule;
                const refinedRule = current.refined;
                return (
                  <Stack spacing={0.8}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
                      <Box>
                        <Typography sx={{ fontSize: '0.76rem', fontWeight: 700 }}>
                          {rule.title || 'Rule'}
                        </Typography>
                        <Typography sx={{ fontSize: '0.62rem', color: 'text.secondary' }}>
                          Rule {currentIndex + 1} of {batchRefineResults.length}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                        {batchRefineResults.length > 1 && (
                          <>
                            <IconButton
                              size="small"
                              disableRipple
                              disabled={currentIndex === 0}
                              onClick={() => setBatchRefineIndex((prev) => Math.max(0, prev - 1))}
                              sx={{ p: 0.2, color: colors.grey, '&:focus': { outline: 'none' } }}
                            >
                              <ChevronLeftIcon fontSize="small" />
                            </IconButton>
                            <IconButton
                              size="small"
                              disableRipple
                              disabled={currentIndex >= batchRefineResults.length - 1}
                              onClick={() => setBatchRefineIndex((prev) => Math.min(batchRefineResults.length - 1, prev + 1))}
                              sx={{ p: 0.2, color: colors.grey, '&:focus': { outline: 'none' } }}
                            >
                              <ChevronRightIcon fontSize="small" />
                            </IconButton>
                          </>
                        )}
                        <Chip
                          label={current.status === 'updated' ? 'APPLIED' : current.status.toUpperCase()}
                          size="small"
                          sx={{
                            fontSize: '0.62rem',
                            height: 18,
                            bgcolor:
                              current.status === 'approved' || current.status === 'updated'
                                ? colors.surfaceSuccess
                                : current.status === 'error'
                                  ? colors.surfaceDanger
                                  : colors.surfaceMuted,
                            color:
                              current.status === 'approved' || current.status === 'updated'
                                ? colors.successText
                                : current.status === 'error'
                                  ? colors.dangerText
                                  : colors.secondaryText,
                          }}
                        />
                      </Box>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 0.8 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4, flexWrap: 'wrap' }}>
                        <Chip label={rule.category || 'uncategorized'} size="small" sx={{ fontSize: '0.6rem', height: 17, bgcolor: `${colors.green}1f`, color: colors.darkGreen }} />
                        {!isPersistedRuleInKnowledgeBase(rule) && (
                          <Chip label="Will be added to Rules Mgmt" size="small" sx={{ fontSize: '0.6rem', height: 17, bgcolor: colors.surfaceWarning, color: colors.warningText }} />
                        )}
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                        <Tooltip title="Approve for apply">
                          <span>
                            <IconButton
                              size="small"
                              disableRipple
                              disabled={!refinedRule || isBatchApplying}
                              onClick={() =>
                                setBatchRefineResults((prev) =>
                                  prev.map((item, idx) =>
                                    idx === currentIndex ? { ...item, status: 'approved', error: undefined } : item
                                  )
                                )
                              }
                              sx={{ p: 0.25, color: colors.green, '&:focus': { outline: 'none' } }}
                            >
                              <CheckIcon sx={{ fontSize: '0.9rem' }} />
                            </IconButton>
                          </span>
                        </Tooltip>
                        <Tooltip title="Skip">
                          <IconButton
                            size="small"
                            disableRipple
                            disabled={isBatchApplying}
                            onClick={() =>
                              setBatchRefineResults((prev) =>
                                prev.map((item, idx) =>
                                  idx === currentIndex ? { ...item, status: 'skipped', error: undefined } : item
                                )
                              )
                            }
                            sx={{ p: 0.25, color: colors.grey, '&:focus': { outline: 'none' } }}
                          >
                            <CloseIcon sx={{ fontSize: '0.9rem' }} />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </Box>

                    {current.error ? (
                      <Alert severity="error">{current.error}</Alert>
                    ) : refinedRule ? (
                      <Stack spacing={0.75}>
                        <Box sx={{ p: 0.8, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                          <Typography sx={{ fontSize: '0.66rem', fontWeight: 700, mb: 0.45 }}>
                            Notes Used for Refine
                          </Typography>
                          {current.notesUsed && current.notesUsed.length > 0 ? (
                            (() => {
                              const noteTotal = current.notesUsed!.length;
                              const noteCursorKey = current.ruleUsage.rule.key || String(currentIndex);
                              const rawNoteIndex = batchNoteCursorByRule[noteCursorKey] ?? 0;
                              const noteIndex = Math.min(Math.max(rawNoteIndex, 0), noteTotal - 1);
                              const n = current.notesUsed![noteIndex];
                              return (
                                <Stack spacing={0.4}>
                                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                    <Typography sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
                                      Note {noteIndex + 1} of {noteTotal}
                                    </Typography>
                                    {noteTotal > 1 && (
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.2 }}>
                                        <IconButton
                                          size="small"
                                          disableRipple
                                          disabled={noteIndex === 0}
                                          onClick={() =>
                                            setBatchNoteCursorByRule((prev) => ({
                                              ...prev,
                                              [noteCursorKey]: Math.max(0, noteIndex - 1),
                                            }))
                                          }
                                          sx={{ p: 0.2, color: colors.grey, '&:focus': { outline: 'none' } }}
                                        >
                                          <ChevronLeftIcon fontSize="small" />
                                        </IconButton>
                                        <IconButton
                                          size="small"
                                          disableRipple
                                          disabled={noteIndex >= noteTotal - 1}
                                          onClick={() =>
                                            setBatchNoteCursorByRule((prev) => ({
                                              ...prev,
                                              [noteCursorKey]: Math.min(noteTotal - 1, noteIndex + 1),
                                            }))
                                          }
                                          sx={{ p: 0.2, color: colors.grey, '&:focus': { outline: 'none' } }}
                                        >
                                          <ChevronRightIcon fontSize="small" />
                                        </IconButton>
                                      </Box>
                                    )}
                                  </Box>
                                <Box sx={{ p: 0.45, bgcolor: colors.surfaceMutedAlt, borderRadius: 1 }}>
                                  <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary' }}>
                                    {n.itemLabel} • {n.verdict.toUpperCase()}
                                    {n.verificationIndex !== null ? ` • v${n.verificationIndex + 1}` : ''}
                                  </Typography>
                                  <Typography sx={{ fontSize: '0.61rem', mt: 0.15, whiteSpace: 'pre-wrap' }}>
                                    {n.noteText}
                                  </Typography>
                                  {n.explanation && (
                                    <Typography sx={{ fontSize: '0.58rem', mt: 0.2, color: 'text.secondary', whiteSpace: 'pre-wrap' }}>
                                      Explanation: {n.explanation}
                                    </Typography>
                                  )}
                                  <Box sx={{ mt: 0.35, p: 0.45, bgcolor: colors.surfaceSuccessTint, borderRadius: 0.7 }}>
                                    <Typography sx={{ fontSize: '0.58rem', color: colors.darkGreen, whiteSpace: 'pre-wrap' }}>
                                      Code: {n.codeEvidence || 'None'}
                                    </Typography>
                                    <Typography sx={{ fontSize: '0.58rem', color: colors.darkGreen, whiteSpace: 'pre-wrap' }}>
                                      Test: {n.testEvidence || 'None'}
                                    </Typography>
                                  </Box>
                                  {(n.codeSnippet || n.testCommand || n.testOutput || n.testCode) && (
                                    <Box sx={{ mt: 0.35, p: 0.45, bgcolor: colors.surfaceMutedAlt, borderRadius: 0.7 }}>
                                      {n.codeSnippet && (
                                        <>
                                          <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', mb: 0.2 }}>
                                            Code Snippet
                                          </Typography>
                                          <Box sx={{ fontSize: '0.57rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', mb: 0.35 }}>
                                            {n.codeSnippet}
                                          </Box>
                                        </>
                                      )}
                                      {n.testCommand && (
                                        <>
                                          <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', mb: 0.2 }}>
                                            Test Command
                                          </Typography>
                                          <Box sx={{ fontSize: '0.57rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', mb: 0.35 }}>
                                            {n.testCommand}
                                          </Box>
                                        </>
                                      )}
                                      {n.testOutput && (
                                        <>
                                          <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', mb: 0.2 }}>
                                            Test Output
                                          </Typography>
                                          <Box sx={{ fontSize: '0.57rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', mb: 0.35 }}>
                                            {n.testOutput}
                                          </Box>
                                        </>
                                      )}
                                      {n.testCode && (
                                        <>
                                          <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', mb: 0.2 }}>
                                            Test Code
                                          </Typography>
                                          <Box sx={{ fontSize: '0.57rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                            {n.testCode}
                                          </Box>
                                        </>
                                      )}
                                    </Box>
                                  )}
                                </Box>
                                </Stack>
                              );
                            })()
                          ) : (
                            <Typography sx={{ fontSize: '0.62rem', color: 'text.secondary' }}>
                              No mapped notes found.
                            </Typography>
                          )}
                        </Box>

                        <Box sx={{ p: 0.8, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                          <Typography sx={{ fontSize: '0.66rem', fontWeight: 700, mb: 0.5 }}>
                            Proposed Changes (Diff)
                          </Typography>
                          {[
                            { label: 'Content', key: 'content', before: rule.content || '', after: refinedRule.content || '', multiline: true },
                          ].map((field) => {
                            const fieldEditKey = `batch-${currentIndex}-${field.key}`;
                            const isEditing = editingDiffField === fieldEditKey;
                            const draftValue = diffDrafts[fieldEditKey] ?? field.after;
                            return (
                            <Box key={field.label} sx={{ mb: 0.55 }}>
                              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.2 }}>
                                <Typography sx={{ fontSize: '0.61rem', color: 'text.secondary' }}>
                                  {field.label}
                                </Typography>
                                {!isEditing && (
                                  <Tooltip title={`Edit ${field.label}`}>
                                    <IconButton
                                      size="small"
                                      disableRipple
                                      sx={{ p: 0.2, color: colors.grey, '&:focus': { outline: 'none' } }}
                                      onClick={() => {
                                        setEditingDiffField(fieldEditKey);
                                        setDiffDrafts((prev) => ({ ...prev, [fieldEditKey]: field.after }));
                                      }}
                                    >
                                      <EditOutlinedIcon sx={{ fontSize: '0.82rem' }} />
                                    </IconButton>
                                  </Tooltip>
                                )}
                              </Box>
                              <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 0.5 }}>
                                <Box sx={{ p: 0.45, bgcolor: colors.surfaceMutedAlt, borderRadius: 1 }}>
                                  <Typography sx={{ fontSize: '0.57rem', color: 'text.secondary', mb: 0.1 }}>Before</Typography>
                                  <Typography sx={{ fontSize: '0.61rem', whiteSpace: 'pre-wrap' }}>
                                    {field.before || 'None'}
                                  </Typography>
                                </Box>
                                <Box sx={{ p: 0.45, bgcolor: colors.surfaceSuccessTint, borderRadius: 1 }}>
                                  <Typography sx={{ fontSize: '0.57rem', color: 'text.secondary', mb: 0.1 }}>After</Typography>
                                  {isEditing ? (
                                    <>
                                      <TextField
                                        fullWidth
                                        multiline={field.multiline}
                                        minRows={field.multiline ? 2 : undefined}
                                        value={draftValue}
                                        onChange={(e) => setDiffDrafts((prev) => ({ ...prev, [fieldEditKey]: e.target.value }))}
                                        sx={{ '& .MuiInputBase-input': { fontSize: '0.6rem', py: 0.3 } }}
                                      />
                                      <Box sx={{ mt: 0.3, display: 'flex', gap: 0.25 }}>
                                        <Tooltip title="Save">
                                          <IconButton
                                            size="small"
                                            disableRipple
                                            sx={{ p: 0.2, color: colors.green, '&:focus': { outline: 'none' } }}
                                            onClick={() => {
                                              const nextValue = (diffDrafts[fieldEditKey] ?? '').trimEnd();
                                              setBatchRefineResults((prev) =>
                                                prev.map((item, idx) => {
                                                  if (idx !== currentIndex || !item.refined) return item;
                                                  return {
                                                    ...item,
                                                    refined: {
                                                      ...item.refined,
                                                      content: nextValue,
                                                    },
                                                  };
                                                })
                                              );
                                              setEditingDiffField(null);
                                            }}
                                          >
                                            <CheckIcon sx={{ fontSize: '0.82rem' }} />
                                          </IconButton>
                                        </Tooltip>
                                        <Tooltip title="Cancel">
                                          <IconButton
                                            size="small"
                                            disableRipple
                                            sx={{ p: 0.2, color: colors.grey, '&:focus': { outline: 'none' } }}
                                            onClick={() => {
                                              setDiffDrafts((prev) => {
                                                const next = { ...prev };
                                                delete next[fieldEditKey];
                                                return next;
                                              });
                                              setEditingDiffField(null);
                                            }}
                                          >
                                            <CloseIcon sx={{ fontSize: '0.82rem' }} />
                                          </IconButton>
                                        </Tooltip>
                                      </Box>
                                    </>
                                  ) : hasFieldChange(field.before, field.after) ? (
                                    <InlineDiffText before={field.before || ''} after={field.after || ''} />
                                  ) : (
                                    <Typography sx={{ fontSize: '0.61rem', whiteSpace: 'pre-wrap' }}>
                                      {field.after || 'None'}
                                    </Typography>
                                  )}
                                </Box>
                              </Box>
                            </Box>
                            );
                          })}
                        </Box>
                      </Stack>
                    ) : (
                      <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary' }}>
                        Waiting for refine result...
                      </Typography>
                    )}
                  </Stack>
                );
              })()
            )}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, gap: 0.6 }}>
          <Tooltip title="Close">
            <IconButton
              size="small"
              disableRipple
              onClick={() => setBatchReviewOpen(false)}
              sx={{ p: 0.35, color: colors.grey, '&:focus': { outline: 'none' } }}
            >
              <CloseIcon sx={{ fontSize: '0.95rem' }} />
            </IconButton>
          </Tooltip>
          <CompactIconButton
            label={isBatchApplying ? 'Applying approved batch changes' : `Apply approved batch changes (${batchCounts.approved})`}
            icon={<CheckIcon sx={{ fontSize: '0.95rem' }} />}
            tone="green"
            onClick={applyBatchApproved}
            disabled={batchCounts.approved === 0}
            loading={isBatchApplying}
          />
        </DialogActions>
      </Dialog>

      <Dialog open={!!refineTarget} onClose={() => !isRefining && !isUpdating && setRefineTarget(null)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontSize: '0.86rem', fontWeight: 700, py: 1.1 }}>Refine Rule</DialogTitle>
        <DialogContent>
          {refineTarget && (
            <Stack spacing={1.25} sx={{ mt: 0.5 }}>
              {refineError && <Alert severity="error">{refineError}</Alert>}
              <Typography sx={{ fontSize: '0.66rem', color: 'text.secondary' }}>
                This uses notes attached to task proof records, then saves or updates the refined rule in Rules Management.
              </Typography>
              <Box sx={{ p: 0.8, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Typography sx={{ fontSize: '0.66rem', fontWeight: 700, mb: 0.55 }}>
                  Current Rule Fields
                </Typography>
                <Stack spacing={0.45}>
                  <Typography sx={{ fontSize: '0.62rem' }}>
                    <strong>Category:</strong> {refineTarget.rule.category || 'uncategorized'}
                  </Typography>
                  <Typography sx={{ fontSize: '0.62rem' }}>
                    <strong>Strict:</strong> {refineTarget.rule.is_strict ? 'Yes' : 'No'} • <strong>Testable:</strong> {refineTarget.rule.is_testable ? 'Yes' : 'No'}
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
                    <Chip
                      label={isPersistedRuleInKnowledgeBase(refineTarget.rule) ? 'Already in Rules Mgmt' : 'Will be added on save'}
                      size="small"
                      sx={{
                        bgcolor: isPersistedRuleInKnowledgeBase(refineTarget.rule) ? colors.surfaceSuccessSoft : colors.surfaceWarning,
                        color: isPersistedRuleInKnowledgeBase(refineTarget.rule) ? colors.successText : colors.warningText,
                        fontSize: '0.6rem',
                        height: 18,
                      }}
                    />
                  </Box>
                  <Box sx={{ p: 0.55, bgcolor: colors.surfaceMutedAlt, borderRadius: 1 }}>
                    <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', mb: 0.15 }}>Content</Typography>
                    <Typography sx={{ fontSize: '0.62rem', whiteSpace: 'pre-wrap' }}>
                      {refineTarget.rule.content || 'None'}
                    </Typography>
                  </Box>
                  {refineTarget.rule.context ? (
                    <Box sx={{ p: 0.55, bgcolor: colors.surfaceMutedAlt, borderRadius: 1 }}>
                      <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', mb: 0.15 }}>Context</Typography>
                      <Typography sx={{ fontSize: '0.62rem', whiteSpace: 'pre-wrap' }}>
                        {refineTarget.rule.context}
                      </Typography>
                    </Box>
                  ) : null}
                  {refineTarget.rule.evidence ? (
                    <Box sx={{ p: 0.55, bgcolor: colors.surfaceMutedAlt, borderRadius: 1 }}>
                      <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', mb: 0.15 }}>Evidence</Typography>
                      <Typography sx={{ fontSize: '0.62rem', whiteSpace: 'pre-wrap' }}>
                        {refineTarget.rule.evidence}
                      </Typography>
                    </Box>
                  ) : null}
                </Stack>
              </Box>
              <Box sx={{ p: 0.8, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Typography sx={{ fontSize: '0.66rem', fontWeight: 700, mb: 0.55 }}>
                  Proof Notes for Refine
                </Typography>
                {refineTarget.entries.length === 0 ? (
                  <Typography sx={{ fontSize: '0.61rem', color: 'text.secondary', fontStyle: 'italic' }}>
                    No proof records found for this rule.
                  </Typography>
                ) : (
                  (() => {
                    const total = refineTarget.entries.length;
                    const currentIndex = Math.min(Math.max(refineNoteIndex, 0), total - 1);
                    const entry = refineTarget.entries[currentIndex];
                    const resolved = resolveExistingNote(entry);
                    const noteText = (resolved?.note?.note_text || '').trim();
                    return (
                      <Stack spacing={0.5}>
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <Typography sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
                            Note {currentIndex + 1} of {total}
                          </Typography>
                          {total > 1 && (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.2 }}>
                              <IconButton
                                size="small"
                                disabled={currentIndex === 0}
                                onClick={() => setRefineNoteIndex((prev) => Math.max(0, prev - 1))}
                                sx={{ p: 0.2, color: colors.grey, '&:focus': { outline: 'none' } }}
                              >
                                <ChevronLeftIcon fontSize="small" />
                              </IconButton>
                              <IconButton
                                size="small"
                                disabled={currentIndex >= total - 1}
                                onClick={() => setRefineNoteIndex((prev) => Math.min(total - 1, prev + 1))}
                                sx={{ p: 0.2, color: colors.grey, '&:focus': { outline: 'none' } }}
                              >
                                <ChevronRightIcon fontSize="small" />
                              </IconButton>
                            </Box>
                          )}
                        </Box>
                        <Box sx={{ p: 0.55, bgcolor: colors.surfaceMutedAlt, borderRadius: 1 }}>
                          <Typography sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
                            {entry.itemLabel || 'Unknown item'} • {entry.verdict.toUpperCase()}
                          </Typography>
                          <Typography sx={{ fontSize: '0.61rem', mt: 0.2, whiteSpace: 'pre-wrap' }}>
                            <strong>Note:</strong> {noteText || 'No note'}
                          </Typography>
                        </Box>
                        <Accordion
                          title={<Typography sx={{ fontSize: '0.61rem', fontWeight: 600 }}>View Original Proof</Typography>}
                          defaultOpen={false}
                        >
                          <Box sx={{ p: 0.35 }}>
                            <Typography sx={{ fontSize: '0.61rem', whiteSpace: 'pre-wrap' }}>
                              {entry.explanation || 'No explanation'}
                            </Typography>
                            {entry.codeBlocks.length > 0 ? (
                              <Box sx={{ mt: 0.4 }}>
                                <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', mb: 0.2 }}>
                                  Code Evidence
                                </Typography>
                                <Stack spacing={0.35}>
                                  {entry.codeBlocks.map((cb, cbIdx) => (
                                    <Box key={cbIdx} sx={{ p: 0.45, bgcolor: colors.surfaceMutedAlt, borderRadius: 1 }}>
                                      <Typography sx={{ fontSize: '0.57rem', color: colors.darkGreen, mb: 0.15 }}>
                                        {cb.file_path || 'Unknown file'}{cb.line_range ? ` (${cb.line_range})` : ''}
                                      </Typography>
                                      <Box sx={{ fontSize: '0.56rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                        {cb.code_snippet || ''}
                                      </Box>
                                    </Box>
                                  ))}
                                </Stack>
                              </Box>
                            ) : null}
                            {entry.testEvidence ? (
                              <Box sx={{ mt: 0.4 }}>
                                <Typography sx={{ fontSize: '0.58rem', color: 'text.secondary', mb: 0.2 }}>
                                  Test Evidence
                                </Typography>
                                <Box sx={{ p: 0.45, bgcolor: colors.surfaceMutedAlt, borderRadius: 1 }}>
                                  <Typography sx={{ fontSize: '0.57rem' }}>
                                    {entry.testEvidence.name || 'Unnamed test'} • {String(entry.testEvidence.result || 'unknown').toUpperCase()}
                                  </Typography>
                                  {entry.testEvidence.command && (
                                    <Box sx={{ mt: 0.2, fontSize: '0.56rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                      {entry.testEvidence.command}
                                    </Box>
                                  )}
                                  {entry.testEvidence.output && (
                                    <Box sx={{ mt: 0.2, fontSize: '0.56rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                      {entry.testEvidence.output}
                                    </Box>
                                  )}
                                  {entry.testEvidence.test_file && (
                                    <Typography sx={{ mt: 0.2, fontSize: '0.57rem', color: colors.darkGreen }}>
                                      {entry.testEvidence.test_file}
                                    </Typography>
                                  )}
                                  {entry.testEvidence.test_code && (
                                    <Box sx={{ mt: 0.2, fontSize: '0.56rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                      {entry.testEvidence.test_code}
                                    </Box>
                                  )}
                                </Box>
                              </Box>
                            ) : null}
                          </Box>
                        </Accordion>
                      </Stack>
                    );
                  })()
                )}
              </Box>
              {!refined ? null : (
                <>
                  <Box sx={{ p: 0.8, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                    <Typography sx={{ fontSize: '0.66rem', fontWeight: 700, mb: 0.55 }}>
                      Proposed Changes (Diff)
                    </Typography>
                    {[
                      {
                        label: 'Content',
                        key: 'content',
                        before: refineTarget.rule.content || '',
                        after: refined.content || '',
                        multiline: true,
                      },
                      {
                        label: 'Context',
                        key: 'context',
                        before: refineTarget.rule.context || '',
                        after: refined.context || '',
                        multiline: true,
                      },
                      {
                        label: 'Evidence',
                        key: 'evidence',
                        before: refineTarget.rule.evidence || '',
                        after: refined.evidence || '',
                        multiline: true,
                      },
                      {
                        label: 'Confidence',
                        key: 'confidence',
                        before: String((refineTarget.rule as any).confidence ?? ''),
                        after: String(refined.confidence ?? ''),
                        multiline: false,
                      },
                      {
                        label: 'Decay',
                        key: 'decay',
                        before: String((refineTarget.rule as any).decay ?? ''),
                        after: String(refined.decay ?? ''),
                        multiline: false,
                      },
                      {
                        label: 'Confidence Reasoning',
                        key: 'confidence_reasoning',
                        before: String((refineTarget.rule as any).confidence_reasoning ?? ''),
                        after: refined.confidence_reasoning || '',
                        multiline: true,
                      },
                      {
                        label: 'Decay Reasoning',
                        key: 'decay_reasoning',
                        before: String((refineTarget.rule as any).decay_reasoning ?? ''),
                        after: refined.decay_reasoning || '',
                        multiline: true,
                      },
                    ].map((field) => {
                      const changed = hasFieldChange(field.before, field.after);
                      const draftValue = diffDrafts[field.key] ?? field.after;
                      const isEditing = editingDiffField === field.key;
                      return (
                        <Box key={field.label} sx={{ mb: 0.65, '&:last-of-type': { mb: 0 } }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.18 }}>
                            <Typography sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
                              {field.label} {changed ? '(changed)' : '(unchanged)'}
                            </Typography>
                            {!isEditing && (
                              <Tooltip title={`Edit ${field.label}`}>
                                <IconButton
                                  size="small"
                                  sx={{ p: 0.25, color: colors.grey }}
                                  onClick={() => {
                                    setEditingDiffField(field.key);
                                    setDiffDrafts((prev) => ({ ...prev, [field.key]: field.after }));
                                  }}
                                >
                                  <EditOutlinedIcon sx={{ fontSize: '0.82rem' }} />
                                </IconButton>
                              </Tooltip>
                            )}
                          </Box>
                          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 0.5 }}>
                            <Box sx={{ p: 0.45, bgcolor: colors.surfaceMutedSoft, borderRadius: 1 }}>
                              <Typography sx={{ fontSize: '0.56rem', color: 'text.secondary', mb: 0.12 }}>Before</Typography>
                              <Typography sx={{ fontSize: '0.6rem', whiteSpace: 'pre-wrap' }}>
                                {field.before || 'None'}
                              </Typography>
                            </Box>
                            <Box sx={{ p: 0.45, bgcolor: colors.surfaceMutedSoft, borderRadius: 1 }}>
                              <Typography sx={{ fontSize: '0.56rem', color: 'text.secondary', mb: 0.12 }}>After</Typography>
                              {isEditing ? (
                                <>
                                  <TextField
                                    fullWidth
                                    multiline={field.multiline}
                                    minRows={field.multiline ? 2 : undefined}
                                    value={draftValue}
                                    onChange={(e) => setDiffDrafts((prev) => ({ ...prev, [field.key]: e.target.value }))}
                                    sx={{
                                      '& .MuiInputBase-input': { fontSize: '0.6rem', py: 0.35 },
                                    }}
                                  />
                                  <Box sx={{ mt: 0.35, display: 'flex', gap: 0.35 }}>
                                    <Tooltip title="Save">
                                      <IconButton
                                        size="small"
                                        sx={{ p: 0.22, color: colors.green }}
                                      onClick={() => {
                                        const nextValue = (diffDrafts[field.key] ?? '').trimEnd();
                                        setRefined((prev) => {
                                          if (!prev) return prev;
                                          if (field.key === 'content') return { ...prev, content: nextValue };
                                          if (field.key === 'context') return { ...prev, context: nextValue || null };
                                          if (field.key === 'evidence') return { ...prev, evidence: nextValue || null };
                                          if (field.key === 'confidence') {
                                            const parsed = Number(nextValue);
                                            return Number.isFinite(parsed) ? { ...prev, confidence: parsed } : prev;
                                          }
                                          if (field.key === 'decay') {
                                            const parsed = Number(nextValue);
                                            return Number.isFinite(parsed) ? { ...prev, decay: parsed } : prev;
                                          }
                                          if (field.key === 'confidence_reasoning') return { ...prev, confidence_reasoning: nextValue };
                                          return { ...prev, decay_reasoning: nextValue };
                                        });
                                        setEditingDiffField(null);
                                      }}
                                    >
                                        <CheckIcon sx={{ fontSize: '0.82rem' }} />
                                      </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Cancel">
                                      <IconButton
                                        size="small"
                                        sx={{ p: 0.22, color: colors.grey }}
                                      onClick={() => {
                                        setDiffDrafts((prev) => {
                                          const next = { ...prev };
                                          delete next[field.key];
                                          return next;
                                        });
                                        setEditingDiffField(null);
                                      }}
                                    >
                                        <CloseIcon sx={{ fontSize: '0.82rem' }} />
                                      </IconButton>
                                    </Tooltip>
                                  </Box>
                                </>
                              ) : (
                                <Box sx={{ bgcolor: changed ? colors.surfaceTint : 'transparent', borderRadius: 0.7, p: 0.35 }}>
                                  {changed ? (
                                    <InlineDiffText before={field.before || ''} after={field.after || ''} />
                                  ) : (
                                    <Typography sx={{ fontSize: '0.6rem', whiteSpace: 'pre-wrap' }}>
                                      {field.after || 'None'}
                                    </Typography>
                                  )}
                                </Box>
                              )}
                              {!changed && (
                                <Typography sx={{ mt: 0.2, fontSize: '0.56rem', color: 'text.secondary' }}>
                                  No changes
                                </Typography>
                              )}
                            </Box>
                          </Box>
                        </Box>
                      );
                    })}
                  </Box>
                </>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, gap: 0.5 }}>
          <Tooltip title="Cancel">
            <IconButton
              size="small"
              disableRipple
              onClick={() => setRefineTarget(null)}
              sx={{
                p: 0.35,
                color: colors.grey,
                '&:hover': { bgcolor: 'rgba(120, 120, 120, 0.1)' },
                '&:focus, &.Mui-focusVisible': { outline: 'none', bgcolor: 'rgba(120, 120, 120, 0.1)' },
              }}
            >
              <CloseIcon sx={{ fontSize: '0.95rem' }} />
            </IconButton>
          </Tooltip>
          {!refined ? (
            <Tooltip title={isRefining ? 'Refining...' : 'Refine'}>
              <span>
                <IconButton
                  size="small"
                  disableRipple
                  onClick={runRefine}
                  disabled={isRefining || isUpdating}
                  sx={{
                    p: 0.35,
                    color: colors.darkGreen,
                    '&:hover': { bgcolor: 'rgba(76, 111, 59, 0.08)' },
                    '&:focus, &.Mui-focusVisible': { outline: 'none', bgcolor: 'rgba(76, 111, 59, 0.08)' },
                  }}
                >
                  <AutoFixHighIcon sx={{ fontSize: '0.95rem' }} />
                </IconButton>
              </span>
            </Tooltip>
          ) : (
            <Tooltip title={isUpdating ? 'Saving...' : refineTarget && isPersistedRuleInKnowledgeBase(refineTarget.rule) ? 'Update Rule' : 'Save to Rules Management'}>
              <span>
                <IconButton
                  size="small"
                  disableRipple
                  onClick={updateRule}
                  disabled={isUpdating}
                  sx={{
                    p: 0.35,
                    color: colors.green,
                    '&:hover': { bgcolor: 'rgba(124, 179, 66, 0.12)' },
                    '&:focus, &.Mui-focusVisible': { outline: 'none', bgcolor: 'rgba(124, 179, 66, 0.12)' },
                  }}
                >
                  <CheckIcon sx={{ fontSize: '0.95rem' }} />
                </IconButton>
              </span>
            </Tooltip>
          )}
        </DialogActions>
      </Dialog>
    </>
  );
}
