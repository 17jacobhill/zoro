import { type ReactElement } from "react";
import {
  Select as MuiSelect,
  type SelectProps as MuiSelectProps,
} from "@mui/material";
import { colors } from "./colors";

interface SelectProps extends Omit<MuiSelectProps, 'color'> {
  colorVariant?: 'green' | 'grey';
}

const Select = ({
  variant = "outlined",
  size = "small",
  sx,
  colorVariant = 'green',
  ...props
}: SelectProps): ReactElement => {
  const borderColor = colorVariant === 'green' ? colors.green : colors.grey;
  const hoverColor = colorVariant === 'green' ? colors.darkGreen : colors.grey;
  const focusColor = colorVariant === 'green' ? colors.green : colors.grey;

  return (
    <MuiSelect
      variant={variant}
      size={size}
      sx={{
        minHeight: size === 'small' ? 36 : undefined,
        borderRadius: 1.25,
        fontSize: '12px',
        '& .MuiOutlinedInput-notchedOutline': {
          borderColor: borderColor,
        },
        '&:hover .MuiOutlinedInput-notchedOutline': {
          borderColor: hoverColor,
        },
        '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
          borderColor: focusColor,
        },
        '& .MuiSelect-icon': {
          color: colorVariant === 'green' ? colors.green : colors.grey,
        },
        '&:hover .MuiSelect-icon': {
          color: hoverColor,
        },
        '&.Mui-focused .MuiSelect-icon': {
          color: focusColor,
        },
        '&.Mui-focused': {
          outline: 'none',
        },
        '&.Mui-disabled': {
          opacity: 0.5,
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: colors.grey,
          },
        },
        '& .MuiSelect-select': {
          fontSize: '12px',
          lineHeight: 1.35,
          display: 'flex',
          alignItems: 'center',
          minHeight: 'auto',
        },
        ...sx,
      }}
      MenuProps={{
        ...props.MenuProps,
        PaperProps: {
          ...props.MenuProps?.PaperProps,
          sx: {
            '& .MuiMenuItem-root': {
              fontSize: '12px',
              minHeight: 32,
              '&:hover': {
                backgroundColor: `${focusColor}20`,
              },
              '&.Mui-selected': {
                backgroundColor: `${focusColor}30`,
                '&:hover': {
                  backgroundColor: `${focusColor}40`,
                },
              },
              '&.Mui-focusVisible': {
                backgroundColor: `${focusColor}20`,
              },
            },
            ...props.MenuProps?.PaperProps?.sx,
          },
        },
      }}
      {...props}
    />
  );
};

export { Select };
