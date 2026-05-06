import { type ReactElement } from 'react';
import {
  InputLabel as MuiInputLabel,
  type InputLabelProps as MuiInputLabelProps,
} from '@mui/material';

import { colors } from './colors';

interface InputLabelProps extends MuiInputLabelProps {}

const InputLabel = ({ sx, ...props }: InputLabelProps): ReactElement => {
  return (
    <MuiInputLabel
      sx={{
        fontSize: '11px',
        color: colors.grey,
        '&.Mui-focused': {
          color: colors.green,
        },
        ...sx,
      }}
      {...props}
    />
  );
};

export { InputLabel };
