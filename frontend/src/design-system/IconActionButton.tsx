import { type ReactElement, type ReactNode } from 'react';
import { IconButton, type IconButtonProps, alpha } from '@mui/material';

import { colors } from './colors';

type Tone = 'green' | 'dark-green' | 'grey' | 'red' | 'gold' | 'blue';

interface IconActionButtonProps extends Omit<IconButtonProps, 'color' | 'children'> {
  children: ReactNode;
  tone?: Tone;
  active?: boolean;
}

const toneMap: Record<Tone, string> = {
  green: colors.green,
  'dark-green': colors.darkGreen,
  grey: colors.grey,
  red: colors.red,
  gold: colors.gold,
  blue: colors.blue,
};

const IconActionButton = ({
  children,
  tone = 'grey',
  active = false,
  size = 'small',
  sx,
  ...props
}: IconActionButtonProps): ReactElement => {
  const toneColor = toneMap[tone];

  return (
    <IconButton
      size={size}
      disableRipple
      sx={{
        color: toneColor,
        p: 0.5,
        borderRadius: 1,
        backgroundColor: active ? alpha(toneColor, 0.14) : 'transparent',
        transition: 'background-color 120ms ease, color 120ms ease',
        '&:hover': {
          backgroundColor: alpha(toneColor, active ? 0.18 : 0.1),
        },
        '&:focus': {
          outline: 'none',
        },
        '&.Mui-focusVisible': {
          outline: 'none',
          backgroundColor: alpha(toneColor, 0.16),
        },
        '&.Mui-disabled': {
          opacity: 0.35,
        },
        ...sx,
      }}
      {...props}
    >
      {children}
    </IconButton>
  );
};

export { IconActionButton };
