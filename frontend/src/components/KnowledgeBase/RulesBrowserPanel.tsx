import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, CircularProgress, Dialog, DialogTitle, DialogContent, DialogActions, Chip } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import DeleteIcon from '@mui/icons-material/Delete';
import StarIcon from '@mui/icons-material/Star';
import StarBorderIcon from '@mui/icons-material/StarBorder';
import { CompactIconButton } from '../../design-system/CompactIconButton';
import { FormControl } from '../../design-system/FormControl';
import { InputLabel } from '../../design-system/InputLabel';
import { MenuItem } from '../../design-system/MenuItem';
import { PanelHeader } from '../../design-system/PanelHeader';
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
  const [editingItem, setEditingItem] = useState<KnowledgeItem | null>(null);

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
      await api.toggleFavorite(itemId, !currentFavorite);
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

  const handleOpenAddModal = () => {
    setEditingItem(null);
    setAddRuleModalOpen(true);
  };

  const handleOpenEditModal = (item: KnowledgeItem) => {
    setEditingItem(item);
    setAddRuleModalOpen(true);
  };

  const handleCloseRuleModal = () => {
    setAddRuleModalOpen(false);
    setEditingItem(null);
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <PanelHeader
        title="Rules Management"
        subtitle="Review, refine, and favorite the rules that support the main workflow."
        badge={
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
        }
      />

      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
          <TextField
            fullWidth
            size="small"
            placeholder="Search rules..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            sx={{ flex: 2 }}
          />

          <FormControl size="small" sx={{ flex: 1 }}>
            <InputLabel>Category</InputLabel>
            <Select
              value={categoryFilter}
              label="Category"
              onChange={(e) => setCategoryFilter(e.target.value as string)}
            >
              <MenuItem value="">All</MenuItem>
              {categories.map(cat => (
                <MenuItem key={cat} value={cat}>{cat}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <CompactIconButton
            label={favoritesOnly ? 'Show all rules' : 'Show favorites only'}
            icon={favoritesOnly ? <StarIcon sx={{ fontSize: 18 }} /> : <StarBorderIcon sx={{ fontSize: 18 }} />}
            tone={favoritesOnly ? 'gold' : 'grey'}
            active={favoritesOnly}
            onClick={() => setFavoritesOnly((prev) => !prev)}
            sx={{ alignSelf: 'center' }}
          />
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
          <CompactIconButton
            label="Add rule"
            icon={<AddIcon sx={{ fontSize: 18 }} />}
            tone="green"
            onClick={handleOpenAddModal}
          />
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
                onEdit={() => handleOpenEditModal(item)}
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
        onClose={handleCloseRuleModal}
        onSuccess={(savedItem) => {
          if (savedItem?.item_id) {
            setSelectedItemId(savedItem.item_id);
          }
          loadItems();
          handleCloseRuleModal();
        }}
        mode={editingItem ? 'edit' : 'create'}
        initialRule={editingItem}
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
          <CompactIconButton
            label="Cancel delete"
            icon={<CloseIcon sx={{ fontSize: 17 }} />}
            tone="grey"
            onClick={cancelDelete}
          />
          <CompactIconButton
            label="Delete rule"
            icon={<DeleteIcon sx={{ fontSize: 17 }} />}
            tone="red"
            onClick={confirmDelete}
          />
        </DialogActions>
      </Dialog>
    </Box>
  );
};
