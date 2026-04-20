import { type ReactElement, type ReactNode, useState } from "react";
import {
  Box,
  Collapse,
  Typography,
} from "@mui/material";
import { ExpandMore, ExpandLess } from "@mui/icons-material";
import { colors } from "./colors";

interface CollapsibleSectionProps {
  title: string | ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
  sx?: any;
}

const CollapsibleSection = ({
  title,
  defaultOpen = false,
  children,
  sx,
}: CollapsibleSectionProps): ReactElement => {
  const [expanded, setExpanded] = useState(defaultOpen);

  return (
    <Box sx={{ ...sx }}>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          p: 1.5,
          borderBottom: "1px solid",
          borderColor: "divider",
          bgcolor: "background.default",
          cursor: "pointer",
        }}
        onClick={() => setExpanded(!expanded)}
      >
        {typeof title === "string" ? (
          <Typography variant="body2" fontWeight={600}>
            {title}
          </Typography>
        ) : (
          title
        )}
        {expanded ? (
          <ExpandLess sx={{ color: colors.green }} />
        ) : (
          <ExpandMore sx={{ color: colors.green }} />
        )}
      </Box>

      <Collapse in={expanded}>
        <Box sx={{ p: 1.5 }}>{children}</Box>
      </Collapse>
    </Box>
  );
};

export { CollapsibleSection };
