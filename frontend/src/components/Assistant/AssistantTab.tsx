import { useState, useEffect, useCallback } from 'react';
import { Box, Typography } from '@mui/material';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { ChatList } from './ChatList';
import { PlanVisualization } from './PlanVisualization';
import { AssistantNodeDetails } from './AssistantNodeDetails';
import { RecommendationsPanel } from './RecommendationsPanel';
import { EnforcementPanelV2 } from './EnforcementPanelV2';
import { api } from '../../services/api';
import { clineApi } from '../../services/clineApi';
import { Button } from '../../design-system/Button';
import { FloatingVerifyPanel, type FloatingVerifyPanelState } from '../../design-system/FloatingVerifyPanel';

export function AssistantTab() {
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [plan, setPlan] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [verifyPanel, setVerifyPanel] = useState<FloatingVerifyPanelState>({ status: 'closed' });
  const [showEnforcement, setShowEnforcement] = useState(false);
  const [enforcementTarget, setEnforcementTarget] = useState<{
    nodeId: string;
    targetKind: 'step' | 'substep' | 'rule';
    targetId: string;
  } | null>(null);

  const loadPlan = useCallback(async () => {
    if (!selectedChatId) {
      setPlan(null);
      return;
    }

    setLoading(true);
    try {
      const response = await api.getPlan(selectedChatId);
      setPlan(response);

      // Keep selected node in sync with latest plan payload without causing a fetch loop.
      setSelectedNode((prev: any | null) => {
        if (!prev) return null;
        const updatedSelected = response?.nodes?.find((n: any) => n.id === prev.id);
        return updatedSelected || null;
      });
    } catch (error: any) {
      console.error('Failed to load plan:', error);
      setPlan(null);
      setSelectedNode(null);
    } finally {
      setLoading(false);
    }
  }, [selectedChatId]);

  useEffect(() => {
    void loadPlan();
  }, [loadPlan]);

  useEffect(() => {
    const onFocus = () => {
      void loadPlan();
    };
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [loadPlan]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node);
  }, []);

  const handleNodeUpdate = useCallback((updatedNode: any) => {
    if (!plan) return;

    setPlan({
      ...plan,
      nodes: plan.nodes.map((n: any) => (n.id === updatedNode.id ? updatedNode : n)),
    });

    setSelectedNode(updatedNode);
  }, [plan]);

  const handleVerify = useCallback(async (payload: {
    title: string;
    target: {
      kind: 'node' | 'substep' | 'rule';
      node_id: string;
      substep_id?: string;
      rule_id?: string;
    };
  }) => {
    if (!selectedChatId || !plan) return;

    setVerifyPanel({ status: 'loading', title: payload.title });
    try {
      let res;
      const { kind, node_id, substep_id, rule_id } = payload.target;
      
      // Find the node in the plan to get full data including rules
      const node = plan.nodes?.find((n: any) => n.id === node_id);
      
      if (kind === 'node') {
        res = await clineApi.executeStep(selectedChatId, node_id, node);
      } else if (kind === 'substep' && substep_id) {
        res = await clineApi.executeSubstep(selectedChatId, node_id, substep_id, node);
      } else if (kind === 'rule' && rule_id) {
        res = await clineApi.executeRule(selectedChatId, node_id, rule_id, node);
      } else {
        throw new Error('Invalid target configuration');
      }

      setVerifyPanel({
        status: 'result',
        title: payload.title,
        result: {
          verdict: res.verdict,
          message: res.message,
          action_text: res.action_text,
          tracking_commands: res.tracking_commands,
        },
      });

      // Auto-refresh plan after execution to update status
      await loadPlan();
    } catch (e: any) {
      setVerifyPanel({ status: 'error', title: payload.title, error: e?.message || 'Execution failed' });
    }
  }, [selectedChatId, plan, loadPlan]);

  const handleNodeDelete = useCallback(async (nodeId: string) => {
    if (!plan || !selectedChatId) return;

    // Save original plan for rollback
    const originalPlan = plan;

    // Find edges connected to this node
    const incomingEdges = plan.edges.filter((e: any) => e.to === nodeId);
    const outgoingEdges = plan.edges.filter((e: any) => e.from === nodeId);
    
    // Graph mending: connect all predecessors to all successors
    const newEdges: any[] = [];
    incomingEdges.forEach((inEdge: any) => {
      outgoingEdges.forEach((outEdge: any) => {
        newEdges.push({
          id: `e-${inEdge.from}-${outEdge.to}`,
          from: inEdge.from,
          to: outEdge.to,
        });
      });
    });
    
    // Optimistic update: remove node and its edges, add new mended edges
    const updatedPlan = {
      ...plan,
      nodes: plan.nodes.filter((n: any) => n.id !== nodeId),
      edges: [
        ...plan.edges.filter((e: any) => e.from !== nodeId && e.to !== nodeId),
        ...newEdges
      ]
    };
    
    setPlan(updatedPlan);
    
    // Close details panel if this node was selected
    if (selectedNode?.id === nodeId) {
      setSelectedNode(null);
    }

    // Persist to backend
    try {
      await api.deletePlanNode(selectedChatId, nodeId);
      console.log(`Node ${nodeId} deleted successfully`);
    } catch (error) {
      console.error('Failed to delete node:', error);
      // Rollback on error
      setPlan(originalPlan);
      if (selectedNode?.id === nodeId) {
        setSelectedNode(selectedNode);
      }
    }
  }, [plan, selectedNode, selectedChatId]);

  const handleOpenEnforcement = useCallback((nodeId: string, targetKind: 'step' | 'substep' | 'rule', targetId: string) => {
    setEnforcementTarget({ nodeId, targetKind, targetId });
    setShowEnforcement(true);
  }, []);

  return (
    <PanelGroup direction="horizontal" style={{ flex: 1, overflow: 'hidden' }}>
      {/* Chat List Panel */}
      <Panel defaultSize={15} minSize={10} maxSize={30}>
        <ChatList onChatSelect={setSelectedChatId} selectedChatId={selectedChatId} />
      </Panel>

      <PanelResizeHandle style={{ width: '1px', backgroundColor: '#d0d0d0', cursor: 'col-resize' }} />

      {/* Plan Visualization Panel */}
      <Panel>
        {!selectedChatId ? (
          <Box sx={{ p: 2 }}><Typography>Select a chat to view its plan</Typography></Box>
        ) : (
          <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
            <Box sx={{ p: 1, borderBottom: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
              <Button
                size="small"
                colorVariant="green"
                disabled={loading}
                onClick={() => void loadPlan()}
              >
                {loading ? 'Refreshing…' : 'Refresh'}
              </Button>
            </Box>
            <Box sx={{ flex: 1, minHeight: 0 }}>
              <PlanVisualization 
                plan={plan} 
                loading={loading} 
                onNodeClick={handleNodeClick}
                onNodeDelete={handleNodeDelete}
              />
            </Box>

            <FloatingVerifyPanel
              state={verifyPanel}
              onClose={() => setVerifyPanel({ status: 'closed' })}
            />
          </Box>
        )}
      </Panel>

      {/* Right Side Panel (always present): Recommendations above Details */}
      <PanelResizeHandle style={{ width: '1px', backgroundColor: '#d0d0d0', cursor: 'col-resize' }} />
      <Panel defaultSize={30} minSize={20} maxSize={50}>
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <Box
            sx={{
              flexShrink: 0,
              maxHeight: '30%',
              overflow: 'auto',
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            <RecommendationsPanel chatId={selectedChatId} />
          </Box>
          <Box sx={{ flex: 1, minHeight: 0 }}>
            {selectedNode ? (
              <AssistantNodeDetails 
                task={selectedNode}
                chatId={selectedChatId || undefined}
                onClose={() => setSelectedNode(null)}
                onTaskUpdate={handleNodeUpdate}
                onVerify={handleVerify}
                onOpenEnforcement={handleOpenEnforcement}
              />
            ) : (
              <Box sx={{ p: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Click a node to view details.
                </Typography>
              </Box>
            )}
          </Box>
        </Box>
      </Panel>

      {/* Enforcement Panel (V2) */}
      {showEnforcement && enforcementTarget && selectedChatId && (
        <>
          <PanelResizeHandle style={{ width: '1px', backgroundColor: '#d0d0d0', cursor: 'col-resize' }} />
          <Panel defaultSize={35} minSize={25} maxSize={50}>
            <EnforcementPanelV2
              chatId={selectedChatId}
              nodeId={enforcementTarget.nodeId}
              targetId={enforcementTarget.targetId}
              onClose={() => setShowEnforcement(false)}
            />
          </Panel>
        </>
      )}
    </PanelGroup>
  );
}
