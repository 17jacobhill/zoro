import { useState, useEffect } from 'react';
import { Box, Typography, Stack, Chip, CircularProgress, IconButton, Checkbox, MenuItem, Dialog, DialogTitle, DialogContent, DialogActions, Collapse } from '@mui/material';
import { Close as CloseIcon, Add as AddIcon, Delete as DeleteIcon, ExpandMore as ExpandMoreIcon, Refresh as RefreshIcon } from '@mui/icons-material';
import { TextField } from '../../design-system/TextField';
import { Button } from '../../design-system/Button';
import { colors } from '../../design-system/colors';
import { api } from '../../services/api';

interface Requirement {
  id: string;
  description: string;
  category: 'feature' | 'rule' | 'integration' | 'edge';
  source: 'auto' | 'user';
}

interface FileSummary {
  path: string;
  lines_changed: string;
  changes: string;
  impact: string;
  substeps_fulfilled: string[];
}

interface CodeBlock {
  file: string;
  lines: string;
  code: string;
  annotation: string;
}

interface RequirementVerification {
  requirement_id: string;
  verdict: 'pass' | 'fail' | 'unclear';
  evidence: string;
  files_changed: FileSummary[];
  code_changed: CodeBlock[];
}

interface RequirementTest {
  requirement_id: string;
  test_name: string;
  test_description: string;
  test_code: string;
  status: 'pass' | 'fail' | 'error';
  output: string;
}

interface EnforcementPanelV2Props {
  chatId: string;
  nodeId: string;
  targetId: string;
  onClose: () => void;
}

export function EnforcementPanelV2({ chatId, nodeId, targetId, onClose }: EnforcementPanelV2Props) {
  // State
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [verifications, setVerifications] = useState<RequirementVerification[]>([]);
  const [tests, setTests] = useState<RequirementTest[]>([]);
  const [overallVerdict, setOverallVerdict] = useState<'done' | 'partial' | 'not_done'>('not_done');
  
  // Selection state
  const [selectedRequirementIds, setSelectedRequirementIds] = useState<Set<string>>(new Set());
  
  // Expand/collapse evidence state
  const [expandedEvidenceIds, setExpandedEvidenceIds] = useState<Set<string>>(new Set());
  
  // Expand/collapse tests state
  const [expandedTestIds, setExpandedTestIds] = useState<Set<string>>(new Set());
  
  // Add requirement form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newReqDescription, setNewReqDescription] = useState('');
  const [newReqCategory, setNewReqCategory] = useState<'feature' | 'rule' | 'integration' | 'edge' | ''>('');
  const [addingRequirement, setAddingRequirement] = useState(false);
  
  // Delete confirmation dialog state
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deletingRequirements, setDeletingRequirements] = useState(false);
  
  // Loading states
  const [listingRequirements, setListingRequirements] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [testing, setTesting] = useState(false);
  
  // Step-level verification state
  const [stepVerifying, setStepVerifying] = useState(false);
  const [stepVerifyError, setStepVerifyError] = useState<string | null>(null);
  const [stepVerification, setStepVerification] = useState<any>(null);
  
  // Cache state
  const [isCached, setIsCached] = useState(false);
  const [cacheTime, setCacheTime] = useState<string | null>(null);
  
  // Error states
  const [listError, setListError] = useState<string | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Enable/disable logic
  const hasRequirements = requirements.length > 0;
  const hasSelection = selectedRequirementIds.size > 0;
  const hasVerifications = verifications.length > 0;
  const canVerify = hasSelection && !listingRequirements;
  
  // Check if all SELECTED requirements have verifications
  const allSelectedHaveVerifications = hasSelection && Array.from(selectedRequirementIds).every(reqId => 
    verifications.some(v => v.requirement_id === reqId)
  );
  
  const canTest = allSelectedHaveVerifications && !verifying;

  // Load existing record on mount and when props change
  useEffect(() => {
    // Reset all state first
    setRequirements([]);
    setVerifications([]);
    setTests([]);
    setOverallVerdict('not_done');
    setExpandedEvidenceIds(new Set());
    setExpandedTestIds(new Set());
    setListError(null);
    setVerifyError(null);
    setTestError(null);
    setAddError(null);
    setDeleteError(null);
    setIsCached(false);
    setCacheTime(null);
    setStepVerification(null);
    setStepVerifyError(null);
    
    // Then load fresh data
    loadExistingRecord();
  }, [chatId, nodeId, targetId]);

  // Reset selection when props change
  useEffect(() => {
    setSelectedRequirementIds(new Set());
  }, [chatId, nodeId, targetId]);

  const handleToggleRequirement = (reqId: string) => {
    setSelectedRequirementIds(prev => {
      const next = new Set(prev);
      if (next.has(reqId)) {
        next.delete(reqId);
      } else {
        next.add(reqId);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    setSelectedRequirementIds(new Set(requirements.map(r => r.id)));
  };

  const handleDeselectAll = () => {
    setSelectedRequirementIds(new Set());
  };

  const handleToggleEvidence = (reqId: string) => {
    setExpandedEvidenceIds(prev => {
      const next = new Set(prev);
      if (next.has(reqId)) {
        next.delete(reqId);
      } else {
        next.add(reqId);
      }
      return next;
    });
  };

  const handleToggleTests = (reqId: string) => {
    setExpandedTestIds(prev => {
      const next = new Set(prev);
      if (next.has(reqId)) {
        next.delete(reqId);
      } else {
        next.add(reqId);
      }
      return next;
    });
  };

  const handleShowAddForm = () => {
    setShowAddForm(true);
  };

  const handleShowDeleteDialog = () => {
    setShowDeleteDialog(true);
  };

  const handleCloseDeleteDialog = () => {
    setShowDeleteDialog(false);
    setDeleteError(null);
  };

  const handleConfirmDelete = async () => {
    setDeletingRequirements(true);
    setDeleteError(null);

    const idsToDelete = Array.from(selectedRequirementIds);
    const errors: string[] = [];

    for (const reqId of idsToDelete) {
      try {
        const data = await api.deleteRequirementV2({
          chat_id: chatId,
          node_id: nodeId,
          target_id: targetId,
          requirement_id: reqId,
        });

        if (!data.success) {
          errors.push(`${reqId}: ${data.error || 'Unknown error'}`);
        }
      } catch (error) {
        errors.push(`${reqId}: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    }

    setDeletingRequirements(false);

    if (errors.length === 0) {
      setRequirements(prev => prev.filter(r => !selectedRequirementIds.has(r.id)));
      setSelectedRequirementIds(new Set());
      handleCloseDeleteDialog();
    } else {
      setDeleteError(`Failed to delete ${errors.length} item(s): ${errors.join(', ')}`);
    }
  };

  const handleCancelAdd = () => {
    setShowAddForm(false);
    setNewReqDescription('');
    setNewReqCategory('');
  };

  const isAddFormValid = () => {
    return newReqDescription.trim().length >= 10 && newReqCategory !== '';
  };

  const handleAddRequirement = async () => {
    if (!isAddFormValid()) return;

    setAddingRequirement(true);
    setAddError(null);
    
    const tempId = `temp-${Date.now()}`;
    const optimisticReq: Requirement = {
      id: tempId,
      description: newReqDescription.trim(),
      category: newReqCategory as 'feature' | 'rule' | 'integration' | 'edge',
      source: 'user',
    };

    setRequirements(prev => [...prev, optimisticReq]);

    try {
      const data = await api.addRequirementV2({
        chat_id: chatId,
        node_id: nodeId,
        target_id: targetId,
        description: newReqDescription.trim(),
        category: newReqCategory,
      });

      if (data.success && data.requirement) {
        setRequirements(prev => 
          prev.map(r => r.id === tempId ? data.requirement : r)
        );
        setAddError(null);
        handleCancelAdd();
      } else {
        setRequirements(prev => prev.filter(r => r.id !== tempId));
        setAddError(data.error || 'Failed to add requirement');
      }
    } catch (error) {
      setRequirements(prev => prev.filter(r => r.id !== tempId));
      setAddError(error instanceof Error ? error.message : 'Unknown error');
    } finally {
      setAddingRequirement(false);
    }
  };

  const loadExistingRecord = async () => {
    try {
      const data = await api.getEnforcementV2Record(chatId, nodeId, targetId);
      
      if (data.success && data.record) {
        setRequirements(data.record.requirements || []);
        setVerifications(data.record.verifications || []);
        setTests(data.record.tests || []);
        setOverallVerdict(data.record.overall_verdict || 'not_done');
        
        // Load step_verification if exists (for step-level records)
        if (data.record.step_verification) {
          setStepVerification(data.record.step_verification);
        }
      }
    } catch (error) {
      console.log('No existing enforcement record found');
    }
  };

  const handleListRequirements = async () => {
    setListingRequirements(true);
    setListError(null);
    
    try {
      const data = await api.listRequirementsV2({
        chat_id: chatId,
        node_id: nodeId,
        target_id: targetId,
      });
      
      if (data.success) {
        setRequirements(data.requirements || []);
        setVerifications([]);
        setTests([]);
        setOverallVerdict('not_done');
      } else {
        setListError(data.error || 'Failed to list requirements');
      }
    } catch (error) {
      setListError(error instanceof Error ? error.message : 'Unknown error');
    } finally {
      setListingRequirements(false);
    }
  };

  const handleVerifySelected = async () => {
    setVerifying(true);
    setVerifyError(null);
    
    const selectedReqs = requirements.filter(r => selectedRequirementIds.has(r.id));
    
    try {
      const data = await api.verifyRequirementsV2({
        chat_id: chatId,
        node_id: nodeId,
        target_id: targetId,
        requirements: selectedReqs,
      });
      
      if (data.success) {
        // Merge: keep existing verifications for requirements NOT being updated
        const incomingIds = new Set(data.verifications?.map((v: RequirementVerification) => v.requirement_id) || []);
        const kept = verifications.filter((v: RequirementVerification) => !incomingIds.has(v.requirement_id));
        setVerifications([...kept, ...(data.verifications || [])]);
        
        setOverallVerdict(data.overall_verdict || 'not_done');
      } else {
        setVerifyError(data.error || 'Failed to verify requirements');
      }
    } catch (error) {
      setVerifyError(error instanceof Error ? error.message : 'Unknown error');
    } finally {
      setVerifying(false);
    }
  };

  const handleTestSelected = async () => {
    setTesting(true);
    setTestError(null);
    
    const selectedReqs = requirements.filter(r => selectedRequirementIds.has(r.id));
    
    try {
      const data = await api.testRequirementsV2({
        chat_id: chatId,
        node_id: nodeId,
        target_id: targetId,
        requirements: selectedReqs,
      });
      
      if (data.success) {
        // Merge: keep existing tests for requirements NOT being updated
        const incomingIds = new Set(data.tests?.map((t: RequirementTest) => t.requirement_id) || []);
        const kept = tests.filter((t: RequirementTest) => !incomingIds.has(t.requirement_id));
        setTests([...kept, ...(data.tests || [])]);
      } else {
        setTestError(data.error || 'Failed to generate tests');
      }
    } catch (error) {
      setTestError(error instanceof Error ? error.message : 'Unknown error');
    } finally {
      setTesting(false);
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'feature': return colors.darkGreen;
      case 'rule': return colors.grey;
      case 'integration': return colors.gold;
      case 'edge': return colors.red;
      default: return colors.grey;
    }
  };

  const getVerdictColor = (verdict: string) => {
    switch (verdict) {
      case 'pass': return colors.green;
      case 'fail': return colors.red;
      case 'unclear': return colors.gold;
      default: return colors.grey;
    }
  };

  const getTimeAgo = (timestamp: string | null) => {
    if (!timestamp) return '';
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now.getTime() - then.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins === 1) return '1 min ago';
    if (diffMins < 60) return `${diffMins} mins ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours === 1) return '1 hour ago';
    if (diffHours < 24) return `${diffHours} hours ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return '1 day ago';
    return `${diffDays} days ago`;
  };

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        bgcolor: 'background.paper',
        display: 'flex',
        flexDirection: 'column',
        p: 2,
        borderLeft: '1px solid',
        borderColor: 'divider',
      }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="subtitle2" fontWeight={600}>
          Enforcement Panel V2
        </Typography>
        <IconButton onClick={onClose} size="small" sx={{ color: colors.grey }}>
          <CloseIcon />
        </IconButton>
      </Box>

      <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
        {targetId === nodeId ? 'Step' : 'Substep'}: {targetId}
      </Typography>

      {isCached && cacheTime && (
        <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'center' }}>
          <Chip 
            label={`Cached ${getTimeAgo(cacheTime)}`} 
            size="small" 
            sx={{ bgcolor: 'grey.200', color: 'text.secondary' }}
          />
          <IconButton onClick={loadExistingRecord} size="small" disabled={listingRequirements || verifying || testing}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Box>
      )}

      {/* Action Buttons */}
      <Stack spacing={2} sx={{ mb: 3 }}>
        {targetId === nodeId && (
          <Button
            onClick={async () => {
              setStepVerifying(true);
              setStepVerifyError(null);
              try {
                const data = await api.verifyStepV2(chatId, nodeId);
                if (data.success) {
                  setStepVerification(data.verification);
                } else {
                  setStepVerifyError(data.error || 'Failed to verify step');
                }
              } catch (error) {
                setStepVerifyError(error instanceof Error ? error.message : 'Unknown error');
              } finally {
                setStepVerifying(false);
              }
            }}
            disabled={stepVerifying}
            colorVariant="green"
            fullWidth
            startIcon={stepVerifying ? <CircularProgress size={16} sx={{ color: 'white' }} /> : undefined}
            sx={{ borderRadius: 0 }}
          >
            {stepVerifying ? 'Verifying Step...' : 'Verify Step'}
          </Button>
        )}

        {targetId !== nodeId && (
          <>
            <Button
              onClick={handleListRequirements}
              disabled={listingRequirements}
              colorVariant="dark-green"
              fullWidth
              startIcon={listingRequirements ? <CircularProgress size={16} sx={{ color: 'white' }} /> : undefined}
              sx={{ borderRadius: 0 }}
            >
              {listingRequirements ? 'Listing...' : 'List Requirements'}
            </Button>

            <Button
              onClick={handleVerifySelected}
              disabled={!canVerify || verifying}
              colorVariant="green"
              fullWidth
              startIcon={verifying ? <CircularProgress size={16} sx={{ color: 'white' }} /> : undefined}
              sx={{ borderRadius: 0 }}
            >
              {verifying ? 'Verifying...' : `Verify Selected (${selectedRequirementIds.size})`}
            </Button>

            <Button
              onClick={handleTestSelected}
              disabled={!canTest || testing}
              colorVariant="dark-green"
              fullWidth
              startIcon={testing ? <CircularProgress size={16} sx={{ color: 'white' }} /> : undefined}
              sx={{ borderRadius: 0 }}
            >
              {testing ? 'Testing...' : `Test Selected (${selectedRequirementIds.size})`}
            </Button>
          </>
        )}
      </Stack>

      {/* Errors */}
      {listError && (
        <Box sx={{ mb: 2, p: 1.5, bgcolor: 'rgba(244, 67, 54, 0.1)', border: '1px solid #f44336', borderRadius: 0 }}>
          <Typography variant="caption" color="error">{listError}</Typography>
        </Box>
      )}
      {verifyError && (
        <Box sx={{ mb: 2, p: 1.5, bgcolor: 'rgba(244, 67, 54, 0.1)', border: '1px solid #f44336', borderRadius: 0 }}>
          <Typography variant="caption" color="error">{verifyError}</Typography>
        </Box>
      )}
      {testError && (
        <Box sx={{ mb: 2, p: 1.5, bgcolor: 'rgba(244, 67, 54, 0.1)', border: '1px solid #f44336', borderRadius: 0 }}>
          <Typography variant="caption" color="error">{testError}</Typography>
        </Box>
      )}

      {/* Overall Verdict */}
      {hasVerifications && (
        <Box sx={{ mb: 2, p: 1.5, bgcolor: 'grey.50', borderRadius: 0, border: '1px solid', borderColor: 'divider' }}>
          <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
            Overall Verdict:
          </Typography>
          <Chip
            label={overallVerdict.toUpperCase()}
            size="small"
            sx={{
              bgcolor: getVerdictColor(overallVerdict),
              color: 'white',
              fontWeight: 'bold',
            }}
          />
        </Box>
      )}

      {/* Step Verification Error */}
      {stepVerifyError && (
        <Box sx={{ mb: 2, p: 1.5, bgcolor: 'rgba(244, 67, 54, 0.1)', border: '1px solid #f44336', borderRadius: 0 }}>
          <Typography variant="caption" color="error">{stepVerifyError}</Typography>
        </Box>
      )}

      {/* Content Area */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {/* Step Verification Display */}
        {stepVerification && targetId === nodeId && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
              Step Verification
            </Typography>

            {/* Verdict Badge */}
            <Box sx={{ mb: 2 }}>
              <Chip
                label={stepVerification.verdict?.toUpperCase() || 'UNKNOWN'}
                size="small"
                sx={{
                  bgcolor: getVerdictColor(stepVerification.verdict || 'unclear'),
                  color: 'white',
                  fontWeight: 'bold',
                }}
              />
            </Box>

            {/* Overview */}
            {stepVerification.overview && (
              <Box sx={{ mb: 2, p: 1.5, bgcolor: 'grey.50', borderRadius: 0, border: '1px solid', borderColor: 'divider' }}>
                <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 1 }}>
                  Overview:
                </Typography>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem' }}>
                  {stepVerification.overview}
                </Typography>
              </Box>
            )}

            {/* Rules Analysis */}
            {stepVerification.rules_analysis && stepVerification.rules_analysis.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 1 }}>
                  Rules Analysis ({stepVerification.rules_analysis.length}):
                </Typography>
                <Stack spacing={1}>
                  {stepVerification.rules_analysis.map((rule: any, idx: number) => (
                    <Box
                      key={idx}
                      sx={{
                        p: 1.5,
                        border: '1px solid',
                        borderColor: rule.followed ? colors.green : colors.red,
                        bgcolor: rule.followed ? `${colors.green}10` : `${colors.red}10`,
                        borderRadius: 0,
                      }}
                    >
                      <Box sx={{ display: 'flex', gap: 1, mb: 0.5, alignItems: 'center' }}>
                        <Chip
                          label={rule.followed ? 'FOLLOWED' : 'VIOLATED'}
                          size="small"
                          sx={{
                            bgcolor: rule.followed ? colors.green : colors.red,
                            color: 'white',
                            fontSize: '0.7rem',
                            fontWeight: 'bold',
                          }}
                        />
                        <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
                          {rule.rule_id}
                        </Typography>
                      </Box>
                      <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
                        {rule.rule_text}
                      </Typography>
                      <Typography variant="caption" sx={{ display: 'block', fontStyle: 'italic', color: 'text.secondary' }}>
                        {rule.evidence}
                      </Typography>
                      {rule.used_in_substeps && rule.used_in_substeps.length > 0 && (
                        <Box sx={{ mt: 0.5 }}>
                          <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
                            Used in: {rule.used_in_substeps.join(', ')}
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  ))}
                </Stack>
              </Box>
            )}

            {/* Files Summary */}
            {stepVerification.files_summary && stepVerification.files_summary.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 1 }}>
                  Files Changed ({stepVerification.files_summary.length}):
                </Typography>
                <Stack spacing={1}>
                  {stepVerification.files_summary.map((file: any, idx: number) => (
                    <Box 
                      key={idx} 
                      sx={{ 
                        p: 1, 
                        bgcolor: 'grey.50', 
                        border: '1px solid', 
                        borderColor: 'divider',
                        borderRadius: 0,
                      }}
                    >
                      <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 'bold', display: 'block' }}>
                        {file.path}
                      </Typography>
                      <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', fontSize: '0.65rem' }}>
                        Lines: {file.lines_changed}
                      </Typography>
                      <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                        {file.changes}
                      </Typography>
                      {file.impact && (
                        <Typography variant="caption" sx={{ display: 'block', mt: 0.5, fontStyle: 'italic', color: 'text.secondary' }}>
                          Impact: {file.impact}
                        </Typography>
                      )}
                      {file.substeps_fulfilled && file.substeps_fulfilled.length > 0 && (
                        <Typography variant="caption" sx={{ display: 'block', mt: 0.5, fontSize: '0.65rem', color: 'text.secondary' }}>
                          Substeps: {file.substeps_fulfilled.join(', ')}
                        </Typography>
                      )}
                    </Box>
                  ))}
                </Stack>
              </Box>
            )}

            {/* Code Blocks */}
            {stepVerification.code_blocks && stepVerification.code_blocks.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 1 }}>
                  Code ({stepVerification.code_blocks.length} snippets):
                </Typography>
                <Stack spacing={1}>
                  {stepVerification.code_blocks.map((code: any, idx: number) => (
                    <Box 
                      key={idx} 
                      sx={{ 
                        p: 1, 
                        bgcolor: '#f5f5f5', 
                        border: '1px solid', 
                        borderColor: 'divider',
                        borderRadius: 0,
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}>
                          {code.file}
                        </Typography>
                        <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary', fontSize: '0.65rem' }}>
                          {code.lines}
                        </Typography>
                      </Box>
                      <Box 
                        sx={{ 
                          p: 1, 
                          bgcolor: 'white', 
                          fontFamily: 'monospace', 
                          fontSize: '0.7rem',
                          overflowX: 'auto',
                          whiteSpace: 'pre',
                          border: '1px solid',
                          borderColor: 'divider',
                        }}
                      >
                        {code.code}
                      </Box>
                      {code.annotation && (
                        <Typography variant="caption" sx={{ display: 'block', mt: 0.5, fontStyle: 'italic', color: 'text.secondary' }}>
                          {code.annotation}
                        </Typography>
                      )}
                    </Box>
                  ))}
                </Stack>
              </Box>
            )}
          </Box>
        )}
        {/* Requirements List */}
        {requirements.length > 0 && (
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1, gap: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
                <Typography variant="subtitle2" fontWeight={600}>
                  Requirements ({requirements.length})
                  {selectedRequirementIds.size > 0 && (
                    <Typography component="span" variant="caption" sx={{ ml: 1, color: 'text.secondary' }}>
                      ({selectedRequirementIds.size} selected)
                    </Typography>
                  )}
                </Typography>
                <Button
                  onClick={handleSelectAll}
                  disabled={requirements.length === 0 || selectedRequirementIds.size === requirements.length}
                  colorVariant="dark-green"
                  sx={{ 
                    borderRadius: 0, 
                    fontSize: '0.7rem', 
                    py: 0.25, 
                    px: 1,
                    minWidth: 'auto',
                  }}
                >
                  Select All
                </Button>
                <Button
                  onClick={handleDeselectAll}
                  disabled={selectedRequirementIds.size === 0}
                  colorVariant="transparent"
                  sx={{ 
                    borderRadius: 0, 
                    fontSize: '0.7rem', 
                    py: 0.25, 
                    px: 1,
                    minWidth: 'auto',
                  }}
                >
                  Deselect All
                </Button>
              </Box>
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <IconButton 
                  size="small" 
                  sx={{ color: colors.red }} 
                  onClick={handleShowDeleteDialog}
                  disabled={selectedRequirementIds.size === 0}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
                <IconButton size="small" sx={{ color: colors.darkGreen }} onClick={handleShowAddForm}>
                  <AddIcon fontSize="small" />
                </IconButton>
              </Box>
            </Box>
            
            {/* Add Requirement Form (at top) */}
            {showAddForm && (
              <Box sx={{ mb: 2, p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 0, bgcolor: 'grey.50' }}>
                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
                  Add New Requirement
                </Typography>
                
                {addError && (
                  <Box sx={{ mb: 2, p: 1, bgcolor: 'rgba(244, 67, 54, 0.1)', border: '1px solid #f44336', borderRadius: 0 }}>
                    <Typography variant="caption" color="error">{addError}</Typography>
                  </Box>
                )}
                
                <Stack spacing={2}>
                  <TextField
                    label="Description"
                    multiline
                    rows={3}
                    value={newReqDescription}
                    onChange={(e) => setNewReqDescription(e.target.value)}
                    placeholder="Describe the requirement (min 10 characters)"
                    fullWidth
                    size="small"
                    error={newReqDescription.length > 0 && newReqDescription.trim().length < 10}
                    helperText={newReqDescription.length > 0 && newReqDescription.trim().length < 10 ? 'Minimum 10 characters required' : ''}
                    sx={{ 
                      borderRadius: 0,
                      '& .MuiOutlinedInput-root': {
                        '&.Mui-focused fieldset': {
                          borderColor: colors.darkGreen,
                        },
                      },
                      '& .MuiInputLabel-root.Mui-focused': {
                        color: colors.darkGreen,
                      },
                    }}
                  />
                  
                  <TextField
                    select
                    label="Category"
                    value={newReqCategory}
                    onChange={(e) => setNewReqCategory(e.target.value as 'feature' | 'rule' | 'integration' | 'edge')}
                    fullWidth
                    size="small"
                    error={!newReqCategory}
                    helperText={!newReqCategory ? 'Category is required' : ''}
                    sx={{ 
                      borderRadius: 0,
                      '& .MuiOutlinedInput-root': {
                        '&.Mui-focused fieldset': {
                          borderColor: colors.darkGreen,
                        },
                      },
                      '& .MuiInputLabel-root.Mui-focused': {
                        color: colors.darkGreen,
                      },
                    }}
                  >
                    <MenuItem value="feature">Feature</MenuItem>
                    <MenuItem value="rule">Rule</MenuItem>
                    <MenuItem value="integration">Integration</MenuItem>
                    <MenuItem value="edge">Edge Case</MenuItem>
                  </TextField>

                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                      onClick={handleCancelAdd}
                      colorVariant="transparent"
                      sx={{ borderRadius: 0, flex: 1 }}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleAddRequirement}
                      disabled={!isAddFormValid() || addingRequirement}
                      colorVariant="dark-green"
                      sx={{ borderRadius: 0, flex: 1 }}
                      startIcon={addingRequirement ? <CircularProgress size={16} sx={{ color: 'white' }} /> : undefined}
                    >
                      {addingRequirement ? 'Adding...' : 'Add Requirement'}
                    </Button>
                  </Box>
                </Stack>
              </Box>
            )}
            
            <Stack spacing={1}>
              {requirements.map((req) => {
                const verification = verifications.find(v => v.requirement_id === req.id);
                const reqTests = tests.filter(t => t.requirement_id === req.id);
                
                return (
                  <Box
                    key={req.id}
                    sx={{
                      p: 1.5,
                      border: '1px solid',
                      borderColor: verification 
                        ? getVerdictColor(verification.verdict)
                        : 'divider',
                      bgcolor: verification
                        ? `${getVerdictColor(verification.verdict)}10`
                        : 'transparent',
                      borderRadius: 0,
                    }}
                  >
                    {/* Requirement Header */}
                    <Box sx={{ display: 'flex', gap: 1, mb: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                      <Checkbox
                        size="small"
                        checked={selectedRequirementIds.has(req.id)}
                        onChange={() => handleToggleRequirement(req.id)}
                        sx={{ 
                          p: 0, 
                          mr: 0.5,
                          color: colors.grey,
                          '&.Mui-checked': {
                            color: colors.green,
                          },
                        }}
                      />
                      <Chip
                        label={req.category}
                        size="small"
                        sx={{
                          bgcolor: getCategoryColor(req.category),
                          color: 'white',
                          fontSize: '0.7rem',
                        }}
                      />
                      <Chip
                        label={req.source}
                        size="small"
                        variant="outlined"
                        sx={{ fontSize: '0.7rem' }}
                      />
                      <Typography
                        variant="caption"
                        sx={{ fontFamily: 'monospace', color: 'text.secondary' }}
                      >
                        {req.id}
                      </Typography>
                    </Box>

                    {/* Requirement Description */}
                    <Typography variant="body2" sx={{ mb: 1 }}>
                      {req.description}
                    </Typography>

                    {/* Verification Result */}
                    {verification && (
                      <Box sx={{ mt: 1, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                        <Box 
                          sx={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: 1, 
                            mb: 0.5,
                            cursor: 'pointer',
                          }}
                          onClick={() => handleToggleEvidence(req.id)}
                        >
                          <Chip
                            label={verification.verdict.toUpperCase()}
                            size="small"
                            sx={{
                              bgcolor: getVerdictColor(verification.verdict),
                              color: 'white',
                              fontSize: '0.7rem',
                              fontWeight: 'bold',
                            }}
                          />
                          <Typography variant="caption" fontWeight={600} sx={{ flex: 1 }}>
                            Evidence
                          </Typography>
                          <IconButton 
                            size="small" 
                            sx={{ 
                              p: 0,
                              transform: expandedEvidenceIds.has(req.id) ? 'rotate(180deg)' : 'rotate(0deg)',
                              transition: 'transform 0.2s',
                            }}
                          >
                            <ExpandMoreIcon fontSize="small" />
                          </IconButton>
                        </Box>

                        <Collapse in={expandedEvidenceIds.has(req.id)}>
                          <Box sx={{ mt: 1 }}>
                            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1, fontStyle: 'italic' }}>
                              {verification.evidence}
                            </Typography>

                            {verification.files_changed && verification.files_changed.length > 0 && (
                              <Box sx={{ mt: 1.5, mb: 1.5 }}>
                                <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 0.5 }}>
                                  Files Changed ({verification.files_changed.length}):
                                </Typography>
                                <Stack spacing={1}>
                                  {verification.files_changed.map((file, idx) => (
                                    <Box 
                                      key={idx} 
                                      sx={{ 
                                        p: 1, 
                                        bgcolor: 'grey.50', 
                                        border: '1px solid', 
                                        borderColor: 'divider',
                                        borderRadius: 0,
                                      }}
                                    >
                                      <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 'bold', display: 'block' }}>
                                        {file.path}
                                      </Typography>
                                      <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', fontSize: '0.65rem' }}>
                                        Lines: {file.lines_changed}
                                      </Typography>
                                      <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                                        {file.changes}
                                      </Typography>
                                      {file.impact && (
                                        <Typography variant="caption" sx={{ display: 'block', mt: 0.5, fontStyle: 'italic', color: 'text.secondary' }}>
                                          Impact: {file.impact}
                                        </Typography>
                                      )}
                                    </Box>
                                  ))}
                                </Stack>
                              </Box>
                            )}

                            {verification.code_changed && verification.code_changed.length > 0 && (
                              <Box sx={{ mt: 1.5 }}>
                                <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 0.5 }}>
                                  Code ({verification.code_changed.length} snippets):
                                </Typography>
                                <Stack spacing={1}>
                                  {verification.code_changed.map((code, idx) => (
                                    <Box 
                                      key={idx} 
                                      sx={{ 
                                        p: 1, 
                                        bgcolor: '#f5f5f5', 
                                        border: '1px solid', 
                                        borderColor: 'divider',
                                        borderRadius: 0,
                                      }}
                                    >
                                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                        <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}>
                                          {code.file}
                                        </Typography>
                                        <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary', fontSize: '0.65rem' }}>
                                          {code.lines}
                                        </Typography>
                                      </Box>
                                      <Box 
                                        sx={{ 
                                          p: 1, 
                                          bgcolor: 'white', 
                                          fontFamily: 'monospace', 
                                          fontSize: '0.7rem',
                                          overflowX: 'auto',
                                          whiteSpace: 'pre',
                                          border: '1px solid',
                                          borderColor: 'divider',
                                        }}
                                      >
                                        {code.code}
                                      </Box>
                                      {code.annotation && (
                                        <Typography variant="caption" sx={{ display: 'block', mt: 0.5, fontStyle: 'italic', color: 'text.secondary' }}>
                                          {code.annotation}
                                        </Typography>
                                      )}
                                    </Box>
                                  ))}
                                </Stack>
                              </Box>
                            )}
                          </Box>
                        </Collapse>
                      </Box>
                    )}

                    {/* Test Results */}
                    {reqTests.length > 0 && (
                      <Box sx={{ mt: 1, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                        <Box 
                          sx={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: 1, 
                            mb: 0.5,
                            cursor: 'pointer',
                          }}
                          onClick={() => handleToggleTests(req.id)}
                        >
                          <Typography variant="caption" fontWeight={600} sx={{ flex: 1 }}>
                            Tests ({reqTests.length})
                          </Typography>
                          <IconButton 
                            size="small" 
                            sx={{ 
                              p: 0,
                              transform: expandedTestIds.has(req.id) ? 'rotate(180deg)' : 'rotate(0deg)',
                              transition: 'transform 0.2s',
                            }}
                          >
                            <ExpandMoreIcon fontSize="small" />
                          </IconButton>
                        </Box>

                        <Collapse in={expandedTestIds.has(req.id)}>
                          <Stack spacing={1} sx={{ mt: 1 }}>
                            {reqTests.map((test, idx) => (
                              <Box key={idx} sx={{ p: 1, bgcolor: 'grey.50', borderRadius: 0, border: '1px solid', borderColor: 'divider' }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                  <Chip
                                    label={test.status.toUpperCase()}
                                    size="small"
                                    sx={{
                                      bgcolor: test.status === 'pass' ? colors.green : '#f44336',
                                      color: 'white',
                                      fontSize: '0.65rem',
                                      fontWeight: 'bold',
                                    }}
                                  />
                                  <Typography variant="caption" sx={{ fontSize: '0.7rem', fontWeight: 600 }}>
                                    {test.test_name}
                                  </Typography>
                                </Box>
                                <Typography variant="caption" sx={{ display: 'block', mb: 0.5, fontStyle: 'italic', color: 'text.secondary' }}>
                                  {test.test_description}
                                </Typography>
                                {test.output && (
                                  <Typography variant="caption" sx={{ display: 'block', mt: 0.5, fontSize: '0.65rem' }}>
                                    {test.output}
                                  </Typography>
                                )}
                              </Box>
                            ))}
                          </Stack>
                        </Collapse>
                      </Box>
                    )}
                  </Box>
                );
              })}
            </Stack>
          </Box>
        )}

        {/* Empty State */}
        {requirements.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
            <Typography variant="body2">
              {targetId === nodeId 
                ? 'Click "Verify Step" to verify this step'
                : 'Click "List Requirements" to generate a checklist'
              }
            </Typography>
          </Box>
        )}
      </Box>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onClose={handleCloseDeleteDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Delete Requirements</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Are you sure you want to delete {selectedRequirementIds.size} requirement(s)?
          </Typography>

          {deleteError && (
            <Box sx={{ mb: 2, p: 1.5, bgcolor: 'rgba(244, 67, 54, 0.1)', border: '1px solid #f44336', borderRadius: 0 }}>
              <Typography variant="caption" color="error">{deleteError}</Typography>
            </Box>
          )}

          <Box sx={{ maxHeight: 200, overflow: 'auto', bgcolor: 'grey.50', p: 1, borderRadius: 0 }}>
            {Array.from(selectedRequirementIds).map((reqId) => {
              const req = requirements.find(r => r.id === reqId);
              return req ? (
                <Box key={reqId} sx={{ mb: 1, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                  <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary', display: 'block' }}>
                    {req.id}
                  </Typography>
                  <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>
                    {req.description.slice(0, 80)}{req.description.length > 80 ? '...' : ''}
                  </Typography>
                </Box>
              ) : null;
            })}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={handleCloseDeleteDialog} 
            colorVariant="transparent" 
            sx={{ borderRadius: 0 }}
            disabled={deletingRequirements}
          >
            Cancel
          </Button>
          <Button 
            onClick={handleConfirmDelete}
            colorVariant="red" 
            sx={{ borderRadius: 0 }}
            disabled={deletingRequirements}
            startIcon={deletingRequirements ? <CircularProgress size={16} sx={{ color: 'white' }} /> : undefined}
          >
            {deletingRequirements ? 'Deleting...' : `Delete ${selectedRequirementIds.size}`}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}