import { Box } from '@mui/material';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { FileManagementPanel } from './FileManagementPanel';
import { RulesBrowserPanel } from './RulesBrowserPanel';
import { CategoryPanel } from './CategoryPanel';

export const KnowledgeBaseTab: React.FC = () => {
  return (
    <Box sx={{ height: '100%', p: 2, overflow: 'hidden' }}>
      <PanelGroup direction="horizontal" style={{ height: '100%' }}>
        <Panel defaultSize={24} minSize={16}>
          <Box sx={{ height: '100%', overflow: 'auto', pr: 1 }}>
            <FileManagementPanel />
          </Box>
        </Panel>

        <PanelResizeHandle style={{ width: '1px', backgroundColor: '#d0d0d0', cursor: 'col-resize' }} />

        <Panel defaultSize={46} minSize={28}>
          <Box sx={{ height: '100%', overflow: 'auto', px: 1 }}>
            <RulesBrowserPanel />
          </Box>
        </Panel>

        <PanelResizeHandle style={{ width: '1px', backgroundColor: '#d0d0d0', cursor: 'col-resize' }} />

        <Panel defaultSize={30} minSize={18}>
          <Box sx={{ height: '100%', overflow: 'auto', pl: 1 }}>
            <CategoryPanel />
          </Box>
        </Panel>
      </PanelGroup>
    </Box>
  );
};
