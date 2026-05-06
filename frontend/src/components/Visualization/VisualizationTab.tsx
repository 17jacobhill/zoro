import { useState, useEffect } from 'react';
import { Box, Typography, List, ListItem, ListItemButton, alpha } from '@mui/material';
import { Add, Chat, Delete } from '@mui/icons-material';
import { Panel, PanelGroup } from 'react-resizable-panels';
import { ChatVisualizationView } from '../ChatVisualizationView';
import { IconActionButton } from '../../design-system/IconActionButton';
import { PanelHeader } from '../../design-system/PanelHeader';
import { PanelResizeHandle } from '../../design-system/PanelResizeHandle';
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
    <Box sx={{ flex: 1, minHeight: 0, height: '100%', overflow: 'hidden' }}>
      <PanelGroup direction="horizontal" style={{ height: '100%' }}>
        <Panel defaultSize={15} minSize={10}>
          <Box sx={{ p: 2, height: '100%', minHeight: 0, overflow: 'auto' }}>
            <PanelHeader
              title="Sessions"
              actions={
                <IconActionButton tone="green" aria-label="Create visualization" onClick={handleNewVisualization}>
                  <Add sx={{ fontSize: 18 }} />
                </IconActionButton>
              }
            />
            <List dense>
              {visualizations.map((vis) => (
                <ListItem
                  key={vis.chat_id}
                  disablePadding
                  secondaryAction={
                    <IconActionButton edge="end" tone="grey" aria-label="Delete visualization" onClick={() => handleDeleteVisualization(vis.chat_id)}>
                      <Delete sx={{ fontSize: 17 }} />
                    </IconActionButton>
                  }
                >
                  <ListItemButton
                    selected={vis.chat_id === selectedVis}
                    onClick={() => setSelectedVis(vis.chat_id)}
                    sx={{
                      borderLeft: '3px solid transparent',
                      borderRadius: 1,
                      '&:hover': {
                        bgcolor: alpha(colors.green, 0.04),
                      },
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
        <PanelResizeHandle />
        <Panel>
          <Box sx={{ p: 2, height: '100%', minHeight: 0, overflow: 'auto' }}>
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
