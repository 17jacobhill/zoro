import { type ReactElement, type ReactNode, useState } from "react";
import {
  Box,
  Collapse,
  Typography,
} from "@mui/material";
import { ExpandMore, ExpandLess } from "@mui/icons-material";
import { colors } from "./colors";

interface AccordionProps {
  title: string | ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}

const Accordion = ({
  title,
  defaultOpen = true,
  children,
}: AccordionProps): ReactElement => {
  const [expanded, setExpanded] = useState(defaultOpen);

  return (
    <Box sx={{ width: "100%", display: "flex", flexDirection: "column" }}>
      <Box
        sx={{
          p: 1.5,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid",
          borderColor: "divider",
          cursor: "pointer",
        }}
        onClick={() => setExpanded(!expanded)}
      >
        {typeof title === "string" ? (
          <Typography variant="subtitle2" fontWeight={600}>
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

      <Collapse in={expanded}>{children}</Collapse>
    </Box>
  );
};

export { Accordion };
