import { useState, useEffect } from 'react';
import { Box, Typography, IconButton, List, ListItem, ListItemText, ListItemButton, alpha } from '@mui/material';
import { Add, Chat, Delete } from '@mui/icons-material';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { ChatVisualizationView } from '../ChatVisualizationView';
import { api, type ChatVisualization } from '../../services/api';
import { colors } from '../../design-system/colors';

export function VisualizationTab() {
  const [visualizations, setVisualizations] = useState<ChatVisualization[]>([]);
  const [selectedVis, setSelectedVis] = useState<string | null>(null);

  useEffect(() => {
    const fetchVisualizations = async () => {
      const response = await api.getChatVisualizations();
      setVisualizations(response);
    };
    fetchVisualizations();
  }, []);

  const handleNewVisualization = async () => {
    const response = await api.createChatVisualization();
    setVisualizations([...visualizations, response]);
    setSelectedVis(response.chat_id);
  };

  const handleDeleteVisualization = async (chatId: string) => {
    await api.deleteChatVisualization(chatId);
    setVisualizations(visualizations.filter((vis) => vis.chat_id !== chatId));
    if (selectedVis === chatId) {
      setSelectedVis(null);
    }
  };

  const handleUpdateVisualizationName = (chatId: string, name: string) => {
    setVisualizations(visualizations.map((vis) => 
      vis.chat_id === chatId ? { ...vis, name } : vis
    ));
  };

  return (
    <Box sx={{ flex: 1, overflow: 'hidden' }}>
      <PanelGroup direction="horizontal">
        <Panel defaultSize={15} minSize={10}>
          <Box sx={{ p: 2, height: '100%', overflow: 'auto' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography sx={{ fontSize: '0.92rem', fontWeight: 600, lineHeight: 1.2 }}>
                Sessions
              </Typography>
              <IconButton onClick={handleNewVisualization} sx={{ color: colors.green, '&:focus': { outline: 'none' } }} disableRipple>
                <Add sx={{ fontSize: 18 }} />
              </IconButton>
            </Box>
            <List dense>
              {visualizations.map((vis) => (
                <ListItem
                  key={vis.chat_id}
                  disablePadding
                  secondaryAction={
                    <IconButton edge="end" aria-label="delete" onClick={() => handleDeleteVisualization(vis.chat_id)} disableRipple sx={{ '&:focus': { outline: 'none' } }}>
                      <Delete sx={{ fontSize: 17 }} />
                    </IconButton>
                  }
                >
                  <ListItemButton
                    selected={vis.chat_id === selectedVis}
                    onClick={() => setSelectedVis(vis.chat_id)}
                    sx={{
                      '&.Mui-selected': {
                        bgcolor: alpha(colors.green, 0.08),
                        borderLeft: '3px solid',
                        borderColor: colors.green,
                        '&:hover': {
                          bgcolor: alpha(colors.green, 0.12),
                        },
                      },
                    }}
                  >
                    <Chat sx={{ mr: 0.9, fontSize: 16 }} />
                    <Typography 
                      sx={{ 
                        fontSize: '0.8rem',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {vis.name || vis.chat_id}
                    </Typography>
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          </Box>
        </Panel>
        <PanelResizeHandle style={{ width: '1px', backgroundColor: '#d0d0d0', cursor: 'col-resize' }} />
        <Panel>
          <Box sx={{ p: 2, height: '100%', overflow: 'auto' }}>
            {selectedVis ? (
              <ChatVisualizationView chatId={selectedVis} onUpdateName={handleUpdateVisualizationName} />
            ) : (
              <Typography>Select a chat or create a new one</Typography>
            )}
          </Box>
        </Panel>
      </PanelGroup>
    </Box>
  );
}
