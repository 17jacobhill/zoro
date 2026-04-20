import { Box, CircularProgress, IconButton, Paper, Typography } from '@mui/material';
import { Close } from '@mui/icons-material';

export type VerifyVerdict = 'done' | 'not_done' | 'unclear';

export type FloatingVerifyPanelResult = {
  verdict: VerifyVerdict;
  message: string;
  action_text?: string;
  tracking_commands?: string[];
  audit_suggestion?: string;
};

export type FloatingVerifyPanelState =
  | { status: 'closed' }
  | { status: 'loading'; title: string }
  | { status: 'error'; title: string; error: string }
  | { status: 'result'; title: string; result: FloatingVerifyPanelResult };

function getVerdictLabel(verdict: VerifyVerdict): string {
  if (verdict === 'done') return 'done';
  if (verdict === 'not_done') return 'not done';
  return 'unclear';
}


export function FloatingVerifyPanel(props: {
  state: FloatingVerifyPanelState;
  onClose: () => void;
}) {
  const { state, onClose } = props;

  if (state.status === 'closed') return null;

  const content = (() => {
    if (state.status === 'loading') {
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CircularProgress size={16} />
          <Typography variant="body2">Checking…</Typography>
        </Box>
      );
    }

    if (state.status === 'error') {
      return (
        <Typography variant="body2" color="error" sx={{ whiteSpace: 'pre-wrap' }}>
          {state.error}
        </Typography>
      );
    }

    const { result } = state;

    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
          verdict: {getVerdictLabel(result.verdict)}
        </Typography>
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
          {result.message}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, fontStyle: 'italic' }}>
          Check Cline's UI for execution details
        </Typography>
      </Box>
    );
  })();

  const title = state.status === 'loading' ? state.title
    : state.status === 'error' ? state.title
    : state.status === 'result' ? state.title
    : '';

  return (
    <Paper
      elevation={8}
      sx={{
        position: 'absolute',
        top: 12,
        right: 12,
        width: 420,
        maxWidth: 'calc(100% - 24px)',
        p: 1.5,
        border: '1px solid',
        borderColor: 'divider',
        zIndex: 20,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="subtitle2" fontWeight={600}>
          {title}
        </Typography>
        <IconButton size="small" onClick={onClose}>
          <Close fontSize="small" />
        </IconButton>
      </Box>

      {content}
    </Paper>
  );
}
