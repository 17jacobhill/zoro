import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, MenuItem, FormControl, InputLabel, CircularProgress, Dialog, DialogTitle, DialogContent, DialogActions, Chip } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import StarIcon from '@mui/icons-material/Star';
import StarBorderIcon from '@mui/icons-material/StarBorder';
import { Button } from '../../design-system/Button';
import { TextField } from '../../design-system/TextField';
import { Select } from '../../design-system/Select';
import { api } from '../../services/api';
import { RuleCard } from './RuleCard';
import { AddRuleModal } from './AddRuleModal';
import { colors } from '../../design-system/colors';
import type { KnowledgeItem } from '../../types/knowledge';

export const RulesBrowserPanel: React.FC = () => {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [recentlyAddedIds, setRecentlyAddedIds] = useState<Set<string>>(new Set());
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<string | null>(null);
  const [addRuleModalOpen, setAddRuleModalOpen] = useState(false);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const filters: any = {};
      if (categoryFilter) filters.category = categoryFilter;
      filters.type = 'rule';
      if (searchQuery) filters.search = searchQuery;
      if (favoritesOnly) filters.favorites = true;

      const data = await api.fetchKBItems(filters);
      
      // Sort by created_at descending (newest first)
      const sortedItems = (data.items || []).sort((a: any, b: any) => {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
      
      setItems(sortedItems);

      const uniqueCategories = Array.from(new Set(data.items.map((i: any) => i.category)));
      setCategories(uniqueCategories);
    } catch (error) {
      console.error('Failed to load items:', error);
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, searchQuery, favoritesOnly]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadItems();
    }, 300);
    return () => clearTimeout(timer);
  }, [loadItems]);

  useEffect(() => {
    const handleProcessComplete = (event: Event) => {
      const customEvent = event as CustomEvent;
      const { newly_added_ids } = customEvent.detail;
      setRecentlyAddedIds(new Set(newly_added_ids));
      loadItems();
    };

    window.addEventListener('kb-process-complete', handleProcessComplete);
    return () => window.removeEventListener('kb-process-complete', handleProcessComplete);
  }, [loadItems]);

  useEffect(() => {
    if (searchQuery || categoryFilter || favoritesOnly) {
      setRecentlyAddedIds(new Set());
    }
  }, [searchQuery, categoryFilter, favoritesOnly]);

  const handleFavoriteToggle = async (itemId: string, currentFavorite: boolean) => {
    try {
      await api.updateKBItem(itemId, { is_favorite: !currentFavorite });
      await loadItems();
    } catch (error) {
      console.error('Failed to toggle favorite:', error);
    }
  };

  const handleTestableToggle = async (itemId: string, currentTestable: boolean) => {
    try {
      await api.updateKBItem(itemId, { is_testable: !currentTestable });
      await loadItems();
    } catch (error) {
      console.error('Failed to toggle testable:', error);
    }
  };

  const handleStrictToggle = async (itemId: string, currentStrict: boolean) => {
    try {
      await api.updateKBItem(itemId, { is_strict: !currentStrict });
      await loadItems();
    } catch (error) {
      console.error('Failed to toggle strict:', error);
    }
  };

  const handleDelete = (itemId: string) => {
    setItemToDelete(itemId);
    setDeleteConfirmOpen(true);
  };

  const confirmDelete = async () => {
    if (!itemToDelete) return;
    
    try {
      await api.deleteKBItem(itemToDelete);
      if (selectedItemId === itemToDelete) {
        setSelectedItemId(null);
      }
      await loadItems();
    } catch (error) {
      console.error('Failed to delete item:', error);
    } finally {
      setDeleteConfirmOpen(false);
      setItemToDelete(null);
    }
  };

  const cancelDelete = () => {
    setDeleteConfirmOpen(false);
    setItemToDelete(null);
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          pb: 0.25,
          mb: 2,
        }}
      >
        <Typography
          variant="body1"
          sx={{ color: '#000', fontSize: '0.95rem', fontWeight: 600, lineHeight: 1.2 }}
        >
          Rules Management
        </Typography>
        <Chip
          label={`${items.length} rules`}
          size="small"
          sx={{
            backgroundColor: colors.green,
            color: 'white',
            fontSize: '10px',
            height: '20px',
          }}
        />
      </Box>

      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
          <TextField
            fullWidth
            size="small"
            placeholder="Search rules..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            sx={{
              flex: 2,
              '& .MuiInputBase-root': { height: 40 },
              '& .MuiInputBase-input': { fontSize: '11px' },
              '& .MuiInputBase-input::placeholder': { fontSize: '11px' }
            }}
          />

          <FormControl size="small" sx={{ flex: 1 }}>
            <InputLabel
              sx={{
                fontSize: '11px',
                color: colors.grey,
                '&.Mui-focused': { color: colors.green }
              }}
            >
              Category
            </InputLabel>
            <Select
              value={categoryFilter}
              label="Category"
              onChange={(e) => setCategoryFilter(e.target.value as string)}
              sx={{
                '& .MuiOutlinedInput-root': { height: 40 },
                '& .MuiSelect-select': { fontSize: '11px', display: 'flex', alignItems: 'center' }
              }}
            >
              <MenuItem value="" sx={{ fontSize: '11px' }}>All</MenuItem>
              {categories.map(cat => (
                <MenuItem key={cat} value={cat} sx={{ fontSize: '11px' }}>{cat}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <Button
            onClick={() => setFavoritesOnly((prev) => !prev)}
            colorVariant={favoritesOnly ? 'green' : 'transparent'}
            startIcon={favoritesOnly ? <StarIcon sx={{ fontSize: 14 }} /> : <StarBorderIcon sx={{ fontSize: 14 }} />}
            sx={{
              minWidth: 116,
              height: 40,
              fontSize: '11px',
              py: 0,
              px: 1
            }}
          >
            Favorites
          </Button>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
          <Button
            onClick={() => setAddRuleModalOpen(true)}
            colorVariant="green"
            startIcon={<AddIcon />}
            sx={{ fontSize: '11px', py: 0.5 }}
          >
            Add Rule
          </Button>
        </Box>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress size={24} sx={{ color: colors.green }} />
        </Box>
      ) : (
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          {items.length === 0 ? (
            <Typography sx={{ color: colors.grey, textAlign: 'center', py: 3 }}>
              No items found
            </Typography>
          ) : (
            items.map(item => (
              <RuleCard
                key={item.item_id}
                item={item}
                isNew={recentlyAddedIds.has(item.item_id)}
                isSelected={selectedItemId === item.item_id}
                onSelect={() => setSelectedItemId(item.item_id)}
                onFavoriteToggle={() => handleFavoriteToggle(item.item_id, item.is_favorite)}
                onDelete={() => handleDelete(item.item_id)}
                onStrictToggle={() => handleStrictToggle(item.item_id, item.is_strict || false)}
                onTestableToggle={() => handleTestableToggle(item.item_id, item.is_testable || false)}
              />
            ))
          )}
        </Box>
      )}

      {/* Add Rule Modal */}
      <AddRuleModal
        open={addRuleModalOpen}
        onClose={() => setAddRuleModalOpen(false)}
        onSuccess={() => {
          loadItems();
          setAddRuleModalOpen(false);
        }}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteConfirmOpen}
        onClose={cancelDelete}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ fontSize: '14px', fontWeight: 'bold' }}>
          Confirm Delete
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: '13px' }}>
            Are you sure you want to delete this item? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2, gap: 1 }}>
          <Button
            onClick={cancelDelete}
            sx={{ 
              flex: 1, 
              fontSize: '12px',
              backgroundColor: colors.grey,
              color: 'white',
              '&:hover': { backgroundColor: colors.darkGreen }
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={confirmDelete}
            sx={{ 
              flex: 1, 
              fontSize: '12px',
              backgroundColor: colors.red,
              color: 'white',
              '&:hover': { backgroundColor: colors.darkGreen }
            }}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
