import { useMemo, useState, useEffect } from 'react';
import { Box, Paper, Typography, IconButton, Divider, Chip, Checkbox, FormControlLabel, CircularProgress } from '@mui/material';
import { Close, FactCheck, Delete, Add, Search } from '@mui/icons-material';
import { TextField } from '../../design-system/TextField';
import { CollapsibleSection } from '../../design-system/CollapsibleSection';
import { Button } from '../../design-system/Button';
import { api } from '../../services/api';
import { colors } from '../../design-system/colors';

interface AssistantNodeDetailsProps {
  task: any;
  onClose: () => void;
  chatId?: string;
  onTaskUpdate?: (updatedTask: any) => void;
  onVerify?: (payload: {
    title: string;
    target: {
      kind: 'node' | 'substep' | 'rule';
      node_id: string;
      substep_id?: string;
      rule_id?: string;
    };
  }) => void;
  onOpenEnforcement?: (nodeId: string, targetKind: 'step' | 'substep' | 'rule', targetId: string) => void;
}

export function AssistantNodeDetails({ task, onClose, chatId, onTaskUpdate, onVerify, onOpenEnforcement }: AssistantNodeDetailsProps) {
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [newPlanRuleName, setNewPlanRuleName] = useState('');
  const [newPlanRuleDescription, setNewPlanRuleDescription] = useState('');
  const [newPlanRuleSource, setNewPlanRuleSource] = useState('manual');
  const [planRuleBusy, setPlanRuleBusy] = useState(false);

  const [newSubstepText, setNewSubstepText] = useState('');
  const [substepBusy, setSubstepBusy] = useState(false);
  const [confirmingSubstepDelete, setConfirmingSubstepDelete] = useState<string | null>(null);
  
  // Search favorites state
  const [searchQuery, setSearchQuery] = useState('');
  const [favorites, setFavorites] = useState<any[]>([]);
  const [favoritesLoading, setFavoritesLoading] = useState(false);
  const [showAddRuleForm, setShowAddRuleForm] = useState(false);
  
  // Fetch favorites on mount
  useEffect(() => {
    const fetchFavorites = async () => {
      setFavoritesLoading(true);
      try {
        const response = await api.getFavorites();
        if (response.success) {
          setFavorites(response.favorites);
        }
      } catch (err: any) {
        console.error('Failed to load favorites:', err);
      } finally {
        setFavoritesLoading(false);
      }
    };
    fetchFavorites();
  }, []);
  
  if (!task) return null;

  const rules = task.rules || [];
  const canDeletePlanRules = Boolean(chatId);
  const canAddPlanRules = Boolean(chatId);
  const canEditSubsteps = Boolean(chatId && task.type === 'code-style');
  const canVerifyPlanTargets = Boolean(chatId && onVerify);

  const substeps = useMemo(() => {
    if (!Array.isArray(task.substeps)) return [];
    return task.substeps.filter((s: any) => s && typeof s === 'object');
  }, [task.substeps]);

  const handleAddSubstep = async () => {
    try {
      if (!chatId) return;
      const nodeId = task.id;
      const text = newSubstepText.trim();
      if (!nodeId || !text) return;

      setSubstepBusy(true);
      setError(null);

      const res = await api.addPlanNodeSubstep(chatId, nodeId, text);
      if (!res?.success) {
        throw new Error(res?.error || 'Failed to add substep');
      }

      onTaskUpdate?.(res.node);
      setNewSubstepText('');
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to add substep');
    } finally {
      setSubstepBusy(false);
    }
  };

  const handleDeleteSubstep = async (substepId: string) => {
    try {
      if (!chatId) return;
      const nodeId = task.id;
      if (!nodeId || !substepId) return;

      setSubstepBusy(true);
      setError(null);

      const res = await api.deletePlanNodeSubstep(chatId, nodeId, substepId);
      if (!res?.success) {
        throw new Error(res?.error || 'Failed to delete substep');
      }

      onTaskUpdate?.(res.node);
      setConfirmingSubstepDelete(null);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to delete substep');
    } finally {
      setSubstepBusy(false);
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
      
      await api.deletePlanNodeRule(chatId, task.id, ruleId);
      
      const updatedTask = { ...task };
      updatedTask.rules = updatedTask.rules.filter((r: any) => r.rule_id !== ruleId);
      
      onTaskUpdate?.(updatedTask);
      setConfirmingDelete(null);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to delete rule');
    }
  };

  const handleAddPlanRule = async () => {
    try {
      if (!chatId) return;

      const nodeId = task.id;
      const name = newPlanRuleName.trim();
      const description = newPlanRuleDescription.trim();
      const source = newPlanRuleSource.trim() || 'manual';

      if (!nodeId) return;
      if (!name || !description) {
        setError('Rule name and description are required');
        return;
      }

      setPlanRuleBusy(true);
      setError(null);

      const res = await api.addPlanNodeRule(chatId, nodeId, { name, description, source });
      if (!res?.success) {
        throw new Error(res?.error || 'Failed to add rule');
      }

      onTaskUpdate?.(res.node);
      setNewPlanRuleName('');
      setNewPlanRuleDescription('');
      setNewPlanRuleSource('manual');
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to add rule');
    } finally {
      setPlanRuleBusy(false);
    }
  };

  const handleAddFavoriteRule = async (favorite: any) => {
    try {
      if (!chatId) return;

      const nodeId = task.id;
      if (!nodeId) return;

      setPlanRuleBusy(true);
      setError(null);

      const res = await api.addPlanNodeRule(chatId, nodeId, {
        name: favorite.rule,
        description: favorite.reasoning,
        source: 'favorite'
      });
      
      if (!res?.success) {
        throw new Error(res?.error || 'Failed to add rule');
      }

      onTaskUpdate?.(res.node);
      setSearchQuery(''); // Clear search after adding
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to add favorite rule');
    } finally {
      setPlanRuleBusy(false);
    }
  };

  const filteredFavorites = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const query = searchQuery.toLowerCase();
    return favorites.filter(f => 
      f.rule.toLowerCase().includes(query) ||
      f.reasoning.toLowerCase().includes(query)
    );
  }, [favorites, searchQuery]);

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
          Node Details
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
            label={task.type}
            size="small"
            sx={{ bgcolor: colors.green, color: 'white' }}
          />
          {task.status && (
            <Chip label={task.status} size="small" sx={{ bgcolor: colors.green, color: 'white' }} />
          )}
          {onOpenEnforcement && (
            <IconButton
              size="small"
              onClick={() => onOpenEnforcement(task.id, 'step', task.id)}
              title="Open Enforcement Panel"
              sx={{ 
                ml: 'auto', 
                color: colors.green,
                '&:hover': { bgcolor: `${colors.green}20` },
                '&:active': { bgcolor: `${colors.green}40` },
              }}
            >
              <FactCheck fontSize="small" />
            </IconButton>
          )}
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

        <CollapsibleSection
          title={
            <Typography variant="caption" color="text.secondary" fontWeight={600}>
              Substeps ({substeps.length})
            </Typography>
          }
          defaultOpen={true}
          sx={{ mb: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}
        >
          {canEditSubsteps && (
            <Box sx={{ mb: 1.5, display: 'flex', gap: 1, alignItems: 'flex-start' }}>
              <TextField
                fullWidth
                size="small"
                label="New substep"
                value={newSubstepText}
                onChange={(e) => setNewSubstepText(e.target.value)}
                disabled={substepBusy}
              />
              <Button
                size="small"
                colorVariant="green"
                disabled={substepBusy || newSubstepText.trim().length === 0}
                onClick={() => void handleAddSubstep()}
              >
                Add
              </Button>
            </Box>
          )}

          {substeps.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No substeps.
            </Typography>
          ) : (
            substeps.map((substep: any, idx: number) => {
              const id = substep?.id || `substep-${idx + 1}`;
              const label = substep?.text || '';
              const checked = Boolean(substep?.completed);
              const isConfirmingThisDelete = confirmingSubstepDelete === id;

              return (
                <Box key={id} sx={{ mb: 1 }}>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                    <FormControlLabel
                      sx={{
                        flex: 1,
                        display: 'flex',
                        alignItems: 'flex-start',
                        m: 0,
                        gap: 1,
                      }}
                      control={
                        <Checkbox
                          checked={checked}
                          disabled
                          size="small"
                          inputProps={{
                            'aria-label': `${id} ${label}`,
                          }}
                          sx={{
                            p: 0.25,
                            mt: '2px',
                            color: checked ? 'success.main' : 'text.primary',
                            '&.Mui-checked': {
                              color: 'success.main',
                            },
                            '&.Mui-disabled': {
                              color: checked ? 'success.main' : 'text.primary',
                            },
                          }}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.primary' }}>
                            {id}
                          </Typography>
                          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                            {label}
                          </Typography>
                        </Box>
                      }
                    />

                    {onOpenEnforcement && (
                      <IconButton
                        size="small"
                        onClick={() => onOpenEnforcement(task.id, 'substep', id)}
                        title="Open Enforcement Panel"
                        sx={{ 
                          color: colors.green,
                          '&:hover': { bgcolor: `${colors.green}20` },
                          '&:active': { bgcolor: `${colors.green}40` },
                        }}
                      >
                        <FactCheck fontSize="small" />
                      </IconButton>
                    )}

                    {canEditSubsteps && (
                      isConfirmingThisDelete ? (
                        <Box sx={{ display: 'flex', gap: 1, flexShrink: 0 }}>
                          <Button
                            size="small"
                            colorVariant="red"
                            disabled={substepBusy}
                            onClick={() => void handleDeleteSubstep(id)}
                          >
                            Confirm
                          </Button>
                          <Button
                            size="small"
                            colorVariant="transparent"
                            disabled={substepBusy}
                            onClick={() => setConfirmingSubstepDelete(null)}
                          >
                            Cancel
                          </Button>
                        </Box>
                      ) : (
                        <IconButton
                          size="small"
                          disabled={substepBusy}
                          onClick={() => {
                            setConfirmingSubstepDelete(id);
                            setError(null);
                          }}
                        >
                          <Delete fontSize="small" />
                        </IconButton>
                      )
                    )}
                  </Box>
                </Box>
              );
            })
          )}
        </CollapsibleSection>
        <Divider sx={{ my: 2 }} />

        <CollapsibleSection
          title={
            <Typography variant="caption" color="text.secondary" fontWeight={600}>
              📋 Rules to Follow ({rules.length})
            </Typography>
          }
          defaultOpen={true}
          sx={{ mb: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}
        >
          {/* Add Rule Button */}
          {canAddPlanRules && (
            <Box sx={{ mb: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 0.5 }}>
                {showAddRuleForm ? (
                  <Button
                    size="small"
                    colorVariant="transparent"
                    onClick={() => setShowAddRuleForm(false)}
                    sx={{ fontSize: '0.7rem', py: 0.25, px: 1 }}
                  >
                    Cancel
                  </Button>
                ) : (
                  <IconButton
                    size="small"
                    onClick={() => setShowAddRuleForm(true)}
                    sx={{ color: colors.green, p: 0.5 }}
                  >
                    <Add fontSize="small" />
                  </IconButton>
                )}
              </Box>

              {/* Add Rule Form (Collapsible) */}
              {showAddRuleForm && (
                <Box sx={{ mt: 1.5, p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1, bgcolor: 'background.paper' }}>
                  {/* Search Favorites */}
                  <TextField
                    fullWidth
                    size="small"
                    placeholder="Search favorites..."
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

                  {/* Search Results */}
                  {searchQuery && (
                    <Box sx={{ mb: 1.5 }}>
                      {favoritesLoading ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
                          <CircularProgress size={16} />
                        </Box>
                      ) : filteredFavorites.length === 0 ? (
                        <Typography variant="caption" color="text.secondary">
                          No favorites match "{searchQuery}"
                        </Typography>
                      ) : (
                        <>
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                            {filteredFavorites.length} favorite {filteredFavorites.length === 1 ? 'match' : 'matches'}
                          </Typography>
                          {filteredFavorites.map((fav) => (
                            <Box
                              key={fav.rule_id}
                              sx={{
                                mb: 0.5,
                                p: 1,
                                border: '1px solid',
                                borderColor: 'divider',
                                borderRadius: 1,
                                bgcolor: 'background.default',
                                display: 'flex',
                                alignItems: 'flex-start',
                                gap: 1,
                              }}
                            >
                              <Box sx={{ flex: 1 }}>
                                <Typography variant="caption" fontWeight={600} sx={{ display: 'block' }}>
                                  {fav.rule}
                                </Typography>
                                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                                  {fav.reasoning}
                                </Typography>
                              </Box>
                              <IconButton
                                size="small"
                                onClick={() => handleAddFavoriteRule(fav)}
                                disabled={planRuleBusy}
                                sx={{ color: colors.green }}
                              >
                                <Add fontSize="small" />
                              </IconButton>
                            </Box>
                          ))}
                        </>
                      )}
                    </Box>
                  )}

                  <Divider sx={{ my: 1 }} />

                  {/* Manual Rule Form */}
                  <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 0.5, fontSize: '0.7rem' }}>
                    Or add manual rule
                  </Typography>
                  <TextField
                    fullWidth
                    size="small"
                    label="Name"
                    value={newPlanRuleName}
                    onChange={(e) => setNewPlanRuleName(e.target.value)}
                    disabled={planRuleBusy}
                    sx={{ 
                      mb: 0.5,
                      '& .MuiInputBase-root': { fontSize: '0.75rem', py: 0.5 },
                      '& .MuiInputLabel-root': { fontSize: '0.75rem' },
                    }}
                  />
                  <TextField
                    fullWidth
                    size="small"
                    label="Description"
                    multiline
                    rows={2}
                    value={newPlanRuleDescription}
                    onChange={(e) => setNewPlanRuleDescription(e.target.value)}
                    disabled={planRuleBusy}
                    sx={{ 
                      mb: 0.5,
                      '& .MuiInputBase-root': { fontSize: '0.75rem', py: 0.5 },
                      '& .MuiInputLabel-root': { fontSize: '0.75rem' },
                    }}
                  />
                  <TextField
                    fullWidth
                    size="small"
                    label="Source"
                    value={newPlanRuleSource}
                    onChange={(e) => setNewPlanRuleSource(e.target.value)}
                    disabled={planRuleBusy}
                    sx={{ 
                      mb: 0.5,
                      '& .MuiInputBase-root': { fontSize: '0.75rem', py: 0.5 },
                      '& .MuiInputLabel-root': { fontSize: '0.75rem' },
                    }}
                  />

                  {error && (
                    <Typography variant="caption" color="error" sx={{ display: 'block', mb: 0.5, fontSize: '0.7rem' }}>
                      {error}
                    </Typography>
                  )}

                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <Button
                      size="small"
                      colorVariant="green"
                      disabled={planRuleBusy}
                      onClick={() => void handleAddPlanRule()}
                      sx={{ fontSize: '0.7rem', py: 0.25, px: 1 }}
                    >
                      Add
                    </Button>
                  </Box>
                </Box>
              )}
            </Box>
          )}

          {rules.map((rule: any, idx: number) => {
            const typeMatch = rule.name?.match(/^\[([^\]]+)\]/);
            const nodeType = typeMatch ? typeMatch[1] : '';
            const isConfirmingDelete = confirmingDelete === rule.rule_id;
            
            return (
              <CollapsibleSection
                key={idx}
                title={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
                    <Typography variant="body2" fontWeight={600}>
                      Rule {idx + 1}
                    </Typography>
                    {nodeType && (
                      <Chip label={nodeType} size="small" sx={{ bgcolor: colors.green, color: 'white' }} />
                    )}

                    {canDeletePlanRules && !isConfirmingDelete && (
                      <Box sx={{ ml: 'auto', display: 'flex' }}>
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteClick(rule.rule_id);
                          }}
                        >
                          <Delete fontSize="small" />
                        </IconButton>
                      </Box>
                    )}
                  </Box>
                }
                defaultOpen={false}
                sx={{ mb: 1, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}
              >
                <Box>
                  {isConfirmingDelete && (
                    <Box sx={{ mb: 1 }}>
                      <Typography variant="body2" color="error" sx={{ mb: 1 }}>
                        Delete this rule from this plan step?
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
                      <Divider sx={{ my: 2 }} />
                    </Box>
                  )}
                  <Typography 
                    variant="body2" 
                    sx={{ mb: 1, fontWeight: 600 }}
                  >
                    {rule.name}
                  </Typography>
                  <Typography 
                    variant="body2" 
                    sx={{ mb: 1 }}
                  >
                    {rule.description}
                  </Typography>
                  <Typography 
                    variant="caption" 
                    color="text.secondary"
                    sx={{ display: 'block', whiteSpace: 'pre-wrap' }}
                  >
                    {rule.source}
                  </Typography>
                </Box>
              </CollapsibleSection>
            );
          })}
        </CollapsibleSection>

        {task.audit && task.audit.length > 0 && (
          <>
            <Divider sx={{ my: 2 }} />
            <CollapsibleSection
              title={
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  📝 Audit Trail ({task.audit.length})
                </Typography>
              }
              defaultOpen={false}
              sx={{ mb: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}
            >
              {task.audit.map((entry: any, idx: number) => (
                <Box 
                  key={idx}
                  sx={{ 
                    mb: 1, 
                    p: 1, 
                    bgcolor: 'action.hover', 
                    borderRadius: 1,
                    fontSize: '0.75rem',
                  }}
                >
                  <Typography variant="caption" sx={{ display: 'block', fontWeight: 600 }}>
                    {new Date(entry.at).toLocaleString()} - {entry.who}
                  </Typography>
                  <Typography variant="caption" sx={{ display: 'block' }}>
                    {entry.action}
                  </Typography>
                  {entry.details && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                      {entry.details}
                    </Typography>
                  )}
                </Box>
              ))}
            </CollapsibleSection>
          </>
        )}

        <Box sx={{ mt: 3, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
          <Typography 
            variant="caption" 
            color="text.secondary"
            sx={{ display: 'block', fontFamily: 'monospace' }}
          >
            ID: {task.id}
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
}
