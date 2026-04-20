import { useState, useEffect } from 'react';
import { Box, Paper, Typography, IconButton, Divider, Chip, MenuItem, FormControl, InputLabel } from '@mui/material';
import { Close, CheckCircle, Error as ErrorIcon, Edit, Delete, Save, Cancel, Favorite, FavoriteBorder, Add } from '@mui/icons-material';
import { TextField } from '../../design-system/TextField';
import { Select } from '../../design-system/Select';
import { CollapsibleSection } from '../../design-system/CollapsibleSection';
import { Button } from '../../design-system/Button';
import { type Task, api } from '../../services/api';

interface LearnerTaskDetailsProps {
  task: Task | any;
  onClose: () => void;
  chatId?: string;
  onTaskUpdate?: (updatedTask: any) => void;
  onFavoritesChange?: () => void;
}

export function LearnerTaskDetails({ task, onClose, chatId, onTaskUpdate, onFavoritesChange }: LearnerTaskDetailsProps) {
  const [editingRule, setEditingRule] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<any>({});
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [favoritedRules, setFavoritedRules] = useState<Set<string>>(new Set());
  const [loadingFavorite, setLoadingFavorite] = useState<string | null>(null);
  const [showAddRule, setShowAddRule] = useState(false);
  const [favorites, setFavorites] = useState<any[]>([]);
  const [selectedFavorite, setSelectedFavorite] = useState<string>('');
  const [newRule, setNewRule] = useState({ rule: '', reasoning: '', confidence: 5, decay: 5 });
  
  useEffect(() => {
    const fetchFavorites = async () => {
      try {
        const response = await api.getFavorites();
        if (response.success) {
          const favoriteIds = new Set<string>(response.favorites.map((f: any) => f.rule_id as string));
          setFavoritedRules(favoriteIds);
        }
      } catch (err) {
        console.error('Failed to load favorites:', err);
      }
    };
    fetchFavorites();
  }, []);

  const handleToggleFavorite = async (ruleId: string) => {
    const isFavorite = favoritedRules.has(ruleId);
    setLoadingFavorite(ruleId);
    try {
      await api.toggleFavorite(ruleId, !isFavorite);
      setFavoritedRules(prev => {
        const newSet = new Set(prev);
        if (isFavorite) {
          newSet.delete(ruleId);
        } else {
          newSet.add(ruleId);
        }
        return newSet;
      });
      onFavoritesChange?.();
    } catch (err: any) {
      setError(err.message || 'Failed to toggle favorite');
    } finally {
      setLoadingFavorite(null);
    }
  };
  
  if (!task) return null;

  const rules = task.rules || [];
  const canEditRules = Boolean(chatId);
  const normalizeScore = (value: any, fallback = 10): number => {
    const n = Number(value);
    if (Number.isFinite(n) && n >= 1 && n <= 10) return Math.round(n);
    return fallback;
  };

  const handleEdit = (rule: any) => {
    setEditingRule(rule.rule_id);
    setEditForm({
      rule: rule.rule,
      reasoning: rule.reasoning,
      confidence: normalizeScore(rule.confidence),
      decay: normalizeScore(rule.decay)
    });
    setError(null);
  };

  const handleCancelEdit = () => {
    setEditingRule(null);
    setEditForm({});
    setError(null);
  };

  const handleSaveEdit = async (ruleId: string) => {
    try {
      if (!chatId) return;
      
      const confidence = parseInt(editForm.confidence);
      const decay = parseInt(editForm.decay);
      
      if (confidence < 1 || confidence > 10) {
        setError('Confidence must be between 1 and 10');
        return;
      }
      if (decay < 1 || decay > 10) {
        setError('Decay must be between 1 and 10');
        return;
      }
      
      await api.updateRule(chatId, task.task_id, ruleId, {
        rule: editForm.rule,
        reasoning: editForm.reasoning,
        confidence,
        decay
      });
      
      const updatedTask = { ...task };
      const ruleIndex = updatedTask.rules.findIndex((r: any) => r.rule_id === ruleId);
      if (ruleIndex !== -1) {
        updatedTask.rules[ruleIndex] = {
          ...updatedTask.rules[ruleIndex],
          rule: editForm.rule,
          reasoning: editForm.reasoning,
          confidence,
          decay
        };
      }
      
      onTaskUpdate?.(updatedTask);
      setEditingRule(null);
      setEditForm({});
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to update rule');
    }
  };

  const handleDeleteClick = (ruleId: string) => {
    setConfirmingDelete(ruleId);
    setError(null);
  };

  const handleCancelDelete = () => {
    setConfirmingDelete(null);
    setError(null);
  };

  const handleDelete = async (ruleId: string) => {
    try {
      if (!chatId) return;
      
      await api.deleteRule(chatId, task.task_id, ruleId);
      
      const updatedTask = { ...task };
      updatedTask.rules = updatedTask.rules.filter((r: any) => r.rule_id !== ruleId);
      
      onTaskUpdate?.(updatedTask);
      setConfirmingDelete(null);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to delete rule');
    }
  };

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
        <Typography variant="subtitle2" fontWeight={600}>
          Task Details
        </Typography>
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
        <Box sx={{ mb: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Chip 
            label={task.title || task.suggested_type || task.type || 'uncategorized'}
            size="small"
            color="primary"
          />
          <Chip 
            icon={task.type === 'good' ? <CheckCircle /> : <ErrorIcon />}
            label={task.type === 'good' ? 'Good Trajectory' : 'Bad Trajectory'}
            size="small"
            color={task.type === 'good' ? 'success' : 'error'}
          />
        </Box>

        <Box sx={{ mb: 2 }}>
          <Typography 
            variant="caption" 
            color="text.secondary"
            sx={{ mb: 0.5, display: 'block', fontWeight: 600 }}
          >
            Description
          </Typography>
          <Typography 
            variant="body2"
            sx={{ whiteSpace: 'pre-wrap' }}
          >
            {task.description || task.task}
          </Typography>
        </Box>

        <Divider sx={{ my: 2 }} />

        {task.notes && task.notes.length > 0 && (
          <>
            <CollapsibleSection
              title={
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  📝 Notes ({task.notes.length})
                </Typography>
              }
              defaultOpen={false}
              sx={{ mb: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}
            >
              {task.notes.map((note: string, idx: number) => (
                <Box 
                  key={idx}
                  sx={{ 
                    mb: 1, 
                    p: 1.5, 
                    bgcolor: 'action.hover', 
                    borderRadius: 1,
                  }}
                >
                  <Typography 
                    variant="body2"
                    sx={{ whiteSpace: 'pre-wrap' }}
                  >
                    {note}
                  </Typography>
                </Box>
              ))}
            </CollapsibleSection>
            <Divider sx={{ my: 2 }} />
          </>
        )}

        {((task.messages && task.messages.length > 0) || task.raw_data) && (
          <>
            <CollapsibleSection
              title={
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  💭 {task.messages ? `Messages (${task.messages.length})` : 'Raw Chat Data'}
                </Typography>
              }
              defaultOpen={false}
              sx={{ mb: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}
            >
              <Box 
                sx={{ 
                  maxHeight: 300,
                  overflow: 'auto',
                  fontFamily: 'monospace',
                  fontSize: '0.7rem',
                  bgcolor: 'action.hover',
                  p: 1,
                  borderRadius: 1,
                  whiteSpace: 'pre-wrap',
                }}
              >
                {task.messages && task.messages.length > 0 ? (
                  task.messages.map((msg: string, idx: number) => (
                    <Typography 
                      key={idx}
                      variant="caption"
                      sx={{ 
                        display: 'block',
                        mb: 0.5,
                        fontFamily: 'monospace',
                      }}
                    >
                      • {msg}
                    </Typography>
                  ))
                ) : (
                  <Typography 
                    variant="caption"
                    sx={{ 
                      fontFamily: 'monospace',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {task.raw_data}
                  </Typography>
                )}
              </Box>
            </CollapsibleSection>
            <Divider sx={{ my: 2 }} />
          </>
        )}

        {task.reasoning && (
          <Box sx={{ mb: 2 }}>
            <Typography 
              variant="caption" 
              color="text.secondary"
              sx={{ mb: 0.5, display: 'block', fontWeight: 600 }}
            >
              💡 Reasoning
            </Typography>
            <Typography 
              variant="body2"
              sx={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem' }}
            >
              {task.reasoning}
            </Typography>
          </Box>
        )}

        <Divider sx={{ my: 2 }} />

        {task.type === 'bad' && (
          <>
            {task.problem && (
              <Box sx={{ mb: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                <Typography 
                  variant="caption" 
                  sx={{ mb: 0.5, display: 'block', fontWeight: 600 }}
                >
                  ⚠️ Problem
                </Typography>
                <Typography 
                  variant="body2"
                  sx={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem' }}
                >
                  {task.problem}
                </Typography>
              </Box>
            )}

            {task.failure_point && (
              <Box sx={{ mb: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                <Typography 
                  variant="caption" 
                  sx={{ mb: 0.5, display: 'block', fontWeight: 600 }}
                >
                  📍 Failure Point
                </Typography>
                <Typography 
                  variant="body2"
                  sx={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem' }}
                >
                  {task.failure_point}
                </Typography>
              </Box>
            )}

            {task.guardrail && (
              <Box sx={{ mb: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                <Typography 
                  variant="caption" 
                  sx={{ mb: 0.5, display: 'block', fontWeight: 600 }}
                >
                  🛡️ Guardrail
                </Typography>
                <Typography 
                  variant="body2"
                  sx={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem' }}
                >
                  {task.guardrail}
                </Typography>
              </Box>
            )}

            <Divider sx={{ my: 2 }} />
          </>
        )}

        {canEditRules && (
          <Box sx={{ mb: 2 }}>
            {!showAddRule ? (
              <Button
                size="small"
                colorVariant="green"
                onClick={async () => {
                  setShowAddRule(true);
                  try {
                    const response = await api.getFavorites();
                    if (response.success) {
                      setFavorites(response.favorites);
                    }
                  } catch (err) {
                    console.error('Failed to load favorites:', err);
                  }
                }}
                fullWidth
              >
                <Add fontSize="small" sx={{ mr: 0.5 }} />
                Add Rule
              </Button>
            ) : (
              <Box sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 1 }}>
                  Add Rule
                </Typography>
                <FormControl fullWidth size="small" sx={{ mb: 1 }}>
                  <InputLabel>Source</InputLabel>
                  <Select
                    value={selectedFavorite}
                    onChange={(e) => setSelectedFavorite(e.target.value as string)}
                    label="Source"
                  >
                    <MenuItem value="manual">Manual Entry</MenuItem>
                    {favorites.map((fav) => (
                      <MenuItem key={fav.rule_id} value={fav.rule_id}>
                        {fav.rule.slice(0, 50)}...
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                
                {selectedFavorite === 'manual' ? (
                  <>
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
                  </>
                ) : selectedFavorite ? (
                  <Box sx={{ p: 1, bgcolor: 'action.hover', borderRadius: 1, mb: 1 }}>
                    <Typography variant="caption" fontWeight={600}>
                      {favorites.find(f => f.rule_id === selectedFavorite)?.rule}
                    </Typography>
                  </Box>
                ) : null}

                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    size="small"
                    colorVariant="blue"
                    onClick={async () => {
                      if (!chatId) return;
                      try {
                        if (selectedFavorite === 'manual') {
                          if (!newRule.rule.trim() || !newRule.reasoning.trim()) {
                            setError('Rule and reasoning are required');
                            return;
                          }
                          await api.addRule(chatId, task.task_id, newRule);
                        } else if (selectedFavorite) {
                          const favorite = favorites.find(f => f.rule_id === selectedFavorite);
                          if (favorite) {
                            await api.addRule(chatId, task.task_id, {
                              rule: favorite.rule,
                              reasoning: favorite.reasoning,
                              confidence: normalizeScore(favorite.confidence),
                              decay: normalizeScore(favorite.decay),
                            });
                          }
                        }
                        
                        const updatedTask = await api.getTask(chatId, task.task_id);
                        if (updatedTask.success) {
                          onTaskUpdate?.(updatedTask.task);
                        }
                        
                        setShowAddRule(false);
                        setSelectedFavorite('');
                        setNewRule({ rule: '', reasoning: '', confidence: 5, decay: 5 });
                        setError(null);
                      } catch (err: any) {
                        setError(err.message || 'Failed to add rule');
                      }
                    }}
                    disabled={!selectedFavorite}
                    fullWidth
                  >
                    Add
                  </Button>
                  <Button
                    size="small"
                    colorVariant="transparent"
                    onClick={() => {
                      setShowAddRule(false);
                      setSelectedFavorite('');
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
        )}

        {rules.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography 
              variant="caption" 
              color="text.secondary"
              sx={{ mb: 1, display: 'block', fontWeight: 600 }}
            >
              📋 Extracted Rules ({rules.length})
            </Typography>
            {rules.map((rule: any, idx: number) => {
              const isEditing = editingRule === rule.rule_id;
              const isConfirmingDelete = confirmingDelete === rule.rule_id;
              const displayConfidence = normalizeScore(rule.confidence);
              const displayDecay = normalizeScore(rule.decay);
              
              return (
                <Box 
                  key={idx}
                  sx={{ mb: 1, border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1.5 }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Typography variant="body2" fontWeight={600}>
                      Rule {idx + 1}
                    </Typography>
                    {rule.confidence !== undefined && (
                      <Chip 
                        label={`${displayConfidence}/${displayDecay}`} 
                        size="small" 
                      />
                    )}
                    {!isEditing && !isConfirmingDelete && (
                      <Box sx={{ ml: 'auto', display: 'flex', gap: 0.5 }}>
                        <IconButton 
                          size="small" 
                          onClick={() => handleToggleFavorite(rule.rule_id)}
                          disabled={loadingFavorite === rule.rule_id}
                          sx={{ color: favoritedRules.has(rule.rule_id) ? '#9a4e4e' : 'text.secondary' }}
                        >
                          {favoritedRules.has(rule.rule_id) ? (
                            <Favorite fontSize="small" />
                          ) : (
                            <FavoriteBorder fontSize="small" />
                          )}
                        </IconButton>
                        {canEditRules && (
                          <>
                            <IconButton size="small" onClick={() => handleEdit(rule)}>
                              <Edit fontSize="small" />
                            </IconButton>
                            <IconButton size="small" onClick={() => handleDeleteClick(rule.rule_id)}>
                              <Delete fontSize="small" />
                            </IconButton>
                          </>
                        )}
                      </Box>
                    )}
                  </Box>

                  {isEditing ? (
                    <Box>
                      <TextField
                        fullWidth
                        multiline
                        rows={2}
                        label="Rule"
                        value={editForm.rule}
                        onChange={(e) => setEditForm({ ...editForm, rule: e.target.value })}
                        sx={{ mb: 1 }}
                        size="small"
                      />
                      <TextField
                        fullWidth
                        multiline
                        rows={3}
                        label="Reasoning"
                        value={editForm.reasoning}
                        onChange={(e) => setEditForm({ ...editForm, reasoning: e.target.value })}
                        sx={{ mb: 1 }}
                        size="small"
                      />
                      <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                        <TextField
                          label="Confidence (1-10)"
                          type="number"
                          value={editForm.confidence}
                          onChange={(e) => setEditForm({ ...editForm, confidence: e.target.value })}
                          sx={{ flex: 1 }}
                          size="small"
                          inputProps={{ min: 1, max: 10 }}
                        />
                        <TextField
                          label="Decay (1-10)"
                          type="number"
                          value={editForm.decay}
                          onChange={(e) => setEditForm({ ...editForm, decay: e.target.value })}
                          sx={{ flex: 1 }}
                          size="small"
                          inputProps={{ min: 1, max: 10 }}
                        />
                      </Box>
                      {error && (
                        <Typography variant="caption" color="error" sx={{ display: 'block', mb: 1 }}>
                          {error}
                        </Typography>
                      )}
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                          size="small"
                          colorVariant="blue"
                          onClick={() => handleSaveEdit(rule.rule_id)}
                        >
                          <Save fontSize="small" sx={{ mr: 0.5 }} />
                          Save
                        </Button>
                        <Button
                          size="small"
                          colorVariant="transparent"
                          onClick={handleCancelEdit}
                        >
                          <Cancel fontSize="small" sx={{ mr: 0.5 }} />
                          Cancel
                        </Button>
                      </Box>
                    </Box>
                  ) : isConfirmingDelete ? (
                    <Box>
                      <Typography variant="body2" color="error" sx={{ mb: 1 }}>
                        Delete this rule?
                      </Typography>
                      {error && (
                        <Typography variant="caption" color="error" sx={{ display: 'block', mb: 1 }}>
                          {error}
                        </Typography>
                      )}
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                          size="small"
                          colorVariant="red"
                          onClick={() => handleDelete(rule.rule_id)}
                        >
                          Confirm Delete
                        </Button>
                        <Button
                          size="small"
                          colorVariant="transparent"
                          onClick={handleCancelDelete}
                        >
                          Cancel
                        </Button>
                      </Box>
                    </Box>
                  ) : (
                    <Box>
                      <Typography 
                        variant="body2" 
                        sx={{ mb: 1, fontWeight: 600 }}
                      >
                        {rule.rule}
                      </Typography>
                      <Typography 
                        variant="caption" 
                        color="text.secondary"
                        sx={{ display: 'block', whiteSpace: 'pre-wrap', mb: 1 }}
                      >
                        {rule.reasoning}
                      </Typography>
                      {rule.confidence !== undefined && (
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          <Chip label={`Confidence: ${displayConfidence}/10`} size="small" />
                          <Chip label={`Decay: ${displayDecay}/10`} size="small" />
                        </Box>
                      )}
                    </Box>
                  )}
                </Box>
              );
            })}
          </Box>
        )}

        <Box sx={{ mt: 3, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
          <Typography 
            variant="caption" 
            color="text.secondary"
            sx={{ display: 'block', fontFamily: 'monospace' }}
          >
            ID: {task.task_id}
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
}
