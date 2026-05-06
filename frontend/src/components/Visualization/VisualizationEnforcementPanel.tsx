import { useState, useEffect } from 'react';
import { Box, Typography, Stack, Chip, CircularProgress, IconButton } from '@mui/material';
import { Close as CloseIcon, Check as CheckIcon, EditOutlined as EditOutlinedIcon, EditNoteOutlined as EditNoteOutlinedIcon } from '@mui/icons-material';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import ScienceIcon from '@mui/icons-material/Science';
import { Accordion } from '../../design-system/Accordion';
import { CompactIconButton } from '../../design-system/CompactIconButton';
import { TextField } from '../../design-system/TextField';
import { colors } from '../../design-system/colors';
import { api } from '../../services/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { prism } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { createRuleNoteKey, toRuleNoteRecord } from './ruleNotes';
import type { RuleNoteRecord } from './ruleNotes';
import type { EvidenceRecord } from './evidence';
import { getRuleVerificationRecordsForItem } from './evidence';

interface Rule {
  category: string;
  text: string;
  context?: string;
  needs_strict_enforcement?: boolean;
  is_testable?: boolean;
  kb_item_id?: string;
}

interface InheritedRule {
  rule: Rule;
  source: string;
}

interface PlanItem {
  id: string;
  title: string;
  rules?: Rule[];
  inherited_rules?: InheritedRule[];
  children?: PlanItem[];
}

interface VisualizationEnforcementPanelProps {
  chatId: string | null;
  selectedItemId: string | null;
  selectedItem: PlanItem | null;
  evidence?: EvidenceRecord[];
  onClose?: () => void;
  onPlanUpdate?: () => Promise<void>;
  notesRefreshKey?: number;
  onRuleNotesSaved?: () => void;
}

export function VisualizationEnforcementPanel({ chatId, selectedItemId, selectedItem, evidence = [], onClose, onPlanUpdate, notesRefreshKey, onRuleNotesSaved }: VisualizationEnforcementPanelProps) {
  const [config, setConfig] = useState<any>(null);
  const [enforcementData, setEnforcementData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [enforcing, setEnforcing] = useState(false);
  const [enforceMessage, setEnforceMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [ruleNotes, setRuleNotes] = useState<Record<string, RuleNoteRecord>>({});
  const [noteSaveState, setNoteSaveState] = useState<Record<string, 'idle' | 'saving' | 'saved' | 'error'>>({});
  const [noteEditorOpen, setNoteEditorOpen] = useState<Record<string, boolean>>({});
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const normalizeCode = (text: string) => (text || '').replace(/\\n/g, '\n');
  
  // Load config on mount
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const result = await api.getConfig();
        if (result.success && result.config) {
          setConfig(result.config);
        }
      } catch (error) {
        console.error('Failed to load config:', error);
      }
    };
    loadConfig();
  }, []);

  useEffect(() => {
    const loadRuleNotes = async () => {
      if (!chatId) return;
      try {
        const result = await api.getRuleNotes(chatId);
        if (result.success) {
          setRuleNotes((result.notes || {}) as Record<string, RuleNoteRecord>);
        }
      } catch (error) {
        console.error('Failed to load rule notes:', error);
      }
    };
    loadRuleNotes();
  }, [chatId, notesRefreshKey]);
  
  // Load enforcement data if in simple or selective mode
  useEffect(() => {
    // Clear old data immediately when step changes
    setEnforcementData(null);
    setEnforceMessage(null);
    
    if (!chatId || !selectedItemId || !config) return;
    
    const needsEnforcementData = 
      config.enforcement_mode === 'no-verification' || 
      config.enforcement_mode === 'selective-verification';
    if (!needsEnforcementData) return;
    
    const loadEnforcementData = async () => {
      setLoading(true);
      
      try {
        const result = await api.getEnforcementHistory(chatId);
        if (result.success && result.enforcement_history) {
          const items = result.enforcement_history.items || {};
          const itemData = items[selectedItemId];
          if (itemData) {
            setEnforcementData(itemData);
          }
        }
      } catch (error) {
        console.error('Failed to load enforcement data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    loadEnforcementData();
  }, [chatId, selectedItemId, config]);
  
  const handleEnforce = async () => {
    if (!chatId || !selectedItemId) return;
    
    setEnforcing(true);
    setEnforceMessage(null);
    
    try {
      const result = await api.enforceItem(chatId, selectedItemId);
      
      if (result.success) {
        setEnforceMessage({ type: 'success', text: 'Enforcement completed successfully' });
        // Reload enforcement data to show new results
        setLoading(true);
        try {
          const historyResult = await api.getEnforcementHistory(chatId);
          if (historyResult.success && historyResult.enforcement_history) {
            const items = historyResult.enforcement_history.items || {};
            const itemData = items[selectedItemId];
            if (itemData) {
              setEnforcementData(itemData);
            }
          }
        } catch (error) {
          console.error('Failed to reload enforcement data:', error);
        } finally {
          setLoading(false);
        }
        // Optionally refresh plan if callback provided
        if (onPlanUpdate) {
          await onPlanUpdate();
        }
      } else {
        setEnforceMessage({ 
          type: 'error', 
          text: result.error || 'Enforcement failed' 
        });
      }
    } catch (error: any) {
      console.error('Failed to enforce item:', error);
      setEnforceMessage({ 
        type: 'error', 
        text: error.message || 'Failed to enforce item' 
      });
    } finally {
      setEnforcing(false);
    }
  };
  
  const getVerdictColor = (v: string) => {
    if (v === 'pass') return colors.green;
    if (v === 'fail') return colors.red;
    return colors.gold;
  };
  
  const saveSingleNote = async (
    noteKey: string,
    recordsOverride?: Record<string, RuleNoteRecord>
  ): Promise<boolean> => {
    if (!chatId) return false;
    setNoteSaveState((prev) => ({ ...prev, [noteKey]: 'saving' }));
    try {
      const payload = recordsOverride || ruleNotes;
      const result = await api.updateRuleNotes(chatId, payload);
      if (!result.success) throw new Error(result.error || 'Failed to save note');
      setNoteSaveState((prev) => ({ ...prev, [noteKey]: 'saved' }));
      onRuleNotesSaved?.();
      setTimeout(() => {
        setNoteSaveState((prev) => ({ ...prev, [noteKey]: 'idle' }));
      }, 1200);
      return true;
    } catch (error) {
      console.error('Failed to save note:', error);
      setNoteSaveState((prev) => ({ ...prev, [noteKey]: 'error' }));
      return false;
    }
  };

  const updateRuleNote = (
    noteKey: string,
    noteText: string,
    meta: Omit<RuleNoteRecord, 'note_key' | 'chat_id' | 'note_text'>
  ): Record<string, RuleNoteRecord> | null => {
    if (!chatId) return null;
    const noteRecord = toRuleNoteRecord(chatId, noteKey, noteText, meta);
    const nextRecords: Record<string, RuleNoteRecord> = {
      ...ruleNotes,
      [noteKey]: noteRecord,
    };
    setRuleNotes(nextRecords);
    return nextRecords;
  };

  const openNoteEditor = (noteKey: string) => {
    setNoteEditorOpen((prev) => ({ ...prev, [noteKey]: true }));
    setNoteDrafts((prev) => ({
      ...prev,
      [noteKey]: prev[noteKey] ?? (ruleNotes[noteKey]?.note_text || ''),
    }));
  };

  const closeNoteEditor = (noteKey: string) => {
    setNoteEditorOpen((prev) => ({ ...prev, [noteKey]: false }));
  };

  const renderVerificationNote = (
    noteKey: string,
    noteMeta: Omit<RuleNoteRecord, 'note_key' | 'chat_id' | 'note_text'>
  ) => {
    const savedText = ruleNotes[noteKey]?.note_text || '';
    const isOpen = !!noteEditorOpen[noteKey];
    const draft = noteDrafts[noteKey] ?? savedText;

    if (!isOpen) {
      if (savedText.trim()) {
        return (
          <Box sx={{ mt: 1.2, p: 0.8, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
            <Typography sx={{ fontSize: '0.66rem', color: 'text.secondary', mb: 0.3 }}>
              Note
            </Typography>
            <Typography sx={{ fontSize: '0.68rem', whiteSpace: 'pre-wrap' }}>
              {savedText}
            </Typography>
            <Box sx={{ mt: 0.6 }}>
              <CompactIconButton
                label="Edit note"
                icon={<EditOutlinedIcon sx={{ fontSize: 16 }} />}
                tone="dark-green"
                onClick={() => openNoteEditor(noteKey)}
              />
            </Box>
          </Box>
        );
      }

      return (
        <Box sx={{ mt: 1.0 }}>
          <CompactIconButton
            label="Add note"
            icon={<EditNoteOutlinedIcon sx={{ fontSize: 16 }} />}
            tone="dark-green"
            onClick={() => openNoteEditor(noteKey)}
          />
        </Box>
      );
    }

    return (
      <>
        <TextField
          fullWidth
          multiline
          minRows={2}
          placeholder="Add review note for this verification..."
          value={draft}
          onChange={(e) => setNoteDrafts((prev) => ({ ...prev, [noteKey]: e.target.value }))}
          inputProps={{ 'aria-label': 'Proof Note' }}
          sx={{
            mt: 1.2,
            '& .MuiInputBase-input': { fontSize: '0.66rem' },
            '& .MuiInputBase-input::placeholder': { fontSize: '0.64rem' },
          }}
        />
        <Box sx={{ mt: 0.6, display: 'flex', alignItems: 'center', gap: 0.8 }}>
          <CompactIconButton
            label="Save note"
            icon={<CheckIcon sx={{ fontSize: 16 }} />}
            tone="green"
            onClick={async () => {
              const nextRecords = updateRuleNote(noteKey, draft, noteMeta);
              const ok = await saveSingleNote(noteKey, nextRecords || undefined);
              if (ok) closeNoteEditor(noteKey);
            }}
            loading={noteSaveState[noteKey] === 'saving'}
          />
          <CompactIconButton
            label="Cancel note editing"
            icon={<CloseIcon sx={{ fontSize: 16 }} />}
            tone="grey"
            onClick={() => closeNoteEditor(noteKey)}
          />
          {noteSaveState[noteKey] === 'saved' && (
            <Typography sx={{ fontSize: '0.66rem', color: colors.green }}>
              Saved
            </Typography>
          )}
          {noteSaveState[noteKey] === 'error' && (
            <Typography sx={{ fontSize: '0.66rem', color: colors.red }}>
              Failed to save
            </Typography>
          )}
        </Box>
      </>
    );
  };


  if (!chatId || !selectedItemId || !selectedItem) {
    return (
      <Box
        sx={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'background.paper',
          borderLeft: '1px solid',
          borderColor: 'divider',
          p: 2,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          Select a plan item to view enforcement evidence
        </Typography>
      </Box>
    );
  }

  const rules = selectedItem.rules || [];
  const inheritedRules = selectedItem.inherited_rules || [];
  const hasChildren = selectedItem.children && selectedItem.children.length > 0;

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        bgcolor: 'background.paper',
        display: 'flex',
        flexDirection: 'column',
        borderLeft: '1px solid',
        borderColor: 'divider',
        overflow: 'hidden',
      }}
    >
      <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Typography sx={{ color: 'text.primary', fontSize: '0.92rem', fontWeight: 600, lineHeight: 1.2 }}>
            Enforcement Evidence
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Item: {selectedItemId}
          </Typography>
        </div>
        {onClose && (
          <IconButton onClick={onClose} size="small" sx={{ color: colors.grey }}>
            <CloseIcon />
          </IconButton>
        )}
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {/* Enforce Button - Only show for leaf nodes in simple mode */}
        {config?.enforcement_mode === 'no-verification' && !hasChildren && (
          <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <CompactIconButton
                label={enforcing ? 'Enforcing this item' : 'Enforce this item'}
                icon={<FactCheckOutlinedIcon sx={{ fontSize: 18 }} />}
                tone="green"
                onClick={handleEnforce}
                disabled={loading}
                loading={enforcing}
              />
            </Box>
            {enforceMessage && (
              <Box 
                sx={{ 
                  mt: 1, 
                  p: 1.5, 
                  borderRadius: 1, 
                  bgcolor: enforceMessage.type === 'success' ? colors.surfaceInfo : colors.surfaceWarningStrong,
                  border: `1px solid ${enforceMessage.type === 'success' ? colors.surfaceInfoBorder : colors.warningBorder}`
                }}
              >
                <Typography 
                  variant="caption" 
                  sx={{ 
                    color: enforceMessage.type === 'success' ? colors.green : colors.gold,
                    fontWeight: 600
                  }}
                >
                  {enforceMessage.text}
                </Typography>
              </Box>
            )}
          </Box>
        )}
        
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={24} sx={{ color: colors.green }} />
          </Box>
        )}
        
        {config?.enforcement_mode === 'no-verification' && enforcementData && !loading ? (
          <>
            {/* Simple Mode: Display Enforcement Data */}
            <Box sx={{ mb: 2, p: 2, bgcolor: colors.surfaceInfo, borderRadius: 1, border: `1px solid ${colors.surfaceInfoBorder}` }}>
              <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                Detected Evidence
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {enforcementData.detected_evidence}
              </Typography>
            </Box>
            
            <Accordion title={`Rules Verified (${enforcementData.rules_verified?.length || 0})`} defaultOpen>
              {enforcementData.rules_verified && enforcementData.rules_verified.length > 0 ? (
                <Stack spacing={2}>
                  {enforcementData.rules_verified.map((rule: any, index: number) => (
                    <Box key={index} sx={{ pb: 2, pt: 1, px: 1, borderBottom: index < (enforcementData.rules_verified?.length || 0) - 1 ? '1px solid' : 'none', borderColor: 'divider' }}>
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
                        <Chip
                          label={rule.verdict.toUpperCase()}
                          size="small"
                          sx={{
                            bgcolor: getVerdictColor(rule.verdict),
                            color: 'white',
                            fontSize: '0.7rem',
                            fontWeight: 'bold',
                          }}
                        />
                        {rule.rule_id && (
                          <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
                            {rule.rule_id}
                          </Typography>
                        )}
                      </Box>
                      <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                        {rule.rule_text}
                      </Typography>
                      <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary', fontStyle: 'italic' }}>
                        {rule.evidence}
                      </Typography>
                      {rule.code_blocks && rule.code_blocks.length > 0 && rule.code_blocks.map((codeBlock: any, cbIndex: number) => (
                        <Box key={cbIndex} sx={{ mb: cbIndex < rule.code_blocks.length - 1 ? 2 : 0 }}>
                          <Typography variant="caption" sx={{ display: 'block', color: colors.green, fontWeight: 600, mb: 0.5 }}>
                            📄 {codeBlock.file}
                            {codeBlock.lines && ` (${codeBlock.lines})`}
                          </Typography>
                          <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
                            <SyntaxHighlighter
                              language="typescript"
                              style={prism}
                              customStyle={{ 
                                fontSize: '0.75rem', 
                                margin: 0,
                                backgroundColor: 'white',
                              }}
                            >
                              {normalizeCode(codeBlock.code)}
                            </SyntaxHighlighter>
                          </Box>
                          {codeBlock.annotation && (
                            <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: 'text.secondary' }}>
                              💡 {codeBlock.annotation}
                            </Typography>
                          )}
                        </Box>
                      ))}
                    </Box>
                  ))}
                </Stack>
              ) : (
                <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                  No rules verified.
                </Typography>
              )}
            </Accordion>
          </>
        ) : config?.enforcement_mode === 'no-verification' && !enforcementData && !loading ? (
          <>
            <Box sx={{ mb: 2, p: 2, bgcolor: colors.surfaceWarningStrong, borderRadius: 1, border: `1px solid ${colors.warningBorder}` }}>
              <Typography variant="body2" sx={{ fontWeight: 'bold', color: colors.warningAccent }}>
                Not enforced yet
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Click "Enforce" in the Supervisor panel to verify these rules
              </Typography>
            </Box>
            
            <Accordion title="Rules for this item" defaultOpen>
              {rules.length === 0 && inheritedRules.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                  No rules for this item.
                </Typography>
              ) : (
                <Stack spacing={3}>
                  {rules.length > 0 && !hasChildren && (
                    <Box>
                      <Typography 
                        variant="subtitle2" 
                        sx={{ 
                          fontWeight: 700, 
                          color: colors.green,
                          mb: 1.5,
                          pb: 0.5,
                          borderBottom: `2px solid ${colors.green}30`
                        }}
                      >
                        Own Rules ({rules.length})
                      </Typography>
                      <Stack spacing={2}>
                        {rules.map((rule, index) => (
                          <Box
                            key={index}
                            sx={{
                              pb: 1,
                              borderBottom: index < rules.length - 1 ? '1px solid' : 'none',
                              borderColor: 'divider',
                            }}
                          >
                            <Typography variant="body2" sx={{ fontWeight: 400, mb: 0.5 }}>
                              [{rule.category}] {rule.text}
                            </Typography>
                            {rule.context && (
                              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                {rule.context}
                              </Typography>
                            )}
                          </Box>
                        ))}
                      </Stack>
                    </Box>
                  )}

                  {inheritedRules.length > 0 && (
                    <Box>
                      <Typography 
                        variant="subtitle2" 
                        sx={{ 
                          fontWeight: 700, 
                          color: colors.grey,
                          mb: 1.5,
                          pb: 0.5,
                          borderBottom: `2px solid ${colors.grey}30`
                        }}
                      >
                        Inherited Rules ({inheritedRules.length})
                      </Typography>
                      <Stack spacing={2}>
                        {inheritedRules.map((inheritedRule, index) => {
                          const rule = inheritedRule.rule;
                          return (
                            <Box
                              key={index}
                              sx={{
                                pb: 1,
                                borderBottom: index < inheritedRules.length - 1 ? '1px solid' : 'none',
                                borderColor: 'divider',
                              }}
                            >
                              <Typography variant="body2" sx={{ fontWeight: 400, mb: 0.5 }}>
                                [{rule.category}] {rule.text}
                              </Typography>
                              <Typography variant="caption" sx={{ color: colors.grey, display: 'block', mb: 0.5 }}>
                                (from {inheritedRule.source})
                              </Typography>
                              {rule.context && (
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                  {rule.context}
                                </Typography>
                              )}
                            </Box>
                          );
                        })}
                      </Stack>
                    </Box>
                  )}
                </Stack>
              )}
            </Accordion>
          </>
        ) : (
          <>
            {/* Verification Mode: Split into Strict and Other Rules */}
            {(() => {
              // Split rules into strict
              const strictRules: Array<{ rule: Rule; source: string }> = [];
              
              // Process own rules (only for leaf/substep items)
              if (!hasChildren) {
                rules.forEach((rule) => {
                  if (rule.needs_strict_enforcement) {
                    strictRules.push({ rule, source: 'own' });
                  }
                });
              }
              
              // Process inherited rules
              inheritedRules.forEach((ir) => {
                if (ir.rule.needs_strict_enforcement) {
                  strictRules.push({ rule: ir.rule, source: ir.source });
                }
              });
              
              return (
                <>
                  {/* TOP SECTION - Strict Rules */}
                  {strictRules.length > 0 && (
                    <Typography variant="caption" sx={{ display: 'block', mb: 2, color: 'text.secondary' }}>
                      Coding agent verified with code evidence before step completion
                    </Typography>
                  )}
                  {strictRules.length > 0 && (
                    <Stack spacing={2}>
                        {strictRules.map((item, idx) => {
                          return (
                            <Box key={idx}>
                              <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
                                <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
                                  <Box component="span">
                                    <Typography component="span" sx={{ fontWeight: 400, fontSize: '0.875rem' }}>
                                      [{item.rule.category}] {item.rule.text}
                                    </Typography>
                                    {item.source !== 'own' && (
                                      <Typography component="span" sx={{ ml: 1, color: colors.grey, fontSize: '0.7rem', fontWeight: 400 }}>
                                        (from {item.source})
                                      </Typography>
                                    )}
                                  </Box>
                                </Box>
                                
                                {(() => {
                                  const verificationsForItem = getRuleVerificationRecordsForItem(
                                    evidence,
                                    selectedItemId,
                                    item.rule,
                                  );

                                  if (verificationsForItem.length === 0) {
                                    return (
                                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', py: 2, pl: 1 }}>
                                        No proof records yet.
                                      </Typography>
                                    );
                                  }

                                  return (
                              <Stack spacing={2}>
                                {verificationsForItem.map((verification, listIndex) => {
                                  const noteKey = createRuleNoteKey({
                                    source: 'rule-verification',
                                    evidenceRecordId: verification.record_id,
                                    itemId: verification.item_id || selectedItemId,
                                    ruleKbItemId: item.rule.kb_item_id,
                                    ruleText: item.rule.text,
                                    timestamp: verification.timestamp || '',
                                    index: verification.record_index,
                                  });
                                  const noteMeta: Omit<RuleNoteRecord, 'note_key' | 'chat_id' | 'note_text'> = {
                                    rule_kb_item_id: item.rule.kb_item_id || null,
                                    rule_text: item.rule.text || '',
                                    plan_item_id: (verification.item_id || selectedItemId) || null,
                                    evidence_record_id: verification.record_id,
                                    verification_timestamp: verification.timestamp || null,
                                    verification_index: verification.record_index,
                                    source: 'rule-verification',
                                    verdict: verification.verdict || 'unclear',
                                    explanation: verification.explanation || '',
                                  };
                                  return (
                                  <Box key={verification.record_id} sx={{ pb: 2, pt: 1, px: 1, borderBottom: listIndex < verificationsForItem.length - 1 ? '1px solid' : 'none', borderColor: 'divider' }}>
                                    <Chip
                                      label={verification.verdict.toUpperCase()}
                                      size="small"
                                      sx={{
                                        bgcolor: getVerdictColor(verification.verdict),
                                        color: 'white',
                                        fontSize: '0.7rem',
                                        fontWeight: 'bold',
                                        mb: 1.5,
                                      }}
                                    />
                                    <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.6, color: 'text.primary' }}>
                                      {verification.explanation}
                                    </Typography>
                                    {(verification.artifacts || []).map((codeBlock, cbIndex) => (
                                      <Box key={cbIndex} sx={{ mb: cbIndex < (verification.artifacts || []).length - 1 ? 2 : 0 }}>
                                        <Typography variant="caption" sx={{ display: 'block', color: colors.green, fontWeight: 600, mb: 0.5 }}>
                                          📄 {codeBlock.file_path}
                                          {codeBlock.line_range && ` (${codeBlock.line_range})`}
                                        </Typography>
                                        <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
                                          <SyntaxHighlighter
                                            language="typescript"
                                            style={prism}
                                            customStyle={{ 
                                              fontSize: '0.75rem', 
                                              margin: 0,
                                              backgroundColor: 'white',
                                            }}
                                          >
                                            {normalizeCode(codeBlock.code_snippet || '')}
                                          </SyntaxHighlighter>
                                        </Box>
                                      </Box>
                                    ))}
                                    {verification.tests && (
                                      <Box sx={{ mt: 2, p: 2, borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
                                        <Typography variant="caption" sx={{ fontWeight: 600, color: colors.green, display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
                                          <ScienceIcon sx={{ fontSize: '0.95rem', color: colors.blue }} />
                                          Test Evidence
                                        </Typography>
                                        <Stack spacing={1}>
                                          <Typography variant="caption">
                                            <strong>Test:</strong> {verification.tests.name}
                                          </Typography>
                                          <Typography variant="caption" sx={{ fontFamily: 'monospace', fontSize: '0.7rem', display: 'block', bgcolor: colors.surfaceMutedAlt, p: 1, borderRadius: 0.5 }}>
                                            {verification.tests.command}
                                          </Typography>
                                          <Box>
                                            <Chip
                                              label={String(verification.tests.result || 'unknown').toUpperCase()}
                                              size="small"
                                              sx={{
                                                bgcolor: getVerdictColor(String(verification.tests.result || 'unclear')),
                                                color: 'white',
                                                fontSize: '0.7rem',
                                                fontWeight: 'bold',
                                              }}
                                            />
                                          </Box>
                                          {verification.tests.output && (
                                            <Accordion title="Test Output" defaultOpen={false}>
                                              <Box sx={{ bgcolor: colors.surfaceMutedAlt, p: 1, borderRadius: 0.5, fontFamily: 'monospace', fontSize: '0.7rem', whiteSpace: 'pre-wrap' }}>
                                                {verification.tests.output}
                                              </Box>
                                            </Accordion>
                                          )}
                                          {verification.tests.test_code && (
                                            <Accordion title={`Test Code: ${verification.tests.test_file}`} defaultOpen={false}>
                                              <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
                                                <SyntaxHighlighter
                                                  language="python"
                                                  style={prism}
                                                  customStyle={{
                                                    fontSize: '0.75rem',
                                                    margin: 0,
                                                    backgroundColor: 'white',
                                                  }}
                                                >
                                                  {normalizeCode(verification.tests.test_code)}
                                                </SyntaxHighlighter>
                                              </Box>
                                            </Accordion>
                                          )}
                                          <Typography variant="caption" sx={{ color: colors.green }}>
                                            📄 {verification.tests.test_file}
                                          </Typography>
                                        </Stack>
                                      </Box>
                                    )}
                                    {renderVerificationNote(noteKey, noteMeta)}
                                  </Box>
                                  );
                                })}
                              </Stack>
                                  );
                                })()}
                              </Box>
                            </Box>
                          );
                        })}
                    </Stack>
                  )}
                  
                  {/* Show message if no rules at all */}
                  {strictRules.length === 0 && (
                    <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                      No rules for this item.
                    </Typography>
                  )}
                </>
              );
            })()}
          </>
        )}
      </Box>

    </Box>
  );
}
