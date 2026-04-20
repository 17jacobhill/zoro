import { Box, Typography, CircularProgress } from '@mui/material';
import { ApprovalPanel } from './ApprovalPanel';
import { colors } from '../../../design-system/colors';
import type { Task } from '../../../services/api';

type Stage = 'upload' | 'parsing' | 'parsed' | 'categorizing' | 'categorized' | 'learning' | 'learned';

interface CategorizingSectionProps {
  stage: Stage;
  pendingTasks: Task[];
  onApprove: (taskId: string) => void;
  onApproveAll: () => void;
}

export function CategorizingSection({
  stage,
  pendingTasks,
  onApprove,
  onApproveAll,
}: CategorizingSectionProps) {
  // Show once categorizing starts
  if (!['categorizing', 'categorized', 'learning', 'learned'].includes(stage)) {
    return null;
  }

  const isActive = stage === 'categorizing';
  const isCategorized = stage === 'categorized';
  // Show completion when: moved past categorization OR categorized with nothing pending
  const isComplete = ['learning', 'learned'].includes(stage) || 
                     (stage === 'categorized' && pendingTasks.length === 0);

  return (
    <Box sx={{ borderBottom: '1px solid #e0e0e0' }}>
      <Box sx={{ p: 2, pb: isCategorized ? 1 : 2 }}>
        <Typography sx={{ fontSize: 14, fontWeight: 'bold', mb: 1 }}>
          Categorizing Tasks
        </Typography>

        {isActive && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CircularProgress size={16} />
            <Typography sx={{ fontSize: 13, color: '#666' }}>
              Categorizing {pendingTasks.length} tasks...
            </Typography>
          </Box>
        )}

        {isComplete && (
          <Typography sx={{ fontSize: 13, color: colors.green }}>
            ✓ Categorizing complete
          </Typography>
        )}
      </Box>

      {/* ApprovalPanel only shows when categorized, not when complete */}
      {isCategorized && (
        <ApprovalPanel
          tasks={pendingTasks}
          onApprove={onApprove}
          onApproveAll={onApproveAll}
          onLearnRules={() => {}} // This will be handled by LearningSection
          showLearnButton={false} // Learning button is in LearningSection
        />
      )}
    </Box>
  );
}
