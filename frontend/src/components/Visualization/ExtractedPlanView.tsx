import { useState, useEffect, useMemo } from 'react';
import { Box, Typography, Chip, Tooltip, Alert, Snackbar, IconButton } from '@mui/material';
import { Add as AddIcon, AddBox as AddBoxIcon, Delete as DeleteIcon, ToggleOn, ToggleOff, AutoFixHigh as AutoFixHighIcon, Edit as EditIcon, ArrowUpward as ArrowUpwardIcon, ArrowDownward as ArrowDownwardIcon, CallMade as CallMadeIcon, Close as CloseIcon, Check as CheckIcon } from '@mui/icons-material';
import ScienceIcon from '@mui/icons-material/Science';
import { Accordion } from '../../design-system/Accordion';
import { CompactIconButton } from '../../design-system/CompactIconButton';
import { MenuItem } from '../../design-system/MenuItem';
import { TextField } from '../../design-system/TextField';
import { Select } from '../../design-system/Select';
import { colors } from '../../design-system/colors';
import { api } from '../../services/api';
import { ConflictResolutionModal } from './ConflictResolutionModal';
import RuleSelectionModal from './RuleSelectionModal';
import { RefinePlanItemModal } from './RefinePlanItemModal';
import ReactMarkdown from 'react-markdown';
import type { EvidenceRecord } from './evidence';
import { getRuleVerificationRecordsForItem } from './evidence';

interface Rule {
  category: string;
  text: string;
  context?: string;
  evidence?: string;
  confidence?: number;
  decay?: number;
  reasoning?: string;
  context_match?: number;
  relevance_score?: number;
  confidence_justification?: string;
  specificity_match?: string;
  original_confidence?: number;
  original_decay?: number;
  needs_strict_enforcement?: boolean;
  is_testable?: boolean;
  kb_item_id?: string;
}

interface RuleConflict {
  conflict_id: string;
  rule_item_ids: string[];
  rule_indices: { [key: string]: number[] };
  explanation: string;
  severity: 'low' | 'medium' | 'high';
  resolved: boolean;
  chosen_rule_index?: number;
  resolved_at?: string;
}

interface InheritedRule {
  rule: Rule;
  source: string;
}

interface PlanItem {
  id?: string;
  number: string;
  title: string;
  description?: string;
  children?: PlanItem[];
  rules?: Rule[];
  inherited_rules?: InheritedRule[];
  conflicts?: RuleConflict[];
  has_unresolved_conflicts?: boolean;
}

interface ExtractedPlan {
  plan: {
    title?: string;
    description?: string;
    items: PlanItem[];
  };
  rules_retrieved?: boolean;
  plan_tracking?: Record<string, string>;
}

interface ExtractedPlanViewProps {
  plan: ExtractedPlan;
  chatId: string;
  evidence?: EvidenceRecord[];
  onPlanUpdate?: (plan: ExtractedPlan) => void;
  onItemSelect?: (itemId: string) => void;
  selectedItemId?: string | null;
  visualization?: any;
}

interface PlanSearchResult {
  itemId: string;
  itemNumber: string;
  itemTitle: string;
  type: 'item' | 'rule' | 'inherited_rule';
  text: string;
  source?: string;
}

type ItemStatus = 'pending' | 'in_progress' | 'completed';

function PlanTreeItem({ 
  item, 
  level, 
  siblingIndex,
  siblingCount,
  parentId,
  tracking,
  onItemSelect,
  selectedItemId,
  chatId,
  evidence = [],
  onPlanUpdate,
  onDeleteItem,
  onMoveItem,
  onAddChild,
  onDeleteRule,
  onAddRule,
  onMoveRule,
  onToggleStrictEnforcement,
  onToggleTestable,
  onRefinePhase
}: {
  item: PlanItem; 
  level: number;
  siblingIndex: number;
  siblingCount: number;
  parentId?: string;
  tracking: Record<string, string>;
  onItemSelect?: (itemId: string) => void;
  selectedItemId?: string | null;
  chatId: string;
  evidence?: EvidenceRecord[];
  onPlanUpdate?: (plan: ExtractedPlan) => void;
  onDeleteItem?: (itemId: string) => void;
  onMoveItem?: (itemId: string, direction: 'up' | 'down') => void;
  onAddChild?: (parentId: string | null, title: string, description: string, position?: number) => void;
  onDeleteRule?: (itemId: string, ruleIndex: number) => void;
  onAddRule?: (itemId: string) => void;
  onMoveRule?: (
    itemId: string,
    ruleIndex: number,
    sourceType: 'own' | 'inherited',
    direction: 'up' | 'down' | 'adopt',
    targetItemId?: string
  ) => void;
  onToggleStrictEnforcement?: (itemId: string, ruleIndex: number, currentlyStrict: boolean) => void;
  onToggleTestable?: (itemId: string, ruleIndex: number, currentlyTestable: boolean) => void;
  onRefinePhase?: (itemId: string) => void;
}) {
  const [conflictModalOpen, setConflictModalOpen] = useState(false);
  const [selectedConflict, setSelectedConflict] = useState<RuleConflict | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newItemTitle, setNewItemTitle] = useState('');
  const [newItemDescription, setNewItemDescription] = useState('');
  const [newItemPosition, setNewItemPosition] = useState<number>(0);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(item.title);
  const [editDescription, setEditDescription] = useState(item.description || '');
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [pendingDownMoveRuleIndex, setPendingDownMoveRuleIndex] = useState<number | null>(null);
  const [pendingDownMoveTargetId, setPendingDownMoveTargetId] = useState<string>('');

  const hasChildren = item.children && item.children.length > 0;
  const numChildren = item.children?.length || 0;
  const hasRules = item.rules && item.rules.length > 0;
  const inheritedRules = item.inherited_rules || [];
  const hasInheritedRules = inheritedRules.length > 0;
  const hasConflicts = item.has_unresolved_conflicts || false;
  const conflicts = item.conflicts || [];
  const unresolvedConflicts = conflicts.filter(c => !c.resolved);
  
  // Get status for this item
  const status = (item.id ? tracking[item.id] : 'pending') as ItemStatus || 'pending';
  
  const getStatusColor = (status: ItemStatus) => {
    switch (status) {
      case 'completed':
        return colors.green;
      case 'in_progress':
        return colors.gold;
      default:
        return colors.grey;
    }
  };

  useEffect(() => {
    if (!isEditing) {
      setEditTitle(item.title);
      setEditDescription(item.description || '');
    }
  }, [item.title, item.description, isEditing]);

  const handleSaveEdit = async () => {
    if (!item.id) return;
    setIsSavingEdit(true);
    try {
      await api.updatePlanItem(chatId, item.id, {
        title: editTitle,
        description: editDescription,
      });
      if (onPlanUpdate) {
        const result = await api.getVisualizationPlan(chatId);
        if (result.success && result.plan) {
          onPlanUpdate(result.plan);
        }
      }
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to update item:', error);
    } finally {
      setIsSavingEdit(false);
    }
  };

  const getStatusIcon = (status: ItemStatus) => {
    switch (status) {
      case 'completed':
        return '✓';
      case 'in_progress':
        return '◐';
      default:
        return '○';
    }
  };
  
  const statusColor = getStatusColor(status);
  const statusIcon = getStatusIcon(status);
  const isSelected = !!item.id && selectedItemId === item.id;
  const completionStats = (() => {
    if (!item.id) return { verifiedRules: 0, testedRules: 0 };
    const allRules = [...(item.rules || []), ...inheritedRules.map((ir) => ir.rule)];
    if (allRules.length === 0) return { verifiedRules: 0, testedRules: 0 };

    let verifiedRules = 0;
    let testedRules = 0;
    for (const rule of allRules) {
      const verifications = getRuleVerificationRecordsForItem(evidence, item.id, rule);
      const hasPass = verifications.some((v) => String(v.verdict || '').toLowerCase() === 'pass');
      const hasPassingTest = verifications.some(
        (v) =>
          String(v.verdict || '').toLowerCase() === 'pass' &&
          !!v.tests &&
          (v.tests.result ? String(v.tests.result).toLowerCase() === 'pass' : true)
      );
      if (hasPass) verifiedRules += 1;
      if (hasPassingTest) testedRules += 1;
    }
    return { verifiedRules, testedRules };
  })();

  const handlePrepareMoveDown = (ruleIndex: number) => {
    const children = item.children || [];
    if (children.length === 0 || !item.id || !onMoveRule) return;

    if (children.length === 1) {
      onMoveRule(item.id, ruleIndex, 'own', 'down', children[0].id);
      return;
    }

    setPendingDownMoveRuleIndex(ruleIndex);
    setPendingDownMoveTargetId(children[0].id || '');
  };

  const handleConfirmMoveDown = (ruleIndex: number) => {
    if (!item.id || !onMoveRule || !pendingDownMoveTargetId) return;
    onMoveRule(item.id, ruleIndex, 'own', 'down', pendingDownMoveTargetId);
    setPendingDownMoveRuleIndex(null);
    setPendingDownMoveTargetId('');
  };

  const handleCancelMoveDown = () => {
    setPendingDownMoveRuleIndex(null);
    setPendingDownMoveTargetId('');
  };

  const handleSubmitNewItem = () => {
    if (newItemTitle.trim() && onAddChild) {
      onAddChild(item.id || null, newItemTitle, newItemDescription, numChildren > 0 ? newItemPosition : undefined);
      setNewItemTitle('');
      setNewItemDescription('');
      setNewItemPosition(0);
      setShowAddForm(false);
    }
  };

  return (
    <Box sx={{ ml: level * 2 }}>
      {hasChildren ? (
        <Accordion
          title={
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                width: '100%',
                borderRadius: 0.75,
                px: 0.5,
                py: 0.2,
                bgcolor: isSelected ? `${colors.green}22` : 'transparent',
              }}
            >
              <span style={{ 
                fontSize: '16px',
                color: statusColor,
                fontWeight: 'bold',
                marginRight: '4px'
              }}>
                {statusIcon}
              </span>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: level === 0 ? 'bold' : level === 1 ? 600 : 'normal',
                  color: isSelected ? colors.darkGreen : colors.green,
                  flex: 1,
                  cursor: item.id && onItemSelect ? 'pointer' : 'default',
                  '&:hover': {
                    textDecoration: item.id && onItemSelect ? 'underline' : 'none',
                  }
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (item.id && onItemSelect) onItemSelect(item.id);
                }}
              >
                {item.number} {item.title}
              </Typography>
              
              {item.id && (
                <Box sx={{ display: 'flex', gap: 0.5, mr: 1 }}>
                  <Tooltip title="Edit item">
                    <IconButton
                      size="small"
                      disableRipple
                      onClick={(e) => {
                        e.stopPropagation();
                        setIsEditing(true);
                      }}
                      sx={{ color: colors.green, padding: '2px', '&:focus': { outline: 'none' } }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  {level === 0 && (
                    <Tooltip title="Refine & enrich substeps">
                      <IconButton
                        size="small"
                        disableRipple
                        onClick={(e) => {
                          e.stopPropagation();
                          onRefinePhase?.(item.id!);
                        }}
                        sx={{ color: colors.green, padding: '2px', '&:focus': { outline: 'none' } }}
                      >
                        <AutoFixHighIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                  
                  <Tooltip title="Add child item">
                    <IconButton
                      size="small"
                      disableRipple
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowAddForm(true);
                      }}
                      sx={{ color: colors.green, padding: '2px', '&:focus': { outline: 'none' } }}
                    >
                      <AddBoxIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  {onMoveItem && (
                    <>
                      <Tooltip title={siblingIndex === 0 ? 'Already first among siblings' : 'Move item up'}>
                        <span>
                          <IconButton
                            size="small"
                            disableRipple
                            disabled={siblingIndex === 0}
                            onClick={(e) => {
                              e.stopPropagation();
                              onMoveItem(item.id!, 'up');
                            }}
                            sx={{ color: colors.grey, padding: '2px', '&:focus': { outline: 'none' } }}
                          >
                            <ArrowUpwardIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip
                        title={
                          siblingIndex >= siblingCount - 1
                            ? 'Already last among siblings'
                            : 'Move item down'
                        }
                      >
                        <span>
                          <IconButton
                            size="small"
                            disableRipple
                            disabled={siblingIndex >= siblingCount - 1}
                            onClick={(e) => {
                              e.stopPropagation();
                              onMoveItem(item.id!, 'down');
                            }}
                            sx={{ color: colors.grey, padding: '2px', '&:focus': { outline: 'none' } }}
                          >
                            <ArrowDownwardIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </>
                  )}
                  
                  <Tooltip title="Delete item">
                    <IconButton
                      size="small"
                      disableRipple
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteItem?.(item.id!);
                      }}
                      sx={{ color: colors.red, padding: '2px', '&:focus': { outline: 'none' } }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              )}
              
              <span style={{
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '4px',
                backgroundColor: statusColor + '20',
                color: statusColor,
                fontWeight: 500,
                textTransform: 'uppercase'
              }}>
                {status.replace('_', ' ')}
              </span>
              {status === 'completed' && (
                <span style={{
                  fontSize: '10px',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  border: `1px solid ${colors.dividerStrong}`,
                  color: colors.strongText,
                  fontWeight: 500,
                  marginLeft: '4px',
                  whiteSpace: 'nowrap'
                }}>
                  Verified {completionStats.verifiedRules} • Tested {completionStats.testedRules}
                </span>
              )}
            </Box>
          }
          defaultOpen={true}
        >
          <Box>
            {isEditing ? (
              <Box sx={{ px: 2, pb: 1 }}>
                <TextField
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  label="Title"
                  fullWidth
                  size="small"
                  sx={{ mb: 1 }}
                />
                <TextField
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  label="Description"
                  fullWidth
                  size="small"
                  multiline
                  minRows={2}
                  sx={{ mb: 1 }}
                />
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  <CompactIconButton
                    label="Save item edits"
                    icon={<CheckIcon sx={{ fontSize: 17 }} />}
                    tone="green"
                    onClick={handleSaveEdit}
                    loading={isSavingEdit}
                  />
                  <CompactIconButton
                    label="Cancel item editing"
                    icon={<CloseIcon sx={{ fontSize: 17 }} />}
                    tone="grey"
                    onClick={() => setIsEditing(false)}
                  />
                </Box>
              </Box>
            ) : (
              item.description && (
                <Box
                  sx={{
                    px: 2,
                    mb: 1,
                    color: 'text.secondary',
                    fontStyle: 'italic',
                    fontSize: '0.75rem',
                    '& p': { margin: 0 },
                  }}
                >
                  <ReactMarkdown>{item.description}</ReactMarkdown>
                </Box>
              )
            )}
            
            {((hasChildren && hasRules) || (!hasChildren && (hasRules || !!item.id))) && (
              <Box sx={{ mt: 1, ml: 3, mb: 2 }}>
                <Accordion
                  title={
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                      <Typography
                        variant="caption"
                        sx={{ fontWeight: 'bold', color: colors.green }}
                      >
                        {hasChildren ? `Rules (${item.rules?.length || 0})` : `Own Rules (${item.rules?.length || 0})`}
                      </Typography>
                      {item.id && onAddRule && (
                        <Tooltip title="Add rule">
                          <IconButton
                            size="small"
                            disableRipple
                            onClick={(e) => {
                              e.stopPropagation();
                              onAddRule(item.id!);
                            }}
                            sx={{ color: colors.green, padding: '2px', '&:focus': { outline: 'none' } }}
                          >
                            <AddIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Box>
                  }
                  defaultOpen={false}
                >
                  <Box sx={{ pl: 2 }}>
                    {(item.rules || []).length === 0 && (
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        {hasChildren ? 'No rules yet.' : 'No own rules yet.'}
                      </Typography>
                    )}
                    {(item.rules || []).map((rule, idx) => (
                      <Box key={idx} sx={{ mb: 2, display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                        <Box sx={{ flex: 1 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5, flexWrap: 'wrap' }}>
                            {rule.needs_strict_enforcement && (
                              <Chip 
                                label="⚡ Strict" 
                                size="small"
                                sx={{ 
                                  bgcolor: colors.green,
                                  color: 'white',
                                  fontWeight: 500,
                                  fontSize: '0.65rem',
                                  height: '18px'
                                }}
                              />
                            )}
                            {rule.is_testable && (
                              <Chip 
                                label="🧪" 
                                size="small"
                                sx={{ 
                                  bgcolor: colors.blue,
                                  color: 'white',
                                  fontWeight: 500,
                                  fontSize: '0.65rem',
                                  height: '18px'
                                }}
                              />
                            )}
                            {item.id && onToggleStrictEnforcement && (
                              <Tooltip title={rule.needs_strict_enforcement ? "Remove strict enforcement" : "Mark for strict enforcement"}>
                                <IconButton
                                  size="small"
                                  disableRipple
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onToggleStrictEnforcement(item.id!, idx, rule.needs_strict_enforcement || false);
                                  }}
                                  sx={{ 
                                    color: rule.needs_strict_enforcement ? colors.green : colors.grey,
                                    padding: '2px',
                                    '&:focus': { outline: 'none' }
                                  }}
                                >
                                  {rule.needs_strict_enforcement ? <ToggleOn fontSize="small" /> : <ToggleOff fontSize="small" />}
                                </IconButton>
                              </Tooltip>
                            )}
                            {item.id && onToggleTestable && (
                              <Tooltip title={!rule.needs_strict_enforcement ? "Mark as strict first to enable testing" : rule.is_testable ? "Remove testable marking" : "Mark as testable (requires test evidence)"}>
                                <span>
                                  <IconButton
                                    size="small"
                                    disableRipple
                                    disabled={!rule.needs_strict_enforcement}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onToggleTestable(item.id!, idx, rule.is_testable || false);
                                    }}
                                    sx={{ 
                                      color: rule.is_testable ? colors.blue : colors.grey,
                                      padding: '2px',
                                      '&:focus': { outline: 'none' },
                                      opacity: !rule.needs_strict_enforcement ? 0.3 : 1
                                    }}
                                  >
                                    <ScienceIcon fontSize="small" />
                                  </IconButton>
                                </span>
                              </Tooltip>
                            )}
                            {item.id && onMoveRule && parentId && (
                              <Tooltip title="Move rule to parent">
                                <IconButton
                                  size="small"
                                  disableRipple
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onMoveRule(item.id!, idx, 'own', 'up');
                                  }}
                                  sx={{ color: colors.grey, padding: '2px', '&:focus': { outline: 'none' } }}
                                >
                                  <ArrowUpwardIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                            {item.id && onMoveRule && hasChildren && (
                              <Tooltip title="Move rule to child">
                                <IconButton
                                  size="small"
                                  disableRipple
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handlePrepareMoveDown(idx);
                                  }}
                                  sx={{ color: colors.grey, padding: '2px', '&:focus': { outline: 'none' } }}
                                >
                                  <ArrowDownwardIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                          </Box>
                          <Typography variant="caption" sx={{ display: 'block', fontWeight: 600 }}>
                            <strong>[{rule.category}]</strong> {rule.text}
                          </Typography>
                        
                          {rule.context && (
                            <Typography
                              variant="caption"
                              sx={{ display: 'block', fontStyle: 'italic', color: 'text.secondary', ml: 1, mt: 0.5, fontSize: '0.7rem' }}
                            >
                              Context: {rule.context}
                            </Typography>
                          )}
                          {rule.evidence && (
                            <Typography
                              variant="caption"
                              sx={{ display: 'block', fontStyle: 'italic', color: 'text.secondary', ml: 1, fontSize: '0.7rem' }}
                            >
                              Evidence: {rule.evidence}
                            </Typography>
                          )}
                          {hasChildren && (item.children?.length || 0) > 1 && pendingDownMoveRuleIndex === idx && (
                            <Box sx={{ mt: 0.25, ml: 1, display: 'flex', gap: 0.5, alignItems: 'center', flexWrap: 'wrap' }}>
                              <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem', lineHeight: 1.1 }}>
                                Move to child:
                              </Typography>
                              <Select
                                size="small"
                                value={pendingDownMoveTargetId}
                                onChange={(e) => setPendingDownMoveTargetId(e.target.value as string)}
                                colorVariant="green"
                                sx={{
                                  minWidth: 130,
                                  '& .MuiInputBase-input': { fontSize: '0.62rem', py: 0.35 }
                                }}
                              >
                                {(item.children || []).map((child) => (
                                  <MenuItem key={child.id || child.number} value={child.id || ''} sx={{ fontSize: '0.62rem', minHeight: '24px' }}>
                                    {child.number} {child.title}
                                  </MenuItem>
                                ))}
                              </Select>
                              <CompactIconButton
                                label="Move rule to selected child"
                                icon={<CheckIcon sx={{ fontSize: 15 }} />}
                                tone="green"
                                onClick={() => handleConfirmMoveDown(idx)}
                                disabled={!pendingDownMoveTargetId}
                                size="small"
                              />
                              <Tooltip title="Cancel move">
                                <IconButton
                                  size="small"
                                  disableRipple
                                  onClick={handleCancelMoveDown}
                                  sx={{ color: colors.grey, padding: '2px', '&:focus': { outline: 'none' } }}
                                >
                                  <CloseIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </Box>
                          )}
                        </Box>
                        {item.id && onDeleteRule && (
                          <Tooltip title="Delete rule">
                            <IconButton
                              size="small"
                              disableRipple
                              onClick={(e) => {
                                e.stopPropagation();
                                onDeleteRule(item.id!, idx);
                              }}
                              sx={{ color: colors.red, padding: '2px', '&:focus': { outline: 'none' } }}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                      </Box>
                    ))}
                  </Box>
                </Accordion>
              </Box>
            )}
            
            {showAddForm && (
              <Box sx={{ mt: 2, ml: 3, p: 2, border: `1px solid ${colors.green}`, borderRadius: 1, bgcolor: 'background.paper' }}>
                <Typography variant="caption" sx={{ display: 'block', fontWeight: 'bold', mb: 1, color: colors.darkGreen }}>
                  Add Child Item
                </Typography>
                <TextField
                  fullWidth
                  size="small"
                  label="Title"
                  value={newItemTitle}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewItemTitle(e.target.value)}
                  sx={{ mb: 1 }}
                  autoFocus
                />
                <TextField
                  fullWidth
                  size="small"
                  label="Description (optional)"
                  value={newItemDescription}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewItemDescription(e.target.value)}
                  multiline
                  rows={2}
                  sx={{ mb: 1 }}
                />
                {numChildren > 0 && (
                  <Select
                    fullWidth
                    size="small"
                    value={newItemPosition}
                    onChange={(e) => setNewItemPosition(e.target.value as number)}
                    sx={{ mb: 1 }}
                    colorVariant="green"
                  >
                    {Array.from({ length: numChildren + 1 }, (_, i) => (
                      <MenuItem key={i} value={i}>
                        Position {i} {i === 0 ? '(first)' : i === numChildren ? '(last)' : ''}
                      </MenuItem>
                    ))}
                  </Select>
                )}
                <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                  <CompactIconButton
                    label="Cancel adding child item"
                    icon={<CloseIcon sx={{ fontSize: 17 }} />}
                    tone="grey"
                    onClick={() => setShowAddForm(false)}
                    size="small"
                  />
                  <CompactIconButton
                    label="Add child item"
                    icon={<AddIcon sx={{ fontSize: 17 }} />}
                    tone="green"
                    onClick={handleSubmitNewItem}
                    disabled={!newItemTitle.trim()}
                    size="small"
                  />
                </Box>
              </Box>
            )}
            
            {item.children?.map((child, i) => (
              <PlanTreeItem 
                key={i} 
                item={child} 
                level={level + 1} 
                siblingIndex={i}
                siblingCount={item.children?.length || 0}
                parentId={item.id}
                tracking={tracking} 
                onItemSelect={onItemSelect}
                selectedItemId={selectedItemId}
                chatId={chatId}
                evidence={evidence}
                onPlanUpdate={onPlanUpdate}
                onDeleteItem={onDeleteItem}
                onMoveItem={onMoveItem}
                onAddChild={onAddChild}
                onDeleteRule={onDeleteRule}
                onAddRule={onAddRule}
                onMoveRule={onMoveRule}
                onToggleStrictEnforcement={onToggleStrictEnforcement}
                onToggleTestable={onToggleTestable}
                onRefinePhase={onRefinePhase}
              />
            ))}
          </Box>
        </Accordion>
      ) : (
        <Box
          onClick={() => item.id && onItemSelect?.(item.id)}
          sx={{
            p: 1,
            pl: 2,
            mb: 0.5,
            borderLeft: `2px solid ${isSelected ? colors.darkGreen : colors.green}`,
            cursor: item.id && onItemSelect ? 'pointer' : 'default',
            backgroundColor: isSelected ? `${colors.green}22` : 'transparent',
            '&:hover': {
              backgroundColor: item.id && onItemSelect ? (isSelected ? `${colors.green}2a` : colors.green + '10') : colors.grey + '10'
            }
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <span style={{ 
              fontSize: '16px',
              color: statusColor,
              fontWeight: 'bold'
            }}>
              {statusIcon}
            </span>
            <Typography variant="body2" sx={{ fontWeight: isSelected ? 700 : 500, flex: 1, color: isSelected ? colors.darkGreen : 'inherit' }}>
              {item.number} {item.title}
            </Typography>
            
            {item.id && (
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <Tooltip title="Edit item">
                  <IconButton
                    size="small"
                    disableRipple
                    onClick={(e) => {
                      e.stopPropagation();
                      setIsEditing(true);
                    }}
                    sx={{ color: colors.green, padding: '2px', '&:focus': { outline: 'none' } }}
                  >
                    <EditIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Add child item">
                  <IconButton
                    size="small"
                    disableRipple
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowAddForm(true);
                    }}
                    sx={{ color: colors.green, padding: '2px', '&:focus': { outline: 'none' } }}
                  >
                    <AddBoxIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                {onMoveItem && (
                  <>
                    <Tooltip title={siblingIndex === 0 ? 'Already first among siblings' : 'Move item up'}>
                      <span>
                        <IconButton
                          size="small"
                          disableRipple
                          disabled={siblingIndex === 0}
                          onClick={(e) => {
                            e.stopPropagation();
                            onMoveItem(item.id!, 'up');
                          }}
                          sx={{ color: colors.grey, padding: '2px', '&:focus': { outline: 'none' } }}
                        >
                          <ArrowUpwardIcon fontSize="small" />
                        </IconButton>
                      </span>
                    </Tooltip>
                    <Tooltip
                      title={
                        siblingIndex >= siblingCount - 1
                          ? 'Already last among siblings'
                          : 'Move item down'
                      }
                    >
                      <span>
                        <IconButton
                          size="small"
                          disableRipple
                          disabled={siblingIndex >= siblingCount - 1}
                          onClick={(e) => {
                            e.stopPropagation();
                            onMoveItem(item.id!, 'down');
                          }}
                          sx={{ color: colors.grey, padding: '2px', '&:focus': { outline: 'none' } }}
                        >
                          <ArrowDownwardIcon fontSize="small" />
                        </IconButton>
                      </span>
                    </Tooltip>
                  </>
                )}
                
                <Tooltip title="Delete item">
                  <IconButton
                    size="small"
                    disableRipple
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteItem?.(item.id!);
                    }}
                    sx={{ color: colors.red, padding: '2px', '&:focus': { outline: 'none' } }}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            )}
            
            <span style={{
              fontSize: '11px',
              padding: '2px 8px',
              borderRadius: '4px',
              backgroundColor: statusColor + '20',
              color: statusColor,
              fontWeight: 500,
              textTransform: 'uppercase'
            }}>
              {status.replace('_', ' ')}
            </span>
            {status === 'completed' && (
              <span style={{
                fontSize: '10px',
                padding: '2px 8px',
                borderRadius: '4px',
                border: `1px solid ${colors.dividerStrong}`,
                color: colors.strongText,
                fontWeight: 500,
                marginLeft: '4px',
                whiteSpace: 'nowrap'
              }}>
                Verified {completionStats.verifiedRules} • Tested {completionStats.testedRules}
              </span>
            )}
          </Box>
          {isEditing ? (
            <Box sx={{ mt: 1, ml: 3 }}>
              <TextField
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                label="Title"
                fullWidth
                size="small"
                sx={{ mb: 1 }}
              />
              <TextField
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                label="Description"
                fullWidth
                size="small"
                multiline
                minRows={2}
                sx={{ mb: 1 }}
              />
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <CompactIconButton
                  label="Save item edits"
                  icon={<CheckIcon sx={{ fontSize: 17 }} />}
                  tone="green"
                  onClick={handleSaveEdit}
                  loading={isSavingEdit}
                />
                <CompactIconButton
                  label="Cancel item editing"
                  icon={<CloseIcon sx={{ fontSize: 17 }} />}
                  tone="grey"
                  onClick={() => setIsEditing(false)}
                />
              </Box>
            </Box>
          ) : (
            item.description && (
              <Box
                sx={{
                  mt: 0.5,
                  ml: 3,
                  color: 'text.secondary',
                  fontStyle: 'italic',
                  fontSize: '0.75rem',
                  '& p': { margin: 0 },
                }}
              >
                <ReactMarkdown>{item.description}</ReactMarkdown>
              </Box>
            )
          )}
          
          {((hasChildren && hasRules) || (!hasChildren && (hasRules || !!item.id))) && (
            <Box sx={{ mt: 1, ml: 3 }}>
                <Accordion
                  title={
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                      <Typography
                        variant="caption"
                        sx={{ fontWeight: 'bold', color: colors.green }}
                      >
                        {hasChildren ? `Rules (${item.rules?.length || 0})` : `Own Rules (${item.rules?.length || 0})`}
                      </Typography>
                      {item.id && onAddRule && (
                        <Tooltip title="Add rule">
                          <IconButton
                            size="small"
                            disableRipple
                            onClick={(e) => {
                              e.stopPropagation();
                              onAddRule(item.id!);
                            }}
                            sx={{ color: colors.green, padding: '2px', '&:focus': { outline: 'none' } }}
                          >
                            <AddIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Box>
                  }
                  defaultOpen={false}
                >
                <Box sx={{ pl: 2 }}>
                  {(item.rules || []).length === 0 && (
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      {hasChildren ? 'No rules yet.' : 'No own rules yet.'}
                    </Typography>
                  )}
                  {(item.rules || []).map((rule, idx) => (
                    <Box key={idx} sx={{ mb: 2, display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                      <Box sx={{ flex: 1 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5, flexWrap: 'wrap' }}>
                            {rule.needs_strict_enforcement && (
                              <Chip 
                                label="⚡ Strict" 
                                size="small"
                                sx={{ 
                                  bgcolor: colors.green,
                                  color: 'white',
                                  fontWeight: 500,
                                  fontSize: '0.65rem',
                                  height: '18px'
                                }}
                              />
                            )}
                            {rule.is_testable && (
                              <Chip 
                                label="🧪" 
                                size="small"
                                sx={{ 
                                  bgcolor: colors.blue,
                                  color: 'white',
                                  fontWeight: 500,
                                  fontSize: '0.65rem',
                                  height: '18px'
                                }}
                              />
                            )}
                            {item.id && onToggleStrictEnforcement && (
                              <Tooltip title={rule.needs_strict_enforcement ? "Remove strict enforcement" : "Mark for strict enforcement"}>
                                <IconButton
                                  size="small"
                                  disableRipple
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onToggleStrictEnforcement(item.id!, idx, rule.needs_strict_enforcement || false);
                                  }}
                                  sx={{ 
                                    color: rule.needs_strict_enforcement ? colors.green : colors.grey,
                                    padding: '2px',
                                    '&:focus': { outline: 'none' }
                                  }}
                                >
                                  {rule.needs_strict_enforcement ? <ToggleOn fontSize="small" /> : <ToggleOff fontSize="small" />}
                                </IconButton>
                              </Tooltip>
                            )}
                            {item.id && onToggleTestable && (
                              <Tooltip title={!rule.needs_strict_enforcement ? "Mark as strict first to enable testing" : rule.is_testable ? "Remove testable marking" : "Mark as testable (requires test evidence)"}>
                                <span>
                                  <IconButton
                                    size="small"
                                    disableRipple
                                    disabled={!rule.needs_strict_enforcement}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onToggleTestable(item.id!, idx, rule.is_testable || false);
                                    }}
                                    sx={{ 
                                      color: rule.is_testable ? colors.blue : colors.grey,
                                      padding: '2px',
                                      '&:focus': { outline: 'none' },
                                      opacity: !rule.needs_strict_enforcement ? 0.3 : 1
                                    }}
                                  >
                                    <ScienceIcon fontSize="small" />
                                  </IconButton>
                                </span>
                              </Tooltip>
                            )}
                            {item.id && onMoveRule && parentId && (
                              <Tooltip title="Move rule to parent">
                                <IconButton
                                  size="small"
                                  disableRipple
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onMoveRule(item.id!, idx, 'own', 'up');
                                  }}
                                  sx={{ color: colors.grey, padding: '2px', '&:focus': { outline: 'none' } }}
                                >
                                  <ArrowUpwardIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                            {item.id && onMoveRule && hasChildren && (
                              <Tooltip title="Move rule to child">
                                <IconButton
                                  size="small"
                                  disableRipple
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handlePrepareMoveDown(idx);
                                  }}
                                  sx={{ color: colors.grey, padding: '2px', '&:focus': { outline: 'none' } }}
                                >
                                  <ArrowDownwardIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                          </Box>
                          <Typography variant="caption" sx={{ display: 'block', fontWeight: 600 }}>
                            <strong>[{rule.category}]</strong> {rule.text}
                          </Typography>
                      
                          {rule.context && (
                            <Typography
                              variant="caption"
                              sx={{ display: 'block', fontStyle: 'italic', color: 'text.secondary', ml: 1, mt: 0.5, fontSize: '0.7rem' }}
                            >
                              Context: {rule.context}
                            </Typography>
                          )}
                          {rule.evidence && (
                            <Typography
                              variant="caption"
                              sx={{ display: 'block', fontStyle: 'italic', color: 'text.secondary', ml: 1, fontSize: '0.7rem' }}
                            >
                              Evidence: {rule.evidence}
                            </Typography>
                          )}
                          {hasChildren && (item.children?.length || 0) > 1 && pendingDownMoveRuleIndex === idx && (
                            <Box sx={{ mt: 0.25, ml: 1, display: 'flex', gap: 0.5, alignItems: 'center', flexWrap: 'wrap' }}>
                              <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem', lineHeight: 1.1 }}>
                                Move to child:
                              </Typography>
                              <Select
                                size="small"
                                value={pendingDownMoveTargetId}
                                onChange={(e) => setPendingDownMoveTargetId(e.target.value as string)}
                                colorVariant="green"
                                sx={{
                                  minWidth: 130,
                                  '& .MuiInputBase-input': { fontSize: '0.62rem', py: 0.35 }
                                }}
                              >
                                {(item.children || []).map((child) => (
                                  <MenuItem key={child.id || child.number} value={child.id || ''} sx={{ fontSize: '0.62rem', minHeight: '24px' }}>
                                    {child.number} {child.title}
                                  </MenuItem>
                                ))}
                              </Select>
                              <CompactIconButton
                                label="Move rule to selected child"
                                icon={<CheckIcon sx={{ fontSize: 15 }} />}
                                tone="green"
                                onClick={() => handleConfirmMoveDown(idx)}
                                disabled={!pendingDownMoveTargetId}
                                size="small"
                              />
                              <Tooltip title="Cancel move">
                                <IconButton
                                  size="small"
                                  disableRipple
                                  onClick={handleCancelMoveDown}
                                  sx={{ color: colors.grey, padding: '2px', '&:focus': { outline: 'none' } }}
                                >
                                  <CloseIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </Box>
                          )}
                        </Box>
                        {item.id && onDeleteRule && (
                          <Tooltip title="Delete rule">
                            <IconButton
                              size="small"
                              disableRipple
                              onClick={(e) => {
                                e.stopPropagation();
                                onDeleteRule(item.id!, idx);
                              }}
                              sx={{ color: colors.red, padding: '2px', '&:focus': { outline: 'none' } }}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                      </Box>
                    ))}
                </Box>
              </Accordion>
            </Box>
          )}
          
          {hasInheritedRules && (
            <Box sx={{ mt: 1, ml: 3 }}>
              <Accordion
                title={
                  <Typography
                    variant="caption"
                    sx={{ fontWeight: 'bold', color: colors.grey }}
                  >
                    Inherited Rules ({inheritedRules.length})
                  </Typography>
                }
                defaultOpen={false}
              >
                <Box
                  sx={{
                    pl: 2,
                    borderLeft: `2px solid ${colors.grey}`,
                    backgroundColor: colors.grey + '15'
                  }}
                >
                  {inheritedRules.map((r, idx) => (
                    <Box key={idx} sx={{ mb: 1, display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                      <Box sx={{ flex: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5, flexWrap: 'wrap' }}>
                        {r.rule.needs_strict_enforcement && (
                          <Chip 
                            label="⚡ Strict" 
                            size="small"
                            sx={{ 
                              bgcolor: colors.green,
                              color: 'white',
                              fontWeight: 500,
                              fontSize: '0.65rem',
                              height: '18px'
                            }}
                          />
                        )}
                        {item.id && onMoveRule && (
                          <Tooltip title="Adopt to own rules">
                            <IconButton
                              size="small"
                              disableRipple
                              onClick={(e) => {
                                e.stopPropagation();
                                onMoveRule(item.id!, idx, 'inherited', 'adopt');
                              }}
                              sx={{ color: colors.grey, padding: '2px', '&:focus': { outline: 'none' } }}
                            >
                              <CallMadeIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                      </Box>
                      <Typography variant="caption" sx={{ display: 'block' }}>
                        <strong>[{r.rule.category}]</strong> {r.rule.text}
                        <span style={{ color: colors.grey, marginLeft: 8, fontSize: '10px' }}>
                          (from {r.source})
                        </span>
                      </Typography>
                      {r.rule.context && (
                        <Typography
                          variant="caption"
                          sx={{ display: 'block', fontStyle: 'italic', color: 'text.secondary', ml: 1 }}
                        >
                          Context: {r.rule.context}
                        </Typography>
                      )}
                      </Box>
                    </Box>
                  ))}
                </Box>
              </Accordion>
            </Box>
          )}
          
          {hasConflicts && unresolvedConflicts.length > 0 && (
            <Box sx={{ mt: 2, ml: 3 }}>
              <Box sx={{ 
                p: 2, 
                bgcolor: `${colors.red}20`, 
                borderRadius: 1,
                border: `1px solid ${colors.red}`
              }}>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <Typography variant="caption" sx={{ fontWeight: 'bold', color: colors.red }}>
                    ⚠️ RULE CONFLICTS DETECTED ({unresolvedConflicts.length})
                  </Typography>
                </Box>
                <Typography variant="caption" display="block" sx={{ color: 'text.secondary', mb: 2 }}>
                  This item has conflicting rules. Resolve them before starting or completing this item.
                </Typography>
                
                {unresolvedConflicts.map((conflict, idx) => (
                  <Box key={conflict.conflict_id} sx={{ mb: 2 }}>
                    <Box display="flex" alignItems="center" gap={1} mb={1}>
                      <Chip
                        label={conflict.severity.toUpperCase()}
                        size="small"
                        sx={{
                          bgcolor: conflict.severity === 'high' ? colors.red : 
                                  conflict.severity === 'medium' ? colors.gold : colors.blue,
                          color: colors.white,
                          fontSize: '0.7rem',
                          height: '18px'
                        }}
                      />
                      <Typography variant="caption" sx={{ fontWeight: 'bold' }}>
                        Conflict {idx + 1}
                      </Typography>
                    </Box>
                    <Typography variant="caption" display="block" sx={{ mb: 1, ml: 1 }}>
                      {conflict.explanation}
                    </Typography>
                    <Box sx={{ ml: 1, mt: 1 }}>
                      <CompactIconButton
                        label="Resolve conflict"
                        icon={<AutoFixHighIcon sx={{ fontSize: 17 }} />}
                        tone="red"
                        onClick={() => {
                          setSelectedConflict(conflict);
                          setConflictModalOpen(true);
                        }}
                        size="small"
                      />
                    </Box>
                  </Box>
                ))}
              </Box>
            </Box>
          )}
          
          {showAddForm && (
            <Box sx={{ mt: 2, ml: 3, p: 2, border: `1px solid ${colors.green}`, borderRadius: 1, bgcolor: 'background.paper' }}>
              <Typography variant="caption" sx={{ display: 'block', fontWeight: 'bold', mb: 1, color: colors.darkGreen }}>
                Add Child Item
              </Typography>
              <TextField
                fullWidth
                size="small"
                label="Title"
                value={newItemTitle}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewItemTitle(e.target.value)}
                sx={{ mb: 1 }}
                autoFocus
              />
              <TextField
                fullWidth
                size="small"
                label="Description (optional)"
                value={newItemDescription}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewItemDescription(e.target.value)}
                multiline
                rows={2}
                sx={{ mb: 1 }}
              />
              {numChildren > 0 && (
                <Select
                  fullWidth
                  size="small"
                  value={newItemPosition}
                  onChange={(e) => setNewItemPosition(e.target.value as number)}
                  sx={{ mb: 1 }}
                  colorVariant="green"
                >
                  {Array.from({ length: numChildren + 1 }, (_, i) => (
                    <MenuItem key={i} value={i}>
                      Position {i} {i === 0 ? '(first)' : i === numChildren ? '(last)' : ''}
                    </MenuItem>
                  ))}
                </Select>
              )}
              <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                <CompactIconButton
                  label="Cancel adding child item"
                  icon={<CloseIcon sx={{ fontSize: 17 }} />}
                  tone="grey"
                  onClick={() => setShowAddForm(false)}
                  size="small"
                />
                <CompactIconButton
                  label="Add child item"
                  icon={<AddIcon sx={{ fontSize: 17 }} />}
                  tone="green"
                  onClick={handleSubmitNewItem}
                  disabled={!newItemTitle.trim()}
                  size="small"
                />
              </Box>
            </Box>
          )}
        </Box>
      )}
      
      {selectedConflict && item.rules && (
        <ConflictResolutionModal
          open={conflictModalOpen}
          onClose={() => {
            setConflictModalOpen(false);
            setSelectedConflict(null);
          }}
          chatId={chatId}
          itemId={item.id || ''}
          conflict={selectedConflict}
          rules={item.rules}
          onResolved={async () => {
            if (onPlanUpdate) {
              try {
                const result = await api.getVisualizationPlan(chatId);
                if (result.success && result.plan) {
                  onPlanUpdate(result.plan);
                }
              } catch (error) {
                console.error('Failed to refresh plan:', error);
              }
            }
          }}
        />
      )}
    </Box>
  );
}

export function ExtractedPlanView({ plan, chatId, evidence = [], onPlanUpdate, onItemSelect, selectedItemId, visualization }: ExtractedPlanViewProps) {
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [targetItemId, setTargetItemId] = useState<string>('');
  const [refineModalOpen, setRefineModalOpen] = useState(false);
  const [selectedPhase, setSelectedPhase] = useState<PlanItem | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' });
  const [isEditingPlan, setIsEditingPlan] = useState(false);
  const [planTitleDraft, setPlanTitleDraft] = useState(plan.plan.title || '');
  const [planDescDraft, setPlanDescDraft] = useState((plan.plan as any).description || '');
  const [isSavingPlan, setIsSavingPlan] = useState(false);
  const [planSearchQuery, setPlanSearchQuery] = useState('');

  // Reset button state when plan changes (e.g., after re-extraction)
  useEffect(() => {
    setPlanTitleDraft(plan.plan.title || '');
    setPlanDescDraft((plan.plan as any).description || '');
  }, [plan]);

  const refreshPlan = async () => {
    try {
      const result = await api.getVisualizationPlan(chatId);
      if (result.success && result.plan && onPlanUpdate) {
        onPlanUpdate(result.plan);
      }
    } catch (error) {
      console.error('Failed to refresh plan:', error);
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    try {
      await api.deletePlanItem(chatId, itemId);
      setSnackbar({ open: true, message: 'Item deleted successfully', severity: 'success' });
      await refreshPlan();
    } catch (error) {
      console.error('Failed to delete item:', error);
      setSnackbar({ open: true, message: 'Failed to delete item', severity: 'error' });
    }
  };

  const handleMoveItem = async (itemId: string, direction: 'up' | 'down') => {
    try {
      await api.movePlanItem(chatId, itemId, direction);
      setSnackbar({
        open: true,
        message: `Item moved ${direction} successfully`,
        severity: 'success',
      });
      await refreshPlan();
    } catch (error) {
      console.error('Failed to move item:', error);
      setSnackbar({
        open: true,
        message: `Failed to move item ${direction}`,
        severity: 'error',
      });
    }
  };

  const handleAddChildItem = async (parentId: string | null, title: string, description: string, position?: number) => {
    try {
      await api.addPlanItem(chatId, {
        parent_id: parentId || undefined,
        title,
        description,
        position
      });
      setSnackbar({ open: true, message: 'Item added successfully', severity: 'success' });
      await refreshPlan();
    } catch (error) {
      console.error('Failed to add item:', error);
      setSnackbar({ open: true, message: 'Failed to add item', severity: 'error' });
    }
  };

  const handleDeleteRule = async (itemId: string, ruleIndex: number) => {
    try {
      await api.deletePlanItemRule(chatId, itemId, ruleIndex);
      setSnackbar({ open: true, message: 'Rule deleted successfully', severity: 'success' });
      await refreshPlan();
    } catch (error) {
      console.error('Failed to delete rule:', error);
      setSnackbar({ open: true, message: 'Failed to delete rule', severity: 'error' });
    }
  };

  const handleAddRule = async (itemId: string, rule: any) => {
    try {
      await api.addPlanItemRule(chatId, itemId, {
        kb_item_id: rule.item_id
      });
      setSnackbar({ open: true, message: 'Rule added successfully', severity: 'success' });
      await refreshPlan();
    } catch (error) {
      console.error('Failed to add rule:', error);
      setSnackbar({ open: true, message: 'Failed to add rule', severity: 'error' });
    }
  };

  const handleMoveRule = async (
    itemId: string,
    ruleIndex: number,
    sourceType: 'own' | 'inherited',
    direction: 'up' | 'down' | 'adopt',
    targetItemId?: string
  ) => {
    try {
      await api.movePlanItemRule(chatId, itemId, ruleIndex, {
        source_type: sourceType,
        direction,
        target_item_id: targetItemId
      });
      setSnackbar({ open: true, message: 'Rule moved successfully', severity: 'success' });
      await refreshPlan();
    } catch (error) {
      console.error('Failed to move rule:', error);
      setSnackbar({ open: true, message: 'Failed to move rule', severity: 'error' });
    }
  };

  const handleToggleStrictEnforcement = async (itemId: string, ruleIndex: number, currentlyStrict: boolean) => {
    try {
      await api.toggleRuleStrictEnforcement(chatId, itemId, ruleIndex, !currentlyStrict);
      
      // If turning off strict, also turn off testable
      if (currentlyStrict) {
        try {
          await api.toggleRuleTestable(chatId, itemId, ruleIndex, false);
        } catch (error) {
          console.error('Failed to auto-uncheck testable:', error);
        }
      }
      
      setSnackbar({ 
        open: true, 
        message: !currentlyStrict ? 'Rule marked for strict enforcement' : 'Strict enforcement removed',
        severity: 'success' 
      });
      await refreshPlan();
    } catch (error) {
      console.error('Failed to toggle strict enforcement:', error);
      setSnackbar({ open: true, message: 'Failed to toggle strict enforcement', severity: 'error' });
    }
  };

  const handleToggleTestable = async (itemId: string, ruleIndex: number, currentlyTestable: boolean) => {
    try {
      await api.toggleRuleTestable(chatId, itemId, ruleIndex, !currentlyTestable);
      setSnackbar({ 
        open: true, 
        message: !currentlyTestable ? 'Rule marked as testable' : 'Testable marking removed',
        severity: 'success' 
      });
      await refreshPlan();
    } catch (error) {
      console.error('Failed to toggle testable:', error);
      setSnackbar({ open: true, message: 'Failed to toggle testable', severity: 'error' });
    }
  };

  const openRuleModal = (itemId: string) => {
    setTargetItemId(itemId);
    setRuleModalOpen(true);
  };

  const handleRefinePhase = (itemId: string) => {
    const findPhase = (items: PlanItem[]): PlanItem | null => {
      for (const item of items) {
        if (item.id === itemId) {
          return item;
        }
        if (item.children) {
          const found = findPhase(item.children);
          if (found) return found;
        }
      }
      return null;
    };
    
    const phase = findPhase(plan.plan.items);
    if (phase) {
      setSelectedPhase(phase);
      setRefineModalOpen(true);
    }
  };

  const handleSavePlanMeta = async () => {
    setIsSavingPlan(true);
    try {
      await api.updateVisualizationPlan(chatId, {
        title: planTitleDraft,
        description: planDescDraft,
      });
      if (onPlanUpdate) {
        const result = await api.getVisualizationPlan(chatId);
        if (result.success && result.plan) {
          onPlanUpdate(result.plan);
        }
      }
      setIsEditingPlan(false);
    } catch (error) {
      console.error('Failed to update plan metadata:', error);
    } finally {
      setIsSavingPlan(false);
    }
  };

  const rootItems = plan.plan.items || [];
  const hasRenderablePlan =
    rootItems.length > 0 || Boolean(plan.plan.title) || Boolean(plan.plan.description);

  const planSearchResults = useMemo(() => {
    const query = planSearchQuery.trim().toLowerCase();
    if (!query) return [];

    const results: PlanSearchResult[] = [];
    const walk = (items: PlanItem[]) => {
      for (const item of items || []) {
        if (!item.id) {
          if (item.children?.length) walk(item.children);
          continue;
        }

        const itemLabel = `${item.number} ${item.title}`.toLowerCase();
        const itemDesc = (item.description || '').toLowerCase();
        if (itemLabel.includes(query) || itemDesc.includes(query)) {
          results.push({
            itemId: item.id,
            itemNumber: item.number,
            itemTitle: item.title,
            type: 'item',
            text: item.description || item.title,
          });
        }

        for (const rule of item.rules || []) {
          const haystack = [
            rule.category || '',
            rule.text || '',
            rule.context || '',
            rule.evidence || '',
          ].join(' ').toLowerCase();
          if (haystack.includes(query)) {
            results.push({
              itemId: item.id,
              itemNumber: item.number,
              itemTitle: item.title,
              type: 'rule',
              text: `[${rule.category}] ${rule.text}`,
            });
          }
        }

        for (const inherited of item.inherited_rules || []) {
          const rule = inherited.rule;
          const haystack = [
            rule.category || '',
            rule.text || '',
            rule.context || '',
            rule.evidence || '',
            inherited.source || '',
          ].join(' ').toLowerCase();
          if (haystack.includes(query)) {
            results.push({
              itemId: item.id,
              itemNumber: item.number,
              itemTitle: item.title,
              type: 'inherited_rule',
              text: `[${rule.category}] ${rule.text}`,
              source: inherited.source,
            });
          }
        }

        if (item.children?.length) walk(item.children);
      }
    };

    walk(rootItems);
    return results.slice(0, 50);
  }, [planSearchQuery, rootItems]);

  // Get tracking from visualization prop or plan itself
  const tracking = visualization?.plan_tracking || plan.plan_tracking || {};

  return (
    <>
      <Accordion
        title={
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
            <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
              Enriched Plan
            </Typography>
          </Box>
        }
        defaultOpen={true}
      >
        <Box sx={{ px: 2, pt: 1.25 }}>
          {!hasRenderablePlan ? (
            <Box
              sx={{
                py: 2,
                px: 1,
                border: '1px dashed',
                borderColor: colors.divider,
                borderRadius: 1,
                bgcolor: colors.surfaceSubtle,
              }}
            >
              <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: colors.darkGreen, mb: 0.3 }}>
                No extracted plan yet
              </Typography>
              <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>
                Extract a plan for this session to populate the workflow view.
              </Typography>
            </Box>
          ) : (
            <>
          <Box sx={{ mb: 2 }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search plan steps and rules..."
              value={planSearchQuery}
              onChange={(e) => setPlanSearchQuery(e.target.value)}
            />
            {planSearchQuery.trim() && (
              <Box
                sx={{
                  mt: 1,
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  maxHeight: 220,
                  overflow: 'auto',
                  bgcolor: 'background.paper',
                }}
              >
                {planSearchResults.length === 0 ? (
                  <Typography sx={{ px: 1.5, py: 1, fontSize: '0.72rem', color: 'text.secondary' }}>
                    No matches found
                  </Typography>
                ) : (
                  planSearchResults.map((result, idx) => (
                    <Box
                      key={`${result.itemId}-${result.type}-${idx}`}
                      onClick={() => onItemSelect?.(result.itemId)}
                      sx={{
                        px: 1.5,
                        py: 0.9,
                        borderBottom: idx < planSearchResults.length - 1 ? '1px solid' : 'none',
                        borderColor: 'divider',
                        cursor: 'pointer',
                        '&:hover': { bgcolor: `${colors.green}14` },
                      }}
                    >
                      <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: colors.darkGreen }}>
                        {result.itemNumber} {result.itemTitle}
                      </Typography>
                      <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary' }}>
                        {result.type === 'item' ? 'Step' : result.type === 'rule' ? 'Rule' : `Inherited rule (${result.source})`}
                        {' • '}
                        {result.text}
                      </Typography>
                    </Box>
                  ))
                )}
              </Box>
            )}
          </Box>

          {isEditingPlan ? (
            <Box sx={{ mb: 2 }}>
              <TextField
                value={planTitleDraft}
                onChange={(e) => setPlanTitleDraft(e.target.value)}
                label="Plan Title"
                fullWidth
                size="small"
                sx={{ mb: 1 }}
              />
              <TextField
                value={planDescDraft}
                onChange={(e) => setPlanDescDraft(e.target.value)}
                label="Plan Description"
                fullWidth
                size="small"
                multiline
                minRows={2}
                sx={{ mb: 1 }}
              />
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <CompactIconButton
                  label="Save plan metadata"
                  icon={<CheckIcon sx={{ fontSize: 17 }} />}
                  tone="green"
                  onClick={handleSavePlanMeta}
                  loading={isSavingPlan}
                />
                <CompactIconButton
                  label="Cancel plan metadata editing"
                  icon={<CloseIcon sx={{ fontSize: 17 }} />}
                  tone="grey"
                  onClick={() => setIsEditingPlan(false)}
                />
              </Box>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: plan.plan.description ? 1 : 0.25 }}>
              <Box>
                {plan.plan.description && (
                  <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                    {plan.plan.description}
                  </Typography>
                )}
              </Box>
            </Box>
          )}

          <Box>
            {rootItems.map((item, i) => (
              <PlanTreeItem 
                key={i} 
                item={item} 
                level={0} 
                siblingIndex={i}
                siblingCount={rootItems.length}
                parentId={undefined}
                tracking={tracking} 
                onItemSelect={onItemSelect}
                selectedItemId={selectedItemId}
                chatId={chatId}
                evidence={evidence}
                onPlanUpdate={onPlanUpdate}
                onDeleteItem={handleDeleteItem}
                onMoveItem={handleMoveItem}
                onAddChild={handleAddChildItem}
                onDeleteRule={handleDeleteRule}
                onAddRule={openRuleModal}
                onMoveRule={handleMoveRule}
                onToggleStrictEnforcement={handleToggleStrictEnforcement}
                onToggleTestable={handleToggleTestable}
                onRefinePhase={handleRefinePhase}
              />
            ))}
          </Box>
            </>
          )}
        </Box>
      </Accordion>

      <RuleSelectionModal
        open={ruleModalOpen}
        onClose={() => setRuleModalOpen(false)}
        onSelectRule={(rule) => {
          handleAddRule(targetItemId, rule);
          setRuleModalOpen(false);
        }}
      />

      <RefinePlanItemModal
        open={refineModalOpen}
        onClose={() => {
          setRefineModalOpen(false);
          setSelectedPhase(null);
        }}
        itemTitle={selectedPhase?.title || ''}
        onSubmit={async (guidance) => {
          if (!selectedPhase?.id) return;
          try {
            await api.refineSubsteps(chatId, selectedPhase.id, guidance);
            setSnackbar({ open: true, message: 'Substeps refined successfully', severity: 'success' });
            await refreshPlan();
          } catch (error) {
            console.error('Failed to refine substeps:', error);
            setSnackbar({ open: true, message: 'Failed to refine substeps', severity: 'error' });
          }
        }}
      />

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert 
          severity={snackbar.severity} 
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </>
  );
}
