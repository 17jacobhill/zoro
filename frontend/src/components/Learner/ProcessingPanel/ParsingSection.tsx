import { Box, Typography, CircularProgress } from '@mui/material';
import { Button } from '../../../design-system/Button';
import { colors } from '../../../design-system/colors';
import type { Task } from '../../../services/api';

type Stage = 'upload' | 'parsing' | 'parsed' | 'categorizing' | 'categorized' | 'learning' | 'learned';

interface ParsingSectionProps {
  stage: Stage;
  parsedTasks: Task[];
  onCategorize: () => void;
}

export function ParsingSection({ stage, parsedTasks, onCategorize }: ParsingSectionProps) {
  void parsedTasks;
  
  // Show once parsing starts
  if (stage === 'upload') {
    return null;
  }

  const isActive = stage === 'parsing';
  const isParsed = stage === 'parsed';
  const isComplete = ['categorizing', 'categorized', 'learning', 'learned'].includes(stage);

  return (
    <Box sx={{ p: 2, borderBottom: '1px solid #e0e0e0' }}>
      <Typography sx={{ fontSize: 14, fontWeight: 'bold', mb: 1 }}>
        Chat Parsing
      </Typography>

      {isActive && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CircularProgress size={16} />
          <Typography sx={{ fontSize: 13, color: '#666' }}>
            Parsing chat file...
          </Typography>
        </Box>
      )}

      {isParsed && (
        <Button onClick={onCategorize} colorVariant="green" size="small">
          Categorize Tasks
        </Button>
      )}

      {isComplete && (
        <Typography sx={{ fontSize: 13, color: colors.green }}>
          ✓ Parsing complete
        </Typography>
      )}
    </Box>
  );
}
