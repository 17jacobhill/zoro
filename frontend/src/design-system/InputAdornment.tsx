import { type ReactElement } from 'react';
import {
  InputAdornment as MuiInputAdornment,
  type InputAdornmentProps as MuiInputAdornmentProps,
} from '@mui/material';

import { colors } from './colors';

interface InputAdornmentProps extends MuiInputAdornmentProps {}

const InputAdornment = ({ sx, ...props }: InputAdornmentProps): ReactElement => {
  return (
    <MuiInputAdornment
      sx={{
        color: colors.grey,
        '& .MuiSvgIcon-root': {
          fontSize: 16,
        },
        ...sx,
      }}
      {...props}
    />
  );
};

export { InputAdornment };
