import { useCallback, useState, useEffect, useMemo } from 'react';
import ReactFlow, {
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  MarkerType,
  type Connection,
  type Node,
} from 'reactflow';
import 'reactflow/dist/style.css';
import zoroIcon from '../assets/sword.png';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Box, Paper, Typography, Tabs, Tab } from '@mui/material';
import { ProcessingPanel } from './Learner/ProcessingPanel/';
import { FlowNode } from '../design-system/FlowNode';
import { LearnerTaskDetails } from './Learner/LearnerTaskDetails';
import { FavoritesPanel } from './Learner/FavoritesPanel';
import { ChatLibrary } from './Learner/ChatLibrary';
import { AssistantTab } from './Assistant/AssistantTab';
import { VisualizationTab } from './Visualization/VisualizationTab';
import { KnowledgeBaseTab } from './KnowledgeBase/KnowledgeBaseTab';
import { api, type Task, type LogEntry } from '../services/api';
import { colors } from '../design-system/colors';

type Stage = 'upload' | 'parsing' | 'parsed' | 'categorizing' | 'categorized' | 'learning' | 'learned';

const nodeTypes = {
  task: FlowNode,
};

export function WorkflowEditor() {
  const [tabIndex, setTabIndex] = useState(0);
  const [uiConfig, setUiConfig] = useState<{
    show_learner_tab?: boolean;
    show_assistant_tab?: boolean;
    show_knowledge_base_tab?: boolean;
  } | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Stage-based workflow
  const [stage, setStage] = useState<Stage>('upload');
  const [parsedTasks, setParsedTasks] = useState<Task[]>([]);
  const [pendingTasks, setPendingTasks] = useState<Task[]>([]);
  const [approvedTasks, setApprovedTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isLearning, setIsLearning] = useState(false);
  const [currentTaskIndex, setCurrentTaskIndex] = useState<number | undefined>();
  const [currentlyAnalyzingTaskId, setCurrentlyAnalyzingTaskId] = useState<string | null>(null);
  const [currentChat, setCurrentChat] = useState<string>('default');
  const [chats, setChats] = useState<string[]>([]);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [favoritesOpen, setFavoritesOpen] = useState(true);
  const [favoritesRefreshKey, setFavoritesRefreshKey] = useState(0);
  void currentlyAnalyzingTaskId;

  const handleFavoritesChange = useCallback(() => {
    setFavoritesRefreshKey(prev => prev + 1);
  }, []);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const result = await api.getConfig();
        if (result.success && result.config) {
          setUiConfig(result.config);
        }
      } catch (error) {
        console.error('Failed to load config:', error);
      }
    };
    loadConfig();
  }, []);

  const visibleTabs = useMemo(() => {
    const showLearner = uiConfig?.show_learner_tab ?? true;
    const showAssistant = uiConfig?.show_assistant_tab ?? true;
    const showKnowledgeBase = uiConfig?.show_knowledge_base_tab ?? true;

    return [
      { key: 'learner', label: 'Learner', visible: showLearner },
      { key: 'assistant', label: 'Assistant', visible: showAssistant },
      { key: 'visualization', label: 'Visualization', visible: true },
      { key: 'knowledge-base', label: 'Rules Management', visible: showKnowledgeBase },
    ].filter(tab => tab.visible);
  }, [uiConfig]);

  useEffect(() => {
    if (tabIndex >= visibleTabs.length) {
      setTabIndex(0);
    }
  }, [tabIndex, visibleTabs.length]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const handleProcessStart = () => {
    setStage('parsing');
    setIsProcessing(true);
    setLogs([{ type: 'info', message: 'Starting file processing...' }]);
  };

  const handleTasksLoaded = (tasks: Task[], chatName: string, responseLogs?: LogEntry[]) => {
    setCurrentChat(chatName);
    setParsedTasks(tasks);
    setStage('parsed');
    
    const finalLogs = responseLogs || [
      { type: 'success', message: `Extracted ${tasks.length} tasks` }
    ];
    setLogs(finalLogs);
    setIsProcessing(false);
  };

  const handleCategorize = async () => {
    setStage('categorizing');
    setLogs(prev => [...prev, { type: 'info', message: 'Categorizing tasks...' }]);
    
    try {
      const response = await api.categorize(parsedTasks);
      
      if (response.success) {
        const categorizedTasks = response.suggestions.map((suggestion: any, i: number) => ({
          ...parsedTasks[i],
          suggested_type: suggestion.type,
        }));
        
        setPendingTasks(categorizedTasks);
        setStage('categorized');
        setLogs(prev => [
          ...prev,
          { type: 'success', message: `✓ Categorized ${categorizedTasks.length} tasks` }
        ]);
      } else {
        setLogs(prev => [...prev, { type: 'error', message: `Error: ${response.error}` }]);
        setStage('parsed');
      }
    } catch (error: any) {
      console.error('Categorization failed:', error);
      setLogs(prev => [...prev, { type: 'error', message: `Error: ${error.message}` }]);
      setStage('parsed');
    }
  };

  const handleProcessError = (error: string) => {
    setLogs(prev => [...prev, { type: 'error', message: `Error: ${error}` }]);
    setIsProcessing(false);
  };

  const handleApprove = (taskId: string) => {
    const task = pendingTasks.find(t => t.task_id === taskId);
    if (!task) return;

    // Move from pending to approved
    setPendingTasks(prev => prev.filter(t => t.task_id !== taskId));
    setApprovedTasks(prev => [...prev, task]);

    // Create node for approved task (vertical layout)
    const newNode: Node = {
      id: task.task_id,
      type: 'task',
      position: { 
        x: 250, 
        y: 100 + approvedTasks.length * 150 
      },
      data: { 
        label: task.suggested_type || task.type || 'uncategorized',
        task,
        onDelete: () => handleNodeDelete(task.task_id)
      },
    };
    setNodes(prev => [...prev, newNode]);

    // Create edge from previous task if exists
    if (approvedTasks.length > 0) {
      const prevTask = approvedTasks[approvedTasks.length - 1];
      const newEdge = {
        id: `e-${prevTask.task_id}-${task.task_id}`,
        source: prevTask.task_id,
        target: task.task_id,
        type: 'smoothstep',
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      };
      setEdges(prev => [...prev, newEdge]);
    }

    // Update logs
    setLogs(prev => [
      ...prev,
      { type: 'success', message: `Approved: ${task.suggested_type || 'task'}` }
    ]);
  };

  const handleApproveAll = async () => {
    // Approve all pending tasks (vertical layout)
    const newNodes = pendingTasks.map((task, i) => ({
      id: task.task_id,
      type: 'task',
      position: { 
        x: 250, 
        y: 100 + (approvedTasks.length + i) * 150 
      },
      data: { 
        label: task.suggested_type || 'uncategorized',
        task,
        onDelete: () => handleNodeDelete(task.task_id)
      },
    }));

    // Create edges between all consecutive tasks
    const newEdges = pendingTasks.map((task, i) => {
      if (i === 0 && approvedTasks.length > 0) {
        // Connect to last approved task
        return {
          id: `e-${approvedTasks[approvedTasks.length - 1].task_id}-${task.task_id}`,
          source: approvedTasks[approvedTasks.length - 1].task_id,
          target: task.task_id,
          type: 'smoothstep',
          markerEnd: {
            type: MarkerType.ArrowClosed,
          },
        };
      } else if (i > 0) {
        // Connect to previous task in batch
        return {
          id: `e-${pendingTasks[i - 1].task_id}-${task.task_id}`,
          source: pendingTasks[i - 1].task_id,
          target: task.task_id,
          type: 'smoothstep',
          markerEnd: {
            type: MarkerType.ArrowClosed,
          },
        };
      }
      return null;
    }).filter(edge => edge !== null);

    const allApproved = [...approvedTasks, ...pendingTasks];
    setApprovedTasks(allApproved);
    setNodes(prev => [...prev, ...newNodes]);
    setEdges(prev => [...prev, ...newEdges]);
    setLogs(prev => [
      ...prev,
      { type: 'success', message: `Approved all ${pendingTasks.length} tasks` }
    ]);
    setPendingTasks([]);

    try {
      await api.saveCategorizedTasks(currentChat, allApproved);
      setLogs(prev => [...prev, { type: 'info', message: 'Saved categorized tasks' }]);
    } catch (error: any) {
      console.error('Failed to save categorized tasks:', error);
      setLogs(prev => [...prev, { type: 'error', message: `Save failed: ${error.message}` }]);
    }
  };

  const handleLearnRules = async () => {
    setStage('learning');
    setIsLearning(true);
    setLogs(prev => [...prev, { type: 'info', message: '\n→ Learning Phase Started' }]);
    
    try {
      for (let i = 0; i < approvedTasks.length; i++) {
        const task = approvedTasks[i];
        setCurrentTaskIndex(i);
        
        // Highlight current node
        setCurrentlyAnalyzingTaskId(task.task_id);
        setNodes(prev => prev.map(node => ({
          ...node,
          data: {
            ...node.data,
            isAnalyzing: node.id === task.task_id
          }
        })));
        
        setLogs(prev => [
          ...prev,
          { type: 'info', message: `  Analyzing task ${i + 1} of ${approvedTasks.length}: "${task.suggested_type || 'task'}"` }
        ]);
        
        // Small delay so user can see the highlight
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      
      // Clear highlighting before API call
      setCurrentlyAnalyzingTaskId(null);
      setNodes(prev => prev.map(node => ({
        ...node,
        data: {
          ...node.data,
          isAnalyzing: false
        }
      })));
      
      // Call batch analyze API
      const response = await api.analyzeBatch(approvedTasks, currentChat);
      
      if (response.success) {
        const analyzedTasks = response.analyzed_tasks;
        
        // Update approved tasks with analyzed data
        setApprovedTasks(analyzedTasks);
        
        // Update nodes with analyzed data
        setNodes(prev => prev.map(node => {
          const analyzedTask = analyzedTasks.find((t: any) => t.task_id === node.id);
          if (analyzedTask) {
            return { ...node, data: { task: analyzedTask } };
          }
          return node;
        }));
        
        // Count total rules
        const totalRules = analyzedTasks.reduce((sum: number, t: any) => sum + (t.rules?.length || 0), 0);
        
        setLogs(prev => [
          ...prev,
          { type: 'success', message: `✓ Learning Complete - ${totalRules} rules extracted across ${analyzedTasks.length} tasks` }
        ]);

        // Save analyzed tasks to backend
        try {
          await api.saveAnalyzedTasks(currentChat, analyzedTasks);
          setLogs(prev => [...prev, { type: 'info', message: 'Saved analyzed tasks' }]);
          
          // Mark file as processed in config
          await api.markProcessed(`${currentChat}.json`);
        } catch (saveError: any) {
          console.error('Failed to save analyzed tasks:', saveError);
          setLogs(prev => [...prev, { type: 'error', message: `Save failed: ${saveError.message}` }]);
        }
        
        setStage('learned');
      } else {
        setLogs(prev => [
          ...prev,
          { type: 'error', message: `Error: ${response.error}` }
        ]);
      }
    } catch (error: any) {
      console.error('Learning failed:', error);
      setLogs(prev => [
        ...prev,
        { type: 'error', message: `Error: ${error.message || 'Learning failed'}` }
      ]);
    } finally {
      setIsLearning(false);
      setCurrentTaskIndex(undefined);
      setCurrentlyAnalyzingTaskId(null);
      // Clear all highlighting
      setNodes(prev => prev.map(node => ({
        ...node,
        data: {
          ...node.data,
          isAnalyzing: false
        }
      })));
    }
  };

  const loadChatTasks = useCallback(async (chat: string) => {
    const analyzedResponse = await api.getAnalyzedTasks(chat);
    let tasks: any[] = [];
    let isAnalyzed = false;
    
    if (analyzedResponse.success && analyzedResponse.analyzed_tasks.length > 0) {
      tasks = analyzedResponse.analyzed_tasks;
      isAnalyzed = true;
    } else {
      const categorizedResponse = await api.getCategorizedTasks(chat);
      if (categorizedResponse.success) {
        tasks = categorizedResponse.tasks;
        isAnalyzed = false;
      }
    }
    
    if (tasks.length > 0) {
      const newNodes = tasks.map((task: any, i: number) => ({
        id: task.task_id,
        type: 'task',
        position: { x: 250, y: 100 + i * 150 },
        data: { 
          label: task.suggested_type || task.type || 'uncategorized',
          task 
        },
      }));
      
      const newEdges = tasks.slice(1).map((task: any, i: number) => ({
        id: `e-${tasks[i].task_id}-${task.task_id}`,
        source: tasks[i].task_id,
        target: task.task_id,
        type: 'smoothstep',
        markerEnd: { type: MarkerType.ArrowClosed },
      }));
      
      setApprovedTasks(tasks);
      setNodes(newNodes);
      setEdges(newEdges);
      setStage(isAnalyzed ? 'learned' : 'categorized');
    }
    
    return tasks.length;
  }, [setNodes, setEdges]);

  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    const task = node.data.task;
    if (task) {
      setSelectedTask(task);
    }
  }, []);

  const handleNodeDelete = useCallback((nodeId: string) => {
    // Find edges connected to this node
    const incomingEdges = edges.filter(e => e.target === nodeId);
    const outgoingEdges = edges.filter(e => e.source === nodeId);
    
    // Graph mending: connect all predecessors to all successors
    const newEdges: any[] = [];
    incomingEdges.forEach(inEdge => {
      outgoingEdges.forEach(outEdge => {
        newEdges.push({
          id: `e-${inEdge.source}-${outEdge.target}`,
          source: inEdge.source,
          target: outEdge.target,
          type: 'smoothstep',
          markerEnd: { type: MarkerType.ArrowClosed },
        });
      });
    });
    
    // Remove node and its edges, add new mended edges
    setNodes(prev => prev.filter(n => n.id !== nodeId));
    setEdges(prev => {
      const filtered = prev.filter(e => e.source !== nodeId && e.target !== nodeId);
      return [...filtered, ...newEdges];
    });
    
    // Remove from approved tasks
    setApprovedTasks(prev => prev.filter(t => t.task_id !== nodeId));
    
    // Close details panel if this node was selected
    if (selectedTask?.task_id === nodeId) {
      setSelectedTask(null);
    }
    
    setLogs(prev => [
      ...prev,
      { type: 'info', message: `Deleted node: ${nodeId}` }
    ]);
  }, [edges, selectedTask, setNodes, setEdges]);

  useEffect(() => {
    const loadChats = async () => {
      try {
        const response = await api.getChats();
        
        if (response.success) {
          setChats(response.chats);
          
          if (response.chats.length > 0) {
            const firstChat = response.chats[0];
            setCurrentChat(firstChat);
            
            const count = await loadChatTasks(firstChat);
            setShowFileUpload(false);
            setLogs([{ type: 'info', message: `Loaded ${count} tasks from ${firstChat}` }]);
          } else {
            setShowFileUpload(true);
          }
        }
      } catch (error: any) {
        console.error('Failed to load chats:', error);
        setShowFileUpload(true);
      }
    };
    
    loadChats();
  }, [loadChatTasks]);

  const handleChatSelect = async (chat: string) => {
    setShowFileUpload(false);
    setCurrentChat(chat);
    setNodes([]);
    setEdges([]);
    setApprovedTasks([]);
    setPendingTasks([]);
    setSelectedTask(null);
    setLogs([{ type: 'info', message: `Loading ${chat}...` }]);
    
    try {
      const count = await loadChatTasks(chat);
      if (count > 0) {
        setLogs([{ type: 'info', message: `Loaded ${count} tasks from ${chat}` }]);
      } else {
        setLogs([{ type: 'info', message: `No tasks found for ${chat}` }]);
      }
    } catch (error: any) {
      console.error('Failed to load chat:', error);
      setLogs([{ type: 'error', message: `Failed to load ${chat}: ${error.message}` }]);
    }
  };

  const handleNewChat = () => {
    // Clear workflow
    setNodes([]);
    setEdges([]);
    setApprovedTasks([]);
    setPendingTasks([]);
    setParsedTasks([]);
    setSelectedTask(null);
    setStage('upload');
    
    // Reset state
    setCurrentChat('');
    setLogs([{ type: 'info', message: 'Ready to upload new chat' }]);
    
    // Show upload
    setShowFileUpload(true);
  };

  const handleTasksLoadedWrapper = (tasks: Task[], chatName: string, responseLogs?: LogEntry[]) => {
    const loadChats = async () => {
      try {
        const response = await api.getChats();
        if (response.success) {
          setChats(response.chats);
        }
      } catch (error) {
        console.error('Failed to refresh chats:', error);
      }
    };
    loadChats();
    
    setShowFileUpload(false);
    handleTasksLoaded(tasks, chatName, responseLogs);
  };

  return (
    <Box sx={{ height: '100vh', width: '100vw', display: 'flex', flexDirection: 'column', m: 0, p: 0 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, pt: 2, px: 2, pb: 1, flexShrink: 0 }}>
        <img src={zoroIcon} alt="ZORO" style={{ width: 44, height: 44 }} />
        <Typography
          sx={{
            fontFamily: '"SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
            fontWeight: 800,
            fontSize: '1.7rem',
            letterSpacing: '0.04em',
            lineHeight: 1,
          }}
        >
          ZORO
        </Typography>
      </Box>

      <Tabs 
        value={tabIndex} 
        onChange={(_, v) => setTabIndex(v)} 
        sx={{ 
          borderBottom: 1, 
          borderColor: 'divider', 
          flexShrink: 0,
          '& .MuiTab-root': {
            color: colors.grey,
            '&:focus': {
              outline: 'none',
            },
            '&.Mui-focusVisible': {
              outline: 'none',
              backgroundColor: 'transparent',
            },
          },
          '& .Mui-selected': {
            color: `${colors.green} !important`,
          },
          '& .MuiTabs-indicator': {
            backgroundColor: colors.green,
          }
        }}
      >
        {visibleTabs.map(tab => (
          <Tab key={tab.key} label={tab.label} disableRipple />
        ))}
      </Tabs>

      {visibleTabs[tabIndex]?.key === 'learner' && (
        <PanelGroup direction="horizontal" style={{ flex: 1, overflow: 'hidden' }}>
        {/* Chat Library Panel */}
        <Panel defaultSize={15} minSize={10} maxSize={30}>
          <ChatLibrary
            chats={chats}
            selectedChat={currentChat}
            onChatSelect={handleChatSelect}
            onNewChat={handleNewChat}
            onChatsUpdate={setChats}
          />
        </Panel>

        <PanelResizeHandle style={{ width: '1px', backgroundColor: '#d0d0d0', cursor: 'col-resize' }} />

        {/* Left Panel: ProcessingPanel */}
        <Panel defaultSize={20} minSize={15} maxSize={40}>
          <ProcessingPanel
            showFileUpload={showFileUpload}
            stage={stage}
            logs={logs}
            isProcessing={isProcessing}
            parsedTasks={parsedTasks}
            pendingTasks={pendingTasks}
            onTasksLoaded={handleTasksLoadedWrapper}
            onProcessStart={handleProcessStart}
            onProcessError={handleProcessError}
            onCategorize={handleCategorize}
            onApprove={handleApprove}
            onApproveAll={handleApproveAll}
            onLearnRules={handleLearnRules}
            isLearning={isLearning}
            currentTaskIndex={currentTaskIndex}
            totalTasks={approvedTasks.length}
            currentTaskType={currentTaskIndex !== undefined ? approvedTasks[currentTaskIndex]?.suggested_type : undefined}
          />
        </Panel>

        <PanelResizeHandle style={{ width: '1px', backgroundColor: '#d0d0d0', cursor: 'col-resize' }} />

        {/* Center: React Flow */}
        <Panel>
          <Paper sx={{ height: '100%', position: 'relative', overflow: 'hidden', m: 0, borderRadius: 0 }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={handleNodeClick}
              nodeTypes={nodeTypes}
              panOnDrag={true}
              zoomOnScroll={true}
              panOnScroll={false}
              minZoom={0.1}
              maxZoom={2}
              defaultViewport={{ x: 0, y: 0, zoom: 1 }}
              style={{ position: 'absolute', inset: 0 }}
            >
              <Controls />
              <Background />
            </ReactFlow>
          </Paper>
        </Panel>

        {/* Right Panel: DetailsPanel (conditional) */}
        {selectedTask && (
          <>
            <PanelResizeHandle style={{ width: '1px', backgroundColor: '#d0d0d0', cursor: 'col-resize' }} />
            <Panel defaultSize={25} minSize={20} maxSize={50}>
              <LearnerTaskDetails 
                task={selectedTask}
                onClose={() => setSelectedTask(null)}
                chatId={currentChat}
                onTaskUpdate={(updatedTask) => {
                  // Update approved tasks
                  setApprovedTasks(prev => prev.map(t => 
                    t.task_id === updatedTask.task_id ? updatedTask : t
                  ));
                  // Update selected task
                  setSelectedTask(updatedTask);
                  // Update nodes
                  setNodes(prev => prev.map(node => 
                    node.id === updatedTask.task_id 
                      ? { ...node, data: { ...node.data, task: updatedTask } }
                      : node
                  ));
                }}
                onFavoritesChange={handleFavoritesChange}
              />
            </Panel>
          </>
        )}

        {/* Favorites Panel (rightmost, always visible when open) */}
        {favoritesOpen && (
          <>
            <PanelResizeHandle style={{ width: '1px', backgroundColor: '#d0d0d0', cursor: 'col-resize' }} />
            <Panel defaultSize={20} minSize={15} maxSize={30}>
              <FavoritesPanel 
                open={favoritesOpen}
                onClose={() => setFavoritesOpen(false)}
                refreshKey={favoritesRefreshKey}
                onFavoritesChange={handleFavoritesChange}
              />
            </Panel>
          </>
        )}
        </PanelGroup>
      )}

      {visibleTabs[tabIndex]?.key === 'assistant' && <AssistantTab />}

      {visibleTabs[tabIndex]?.key === 'visualization' && <VisualizationTab />}

      {visibleTabs[tabIndex]?.key === 'knowledge-base' && <KnowledgeBaseTab />}

      {/* Thin Favorites Toggle Button (always visible on right edge) */}
      {visibleTabs[tabIndex]?.key === 'learner' && !favoritesOpen && (
        <Box
          onClick={() => setFavoritesOpen(true)}
          sx={{
            position: 'fixed',
            right: 0,
            top: '50%',
            transform: 'translateY(-50%)',
            bgcolor: colors.green,
            color: 'white',
            py: 2,
            px: 0.5,
            cursor: 'pointer',
            writingMode: 'vertical-rl',
            textOrientation: 'mixed',
            fontSize: '0.75rem',
            fontWeight: 600,
            letterSpacing: '0.1em',
            borderTopLeftRadius: 4,
            borderBottomLeftRadius: 4,
            '&:hover': {
              bgcolor: colors.darkGreen,
            },
            zIndex: 1000,
          }}
        >
          FAVORITES
        </Box>
      )}
    </Box>
  );
}
