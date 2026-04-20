import { type ReactElement } from "react";
import {
  TextField as MuiTextField,
  type TextFieldProps as MuiTextFieldProps,
} from "@mui/material";
import { colors } from "./colors";

interface TextFieldProps extends Omit<MuiTextFieldProps, 'color'> {
  colorVariant?: 'green' | 'grey';
}

const TextField = ({
  variant = "outlined",
  sx,
  colorVariant = 'green',
  ...props
}: TextFieldProps): ReactElement => {
  const borderColor = colorVariant === 'green' ? colors.green : colors.grey;
  const hoverColor = colorVariant === 'green' ? colors.darkGreen : colors.grey;
  const focusColor = colorVariant === 'green' ? colors.green : colors.grey;

  return (
    <MuiTextField
      variant={variant}
      sx={{
        // Remove blue ripple effect
        '& .MuiOutlinedInput-root': {
          '& fieldset': {
            borderColor: borderColor,
          },
          '&:hover fieldset': {
            borderColor: hoverColor,
          },
          '&.Mui-focused fieldset': {
            borderColor: focusColor,
          },
          '&.Mui-focused': {
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: focusColor,
            },
          },
        },
        // Label colors
        '& .MuiInputLabel-root': {
          color: colors.grey,
          '&.Mui-focused': {
            color: focusColor,
          },
        },
        // Filled variant
        '& .MuiFilledInput-root': {
          '&:before': {
            borderBottomColor: borderColor,
          },
          '&:hover:before': {
            borderBottomColor: hoverColor,
          },
          '&:after': {
            borderBottomColor: focusColor,
          },
          '&.Mui-focused:after': {
            borderBottomColor: focusColor,
          },
        },
        // Standard variant
        '& .MuiInput-root': {
          '&:before': {
            borderBottomColor: borderColor,
          },
          '&:hover:not(.Mui-disabled):before': {
            borderBottomColor: hoverColor,
          },
          '&:after': {
            borderBottomColor: focusColor,
          },
        },
        // Remove focus outline
        '& .MuiOutlinedInput-root.Mui-focused': {
          outline: 'none',
          boxShadow: 'none',
        },
        '& .MuiInputBase-root.Mui-focused': {
          outline: 'none',
          boxShadow: 'none',
        },
        '& .MuiInputBase-input:focus': {
          outline: 'none',
          boxShadow: 'none',
        },
        '& .MuiInputBase-input': {
          outline: 'none',
        },
        // Disabled state
        '& .Mui-disabled': {
          opacity: 0.5,
        },
        ...sx,
      }}
      {...props}
    />
  );
};

export { TextField };
