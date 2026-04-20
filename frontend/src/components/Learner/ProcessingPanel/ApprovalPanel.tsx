import { Box, Typography, Checkbox } from '@mui/material';
import { useState } from 'react';
import { Accordion } from '../../../design-system/Accordion';
import { Button } from '../../../design-system/Button';
import { type Task } from '../../../services/api';

interface ApprovalPanelProps {
  tasks: Task[];
  onApprove: (taskId: string) => void;
  onApproveAll: () => void;
  onLearnRules?: () => void;
  showLearnButton?: boolean;
}

export function ApprovalPanel({ tasks, onApprove, onApproveAll, onLearnRules, showLearnButton }: ApprovalPanelProps) {
  const [selectedTasks, setSelectedTasks] = useState<Set<string>>(new Set());

  // Show panel if there are tasks OR if learn button should be shown
  if (tasks.length === 0 && !showLearnButton) return null;

  const handleToggle = (taskId: string) => {
    const newSelected = new Set(selectedTasks);
    if (newSelected.has(taskId)) {
      newSelected.delete(taskId);
    } else {
      newSelected.add(taskId);
    }
    setSelectedTasks(newSelected);
  };

  const handleApprove = () => {
    selectedTasks.forEach(taskId => onApprove(taskId));
    setSelectedTasks(new Set());
  };

  return (
    <Accordion title={`Approve Tasks (${tasks.length})`} defaultOpen={true}>
      {showLearnButton && tasks.length === 0 ? (
        <Box sx={{ p: 2, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            All tasks approved!
          </Typography>
          <Button
            size="small"
            fullWidth
            onClick={onLearnRules}
            colorVariant="green"
          >
            Learn Rules
          </Button>
        </Box>
      ) : (
        <Box 
          sx={{ 
            p: 2,
            maxHeight: 'calc(100vh - 400px)',
            overflow: 'auto',
          }}
        >
          {tasks.map((task) => (
            <Box 
              key={task.task_id}
              sx={{ 
                mb: 2,
                p: 1,
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                '&:hover': {
                  bgcolor: 'action.hover',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
                <Checkbox
                  size="small"
                  checked={selectedTasks.has(task.task_id)}
                  onChange={() => handleToggle(task.task_id)}
                />
                <Box sx={{ flex: 1, ml: 1 }}>
                  <Typography 
                    variant="body2" 
                    fontWeight={600}
                    sx={{ mb: 0.5 }}
                  >
                    {task.suggested_type || 'uncategorized'}
                  </Typography>
                  <Typography 
                    variant="caption" 
                    color="text.secondary"
                    sx={{ 
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}
                  >
                    {task.description}
                  </Typography>
                </Box>
              </Box>
              </Box>
          ))}
        </Box>
      )}

      <Box 
        sx={{ 
          p: 2,
          borderTop: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          gap: 1,
        }}
      >
        <Button
          size="small"
          fullWidth
          onClick={handleApprove}
          disabled={selectedTasks.size === 0}
          colorVariant="green"
        >
          Approve ({selectedTasks.size})
        </Button>
        <Button
          size="small"
          onClick={onApproveAll}
          colorVariant="green"
        >
          All
        </Button>
      </Box>
    </Accordion>
  );
}
