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
  size = "small",
  multiline = false,
  sx,
  colorVariant = 'green',
  ...props
}: TextFieldProps): ReactElement => {
  const borderColor = colorVariant === 'green' ? colors.green : colors.grey;
  const hoverColor = colorVariant === 'green' ? colors.darkGreen : colors.grey;
  const focusColor = colorVariant === 'green' ? colors.green : colors.grey;
  const compactHeight = variant === 'standard' ? 32 : 36;

  return (
    <MuiTextField
      variant={variant}
      size={size}
      multiline={multiline}
      sx={{
        // Remove blue ripple effect
        '& .MuiOutlinedInput-root': {
          borderRadius: 1.25,
          ...(multiline
            ? {}
            : {
                minHeight: compactHeight,
                height: compactHeight,
              }),
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
          fontSize: '11px',
          letterSpacing: 0.1,
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
          ...(multiline
            ? {}
            : {
                minHeight: compactHeight,
              }),
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
          fontSize: '12px',
          lineHeight: 1.35,
          '&::placeholder': {
            fontSize: '12px',
            opacity: 0.82,
          },
        },
        '& .MuiInputBase-inputMultiline': {
          fontSize: '12px',
          lineHeight: 1.4,
        },
        '& .MuiFormHelperText-root': {
          fontSize: '10px',
          lineHeight: 1.25,
          marginLeft: 0.5,
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
