import { Box, Typography } from '@mui/material';
import { Accordion } from '../../../design-system/Accordion';

interface LogEntry {
  type: 'success' | 'error' | 'info';
  message: string;
  timestamp?: string;
}

interface LogPanelProps {
  logs: LogEntry[];
  isProcessing: boolean;
}

export function LogPanel({ logs, isProcessing }: LogPanelProps) {
  if (logs.length === 0 && !isProcessing) return null;

  return (
    <Accordion title="Processing Logs" defaultOpen={true}>
      <Box 
        sx={{ 
          p: 2,
          maxHeight: 300,
          overflow: 'auto',
          fontSize: '0.875rem',
          fontFamily: 'monospace',
        }}
      >
        {logs.map((log, idx) => (
          <Typography 
            key={idx}
            variant="body2" 
            sx={{ 
              fontFamily: 'monospace',
              fontSize: '0.8rem',
              mb: 0.5,
              whiteSpace: 'pre-wrap',
            }}
          >
            {log.message}
          </Typography>
        ))}
        
        {isProcessing && (
          <Typography 
            variant="body2"
            sx={{ 
              fontFamily: 'monospace',
              fontSize: '0.8rem',
              fontStyle: 'italic',
              mt: 1,
            }}
          >
            Processing...
          </Typography>
        )}
      </Box>
    </Accordion>
  );
}
