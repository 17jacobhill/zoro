import { type ReactElement } from 'react';
import {
  MenuItem as MuiMenuItem,
  type MenuItemProps as MuiMenuItemProps,
} from '@mui/material';

interface MenuItemProps extends MuiMenuItemProps {}

const MenuItem = ({ sx, ...props }: MenuItemProps): ReactElement => {
  return (
    <MuiMenuItem
      sx={{
        fontSize: '12px',
        minHeight: 32,
        ...sx,
      }}
      {...props}
    />
  );
};

export { MenuItem };
