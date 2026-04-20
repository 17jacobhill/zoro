import { useState, useEffect, useCallback } from 'react';
import { Box, Paper, Typography, IconButton, Divider, CircularProgress } from '@mui/material';
import { Close, Delete, Add, Favorite, FavoriteBorder, Search } from '@mui/icons-material';
import { Button } from '../../design-system/Button';
import { TextField } from '../../design-system/TextField';
import { api } from '../../services/api';

interface FavoritesPanelProps {
  open: boolean;
  onClose: () => void;
  refreshKey?: number;
  onFavoritesChange?: () => void;
}

export function FavoritesPanel({ open, onClose, refreshKey, onFavoritesChange }: FavoritesPanelProps) {
  const [favorites, setFavorites] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newRule, setNewRule] = useState({
    rule: '',
    reasoning: '',
    confidence: 5,
    decay: 5,
  });

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set());
  
  // Filter favorites state (local filtering)
  const [filterQuery, setFilterQuery] = useState('');

  const fetchFavorites = async () => {
    setLoading(true);
    try {
      const response = await api.getFavorites();
      if (response.success) {
        setFavorites(response.favorites);
        setFavoriteIds(new Set(response.favorites.map((f: any) => f.rule_id)));
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load favorites');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchFavorites();
    }
  }, [open]);

  useEffect(() => {
    if (refreshKey !== undefined && refreshKey > 0) {
      fetchFavorites();
    }
  }, [refreshKey]);

  // Debounced search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const response = await api.searchRules(searchQuery);
        if (response.success) {
          setSearchResults(response.results || []);
        }
      } catch (err: any) {
        setError(err.message || 'Search failed');
      } finally {
        setSearchLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleRemoveFavorite = async (ruleId: string) => {
    try {
      await api.toggleFavorite(ruleId, false);
      setFavorites(prev => prev.filter(f => f.rule_id !== ruleId));
      setFavoriteIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(ruleId);
        return newSet;
      });
      onFavoritesChange?.();
    } catch (err: any) {
      setError(err.message || 'Failed to remove favorite');
    }
  };

  const handleToggleFavoriteFromSearch = async (ruleId: string, isFavorite: boolean) => {
    try {
      await api.toggleFavorite(ruleId, isFavorite);
      
      if (isFavorite) {
        // Add to favorites
        const rule = searchResults.find(r => r.rule_id === ruleId);
        if (rule) {
          setFavorites(prev => [...prev, rule]);
          setFavoriteIds(prev => new Set([...prev, ruleId]));
        }
      } else {
        // Remove from favorites
        setFavorites(prev => prev.filter(f => f.rule_id !== ruleId));
        setFavoriteIds(prev => {
          const newSet = new Set(prev);
          newSet.delete(ruleId);
          return newSet;
        });
      }
      
      onFavoritesChange?.();
    } catch (err: any) {
      setError(err.message || 'Failed to toggle favorite');
    }
  };

  const handleAddManualRule = async () => {
    if (!newRule.rule.trim() || !newRule.reasoning.trim()) {
      setError('Rule and reasoning are required');
      return;
    }

    try {
      const response = await api.addManualFavorite(newRule);
      if (response.success) {
        setFavorites(prev => [...prev, response.rule]);
        setFavoriteIds(prev => new Set([...prev, response.rule.rule_id]));
        setNewRule({ rule: '', reasoning: '', confidence: 5, decay: 5 });
        setShowAddForm(false);
        setError(null);
        onFavoritesChange?.();
      }
    } catch (err: any) {
      setError(err.message || 'Failed to add manual rule');
    }
  };

  if (!open) return null;

  return (
    <Paper
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderLeft: '1px solid',
        borderColor: 'divider',
        borderRadius: 0,
        overflow: 'hidden',
      }}
    >
      <Box
        sx={{
          p: 1.5,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.default',
          flexShrink: 0,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Favorite sx={{ fontSize: '1.2rem', color: '#9a4e4e' }} />
          <Typography variant="subtitle2" fontWeight={600}>
            Favorites
          </Typography>
        </Box>
        <IconButton size="small" onClick={onClose}>
          <Close />
        </IconButton>
      </Box>

      <Box
        sx={{
          p: 2,
          overflow: 'auto',
          flex: 1,
        }}
      >
        {/* Search Bar */}
        <TextField
          fullWidth
          size="small"
          placeholder="Search all rules..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: <Search sx={{ mr: 0.5, color: 'text.secondary', fontSize: '0.9rem' }} />,
            sx: {
              fontSize: '0.75rem',
              py: 0.5,
              fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
            }
          }}
          sx={{ 
            mb: 2,
            '& .MuiOutlinedInput-root': {
              '&.Mui-focused fieldset': {
                borderColor: '#87ae73',
              },
            },
            '& .MuiInputBase-input::placeholder': {
              fontSize: '0.75rem',
            },
          }}
        />

        {/* Search Results */}
        {searchQuery && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 1 }}>
              Search Results
            </Typography>
            {searchLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                <CircularProgress size={20} />
              </Box>
            ) : searchResults.length === 0 ? (
              <Typography variant="caption" color="text.secondary">
                No results found for "{searchQuery}"
              </Typography>
            ) : (
              <>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                  {searchResults.length} {searchResults.length === 1 ? 'result' : 'results'}
                </Typography>
                {searchResults.map((rule) => {
                  const isFavorited = favoriteIds.has(rule.rule_id);
                  return (
                    <Box
                      key={rule.rule_id}
                      sx={{
                        mb: 1,
                        p: 1.5,
                        border: '1px solid',
                        borderColor: isFavorited ? '#87ae73' : 'divider',
                        borderRadius: 1,
                        bgcolor: 'background.paper',
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 0.5 }}>
                        <Typography variant="caption" fontWeight={600} sx={{ flex: 1 }}>
                          {rule.rule}
                        </Typography>
                        <IconButton
                          size="small"
                          onClick={() => handleToggleFavoriteFromSearch(rule.rule_id, !isFavorited)}
                          sx={{ ml: 0.5 }}
                        >
                          {isFavorited ? (
                            <Favorite fontSize="small" sx={{ color: '#9a4e4e' }} />
                          ) : (
                            <FavoriteBorder fontSize="small" />
                          )}
                        </IconButton>
                      </Box>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.7rem', mb: 0.5 }}>
                        {rule.reasoning}
                      </Typography>
                      <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>
                        From: {rule.task_type}
                      </Typography>
                    </Box>
                  );
                })}
              </>
            )}
            <Divider sx={{ my: 2 }} />
          </Box>
        )}

        {error && (
          <Typography variant="caption" color="error" sx={{ display: 'block', mb: 2 }}>
            {error}
          </Typography>
        )}

        {/* Favorites List */}
        <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 1 }}>
          My Favorites
        </Typography>
        
        {/* Filter Favorites Search */}
        {favorites.length > 0 && (
          <TextField
            fullWidth
            size="small"
            placeholder="Filter favorites..."
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            InputProps={{
              startAdornment: <Search sx={{ mr: 0.5, color: 'text.secondary', fontSize: '0.9rem' }} />,
              sx: {
                fontSize: '0.75rem',
                py: 0.5,
                fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
              }
            }}
            sx={{ 
              mb: 1.5,
              '& .MuiOutlinedInput-root': {
                '&.Mui-focused fieldset': {
                  borderColor: '#87ae73',
                },
              },
              '& .MuiInputBase-input::placeholder': {
                fontSize: '0.75rem',
              },
            }}
          />
        )}
        
        {loading ? (
          <Typography variant="body2" color="text.secondary">
            Loading favorites...
          </Typography>
        ) : favorites.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Favorite sx={{ fontSize: '3rem', color: 'text.disabled', mb: 1 }} />
            <Typography variant="body2" color="text.secondary">
              No favorites yet
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              Star rules to add them here
            </Typography>
          </Box>
        ) : (
          <>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              {favorites.filter(f => {
                if (!filterQuery.trim()) return true;
                const query = filterQuery.toLowerCase();
                return f.rule.toLowerCase().includes(query) || 
                       f.reasoning.toLowerCase().includes(query);
              }).length} favorite {favorites.filter(f => {
                if (!filterQuery.trim()) return true;
                const query = filterQuery.toLowerCase();
                return f.rule.toLowerCase().includes(query) || 
                       f.reasoning.toLowerCase().includes(query);
              }).length === 1 ? 'rule' : 'rules'}
              {filterQuery && ` matching "${filterQuery}"`}
            </Typography>
            {favorites
              .filter(f => {
                if (!filterQuery.trim()) return true;
                const query = filterQuery.toLowerCase();
                return f.rule.toLowerCase().includes(query) || 
                       f.reasoning.toLowerCase().includes(query);
              })
              .map((rule, idx) => (
              <Box
                key={rule.rule_id}
                sx={{
                  mb: 1,
                  p: 1.5,
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  bgcolor: 'background.paper',
                }}
              >
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                  <Typography variant="caption" fontWeight={600} sx={{ flex: 1 }}>
                    {rule.rule}
                  </Typography>
                  <IconButton
                    size="small"
                    onClick={() => handleRemoveFavorite(rule.rule_id)}
                    sx={{ ml: 0.5 }}
                  >
                    <Delete fontSize="small" />
                  </IconButton>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.7rem' }}>
                  {rule.reasoning}
                </Typography>
              </Box>
            ))}
          </>
        )}

        <Divider sx={{ my: 2 }} />

        {!showAddForm ? (
          <Button
            size="small"
            colorVariant="green"
            onClick={() => setShowAddForm(true)}
            fullWidth
          >
            <Add fontSize="small" sx={{ mr: 0.5 }} />
            Add Manual Rule
          </Button>
        ) : (
          <Box>
            <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 1 }}>
              Add Manual Rule
            </Typography>
            <TextField
              fullWidth
              multiline
              rows={2}
              label="Rule"
              value={newRule.rule}
              onChange={(e) => setNewRule({ ...newRule, rule: e.target.value })}
              sx={{ mb: 1 }}
              size="small"
            />
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Reasoning"
              value={newRule.reasoning}
              onChange={(e) => setNewRule({ ...newRule, reasoning: e.target.value })}
              sx={{ mb: 1 }}
              size="small"
            />
            <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
              <TextField
                label="Confidence"
                type="number"
                value={newRule.confidence}
                onChange={(e) => setNewRule({ ...newRule, confidence: parseInt(e.target.value) || 5 })}
                sx={{ flex: 1 }}
                size="small"
                inputProps={{ min: 1, max: 10 }}
              />
              <TextField
                label="Decay"
                type="number"
                value={newRule.decay}
                onChange={(e) => setNewRule({ ...newRule, decay: parseInt(e.target.value) || 5 })}
                sx={{ flex: 1 }}
                size="small"
                inputProps={{ min: 1, max: 10 }}
              />
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                size="small"
                colorVariant="blue"
                onClick={handleAddManualRule}
                fullWidth
              >
                Add
              </Button>
              <Button
                size="small"
                colorVariant="transparent"
                onClick={() => {
                  setShowAddForm(false);
                  setNewRule({ rule: '', reasoning: '', confidence: 5, decay: 5 });
                  setError(null);
                }}
                fullWidth
              >
                Cancel
              </Button>
            </Box>
          </Box>
        )}
      </Box>
    </Paper>
  );
}