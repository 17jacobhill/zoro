import { Box, Typography } from '@mui/material';
import { Panel, PanelGroup } from 'react-resizable-panels';

import { colors } from '../../design-system/colors';
import { PanelResizeHandle } from '../../design-system/PanelResizeHandle';
import { CategoryPanel } from './CategoryPanel';
import { FileManagementPanel } from './FileManagementPanel';
import { RulesBrowserPanel } from './RulesBrowserPanel';

export const KnowledgeBaseTab: React.FC = () => {
  return (
    <Box sx={{ height: '100%', p: 2, overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={{ px: 0.5 }}>
        <Typography sx={{ fontSize: '0.9rem', fontWeight: 700, color: colors.text, mb: 0.35 }}>
          Rules Management
        </Typography>
        <Typography sx={{ fontSize: '0.74rem', color: colors.grey, maxWidth: 680 }}>
          Keep the full rules workspace, with the rule library centered and file/category tools still available around it.
        </Typography>
      </Box>

      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <PanelGroup direction="horizontal" style={{ height: '100%' }}>
          <Panel defaultSize={22} minSize={15}>
            <Box sx={{ height: '100%', overflow: 'auto', pr: 1 }}>
              <FileManagementPanel />
            </Box>
          </Panel>

          <PanelResizeHandle />

          <Panel defaultSize={50} minSize={30}>
            <Box sx={{ height: '100%', overflow: 'auto', px: 1 }}>
              <RulesBrowserPanel />
            </Box>
          </Panel>

          <PanelResizeHandle />

          <Panel defaultSize={28} minSize={16}>
            <Box sx={{ height: '100%', overflow: 'auto', pl: 1 }}>
              <CategoryPanel />
            </Box>
          </Panel>
        </PanelGroup>
      </Box>
    </Box>
  );
};
