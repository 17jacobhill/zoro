import { useEffect, useState, useMemo } from 'react';
import { Box, List, ListItem, ListItemButton, ListItemText, Typography, alpha, IconButton, InputAdornment, Chip, Autocomplete } from '@mui/material';
import { Description, Delete, Search, Clear, Add } from '@mui/icons-material';
import { TextField } from '../../design-system/TextField';
import { api } from '../../services/api';
import { Button } from '../../design-system/Button';
import { colors } from '../../design-system/colors';
import type { Tag } from '../../services/api';

interface Chat {
  chat_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

interface ChatListProps {
  onChatSelect: (chatId: string) => void;
  selectedChatId: string | null;
}

export function ChatList({ onChatSelect, selectedChatId }: ChatListProps) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<{ chatId: string; message: string } | null>(null);
  const [chatTags, setChatTags] = useState<Record<string, Tag[]>>({});
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [searchText, setSearchText] = useState('');
  const [activeTagFilter, setActiveTagFilter] = useState<Tag | null>(null);
  const [loadingTags, setLoadingTags] = useState<string | null>(null);

  const filteredChats = useMemo(() => {
    if (!searchText && !activeTagFilter) {
      return chats;
    }
    
    return chats.filter(chat => {
      const matchesSearch = !searchText || chat.title.toLowerCase().includes(searchText.toLowerCase());
      const matchesTag = !activeTagFilter || (chatTags[chat.chat_id] || []).includes(activeTagFilter);
      return matchesSearch && matchesTag;
    });
  }, [chats, searchText, activeTagFilter, chatTags]);

  const loadAllTags = async () => {
    console.log('🔍 loadAllTags called');
    const result = await api.getTags();
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

  const loadChatTags = async (chatId: string) => {
    setLoadingTags(chatId);
    const result = await api.getChatTags(chatId);
    setLoadingTags(null);
    
    if (result.success && result.tags) {
      setChatTags(prev => ({ ...prev, [chatId]: result.tags || [] }));
    }
  };

  const loadAllChatTags = async () => {
    for (const chat of chats) {
      const result = await api.getChatTags(chat.chat_id);
      if (result.success && result.tags) {
        setChatTags(prev => ({ ...prev, [chat.chat_id]: result.tags || [] }));
      }
    }
  };

  useEffect(() => {
    const loadChats = async () => {
      try {
        const response = await api.getAssistantChats();
        if (response.success) {
          setChats(response.chats);
        }
      } catch (error) {
        console.error('Failed to load chats:', error);
      } finally {
        setLoading(false);
      }
    };
    loadChats();
  }, []);

  useEffect(() => {
    loadAllTags();
    loadAllChatTags();
  }, [chats]);

  const handleAddTag = async (chatId: string, tag: Tag) => {
    if (!tag.trim()) return;
    
    const originalTags = chatTags[chatId] || [];
    const optimisticTags = [...originalTags, tag].sort();
    
    setChatTags(prev => ({ ...prev, [chatId]: optimisticTags }));
    
    const result = await api.assignTags(chatId, [tag]);
    
    if (result.success) {
      if (result.tags) {
        setChatTags(prev => ({ ...prev, [chatId]: result.tags || [] }));
      }
      await loadAllTags();
    } else {
      setChatTags(prev => ({ ...prev, [chatId]: originalTags }));
    }
  };

  const handleRemoveTag = async (chatId: string, tag: Tag) => {
    const originalTags = chatTags[chatId] || [];
    const optimisticTags = originalTags.filter(t => t !== tag);
    
    setChatTags(prev => ({ ...prev, [chatId]: optimisticTags }));
    
    const result = await api.removeTags(chatId, [tag]);
    
    if (result.success) {
      if (result.tags) {
        setChatTags(prev => ({ ...prev, [chatId]: result.tags || [] }));
      }
      await loadAllTags();
    } else {
      setChatTags(prev => ({ ...prev, [chatId]: originalTags }));
    }
  };

  const handleDelete = async (chatId: string) => {
    const backup = [...chats];
    
    setChats(chats.filter(c => c.chat_id !== chatId));
    setConfirmingDelete(null);
    setDeleteError(null);
    
    try {
      await api.deleteAssistantChat(chatId);
      if (selectedChatId === chatId) {
        onChatSelect('');
      }
    } catch (error) {
      setChats(backup);
      setDeleteError({
        chatId,
        message: error instanceof Error ? error.message : 'Failed to delete chat'
      });
    }
  };

  if (loading) return <Box sx={{ p: 2 }}>Loading...</Box>;
  if (chats.length === 0) return <Box sx={{ p: 2 }}>No plans yet</Box>;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Typography variant="h6" sx={{ p: 2 }}>Plans</Typography>
      <Box sx={{ px: 2, pb: 1 }}>
        <TextField
          size="small"
          fullWidth
          placeholder="Search plans..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search fontSize="small" />
              </InputAdornment>
            ),
            endAdornment: searchText && (
              <InputAdornment position="end">
                <IconButton size="small" onClick={() => setSearchText('')}>
                  <Clear fontSize="small" />
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
        {(searchText || activeTagFilter) && (
          <Button
            colorVariant="green"
            size="small"
            onClick={() => {
              setSearchText('');
              setActiveTagFilter(null);
            }}
            sx={{ mt: 1 }}
          >
            Clear Filters
          </Button>
        )}
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        <List dense>
          {filteredChats.map(chat => (
          <Box key={chat.chat_id}>
            <ListItem disablePadding sx={{ display: 'flex', alignItems: 'center' }}>
              <ListItemButton
                selected={chat.chat_id === selectedChatId}
                onClick={() => onChatSelect(chat.chat_id)}
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
                <Description sx={{ mr: 1, fontSize: 18 }} />
                <ListItemText 
                  primary={
                    <Typography 
                      variant="body2"
                      sx={{ 
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {chat.title}
                    </Typography>
                  }
                  secondary={new Date(chat.created_at).toLocaleDateString()}
                />
              </ListItemButton>
              
              {confirmingDelete === chat.chat_id ? (
                <Box sx={{ display: 'flex', gap: 0.5, px: 1 }}>
                  <Button
                    colorVariant="red"
                    size="small"
                    onClick={() => handleDelete(chat.chat_id)}
                  >
                    Confirm
                  </Button>
                  <Button
                    colorVariant="green"
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
                    setConfirmingDelete(chat.chat_id);
                    setDeleteError(null);
                  }}
                  sx={{ mr: 1 }}
                >
                  <Delete fontSize="small" />
                </IconButton>
              )}
            </ListItem>
            
            {deleteError?.chatId === chat.chat_id && (
              <Box sx={{ px: 2, pb: 1 }}>
                <Typography variant="caption" sx={{ color: '#9a4e4e' }}>
                  {deleteError.message}
                </Typography>
              </Box>
            )}
            
            {/* Tag chips */}
            {(chatTags[chat.chat_id] || []).length > 0 && (
              <Box sx={{ px: 2, pb: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {(chatTags[chat.chat_id] || []).map(tag => (
                  <Chip
                    key={tag}
                    label={tag}
                    size="small"
                    onClick={() => setActiveTagFilter(tag)}
                    onDelete={selectedChatId === chat.chat_id ? () => handleRemoveTag(chat.chat_id, tag) : undefined}
                    sx={{
                      bgcolor: activeTagFilter === tag ? colors.gold : alpha(colors.gold, 0.2),
                      color: activeTagFilter === tag ? '#fff' : colors.gold,
                      fontWeight: activeTagFilter === tag ? 600 : 400,
                      '&:hover': {
                        bgcolor: activeTagFilter === tag ? colors.gold : alpha(colors.gold, 0.3),
                      },
                    }}
                  />
                ))}
              </Box>
            )}
            
            {/* Autocomplete for adding tags when chat is selected */}
            {selectedChatId === chat.chat_id && (
              <Box sx={{ px: 2, pb: 1 }}>
                <Autocomplete
                  size="small"
                  options={allTags}
                  value={null}
                  onChange={(_, newValue) => {
                    if (newValue) {
                      handleAddTag(chat.chat_id, newValue);
                    }
                  }}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      placeholder="Add tag..."
                      InputProps={{
                        ...params.InputProps,
                        startAdornment: (
                          <>
                            <InputAdornment position="start">
                              <Add fontSize="small" />
                            </InputAdornment>
                            {params.InputProps.startAdornment}
                          </>
                        ),
                      }}
                    />
                  )}
                  sx={{ '& .MuiAutocomplete-input': { fontSize: '0.875rem' } }}
                />
              </Box>
            )}
          </Box>
          ))}
        </List>
      </Box>
    </Box>
  );
}
