import { type ReactElement, type ReactNode } from 'react';
import { Box, Typography } from '@mui/material';

import { colors } from './colors';

interface PanelHeaderProps {
  title: string | ReactNode;
  badge?: ReactNode;
  subtitle?: string | ReactNode;
  actions?: ReactNode;
  mb?: number;
}

const PanelHeader = ({
  title,
  badge,
  subtitle,
  actions,
  mb = 2,
}: PanelHeaderProps): ReactElement => {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 1.5,
        pb: 0.35,
        mb,
      }}
    >
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          {typeof title === 'string' ? (
            <Typography
              variant="body1"
              sx={{ color: colors.text, fontSize: '0.95rem', fontWeight: 600, lineHeight: 1.2 }}
            >
              {title}
            </Typography>
          ) : (
            title
          )}
          {badge}
        </Box>
        {subtitle ? (
          typeof subtitle === 'string' ? (
            <Typography sx={{ mt: 0.45, color: colors.mutedText, fontSize: '0.74rem', lineHeight: 1.35 }}>
              {subtitle}
            </Typography>
          ) : (
            <Box sx={{ mt: 0.45 }}>{subtitle}</Box>
          )
        ) : null}
      </Box>
      {actions ? <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>{actions}</Box> : null}
    </Box>
  );
};

export { PanelHeader };
