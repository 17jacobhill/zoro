import { type ComponentProps, type ReactNode } from 'react';
import { CircularProgress, Tooltip, type TooltipProps } from '@mui/material';

import { IconActionButton } from './IconActionButton';

type IconActionButtonProps = ComponentProps<typeof IconActionButton>;

interface CompactIconButtonProps extends Omit<IconActionButtonProps, 'children'> {
  label: string;
  icon: ReactNode;
  loading?: boolean;
  tooltipPlacement?: TooltipProps['placement'];
}

export function CompactIconButton({
  label,
  icon,
  loading = false,
  disabled = false,
  tooltipPlacement = 'top',
  ...props
}: CompactIconButtonProps) {
  const pressed = typeof props.active === 'boolean' ? props.active : undefined;

  return (
    <Tooltip title={label} placement={tooltipPlacement}>
      <span style={{ display: 'inline-flex' }}>
        <IconActionButton
          aria-label={label}
          aria-busy={loading || undefined}
          aria-pressed={pressed}
          disabled={disabled || loading}
          {...props}
        >
          {loading ? <CircularProgress size={14} sx={{ color: 'currentColor' }} /> : icon}
        </IconActionButton>
      </span>
    </Tooltip>
  );
}
