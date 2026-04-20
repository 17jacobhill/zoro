import { Box, Typography, CircularProgress } from '@mui/material';
import { Button } from '../../../design-system/Button';
import { colors } from '../../../design-system/colors';

type Stage = 'upload' | 'parsing' | 'parsed' | 'categorizing' | 'categorized' | 'learning' | 'learned';

interface LearningSectionProps {
  stage: Stage;
  onLearnRules: () => void;
  isLearning: boolean;
  currentTaskIndex?: number;
  totalTasks?: number;
  currentTaskType?: string;
}

export function LearningSection({
  stage,
  onLearnRules,
  isLearning,
  currentTaskIndex,
  totalTasks,
  currentTaskType,
}: LearningSectionProps) {
  // Only show after categorization is complete
  if (!['categorized', 'learning', 'learned'].includes(stage)) {
    return null;
  }

  return (
    <Box sx={{ p: 2, borderBottom: '1px solid #e0e0e0' }}>
      <Typography sx={{ fontSize: 14, fontWeight: 'bold', mb: 1 }}>
        Learning Rules
      </Typography>

      {stage === 'categorized' && !isLearning && (
        <Button onClick={onLearnRules} colorVariant="green" size="small">
          Learn Rules
        </Button>
      )}

      {(stage === 'learning' || isLearning) && currentTaskIndex !== undefined && totalTasks !== undefined && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CircularProgress size={16} />
          <Typography sx={{ fontSize: 13, color: '#666' }}>
            Analyzing task {currentTaskIndex + 1} of {totalTasks}: "{currentTaskType || 'task'}"
          </Typography>
        </Box>
      )}

      {stage === 'learned' && !isLearning && (
        <Typography sx={{ fontSize: 13, color: colors.green }}>
          ✓ Learning complete
        </Typography>
      )}
    </Box>
  );
}
