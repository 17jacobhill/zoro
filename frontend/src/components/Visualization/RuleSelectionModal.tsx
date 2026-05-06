import React, { useState, useEffect, useMemo } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Tabs,
  Tab,
  Box,
  IconButton,
  Typography,
  Chip,
  CircularProgress
} from '@mui/material';
import { Close as CloseIcon, Search as SearchIcon, Star as StarIcon, StarBorder as StarBorderIcon } from '@mui/icons-material';
import { colors } from '../../design-system/colors';
import { InputAdornment } from '../../design-system/InputAdornment';
import { TextField } from '../../design-system/TextField';
import { api } from '../../services/api';

interface Rule {
  item_id: string;
  category: string;
  title?: string;
  content?: string;
  context?: string;
  evidence?: string;
  confidence?: number;
  decay?: number;
  is_favorite?: boolean;
  is_strict?: boolean;
  is_testable?: boolean;
}

interface RuleSelectionModalProps {
  open: boolean;
  onClose: () => void;
  onSelectRule: (rule: Rule) => void;
}

const RuleSelectionModal: React.FC<RuleSelectionModalProps> = ({
  open,
  onClose,
  onSelectRule
}) => {
  const [activeTab, setActiveTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      loadRules();
    }
  }, [open]);

  const loadRules = async () => {
    setLoading(true);
    try {
      const response = await api.fetchKBItems();
      if (response.success && response.items) {
        setRules(response.items);
      }
    } catch (error) {
      console.error('Failed to load rules:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleFavorite = async (itemId: string, currentlyFavorited: boolean) => {
    try {
      await api.toggleFavorite(itemId, !currentlyFavorited);
      setRules(prevRules => 
        prevRules.map(r => 
          r.item_id === itemId 
            ? { ...r, is_favorite: !currentlyFavorited }
            : r
        )
      );
    } catch (error) {
      console.error('Failed to toggle favorite:', error);
    }
  };

  const filteredRules = useMemo(() => {
    let filtered = rules;

    if (activeTab === 1) {
      filtered = rules.filter(rule => rule.is_favorite);
    } else if (activeTab === 2) {
      filtered = rules.filter(rule => rule.is_strict);
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(rule => {
        const category = rule.category?.toLowerCase() || '';
        const title = rule.title?.toLowerCase() || '';
        const content = rule.content?.toLowerCase() || '';
        const context = rule.context?.toLowerCase() || '';
        const evidence = rule.evidence?.toLowerCase() || '';
        return category.includes(query) || title.includes(query) || content.includes(query) || context.includes(query) || evidence.includes(query);
      });
    }

    return filtered;
  }, [rules, activeTab, searchQuery]);

  const handleSelectRule = (rule: Rule) => {
    onSelectRule(rule);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: 'white',
          maxHeight: '80vh'
        }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        borderBottom: '1px solid rgba(0, 0, 0, 0.08)'
      }}>
        <Typography variant="h6" sx={{ color: colors.darkGreen }}>
          Select Rule
        </Typography>
        <IconButton 
          onClick={onClose} 
          size="small"
          disableRipple
          sx={{ 
            color: colors.grey,
            '&:hover': { bgcolor: 'rgba(0,0,0,0.05)' },
            '&:focus': { outline: 'none' }
          }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Box sx={{ borderBottom: 1, borderColor: 'rgba(0, 0, 0, 0.08)', px: 1 }}>
        <Tabs 
          value={activeTab} 
          onChange={(_, newValue) => setActiveTab(newValue)}
          sx={{
            '& .MuiTab-root': {
              color: colors.grey,
              '&.Mui-selected': {
                color: colors.green
              }
            },
            '& .MuiTabs-indicator': {
              backgroundColor: colors.green
            }
          }}
        >
          <Tab label="All Rules" />
          <Tab label="Favorites" />
          <Tab label="Strict" />
        </Tabs>
      </Box>

      <DialogContent sx={{ p: 2 }}>
        {activeTab === 1 && (
          <Box sx={{ 
            mb: 1.5,
            py: 1,
            px: 1.25,
            bgcolor: colors.surfaceGreenTint,
            borderRadius: 1,
            borderLeft: `3px solid ${colors.green}`
          }}>
            <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.25 }}>
              ⭐ Favorited Rules Are Always Included
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.3 }}>
              Favorited rules are always included during plan retrieval. Strict enforcement is controlled by each rule's strict setting.
            </Typography>
          </Box>
        )}
        
        <TextField
          fullWidth
          size="small"
          placeholder="Search category, title, content..."
          value={searchQuery}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ fontSize: 18, color: colors.grey }} />
              </InputAdornment>
            )
          }}
          sx={{
            mb: 1.5,
            '& .MuiInputBase-root': { borderRadius: 1.25 }
          }}
        />

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress sx={{ color: colors.green }} />
          </Box>
        ) : filteredRules.length === 0 ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">
              {searchQuery ? 'No rules match your search' : activeTab === 1 ? 'No favorite rules' : activeTab === 2 ? 'No strict rules' : 'No rules available'}
            </Typography>
          </Box>
        ) : (
          <Box
            sx={{
              border: `1px solid ${colors.divider}`,
              borderRadius: 2,
              overflow: 'hidden',
              bgcolor: colors.surface
            }}
          >
            {filteredRules.map((rule, index) => (
              <Box
                key={rule.item_id}
                sx={{
                  cursor: 'pointer',
                  px: 1.5,
                  py: 1.25,
                  borderBottom: index < filteredRules.length - 1 ? `1px solid ${colors.divider}` : 'none',
                  '&:hover': {
                    bgcolor: colors.surfaceTint
                  },
                  transition: 'background-color 0.15s ease'
                }}
                onClick={() => handleSelectRule(rule)}
              >
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.75, flexWrap: 'wrap' }}>
                      <Chip
                        label={rule.category || 'uncategorized'}
                        size="small"
                        sx={{
                          bgcolor: colors.surfaceGreenSoft,
                          color: colors.darkGreen,
                          fontWeight: 600,
                          fontSize: '0.7rem',
                          height: 22
                        }}
                      />
                      {rule.is_favorite && (
                        <Chip
                          label="Favorite"
                        size="small"
                        sx={{
                          bgcolor: colors.surfaceWarningAlt,
                          color: colors.warningTextStrong,
                            fontWeight: 600,
                            fontSize: '0.7rem',
                            height: 22
                          }}
                        />
                      )}
                      {rule.is_strict && (
                        <Chip
                          label="Strict"
                        size="small"
                        sx={{
                          bgcolor: colors.surfaceDanger,
                          color: colors.dangerText,
                            fontWeight: 600,
                            fontSize: '0.7rem',
                            height: 22
                          }}
                        />
                      )}
                      {rule.is_testable && (
                        <Chip
                          label="Testable"
                        size="small"
                        sx={{
                          bgcolor: colors.surfaceInfoAlt,
                          color: colors.infoText,
                            fontWeight: 600,
                            fontSize: '0.7rem',
                            height: 22
                          }}
                        />
                      )}
                      {rule.confidence !== undefined && (
                        <Typography variant="caption" sx={{ color: colors.grey }}>
                          {(rule.confidence * 100).toFixed(0)}% confidence
                        </Typography>
                      )}
                      {rule.decay !== undefined && (
                        <Typography variant="caption" sx={{ color: colors.grey }}>
                          {(rule.decay * 100).toFixed(0)}% decay
                        </Typography>
                      )}
                    </Box>

                    <Typography
                      variant="body1"
                      sx={{
                        fontWeight: 600,
                        color: colors.darkGreen,
                        mb: 0.25,
                        lineHeight: 1.35
                      }}
                    >
                      {rule.title || rule.content?.split('\n')[0] || 'Untitled'}
                    </Typography>

                    {rule.content && rule.content !== rule.title && (
                      <Typography
                        variant="body2"
                        sx={{
                          color: 'text.secondary',
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                          lineHeight: 1.4
                        }}
                      >
                        {rule.content}
                      </Typography>
                    )}
                  </Box>

                  <IconButton
                    size="small"
                    disableRipple
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleFavorite(rule.item_id, rule.is_favorite || false);
                    }}
                    sx={{
                      color: rule.is_favorite ? colors.gold : colors.grey,
                      '&:hover': { bgcolor: 'rgba(0,0,0,0.05)' },
                      '&:focus': { outline: 'none' }
                    }}
                  >
                    {rule.is_favorite ? <StarIcon /> : <StarBorderIcon />}
                  </IconButton>
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default RuleSelectionModal;
