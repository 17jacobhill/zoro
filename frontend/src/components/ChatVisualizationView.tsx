import { useState, useEffect, useRef, useLayoutEffect, useMemo } from 'react';
import { Box, Typography, IconButton, CircularProgress } from '@mui/material';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { TextField } from '../design-system/TextField';
import PauseIcon from '@mui/icons-material/Pause';
import EditIcon from '@mui/icons-material/Edit';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ReactMarkdown from 'react-markdown';
import { api } from '../services/api';
import { Button } from '../design-system/Button';
import { Accordion } from '../design-system/Accordion';
import { colors } from '../design-system/colors';
import { MonitoringPanel } from './Visualization/MonitoringPanel';
import { RuleLearningPanel } from './Visualization/RuleLearningPanel';
import { ExtractedPlanView } from './Visualization/ExtractedPlanView';
import { VisualizationEnforcementPanel } from './Visualization/VisualizationEnforcementPanel';
import { RuleReviewPanel } from './Visualization/RuleReviewPanel';

interface ParsedChatMessage {
  role: 'user' | 'assistant' | 'other';
  content: string;
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
  const PLAY_DETECTION_DELAY_MS = 3000;
  const PLAY_DETECTED_VISIBLE_MS = 1100;
  const [content, setContent] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('paused');
  const [name, setName] = useState<string>(chatId);
  const [isEditing, setIsEditing] = useState(false);
  const [plan, setPlan] = useState<any>(null);
  const [visualization, setVisualization] = useState<any>(null);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [monitoringOpen, setMonitoringOpen] = useState(false);
  const [monitorPos, setMonitorPos] = useState({ x: 0, y: 80 });
  const [monitorDrag, setMonitorDrag] = useState<{ offsetX: number; offsetY: number } | null>(null);
  const monitorPositioned = useRef(false);
  const [monitorWidth, setMonitorWidth] = useState(360);
  const [monitorResize, setMonitorResize] = useState<{ startX: number; startWidth: number } | null>(null);
  const [monitorHeight, setMonitorHeight] = useState(520);
  const [monitorResizeY, setMonitorResizeY] = useState<{ startY: number; startHeight: number } | null>(null);
  const [ruleLearningOpen, setRuleLearningOpen] = useState(false);
  const [learningPos, setLearningPos] = useState({ x: 0, y: 140 });
  const [learningDrag, setLearningDrag] = useState<{ offsetX: number; offsetY: number } | null>(null);
  const learningPositioned = useRef(false);
  const [learningWidth, setLearningWidth] = useState(360);
  const [learningResize, setLearningResize] = useState<{ startX: number; startWidth: number } | null>(null);
  const [learningHeight, setLearningHeight] = useState(520);
  const [learningResizeY, setLearningResizeY] = useState<{ startY: number; startHeight: number } | null>(null);
  const [notesRefreshKey, setNotesRefreshKey] = useState(0);
  const [playOverlayState, setPlayOverlayState] = useState<'detecting' | 'detected' | null>(null);
  const trackingSignatureRef = useRef<string>('');
  const playOverlayTimersRef = useRef<number[]>([]);
  const MONITOR_MARGIN = 8;
  const MONITOR_MIN_WIDTH = 260;
  const MONITOR_MIN_HEIGHT = 320;
  const MONITOR_ABS_MAX_WIDTH = 1200;
  const MONITOR_ABS_MAX_HEIGHT = 1200;

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

  const fetchChat = async () => {
    setPlan(null);
    setContent(null);
    
    const response = await api.getChatVisualization(chatId);
    const metadata = response as any;
    console.log('📊 Visualization response:', response);
    console.log('📍 plan_tracking:', metadata.plan_tracking);
    setVisualization(response);
    setName(response.name || response.chat_id);
    setStatus(response.status);
    trackingSignatureRef.current = getTrackingSignature(metadata);

    // Hydrate existing stored chat content so play/pause doesn't look like it wiped history.
    const hydratedContent = metadata.cleaned_accumulated_content || metadata.accumulated_content || null;
    setContent(hydratedContent);
    
    const planResult = await api.getVisualizationPlan(chatId);
    if (planResult.success && planResult.plan) {
      setPlan(planResult.plan);
    }
  };

  useEffect(() => {
    fetchChat();
  }, [chatId]);

  useEffect(() => {
    return () => {
      clearPlayOverlayTimers();
    };
  }, []);

  useLayoutEffect(() => {
    if (monitoringOpen && !monitorPositioned.current) {
      const x = Math.max(MONITOR_MARGIN, window.innerWidth - monitorWidth - 16);
      const y = Math.max(MONITOR_MARGIN, Math.min(80, window.innerHeight - monitorHeight - MONITOR_MARGIN));
      setMonitorPos({ x, y });
      monitorPositioned.current = true;
    }
  }, [monitoringOpen, monitorWidth, monitorHeight]);

  useEffect(() => {
    if (ruleLearningOpen && !learningPositioned.current) {
      const x = Math.max(MONITOR_MARGIN, window.innerWidth - learningWidth - 24);
      const y = Math.max(MONITOR_MARGIN, Math.min(140, window.innerHeight - learningHeight - MONITOR_MARGIN));
      setLearningPos({ x, y });
      learningPositioned.current = true;
    }
  }, [ruleLearningOpen, learningWidth, learningHeight]);

  useEffect(() => {
    if (!monitorDrag && !monitorResize && !monitorResizeY && !learningDrag && !learningResize && !learningResizeY) return;

    const handleMove = (event: MouseEvent) => {
      const viewWidth = window.innerWidth;
      const viewHeight = window.innerHeight;
      const maxX = Math.max(MONITOR_MARGIN, viewWidth - monitorWidth - MONITOR_MARGIN);
      const maxY = Math.max(MONITOR_MARGIN, viewHeight - monitorHeight - MONITOR_MARGIN);

      if (monitorDrag) {
        const nextX = Math.min(
          Math.max(MONITOR_MARGIN, event.clientX - monitorDrag.offsetX),
          maxX
        );
        const nextY = Math.min(
          Math.max(MONITOR_MARGIN, event.clientY - monitorDrag.offsetY),
          maxY
        );
        setMonitorPos({ x: nextX, y: nextY });
      }

      if (monitorResize) {
        const delta = event.clientX - monitorResize.startX;
        const maxWidthByViewport = Math.max(
          MONITOR_MIN_WIDTH,
          Math.min(MONITOR_ABS_MAX_WIDTH, viewWidth - monitorPos.x - MONITOR_MARGIN)
        );
        const nextWidth = Math.min(
          Math.max(MONITOR_MIN_WIDTH, monitorResize.startWidth + delta),
          maxWidthByViewport
        );
        setMonitorWidth(nextWidth);
      }

      if (monitorResizeY) {
        const deltaY = event.clientY - monitorResizeY.startY;
        const maxHeightByViewport = Math.max(
          MONITOR_MIN_HEIGHT,
          Math.min(MONITOR_ABS_MAX_HEIGHT, viewHeight - monitorPos.y - MONITOR_MARGIN)
        );
        const nextHeight = Math.min(
          Math.max(MONITOR_MIN_HEIGHT, monitorResizeY.startHeight + deltaY),
          maxHeightByViewport
        );
        setMonitorHeight(nextHeight);
      }

      const learningMaxX = Math.max(MONITOR_MARGIN, viewWidth - learningWidth - MONITOR_MARGIN);
      const learningMaxY = Math.max(MONITOR_MARGIN, viewHeight - learningHeight - MONITOR_MARGIN);

      if (learningDrag) {
        const nextX = Math.min(
          Math.max(MONITOR_MARGIN, event.clientX - learningDrag.offsetX),
          learningMaxX
        );
        const nextY = Math.min(
          Math.max(MONITOR_MARGIN, event.clientY - learningDrag.offsetY),
          learningMaxY
        );
        setLearningPos({ x: nextX, y: nextY });
      }

      if (learningResize) {
        const delta = event.clientX - learningResize.startX;
        const maxWidthByViewport = Math.max(
          MONITOR_MIN_WIDTH,
          Math.min(MONITOR_ABS_MAX_WIDTH, viewWidth - learningPos.x - MONITOR_MARGIN)
        );
        const nextWidth = Math.min(
          Math.max(MONITOR_MIN_WIDTH, learningResize.startWidth + delta),
          maxWidthByViewport
        );
        setLearningWidth(nextWidth);
      }

      if (learningResizeY) {
        const deltaY = event.clientY - learningResizeY.startY;
        const maxHeightByViewport = Math.max(
          MONITOR_MIN_HEIGHT,
          Math.min(MONITOR_ABS_MAX_HEIGHT, viewHeight - learningPos.y - MONITOR_MARGIN)
        );
        const nextHeight = Math.min(
          Math.max(MONITOR_MIN_HEIGHT, learningResizeY.startHeight + deltaY),
          maxHeightByViewport
        );
        setLearningHeight(nextHeight);
      }
    };

    const handleUp = () => {
      setMonitorDrag(null);
      setMonitorResize(null);
      setMonitorResizeY(null);
      setLearningDrag(null);
      setLearningResize(null);
      setLearningResizeY(null);
    };

    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [
    monitorDrag,
    monitorResize,
    monitorResizeY,
    monitorWidth,
    monitorHeight,
    monitorPos,
    learningDrag,
    learningResize,
    learningResizeY,
    learningWidth,
    learningHeight,
    learningPos,
  ]);

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
      await maybeRefreshPlan(metadata);
    };
    
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [chatId, content]);

  useEffect(() => {
    const poll = async () => {
      if (status === 'polling') {
        const response = await api.pollChatVisualization(chatId);
        console.log('poll response', response);
        if (response.content) {
          setContent(prev => prev ? prev + '\n\n' + response.content : response.content);
        }
        
        const metadata = await api.getChatVisualization(chatId);
        const meta = metadata as any;
        setVisualization(metadata);
        setStatus(metadata.status);
        await maybeRefreshPlan(meta);
        
      }
    };
    
    // Poll immediately on mount
    poll();
    
    // Then poll every 30 seconds
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [chatId, status]);

  // Soft-refresh visualization metadata while paused so external viz-update changes show up automatically.
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
      await maybeRefreshPlan(meta);
    };

    refresh();
    const interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
  }, [chatId, status, content]);

  const handleStart = async () => {
    clearPlayOverlayTimers();
    setPlayOverlayState('detecting');

    const detectedTimer = window.setTimeout(() => {
      setPlayOverlayState('detected');
      const dismissTimer = window.setTimeout(() => {
        setPlayOverlayState(null);
      }, PLAY_DETECTED_VISIBLE_MS);
      playOverlayTimersRef.current.push(dismissTimer);
    }, PLAY_DETECTION_DELAY_MS);
    playOverlayTimersRef.current.push(detectedTimer);

    try {
      const response = await api.startChatVisualization(chatId);
      setStatus(response.status);
    } catch (error) {
      clearPlayOverlayTimers();
      setPlayOverlayState(null);
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
                Detecting plan
              </Typography>
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
                Scanning the conversation and getting the workspace ready.
              </Typography>
            </>
          ) : (
            <>
              <CheckCircleOutlineIcon sx={{ fontSize: 32, color: colors.green, mb: 1.1 }} />
              <Typography sx={{ fontSize: '0.92rem', fontWeight: 700, color: colors.darkGreen, mb: 0.35 }}>
                Plan detected
              </Typography>
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
                Opening the planning view now.
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
              <Button onClick={handleSaveName} colorVariant="green" sx={{ ml: 1, '&:focus': { outline: 'none' } }} disableRipple>Save</Button>
            </>
          ) : (
            <>
              <Typography variant="body1">{name}</Typography>
              <IconButton onClick={() => setIsEditing(true)} sx={{ ml: 1, '&:focus': { outline: 'none' } }} disableRipple>
                <EditIcon />
              </IconButton>
            </>
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <IconButton onClick={handleStart} disabled={status === 'polling' || !!playOverlayState} disableRipple sx={{ '&:focus': { outline: 'none' } }}>
            <PlayArrowIcon />
          </IconButton>
          <IconButton onClick={handlePause} disabled={status === 'paused' || !!playOverlayState} disableRipple sx={{ '&:focus': { outline: 'none' } }}>
            <PauseIcon />
          </IconButton>
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
                visualization={visualization}
                onPlanUpdate={(updatedPlan) => setPlan(updatedPlan)}
                onItemSelect={(itemId) => setSelectedItemId(itemId)}
                selectedItemId={selectedItemId}
              />
              <Box sx={{ mt: 2 }}>
                <RuleReviewPanel
                  chatId={chatId}
                  plan={plan}
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
            <PanelResizeHandle style={{ width: '1px', backgroundColor: '#d0d0d0', cursor: 'col-resize' }} />
            <Panel defaultSize={25} minSize={20} maxSize={40}>
              <VisualizationEnforcementPanel
                chatId={chatId}
                selectedItemId={selectedItemId}
                selectedItem={selectedItem}
                onClose={() => setSelectedItemId(null)}
                notesRefreshKey={notesRefreshKey}
                onRuleNotesSaved={() => setNotesRefreshKey((k) => k + 1)}
              />
            </Panel>
          </>
        ) : null;
      })()}
    </PanelGroup>

    {/* Floating Supervisor Panel */}
    <Box
      sx={{
        position: 'fixed',
        left: monitorPos.x,
        top: monitorPos.y,
        zIndex: 20,
        display: 'flex',
        alignItems: 'stretch',
        pointerEvents: monitoringOpen ? 'auto' : 'none',
      }}
    >
      {monitoringOpen && (
        <Box
          sx={{
            position: 'relative',
            width: monitorWidth,
            height: monitorHeight,
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            boxShadow: '0 10px 30px rgba(0,0,0,0.12)',
            pointerEvents: 'auto',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <Box
            onMouseDown={(event) => {
              event.preventDefault();
              setMonitorResize({
                startX: event.clientX,
                startWidth: monitorWidth,
              });
            }}
            sx={{
              position: 'absolute',
              right: 0,
              top: 0,
              width: 10,
              height: '100%',
              cursor: 'ew-resize',
              zIndex: 3,
              bgcolor: 'rgba(135, 174, 115, 0.12)',
              borderLeft: '1px solid',
              borderColor: 'divider',
            }}
          />
          <Box
            onMouseDown={(event) => {
              event.preventDefault();
              setMonitorResizeY({
                startY: event.clientY,
                startHeight: monitorHeight,
              });
            }}
            sx={{
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: 0,
              height: 8,
              cursor: 'ns-resize',
              zIndex: 3,
              bgcolor: 'rgba(135, 174, 115, 0.12)',
              borderTop: '1px solid',
              borderColor: 'divider',
            }}
          />
          <Box
            onMouseDown={(event) => {
              event.preventDefault();
              setMonitorResize({
                startX: event.clientX,
                startWidth: monitorWidth,
              });
              setMonitorResizeY({
                startY: event.clientY,
                startHeight: monitorHeight,
              });
            }}
            sx={{
              position: 'absolute',
              right: 0,
              bottom: 0,
              width: 16,
              height: 16,
              cursor: 'nwse-resize',
              zIndex: 4,
              bgcolor: 'rgba(135, 174, 115, 0.2)',
              borderLeft: '1px solid',
              borderTop: '1px solid',
              borderColor: 'divider',
            }}
          />
          <Box
            onMouseDown={(event) => {
              event.preventDefault();
              setMonitorDrag({
                offsetX: event.clientX - monitorPos.x,
                offsetY: event.clientY - monitorPos.y,
              });
            }}
            sx={{
              cursor: 'move',
              userSelect: 'none',
              px: 1.5,
              py: 1,
              bgcolor: colors.green,
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <Typography variant="caption" sx={{ fontWeight: 600, letterSpacing: '0.08em' }}>
              SUPERVISOR
            </Typography>
            <Box
              onClick={(event) => {
                event.stopPropagation();
                setMonitoringOpen(false);
              }}
              sx={{
                fontSize: '0.7rem',
                fontWeight: 600,
                cursor: 'pointer',
                px: 0.75,
                py: 0.25,
                borderRadius: 1,
                bgcolor: colors.darkGreen,
              }}
            >
              Collapse
            </Box>
          </Box>
          <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden', pb: 1 }}>
            <MonitoringPanel
              chatId={chatId}
            />
          </Box>
        </Box>
      )}
    </Box>

    {/* Floating Rule Learning Panel */}
    <Box
      sx={{
        position: 'fixed',
        left: learningPos.x,
        top: learningPos.y,
        zIndex: 19,
        display: 'flex',
        alignItems: 'stretch',
        pointerEvents: ruleLearningOpen ? 'auto' : 'none',
      }}
    >
      {ruleLearningOpen && (
        <Box
          sx={{
            position: 'relative',
            width: learningWidth,
            height: learningHeight,
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            boxShadow: '0 10px 30px rgba(0,0,0,0.12)',
            pointerEvents: 'auto',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <Box
            onMouseDown={(event) => {
              event.preventDefault();
              setLearningResize({
                startX: event.clientX,
                startWidth: learningWidth,
              });
            }}
            sx={{
              position: 'absolute',
              right: 0,
              top: 0,
              width: 10,
              height: '100%',
              cursor: 'ew-resize',
              zIndex: 3,
              bgcolor: 'rgba(135, 174, 115, 0.12)',
              borderLeft: '1px solid',
              borderColor: 'divider',
            }}
          />
          <Box
            onMouseDown={(event) => {
              event.preventDefault();
              setLearningResizeY({
                startY: event.clientY,
                startHeight: learningHeight,
              });
            }}
            sx={{
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: 0,
              height: 8,
              cursor: 'ns-resize',
              zIndex: 3,
              bgcolor: 'rgba(135, 174, 115, 0.12)',
              borderTop: '1px solid',
              borderColor: 'divider',
            }}
          />
          <Box
            onMouseDown={(event) => {
              event.preventDefault();
              setLearningResize({
                startX: event.clientX,
                startWidth: learningWidth,
              });
              setLearningResizeY({
                startY: event.clientY,
                startHeight: learningHeight,
              });
            }}
            sx={{
              position: 'absolute',
              right: 0,
              bottom: 0,
              width: 16,
              height: 16,
              cursor: 'nwse-resize',
              zIndex: 4,
              bgcolor: 'rgba(135, 174, 115, 0.2)',
              borderLeft: '1px solid',
              borderTop: '1px solid',
              borderColor: 'divider',
            }}
          />
          <Box
            onMouseDown={(event) => {
              event.preventDefault();
              setLearningDrag({
                offsetX: event.clientX - learningPos.x,
                offsetY: event.clientY - learningPos.y,
              });
            }}
            sx={{
              cursor: 'move',
              userSelect: 'none',
              px: 1.5,
              py: 1,
              bgcolor: colors.green,
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <Typography variant="caption" sx={{ fontWeight: 600, letterSpacing: '0.08em' }}>
              RULE LEARNING
            </Typography>
            <Box
              onClick={(event) => {
                event.stopPropagation();
                setRuleLearningOpen(false);
              }}
              sx={{
                fontSize: '0.7rem',
                fontWeight: 600,
                cursor: 'pointer',
                px: 0.75,
                py: 0.25,
                borderRadius: 1,
                bgcolor: colors.darkGreen,
              }}
            >
              Collapse
            </Box>
          </Box>
          <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden', pb: 1 }}>
            <RuleLearningPanel chatId={chatId} />
          </Box>
        </Box>
      )}
    </Box>

    {!monitoringOpen && (
      <Box
        onClick={() => setMonitoringOpen(true)}
        sx={{
          position: 'fixed',
          right: 0,
          top: '44%',
          transform: 'translateY(-50%)',
          bgcolor: colors.green,
          color: 'white',
          border: '1px solid',
          borderColor: colors.green,
          py: 2,
          px: 0.75,
          cursor: 'pointer',
          writingMode: 'vertical-rl',
          textOrientation: 'mixed',
          fontSize: '0.75rem',
          fontWeight: 600,
          letterSpacing: '0.1em',
          borderTopLeftRadius: 6,
          borderBottomLeftRadius: 6,
          boxShadow: '0 6px 18px rgba(0,0,0,0.12)',
          zIndex: 21,
          '&:hover': {
            bgcolor: colors.darkGreen,
            borderColor: colors.darkGreen,
          },
        }}
      >
        SUPERVISOR
      </Box>
    )}

    {!ruleLearningOpen && (
      <Box
        onClick={() => setRuleLearningOpen(true)}
        sx={{
          position: 'fixed',
          right: 0,
          top: '62%',
          transform: 'translateY(-50%)',
          bgcolor: colors.green,
          color: 'white',
          border: '1px solid',
          borderColor: colors.green,
          py: 2,
          px: 0.75,
          cursor: 'pointer',
          writingMode: 'vertical-rl',
          textOrientation: 'mixed',
          fontSize: '0.72rem',
          fontWeight: 600,
          letterSpacing: '0.08em',
          borderTopLeftRadius: 6,
          borderBottomLeftRadius: 6,
          boxShadow: '0 6px 18px rgba(0,0,0,0.12)',
          zIndex: 20,
          '&:hover': {
            bgcolor: colors.darkGreen,
            borderColor: colors.darkGreen,
          },
        }}
      >
        RULE LEARNING
      </Box>
    )}

    </Box>
  );
}
