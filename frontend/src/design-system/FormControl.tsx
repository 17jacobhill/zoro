import { type ReactElement } from 'react';
import {
  FormControl as MuiFormControl,
  type FormControlProps as MuiFormControlProps,
} from '@mui/material';

interface FormControlProps extends MuiFormControlProps {}

const FormControl = ({
  size = 'small',
  sx,
  ...props
}: FormControlProps): ReactElement => {
  return (
    <MuiFormControl
      size={size}
      sx={{
        minWidth: 0,
        ...sx,
      }}
      {...props}
    />
  );
};

export { FormControl };
