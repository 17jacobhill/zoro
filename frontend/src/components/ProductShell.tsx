import { useMemo, useState } from 'react';
import { Box, Tab, Tabs, Typography } from '@mui/material';

import { colors } from '../design-system/colors';
import zoroIcon from '../assets/sword.png';
import { KnowledgeBaseTab } from './KnowledgeBase/KnowledgeBaseTab';
import { VisualizationTab } from './Visualization/VisualizationTab';

export function ProductShell() {
  const [tabIndex, setTabIndex] = useState(0);
  const visibleTabs = useMemo(
    () => [
      { key: 'visualization', label: 'Visualization' },
      { key: 'knowledge-base', label: 'Rules Management' },
    ],
    []
  );

  return (
    <Box
      sx={{
        height: '100vh',
        width: '100vw',
        display: 'flex',
        flexDirection: 'column',
        m: 0,
        p: 0,
        bgcolor: colors.surface,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, pt: 2, px: 2, pb: 1, flexShrink: 0 }}>
        <img src={zoroIcon} alt="ZORO" style={{ width: 44, height: 44 }} />
        <Typography
          sx={{
            fontFamily: '"SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
            fontWeight: 800,
            fontSize: '1.7rem',
            letterSpacing: '0.04em',
            lineHeight: 1,
          }}
        >
          ZORO
        </Typography>
      </Box>

      <Tabs
        value={tabIndex}
        onChange={(_, nextValue) => setTabIndex(nextValue)}
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          flexShrink: 0,
          '& .MuiTab-root': {
            color: colors.grey,
            minHeight: 48,
            textTransform: 'none',
            fontWeight: 600,
            '&:focus': {
              outline: 'none',
            },
            '&.Mui-focusVisible': {
              outline: 'none',
              backgroundColor: 'transparent',
            },
          },
          '& .Mui-selected': {
            color: `${colors.green} !important`,
          },
          '& .MuiTabs-indicator': {
            backgroundColor: colors.green,
          },
        }}
      >
        {visibleTabs.map((tab) => (
          <Tab key={tab.key} label={tab.label} disableRipple />
        ))}
      </Tabs>

      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {visibleTabs[tabIndex]?.key === 'visualization' && <VisualizationTab />}
        {visibleTabs[tabIndex]?.key === 'knowledge-base' && <KnowledgeBaseTab />}
      </Box>
    </Box>
  );
}
