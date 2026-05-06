import { useState, useEffect, useRef, useMemo } from 'react';
import { Box, Typography, IconButton, CircularProgress, Tooltip } from '@mui/material';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { TextField } from '../design-system/TextField';
import PauseIcon from '@mui/icons-material/Pause';
import EditIcon from '@mui/icons-material/Edit';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ReactMarkdown from 'react-markdown';
import { api, type VisualizationPlanDocument } from '../services/api';
import { Accordion } from '../design-system/Accordion';
import { CompactIconButton } from '../design-system/CompactIconButton';
import { colors } from '../design-system/colors';
import { SupervisorPanel } from './Visualization/SupervisorPanel';
import { RuleLearningPanel } from './Visualization/RuleLearningPanel';
import { ExtractedPlanView } from './Visualization/ExtractedPlanView';
import { VisualizationEnforcementPanel } from './Visualization/VisualizationEnforcementPanel';
import { RuleReviewPanel } from './Visualization/RuleReviewPanel';
import { ResizableFloatingPanel } from './Visualization/ResizableFloatingPanel';
import type { EvidenceRecord } from './Visualization/evidence';

interface ParsedChatMessage {
  role: 'user' | 'assistant' | 'other';
  content: string;
}

type PlayOverlayState = 'detecting' | 'enriching' | 'enriched' | 'no_rules';

interface PlayOverlayMeta {
  rulesAttachedCount?: number;
  ruleRetrievalSource?: string;
  warning?: string;
}

type PlayPreparationAction = 'extract_plan' | 'enrich_plan' | 'sync_chat_only';
type PlayPreparationState = 'missing' | 'unenriched' | 'ready';

interface PreparePlayResult {
  action: PlayPreparationAction;
  detected: boolean;
  rulesApplied: boolean;
  rulesAttachedCount: number;
  ruleRetrievalSource: string;
  warning?: string;
}

function decodeEscapedText(input: string): string {
  return input
    .replace(/\\n/g, '\n')
    .replace(/\\r/g, '\r')
    .replace(/\\t/g, '\t')
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\\\/g, '\\');
}

function extractCodexTextBlocks(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  // JSON-form payload first.
  try {
    const parsed = JSON.parse(trimmed);
    const blocks = Array.isArray(parsed) ? parsed : [parsed];
    const texts = blocks
      .filter((b: any) => b && typeof b === 'object' && b.type === 'text' && typeof b.text === 'string')
      .map((b: any) => String(b.text).trim())
      .filter(Boolean);
    if (texts.length) return texts.join('\n\n');
  } catch {
    // fall through to tolerant parser
  }

  // Tolerant parser for Python-ish repr payload:
  // [{'type': 'text', 'text': '...'}]
  if (!/^\s*\[?\s*[{]/.test(trimmed) || !/['"]type['"]\s*:\s*['"]text['"]/.test(trimmed)) {
    return null;
  }
  const texts: string[] = [];
  const re = /['"]text['"]\s*:\s*(['"])((?:\\.|(?!\1)[\s\S])*)\1/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(trimmed)) !== null) {
    const value = decodeEscapedText(m[2]).trim();
    if (value) texts.push(value);
  }
  return texts.length ? texts.join('\n\n') : null;
}

export function ChatVisualizationView({ chatId, onUpdateName }: { chatId: string; onUpdateName: (chatId: string, name: string) => void; }) {
  const PLAY_DETECTED_VISIBLE_MS = 1300;
  const PLAY_NO_RULES_VISIBLE_MS = 2000;
  const PLAY_DETECTION_FAILURE_DISMISS_MS = 400;
  const [content, setContent] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('paused');
  const [name, setName] = useState<string>(chatId);
  const [isEditing, setIsEditing] = useState(false);
  const [plan, setPlan] = useState<VisualizationPlanDocument | null>(null);
  const [evidence, setEvidence] = useState<EvidenceRecord[]>([]);
  const [visualization, setVisualization] = useState<any>(null);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [notesRefreshKey, setNotesRefreshKey] = useState(0);
  const [playOverlayState, setPlayOverlayState] = useState<PlayOverlayState | null>(null);
  const [playOverlayMeta, setPlayOverlayMeta] = useState<PlayOverlayMeta>({});
  const trackingSignatureRef = useRef<string>('');
  const playOverlayTimersRef = useRef<number[]>([]);
  const autoPrepareInFlightRef = useRef(false);
  const autoPrepareAttemptRef = useRef<{ chatId: string; state: PlayPreparationState | null }>({
    chatId: '',
    state: null,
  });

  const getTrackingSignature = (metadata: any): string =>
    JSON.stringify(metadata?.plan_tracking || {});

  const clearPlayOverlayTimers = () => {
    playOverlayTimersRef.current.forEach((timerId) => window.clearTimeout(timerId));
    playOverlayTimersRef.current = [];
  };

  const maybeRefreshPlan = async (metadata: any) => {
    const newTracking = getTrackingSignature(metadata);
    const changed = trackingSignatureRef.current !== newTracking;
    trackingSignatureRef.current = newTracking;
    if (!changed) return;

    const planResult = await api.getVisualizationPlan(chatId);
    if (planResult.success && planResult.plan) {
      setPlan(planResult.plan);
    }
  };

  const fetchEvidence = async () => {
    const evidenceResult = await api.getEvidence(chatId);
    if (evidenceResult.success) {
      setEvidence((evidenceResult.evidence || []) as EvidenceRecord[]);
    }
  };

  const countPlanRules = (items: any[]): number => {
    let total = 0;
    for (const item of items || []) {
      if (Array.isArray(item?.rules)) total += item.rules.length;
      if (Array.isArray(item?.inherited_rules)) total += item.inherited_rules.length;
      if (Array.isArray(item?.children) && item.children.length) {
        total += countPlanRules(item.children);
      }
    }
    return total;
  };

  const hasPlanItems = (planDoc: VisualizationPlanDocument | null | undefined): boolean => {
    const items = planDoc?.plan?.items;
    return Array.isArray(items) && items.length > 0;
  };

  const getPlayPreparationState = (
    planDoc: VisualizationPlanDocument | null | undefined
  ): PlayPreparationState => {
    if (!hasPlanItems(planDoc)) {
      return 'missing';
    }
    const rulesCount = countPlanRules(planDoc?.plan?.items || []);
    return rulesCount > 0 ? 'ready' : 'unenriched';
  };

  const preparePlanForPlay = async (): Promise<PreparePlayResult> => {
    const source = String((visualization as any)?.rule_retrieval_source || 'structured');

    try {
      const result = await api.prepareVisualizationForPlay(chatId);
      if (result.success && result.plan) {
        setPlan(result.plan);
        await fetchEvidence();
        const detected = hasPlanItems(result.plan);
        const rulesAttachedCount = Number(result.rules_attached_count || 0);
        return {
          action: (result.play_action || 'sync_chat_only') as PlayPreparationAction,
          detected,
          rulesApplied: rulesAttachedCount > 0,
          rulesAttachedCount,
          ruleRetrievalSource: String(result.rule_retrieval_source || source),
          warning: result.warnings?.[0],
        };
      }
    } catch (error) {
      console.error('Failed to prepare plan for play:', error);
    }
    return {
      action: 'sync_chat_only',
      detected: false,
      rulesApplied: false,
      rulesAttachedCount: 0,
      ruleRetrievalSource: source,
    };
  };

  const primePlayOverlayForState = (preparationState: PlayPreparationState) => {
    clearPlayOverlayTimers();
    if (preparationState === 'missing') {
      setPlayOverlayState('detecting');
      setPlayOverlayMeta({});
    } else if (preparationState === 'unenriched') {
      setPlayOverlayState('enriching');
      setPlayOverlayMeta({
        ruleRetrievalSource: String((visualization as any)?.rule_retrieval_source || 'structured')
      });
    } else {
      setPlayOverlayState(null);
      setPlayOverlayMeta({});
    }
  };

  const applyPreparedOverlayState = (prepared: PreparePlayResult) => {
    if (prepared.action === 'sync_chat_only') {
      setPlayOverlayState(null);
      setPlayOverlayMeta({});
      return;
    }

    if (prepared.detected) {
      setPlayOverlayMeta({
        rulesAttachedCount: prepared.rulesAttachedCount,
        ruleRetrievalSource: prepared.ruleRetrievalSource,
        warning: prepared.warning,
      });
      setPlayOverlayState(prepared.rulesApplied ? 'enriched' : 'no_rules');
    }

    const dismissTimer = window.setTimeout(() => {
      setPlayOverlayState(null);
      setPlayOverlayMeta({});
    }, prepared.detected
      ? (prepared.rulesApplied ? PLAY_DETECTED_VISIBLE_MS : PLAY_NO_RULES_VISIBLE_MS)
      : PLAY_DETECTION_FAILURE_DISMISS_MS);
    playOverlayTimersRef.current.push(dismissTimer);
  };

  const refreshPlanAndEvidence = async (
    metadata: any,
    options?: { forcePlanReload?: boolean }
  ) => {
    if (options?.forcePlanReload) {
      const planResult = await api.getVisualizationPlan(chatId);
      if (planResult.success && planResult.plan) {
        setPlan(planResult.plan);
      }
    } else {
      await maybeRefreshPlan(metadata);
    }

    await fetchEvidence();
  };

  const fetchChat = async () => {
    setPlan(null);
    setContent(null);
    
    const response = await api.getChatVisualization(chatId);
    const metadata = response as any;
    setVisualization(response);
    setName(response.name || response.chat_id);
    setStatus(response.status);
    trackingSignatureRef.current = getTrackingSignature(metadata);

    // Hydrate existing stored chat content so play/pause doesn't look like it wiped history.
    const hydratedContent = metadata.cleaned_accumulated_content || metadata.accumulated_content || null;
    setContent(hydratedContent);

    await refreshPlanAndEvidence(metadata, { forcePlanReload: true });
  };

  useEffect(() => {
    fetchChat();
  }, [chatId]);

  useEffect(() => {
    return () => {
      clearPlayOverlayTimers();
    };
  }, []);

  // Auto-refresh when window regains focus
  useEffect(() => {
    const onFocus = async () => {
      const response = await api.getChatVisualization(chatId);
      const metadata = response as any;
      setVisualization(response);
      setStatus(response.status);
      if (!content && (metadata.cleaned_accumulated_content || metadata.accumulated_content)) {
        setContent(metadata.cleaned_accumulated_content || metadata.accumulated_content);
      }
      await refreshPlanAndEvidence(metadata);
    };
    
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [chatId, content]);

  useEffect(() => {
    const poll = async () => {
      if (status === 'polling') {
        const response = await api.pollChatVisualization(chatId);
        if (response.content) {
          setContent(prev => prev ? prev + '\n\n' + response.content : response.content);
        }
        
        const metadata = await api.getChatVisualization(chatId);
        const meta = metadata as any;
        setVisualization(metadata);
        setStatus(metadata.status);
        await refreshPlanAndEvidence(meta);
        
      }
    };
    
    // Poll immediately on mount
    poll();
    
    // Then poll every 2 seconds
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [chatId, status]);

  useEffect(() => {
    if (status !== 'polling') return;

    const preparationState = getPlayPreparationState(plan);
    if (preparationState === 'ready') {
      autoPrepareAttemptRef.current = { chatId, state: null };
      return;
    }

    if (autoPrepareInFlightRef.current) return;

    const attempt = autoPrepareAttemptRef.current;
    if (attempt.chatId === chatId && attempt.state === preparationState) {
      return;
    }

    autoPrepareInFlightRef.current = true;
    autoPrepareAttemptRef.current = { chatId, state: preparationState };
    primePlayOverlayForState(preparationState);

    let cancelled = false;

    const runAutoPrepare = async () => {
      try {
        const prepared = await preparePlanForPlay();
        if (cancelled) return;
        applyPreparedOverlayState(prepared);
      } catch (error) {
        if (cancelled) return;
        clearPlayOverlayTimers();
        setPlayOverlayState(null);
        setPlayOverlayMeta({});
        console.error('Failed to auto-prepare plan while polling:', error);
      } finally {
        if (!cancelled) {
          autoPrepareInFlightRef.current = false;
        }
      }
    };

    runAutoPrepare();

    return () => {
      cancelled = true;
      autoPrepareInFlightRef.current = false;
    };
  }, [chatId, plan, status, visualization]);

  // Soft-refresh visualization metadata while paused so external plan updates show up automatically.
  useEffect(() => {
    if (status !== 'paused') return;

    const refresh = async () => {
      const metadata = await api.getChatVisualization(chatId);
      const meta = metadata as any;
      setVisualization(metadata);
      setStatus(metadata.status);
      if (!content && (meta.cleaned_accumulated_content || meta.accumulated_content)) {
        setContent(meta.cleaned_accumulated_content || meta.accumulated_content);
      }
      await refreshPlanAndEvidence(meta);
    };

    refresh();
    const interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
  }, [chatId, status, content]);

  const handleStart = async () => {
    const preparationState = getPlayPreparationState(plan);
    primePlayOverlayForState(preparationState);

    try {
      const response = await api.startChatVisualization(chatId);
      setStatus(response.status);

      const prepared = await preparePlanForPlay();
      applyPreparedOverlayState(prepared);
    } catch (error) {
      clearPlayOverlayTimers();
      setPlayOverlayState(null);
      setPlayOverlayMeta({});
      console.error('Failed to start visualization:', error);
    }
  };

  const handlePause = async () => {
    const response = await api.pauseChatVisualization(chatId);
    setStatus(response.status);
  };

  const handleSaveName = async () => {
    await api.updateChatVisualization(chatId, name);
    onUpdateName(chatId, name);
    setIsEditing(false);
  };

  const shouldRenderCodexStyleLog = useMemo(() => {
    if (!content) return false;
    const source = (visualization as any)?.chat_history_source;
    const chatPath = ((visualization as any)?.chat_file_path || '').toLowerCase();
    const looksLikeRoleTranscript = /^\s*(user|assistant)\s*:/im.test(content);
    return source === 'codex' || chatPath.includes('codex') || looksLikeRoleTranscript;
  }, [content, visualization]);

  const parsedChatMessages = useMemo<ParsedChatMessage[]>(() => {
    if (!content) return [];

    const lines = content.split('\n');
    const messages: ParsedChatMessage[] = [];
    let current: ParsedChatMessage | null = null;

    for (const line of lines) {
      const match = line.match(/^\s*(user|assistant)\s*:\s?(.*)$/i);
      if (match) {
        if (current && current.content.trim()) {
          messages.push({ ...current, content: current.content.trim() });
        }
        const role = match[1].toLowerCase() as 'user' | 'assistant';
        current = { role, content: match[2] || '' };
        continue;
      }

      if (!current) {
        current = { role: 'other', content: line };
      } else {
        current.content = current.content ? `${current.content}\n${line}` : line;
      }
    }

    if (current && current.content.trim()) {
      messages.push({ ...current, content: current.content.trim() });
    }

    return messages;
  }, [content]);

  const formatCodexMessageContent = (raw: string): string => {
    let text = raw;

    const extracted = extractCodexTextBlocks(text);
    if (extracted) text = extracted;

    // Make XML-wrapped blocks readable in markdown without hard boxes.
    text = text.replace(
      /<INSTRUCTIONS>\s*([\s\S]*?)\s*<\/INSTRUCTIONS>/gi,
      (_m, body) => `### Instructions\n\n${String(body).trim()}`
    );
    text = text.replace(
      /<environment_context>\s*([\s\S]*?)\s*<\/environment_context>/gi,
      (_m, body) => `### Environment Context\n\n${String(body).trim()}`
    );

    // Remove repeated extra blank lines.
    text = text.replace(/\n{3,}/g, '\n\n');
    return text.trim();
  };

  return (
    <Box sx={{ position: 'relative', height: '100%' }}>
    {playOverlayState && (
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          zIndex: 20,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'rgba(255, 255, 255, 0.9)',
          backdropFilter: 'blur(6px)',
        }}
      >
        <Box
          sx={{
            minWidth: 280,
            maxWidth: 360,
            px: 3,
            py: 2.5,
            borderRadius: 2,
            border: '1px solid',
            borderColor: 'rgba(76, 111, 59, 0.18)',
            bgcolor: 'rgba(255, 255, 255, 0.98)',
            boxShadow: '0 18px 50px rgba(62, 70, 40, 0.12)',
            textAlign: 'center',
          }}
        >
          {playOverlayState === 'detecting' ? (
            <>
              <CircularProgress
                size={30}
                thickness={4.2}
                sx={{ color: colors.darkGreen, mb: 1.4 }}
              />
              <Typography sx={{ fontSize: '0.92rem', fontWeight: 700, color: colors.darkGreen, mb: 0.35 }}>
                Detecting latest plan
              </Typography>
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
                Scanning the conversation and getting the workspace ready.
              </Typography>
            </>
          ) : playOverlayState === 'enriching' ? (
            <>
              <CircularProgress
                size={30}
                thickness={4.2}
                sx={{ color: colors.darkGreen, mb: 1.4 }}
              />
              <Typography sx={{ fontSize: '0.92rem', fontWeight: 700, color: colors.darkGreen, mb: 0.35 }}>
                Enriching plan with rules
              </Typography>
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
                Applying {playOverlayMeta.ruleRetrievalSource || 'structured'} rules to the extracted plan.
              </Typography>
            </>
          ) : playOverlayState === 'no_rules' ? (
            <>
              <CheckCircleOutlineIcon sx={{ fontSize: 32, color: colors.darkGreen, mb: 1.1 }} />
              <Typography sx={{ fontSize: '0.92rem', fontWeight: 700, color: colors.darkGreen, mb: 0.35 }}>
                Plan detected, no rules applied
              </Typography>
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
                No {playOverlayMeta.ruleRetrievalSource || 'structured'} rules were attached yet.
              </Typography>
            </>
          ) : (
            <>
              <CheckCircleOutlineIcon sx={{ fontSize: 32, color: colors.green, mb: 1.1 }} />
              <Typography sx={{ fontSize: '0.92rem', fontWeight: 700, color: colors.darkGreen, mb: 0.35 }}>
                Plan enriched
              </Typography>
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
                Attached {playOverlayMeta.rulesAttachedCount || 0} rules and opening the planning view.
              </Typography>
            </>
          )}
        </Box>
      </Box>
    )}
    <PanelGroup direction="horizontal" style={{ height: '100%' }}>
      <Panel>
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {isEditing ? (
            <>
              <TextField value={name} onChange={(e) => setName(e.target.value)} variant="standard" />
              <CompactIconButton
                label="Save visualization name"
                icon={<CheckCircleOutlineIcon sx={{ fontSize: 18 }} />}
                tone="green"
                onClick={handleSaveName}
                sx={{ ml: 0.5 }}
              />
            </>
          ) : (
            <>
              <Typography variant="body1">{name}</Typography>
              <Tooltip title="Edit visualization name">
                <IconButton onClick={() => setIsEditing(true)} sx={{ ml: 1, '&:focus': { outline: 'none' } }} disableRipple>
                  <EditIcon />
                </IconButton>
              </Tooltip>
            </>
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Start visualization polling">
            <span>
              <IconButton onClick={handleStart} disabled={status === 'polling' || !!playOverlayState} disableRipple sx={{ '&:focus': { outline: 'none' } }}>
                <PlayArrowIcon />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Pause visualization polling">
            <span>
              <IconButton onClick={handlePause} disabled={status === 'paused' || !!playOverlayState} disableRipple sx={{ '&:focus': { outline: 'none' } }}>
                <PauseIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
        </Box>
        
        <Box sx={{ 
          flex: 1, 
          overflow: 'auto',
          overflowX: 'hidden',
          mx: 2
        }}>
          {plan && (
            <Box sx={{ mb: 4 }}>
              <ExtractedPlanView 
                plan={plan} 
                chatId={chatId}
                evidence={evidence}
                visualization={visualization}
                onPlanUpdate={(updatedPlan) => setPlan(updatedPlan)}
                onItemSelect={(itemId) => setSelectedItemId(itemId)}
                selectedItemId={selectedItemId}
              />
              <Box sx={{ mt: 2 }}>
                <RuleReviewPanel
                  chatId={chatId}
                  plan={plan}
                  evidence={evidence}
                  onItemSelect={(itemId) => setSelectedItemId(itemId)}
                  onPlanUpdate={(updatedPlan) => setPlan(updatedPlan)}
                  notesRefreshKey={notesRefreshKey}
                  onRuleNotesSaved={() => setNotesRefreshKey((k) => k + 1)}
                />
              </Box>
            </Box>
          )}
          
          <Box sx={{ mb: 2 }}>
            <Accordion
              title={
                <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                  Chat Log
                </Typography>
              }
              defaultOpen={true}
            >
              <Box sx={{ 
                p: 2,
                wordBreak: 'break-word',
                '& pre': { 
                  overflowX: 'auto',
                  maxWidth: '100%'
                }
              }}>
                {content ? (
                  shouldRenderCodexStyleLog && parsedChatMessages.length > 0 ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.1 }}>
                      {parsedChatMessages.map((message, index) => (
                        <Box
                          key={`${message.role}-${index}`}
                          sx={{
                            py: 0.25,
                          }}
                        >
                          <Typography
                            sx={{
                              fontSize: '0.66rem',
                              textTransform: 'uppercase',
                              letterSpacing: 0.4,
                              fontWeight: 700,
                              color: message.role === 'assistant' ? colors.green : colors.grey,
                              mb: 0.35,
                            }}
                          >
                            {message.role}
                          </Typography>
                          <Box
                            sx={{
                              fontSize: '0.82rem',
                              lineHeight: 1.45,
                              '& p': { my: 0.4 },
                              '& pre': {
                                p: 0,
                                m: 0,
                                bgcolor: 'transparent',
                                border: 'none',
                              },
                              '& code': {
                                fontSize: '0.78rem',
                                backgroundColor: 'transparent',
                              },
                              '& ul, & ol': { my: 0.5, pl: 2 },
                              '& h1, & h2, & h3, & h4': {
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                my: 0.4,
                              },
                            }}
                          >
                            <ReactMarkdown>{formatCodexMessageContent(message.content)}</ReactMarkdown>
                          </Box>
                        </Box>
                      ))}
                    </Box>
                  ) : (
                    <ReactMarkdown>{content}</ReactMarkdown>
                  )
                ) : (
                  <Typography color="text.secondary">Chat content will appear here...</Typography>
                )}
              </Box>
            </Accordion>
          </Box>
        </Box>
        </Box>
      </Panel>

      {selectedItemId && plan && (() => {
        // Find the selected item in the plan tree
        const findItem = (items: any[]): any => {
          for (const item of items) {
            if (item.id === selectedItemId) return item;
            if (item.children) {
              const found = findItem(item.children);
              if (found) return found;
            }
          }
          return null;
        };
        const selectedItem = findItem(plan.plan.items);
        
        return selectedItem ? (
          <>
            <PanelResizeHandle style={{ width: '1px', backgroundColor: colors.dividerStrong, cursor: 'col-resize' }} />
            <Panel defaultSize={25} minSize={20} maxSize={40}>
              <VisualizationEnforcementPanel
                chatId={chatId}
                selectedItemId={selectedItemId}
                selectedItem={selectedItem}
                evidence={evidence}
                onClose={() => setSelectedItemId(null)}
                notesRefreshKey={notesRefreshKey}
                onRuleNotesSaved={() => setNotesRefreshKey((k) => k + 1)}
              />
            </Panel>
          </>
        ) : null;
      })()}
    </PanelGroup>

    <ResizableFloatingPanel title="SUPERVISOR" collapsedTop="44%" panelZIndex={20} initialY={80}>
      <SupervisorPanel chatId={chatId} visualizationStatus={status} />
    </ResizableFloatingPanel>

    <ResizableFloatingPanel title="RULE LEARNING" collapsedTop="62%" panelZIndex={19} initialY={140}>
      <RuleLearningPanel chatId={chatId} visualizationStatus={status} />
    </ResizableFloatingPanel>

    </Box>
  );
}
