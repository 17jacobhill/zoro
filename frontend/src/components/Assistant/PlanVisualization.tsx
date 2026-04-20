import { useEffect } from 'react';
import ReactFlow, {
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Box, Paper, Typography } from '@mui/material';
import { FlowNode } from '../../design-system/FlowNode';

const nodeTypes = {
  plan: FlowNode,
};

interface PlanVisualizationProps {
  plan: any | null;
  loading: boolean;
  onNodeClick?: (node: any) => void;
  onNodeDelete?: (nodeId: string) => void;
}

export function PlanVisualization({ plan, loading, onNodeClick, onNodeDelete }: PlanVisualizationProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (!plan) {
      setNodes([]);
      setEdges([]);
      return;
    }

    const flowNodes: Node[] = plan.nodes.map((node: any, i: number) => ({
      id: node.id,
      type: 'plan',
      position: { x: 250, y: 100 + i * 150 },
      data: { 
        label: node.type,
        node,
        status: node.status,
        onDelete: onNodeDelete ? () => onNodeDelete(node.id) : undefined
      },
    }));

    const flowEdges: Edge[] = plan.edges.map((edge: any) => ({
      id: edge.id,
      source: edge.from,
      target: edge.to,
      type: 'smoothstep',
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [plan, setNodes, setEdges]);

  if (loading) {
    return <Box sx={{ p: 2 }}><Typography>Loading plan...</Typography></Box>;
  }

  if (!plan) {
    return <Box sx={{ p: 2 }}><Typography>No plan for this chat yet</Typography></Box>;
  }

  return (
      <Paper sx={{ height: '100%', position: 'relative', overflow: 'hidden', m: 0, borderRadius: 0 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={(_event, node) => onNodeClick?.(node.data.node)}
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
  );
}
