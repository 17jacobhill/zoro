import { Box, Typography } from '@mui/material';
import { colors } from '../../../design-system/colors';

type Stage = 'upload' | 'parsing' | 'parsed' | 'categorizing' | 'categorized' | 'learning' | 'learned';

interface StageProgressIndicatorProps {
  stage: Stage;
}

export function StageProgressIndicator({ stage }: StageProgressIndicatorProps) {
  const getStageStatus = (stageName: 'parsing' | 'categorizing' | 'learning') => {
    const stageOrder = {
      parsing: ['parsing', 'parsed', 'categorizing', 'categorized', 'learning', 'learned'],
      categorizing: ['categorizing', 'categorized', 'learning', 'learned'],
      learning: ['learning', 'learned'],
    };

    if (stageOrder[stageName].includes(stage)) {
      if (stage === stageName) return 'active';
      if (stageName === 'parsing' && ['parsed', 'categorizing', 'categorized', 'learning', 'learned'].includes(stage)) return 'complete';
      if (stageName === 'categorizing' && ['categorized', 'learning', 'learned'].includes(stage)) return 'complete';
      if (stageName === 'learning' && stage === 'learned') return 'complete';
    }
    return 'pending';
  };

  const parsingStatus = getStageStatus('parsing');
  const categorizingStatus = getStageStatus('categorizing');
  const learningStatus = getStageStatus('learning');

  return (
    <Box sx={{ p: 2, borderBottom: '1px solid #e0e0e0' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {/* Parsing Stage */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 24,
              height: 24,
              borderRadius: '50%',
              border: '2px solid',
              borderColor: parsingStatus === 'complete' ? colors.green : parsingStatus === 'active' ? colors.darkGreen : colors.grey,
              bgcolor: parsingStatus === 'complete' ? colors.green : parsingStatus === 'active' ? colors.darkGreen : 'transparent',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {parsingStatus === 'complete' && (
              <Typography sx={{ color: 'white', fontSize: 14, fontWeight: 'bold' }}>✓</Typography>
            )}
          </Box>
          <Typography
            sx={{
              fontSize: 14,
              color: parsingStatus === 'pending' ? colors.grey : '#000',
              fontWeight: parsingStatus === 'active' ? 'bold' : 'normal',
            }}
          >
            Parsing
          </Typography>
        </Box>

        <Box sx={{ width: 40, height: 2, bgcolor: parsingStatus === 'complete' ? colors.green : '#e0e0e0' }} />

        {/* Categorizing Stage */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 24,
              height: 24,
              borderRadius: '50%',
              border: '2px solid',
              borderColor: categorizingStatus === 'complete' ? colors.green : categorizingStatus === 'active' ? colors.darkGreen : colors.grey,
              bgcolor: categorizingStatus === 'complete' ? colors.green : categorizingStatus === 'active' ? colors.darkGreen : 'transparent',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {categorizingStatus === 'complete' && (
              <Typography sx={{ color: 'white', fontSize: 14, fontWeight: 'bold' }}>✓</Typography>
            )}
          </Box>
          <Typography
            sx={{
              fontSize: 14,
              color: categorizingStatus === 'pending' ? colors.grey : '#000',
              fontWeight: categorizingStatus === 'active' ? 'bold' : 'normal',
            }}
          >
            Categorizing
          </Typography>
        </Box>

        <Box sx={{ width: 40, height: 2, bgcolor: categorizingStatus === 'complete' ? colors.green : '#e0e0e0' }} />

        {/* Learning Stage */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 24,
              height: 24,
              borderRadius: '50%',
              border: '2px solid',
              borderColor: learningStatus === 'complete' ? colors.green : learningStatus === 'active' ? colors.darkGreen : colors.grey,
              bgcolor: learningStatus === 'complete' ? colors.green : learningStatus === 'active' ? colors.darkGreen : 'transparent',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {learningStatus === 'complete' && (
              <Typography sx={{ color: 'white', fontSize: 14, fontWeight: 'bold' }}>✓</Typography>
            )}
          </Box>
          <Typography
            sx={{
              fontSize: 14,
              color: learningStatus === 'pending' ? colors.grey : '#000',
              fontWeight: learningStatus === 'active' ? 'bold' : 'normal',
            }}
          >
            Learning
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
