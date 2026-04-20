import { useState, useEffect, useMemo } from 'react';
import { Box, List, ListItem, ListItemButton, Typography, Divider, alpha, IconButton, Chip, Autocomplete } from '@mui/material';
import { Add, Chat, Delete } from '@mui/icons-material';
import { Button } from '../../design-system/Button';
import { TextField } from '../../design-system/TextField';
import { colors } from '../../design-system/colors';
import { api } from '../../services/api';
import type { Tag } from '../../services/api';

interface ChatLibraryProps {
  chats: string[];
  selectedChat: string | null;
  onChatSelect: (chat: string) => void;
  onNewChat: () => void;
  onChatsUpdate: (chats: string[]) => void;
}

export function ChatLibrary({ chats, selectedChat, onChatSelect, onNewChat, onChatsUpdate }: ChatLibraryProps) {
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<{ chatId: string; message: string } | null>(null);
  const [chatTags, setChatTags] = useState<Record<string, Tag[]>>({});
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [loadingTags, setLoadingTags] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');
  const [activeTagFilter, setActiveTagFilter] = useState<Tag | null>(null);
  
  const filteredChats = useMemo(() => {
    if (!searchText && !activeTagFilter) {
      return chats;
    }
    
    return chats.filter(chat => {
      const matchesSearch = !searchText || chat.toLowerCase().includes(searchText.toLowerCase());
      const matchesTag = !activeTagFilter || (chatTags[chat] || []).includes(activeTagFilter);
      return matchesSearch && matchesTag;
    });
  }, [chats, searchText, activeTagFilter, chatTags]);
  
  useEffect(() => {
    loadAllTags();
    loadAllChatTags();
  }, []);
  
  const loadAllChatTags = async () => {
    for (const chat of chats) {
      const result = await api.getLearnerChatTags(chat);
      if (result.success && result.tags) {
        setChatTags(prev => ({ ...prev, [chat]: result.tags || [] }));
      }
    }
  };
  
  const loadAllTags = async () => {
    console.log('🔍 loadAllTags called');
    const result = await api.getLearnerTags();
    console.log('📦 getTags result:', result);
    
    if (result.success && result.tags) {
      const tagNames = Array.isArray(result.tags) 
        ? result.tags 
        : Object.keys(result.tags);
      console.log('✅ Setting allTags to:', tagNames);
      setAllTags(tagNames);
    } else {
      console.error('❌ getTags failed:', result.error || 'Unknown error');
    }
  };
  
  const loadChatTags = async (chatName: string) => {
    setLoadingTags(chatName);
    const result = await api.getLearnerChatTags(chatName);
    setLoadingTags(null);
    
    if (result.success && result.tags) {
      setChatTags(prev => ({ ...prev, [chatName]: result.tags || [] }));
    }
  };
  
  useEffect(() => {
    loadAllChatTags();
  }, [chats]);
  
  const handleRemoveTag = async (chatName: string, tag: Tag) => {
    const originalTags = chatTags[chatName] || [];
    const optimisticTags = originalTags.filter(t => t !== tag);
    
    setChatTags(prev => ({ ...prev, [chatName]: optimisticTags }));
    
    const result = await api.removeLearnerTags(chatName, [tag]);
    
    if (result.success) {
      if (result.tags) {
        setChatTags(prev => ({ ...prev, [chatName]: result.tags || [] }));
      }
      await loadAllTags();
    } else {
      setChatTags(prev => ({ ...prev, [chatName]: originalTags }));
    }
  };
  
  const handleAddTag = async (chatName: string, tag: Tag) => {
    if (!tag.trim()) return;
    
    const originalTags = chatTags[chatName] || [];
    const optimisticTags = [...originalTags, tag].sort();
    
    setChatTags(prev => ({ ...prev, [chatName]: optimisticTags }));
    
    const result = await api.assignLearnerTags(chatName, [tag]);
    
    if (result.success) {
      if (result.tags) {
        setChatTags(prev => ({ ...prev, [chatName]: result.tags || [] }));
      }
      await loadAllTags();
    } else {
      setChatTags(prev => ({ ...prev, [chatName]: originalTags }));
    }
  };
  
  const handleDelete = async (chatId: string) => {
    const backup = [...chats];
    
    onChatsUpdate(chats.filter(c => c !== chatId));
    setConfirmingDelete(null);
    setDeleteError(null);
    
    try {
      await api.deleteLearnerChat(chatId);
      if (selectedChat === chatId) {
        onChatSelect('');
      }
    } catch (error) {
      onChatsUpdate(backup);
      setDeleteError({
        chatId,
        message: error instanceof Error ? error.message : 'Failed to delete chat'
      });
    }
  };
  
  return (
    <Box sx={{ 
      width: '100%',
      height: '100%',
      bgcolor: 'background.paper', 
      borderRight: 1, 
      borderColor: 'divider',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <Box sx={{ p: 2 }}>
        <Button
          fullWidth
          startIcon={<Add />}
          onClick={onNewChat}
          size="small"
          colorVariant="green"
        >
          New Chat
        </Button>
        
        <TextField
          fullWidth
          size="small"
          placeholder="Search chats..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          sx={{ 
            mt: 1.5,
            '& .MuiOutlinedInput-root': {
              fontSize: '0.875rem',
            },
          }}
          aria-label="Search chats"
        />
        
        {(searchText || activeTagFilter) && (
          <Button
            fullWidth
            size="small"
            onClick={() => {
              setSearchText('');
              setActiveTagFilter(null);
            }}
            colorVariant="blue"
            sx={{ mt: 1 }}
          >
            Clear Filters
          </Button>
        )}
      </Box>

      <Divider />

      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {chats.length === 0 ? (
          <Box sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              No chats yet
            </Typography>
          </Box>
        ) : (
          <List dense>
            {filteredChats.map((chat) => (
              <Box key={chat}>
                <ListItem disablePadding sx={{ display: 'flex', alignItems: 'center' }}>
                  <ListItemButton
                    selected={chat === selectedChat}
                    onClick={() => onChatSelect(chat)}
                    sx={{
                      flex: 1,
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
                    <Chat sx={{ mr: 1, fontSize: 18 }} />
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {chat}
                    </Typography>
                  </ListItemButton>
                  
                  {confirmingDelete === chat ? (
                    <Box sx={{ display: 'flex', gap: 0.5, px: 1 }}>
                      <Button
                        colorVariant="red"
                        size="small"
                        onClick={() => handleDelete(chat)}
                      >
                        Confirm
                      </Button>
                      <Button
                        colorVariant="blue"
                        size="small"
                        onClick={() => {
                          setConfirmingDelete(null);
                          setDeleteError(null);
                        }}
                      >
                        Cancel
                      </Button>
                    </Box>
                  ) : (
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmingDelete(chat);
                        setDeleteError(null);
                      }}
                      sx={{ mr: 1 }}
                    >
                      <Delete fontSize="small" />
                    </IconButton>
                  )}
                </ListItem>
                
                {deleteError?.chatId === chat && (
                  <Box sx={{ px: 2, pb: 1 }}>
                    <Typography variant="caption" sx={{ color: '#9a4e4e' }}>
                      {deleteError.message}
                    </Typography>
                  </Box>
                )}
                
                <Box sx={{ px: 2, pb: 1, pt: 0.5 }}>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.5 }}>
                    {(chatTags[chat] || []).map((tag) => (
                      <Chip
                        key={tag}
                        label={tag}
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveTagFilter(activeTagFilter === tag ? null : tag);
                        }}
                        onDelete={chat === selectedChat ? () => handleRemoveTag(chat, tag) : undefined}
                        sx={{
                          bgcolor: activeTagFilter === tag ? colors.gold : alpha(colors.gold, 0.7),
                          color: 'white',
                          cursor: 'pointer',
                          fontWeight: activeTagFilter === tag ? 'bold' : 'normal',
                          fontSize: '0.7rem',
                          height: '20px',
                          '& .MuiChip-label': {
                            px: 1,
                            py: 0,
                          },
                          '& .MuiChip-deleteIcon': {
                            color: 'rgba(255,255,255,0.7)',
                            fontSize: '14px',
                            '&:hover': {
                              color: 'white',
                            },
                          },
                          '&:hover': {
                            bgcolor: colors.gold,
                          },
                        }}
                      />
                    ))}
                  </Box>
                  
                  {chat === selectedChat && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                      <Add sx={{ fontSize: 16, color: colors.green }} />
                      <Autocomplete
                        freeSolo
                        options={allTags.filter(t => !chatTags[chat]?.includes(t))}
                        value={null}
                        onChange={(_, value) => {
                          if (value && typeof value === 'string') {
                            handleAddTag(chat, value);
                          }
                        }}
                        disabled={loadingTags === chat}
                        renderInput={(params) => (
                          <TextField
                            {...params}
                            placeholder="Add tag..."
                            size="small"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                const input = e.target as HTMLInputElement;
                                const newTag = input.value.trim();
                                if (newTag) {
                                  handleAddTag(chat, newTag);
                                  input.value = '';
                                  e.preventDefault();
                                }
                              }
                            }}
                            sx={{
                              '& .MuiOutlinedInput-root': {
                                fontSize: '0.75rem',
                                minHeight: '28px',
                              },
                              '& .MuiInputBase-input': {
                                padding: '4px 8px',
                              },
                            }}
                          />
                        )}
                        sx={{ flex: 1 }}
                      />
                    </Box>
                  )}
                </Box>
              </Box>
            ))}
          </List>
        )}
      </Box>
    </Box>
  );
}
