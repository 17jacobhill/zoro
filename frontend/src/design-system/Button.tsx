import { type ReactElement, type ReactNode } from "react";
import {
  Button as MuiButton,
  type ButtonProps as MuiButtonProps,
  alpha,
} from "@mui/material";
import { colors } from "./colors";

interface ButtonProps extends MuiButtonProps {
  children: ReactNode;
  colorVariant?: Color;
}

type Color = "transparent" | "green" | "dark-green" | "red" | "blue";

const Button = ({
  children,
  variant = "outlined",
  onClick,
  sx,
  disabled = false,
  colorVariant = "transparent",
  ...props
}: ButtonProps): ReactElement => {
  let color: string = "transparent";
  let borderColor: string = colors.green;
  let textColor: string = colors.green;
  
  if (colorVariant === "green") {
    color = colors.green;
    textColor = "#ffffff";
  }
  if (colorVariant === "dark-green") {
    color = colors.darkGreen;
    textColor = "#ffffff";
  }
  if (colorVariant === "red") {
    color = colors.red;
    borderColor = colors.red;
    textColor = "#ffffff";
  }
  if (colorVariant === "blue") {
    color = colors.blue;
    borderColor = colors.blue;
    textColor = "#ffffff";
  }

  let hoverColor: string = alpha(colors.green, 0.04);
  let hoverBorderColor: string = colors.darkGreen;
  
  if (colorVariant === "green") {
    hoverColor = colors.darkGreen;
  }
  if (colorVariant === "dark-green") {
    hoverColor = alpha(colors.darkGreen, 0.8);
  }
  if (colorVariant === "red") {
    hoverColor = alpha(colors.red, 0.8);
    hoverBorderColor = colors.red;
  }
  if (colorVariant === "blue") {
    hoverColor = colors.blue;
    hoverBorderColor = colors.blue;
  }

  return (
    <MuiButton
      variant={variant}
      onClick={onClick}
      disabled={disabled}
      disableRipple
      sx={{
        backgroundColor: color,
        borderColor: borderColor,
        color: textColor,
        borderRadius: 1,
        boxShadow: "none",
        textTransform: "none",
        "&:hover": {
          backgroundColor: hoverColor,
          borderColor: hoverBorderColor,
        },
        "&:focus": {
          outline: "none",
        },
        "&:disabled": {
          opacity: 0.5,
          cursor: "not-allowed",
        },
        ...sx,
      }}
      {...props}
    >
      {children}
    </MuiButton>
  );
};

export { Button };
