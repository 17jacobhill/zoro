import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  Typography,
  Divider,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  Chip,
  CircularProgress,
  Alert,
  Tooltip,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import StarIcon from '@mui/icons-material/Star';
import BoltIcon from '@mui/icons-material/Bolt';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ScienceIcon from '@mui/icons-material/Science';
import { ToggleOn, ToggleOff } from '@mui/icons-material';
import { Button } from '../../design-system/Button';
import { TextField } from '../../design-system/TextField';
import { Select } from '../../design-system/Select';
import { colors } from '../../design-system/colors';
import { api } from '../../services/api';

interface AddRuleModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface RefinedRule {
  title: string;
  content: string;
  confidence: number;
  decay: number;
  confidence_reasoning: string;
  decay_reasoning: string;
  context: string | null;
  evidence: string | null;
}

export function AddRuleModal({ open, onClose, onSuccess }: AddRuleModalProps) {
  const [category, setCategory] = useState('');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [context, setContext] = useState('');
  const [evidence, setEvidence] = useState('');
  const [isStrict, setIsStrict] = useState(false);
  const [isTestable, setIsTestable] = useState(false);
  
  const [categories, setCategories] = useState<string[]>([]);
  const [isRefining, setIsRefining] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [refined, setRefined] = useState<RefinedRule | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load categories
  useEffect(() => {
    if (open) {
      loadCategories();
    }
  }, [open]);

  const loadCategories = async () => {
    try {
      const data = await api.fetchKBCategories();
      if (data.success && data.categories) {
        const categoryNames = data.categories.map((c: any) => c.name);
        setCategories(categoryNames);
      }
    } catch (err) {
      console.error('Failed to load categories:', err);
    }
  };

  const handleClose = () => {
    if (!isRefining && !isSaving) {
      resetForm();
      onClose();
    }
  };

  const resetForm = () => {
    setCategory('');
    setTitle('');
    setContent('');
    setContext('');
    setEvidence('');
    setIsStrict(false);
    setIsTestable(false);
    setRefined(null);
    setError(null);
    setSuccessMessage(null);
  };

  const handleRefine = async () => {
    if (!title.trim() || !content.trim() || !category) {
      setError('Title, content, and category are required');
      return;
    }

    setIsRefining(true);
    setError(null);

    try {
      const data = await api.refineRule({
        rule_type: 'rule',
        category,
        title,
        content,
        context: context || null,
        evidence: evidence || null,
      });

      if (data.success && data.refined) {
        setRefined(data.refined);
      } else {
        setError(data.error || 'Failed to refine rule');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to refine rule');
    } finally {
      setIsRefining(false);
    }
  };

  const handleSave = async () => {
    if (!refined) {
      setError('Please refine the rule first');
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const data = await api.createKBItem({
        type: 'rule',
        category,
        title: refined.title,
        content: refined.content,
        context: refined.context,
        evidence: refined.evidence,
        confidence: refined.confidence,
        decay: refined.decay,
        confidence_reasoning: refined.confidence_reasoning,
        decay_reasoning: refined.decay_reasoning,
        is_strict: isStrict,
        is_testable: isTestable,
      });

      if (data.success) {
        setSuccessMessage('Rule saved successfully!');
        setTimeout(() => {
          resetForm();
          onSuccess();
          onClose();
        }, 1500);
      } else {
        setError('Failed to save rule');
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.error || err.message || 'Failed to save rule';
      setError(errorMessage);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRefinedFieldChange = (field: keyof RefinedRule, value: string) => {
    if (refined) {
      setRefined({ ...refined, [field]: value });
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: '#ffffff',
          color: '#1e1e1e',
          maxHeight: '90vh',
          borderRadius: 2,
        }
      }}
    >
      <DialogTitle sx={{ borderBottom: '1px solid rgba(0, 0, 0, 0.08)', pb: 1.25 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                width: 26,
                height: 26,
                borderRadius: '50%',
                bgcolor: '#ecf6e8',
                color: colors.green,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <AutoAwesomeIcon sx={{ fontSize: 15 }} />
            </Box>
            <Typography variant="h6" sx={{ color: '#1e1e1e', fontWeight: 700, fontSize: '1rem' }}>
              Add Rule to Rules Management
            </Typography>
          </Box>
          <IconButton
            onClick={handleClose}
            disabled={isRefining || isSaving}
            size="small"
            disableRipple
            sx={{ color: colors.grey, mt: -0.25, mr: -0.5, '&:focus': { outline: 'none' } }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
        <Typography variant="caption" sx={{ color: colors.grey, mt: 0.6, display: 'block', fontSize: '0.72rem' }}>
          Enter rule details, refine with AI, then save
        </Typography>
      </DialogTitle>

      <DialogContent sx={{ mt: 0.5, overflow: 'auto', pt: 1.5 }}>
        {/* Original Fields */}
        <Box sx={{ mb: 2 }}>
          <Typography sx={{ fontWeight: 700, mb: 1.25, color: colors.grey, fontSize: '0.76rem', textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Original Rule
          </Typography>

          <Box sx={{ display: 'flex', gap: 1.25, mb: 1.25 }}>
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
                value={category}
                label="Category"
                onChange={(e) => setCategory(e.target.value)}
                disabled={isRefining || isSaving}
                sx={{
                  '& .MuiOutlinedInput-root': { height: 40 },
                  '& .MuiSelect-select': { fontSize: '12px', display: 'flex', alignItems: 'center' }
                }}
              >
                {categories.map(cat => (
                  <MenuItem key={cat} value={cat} sx={{ fontSize: '12px' }}>{cat}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <TextField
              fullWidth
              size="small"
              label="Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isRefining || isSaving}
              sx={{
                flex: 2,
                '& .MuiInputBase-root': { height: 40 },
                '& .MuiInputBase-input': { fontSize: '0.85rem' },
                '& .MuiInputLabel-root': {
                  fontSize: '0.78rem',
                  color: colors.grey,
                  '&.Mui-focused': { color: colors.green }
                }
              }}
            />
          </Box>

          <Box sx={{ mb: 1.25, display: 'flex', alignItems: 'center', gap: 1.25, flexWrap: 'wrap' }}>
            <Tooltip title={isStrict ? "Remove strict enforcement" : "Mark for strict enforcement"}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                <IconButton
                  size="small"
                  disableRipple
                  disabled={isRefining || isSaving}
                  onClick={() => {
                    const next = !isStrict;
                    setIsStrict(next);
                    if (!next) setIsTestable(false);
                  }}
                  sx={{
                    color: isStrict ? colors.green : colors.grey,
                    padding: '2px',
                    '&:focus': { outline: 'none' }
                  }}
                >
                  {isStrict ? <ToggleOn fontSize="small" /> : <ToggleOff fontSize="small" />}
                </IconButton>
                <Typography sx={{ fontSize: '11.5px', color: isStrict ? colors.green : colors.grey, fontWeight: 500 }}>
                  Strict
                </Typography>
              </Box>
            </Tooltip>
            <Tooltip title={!isStrict ? "Mark as strict first to enable testing" : isTestable ? "Remove testable marking" : "Mark as testable (requires test evidence)"}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                <span>
                  <IconButton
                    size="small"
                    disableRipple
                    disabled={!isStrict || isRefining || isSaving}
                    onClick={() => setIsTestable(!isTestable)}
                    sx={{
                      color: isTestable ? colors.blue : colors.grey,
                      padding: '2px',
                      opacity: !isStrict ? 0.3 : 1,
                      '&:focus': { outline: 'none' }
                    }}
                  >
                    <ScienceIcon fontSize="small" />
                  </IconButton>
                </span>
                <Typography sx={{ fontSize: '11.5px', color: isTestable ? colors.blue : colors.grey, fontWeight: 500, opacity: !isStrict ? 0.6 : 1 }}>
                  Testable
                </Typography>
              </Box>
            </Tooltip>
          </Box>

          <TextField
            fullWidth
            multiline
            minRows={3}
            maxRows={6}
            label="Content"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            disabled={isRefining || isSaving}
            sx={{
              mb: 1.25,
              '& .MuiInputBase-input': { fontSize: '0.85rem', lineHeight: 1.45 },
              '& .MuiInputLabel-root': {
                fontSize: '0.78rem',
                color: colors.grey,
                '&.Mui-focused': { color: colors.green }
              }
            }}
          />

          <TextField
            fullWidth
            multiline
            minRows={2}
            maxRows={4}
            label="Context (optional)"
            placeholder="What was being built..."
            value={context}
            onChange={(e) => setContext(e.target.value)}
            disabled={isRefining || isSaving}
            sx={{
              mb: 1.25,
              '& .MuiInputBase-input': { fontSize: '0.84rem' },
              '& .MuiInputLabel-root': {
                fontSize: '0.78rem',
                color: colors.grey,
                '&.Mui-focused': { color: colors.green }
              }
            }}
          />

          <TextField
            fullWidth
            multiline
            minRows={2}
            maxRows={4}
            label="Evidence (optional)"
            placeholder="Supporting quotes or examples..."
            value={evidence}
            onChange={(e) => setEvidence(e.target.value)}
            disabled={isRefining || isSaving}
            sx={{
              mb: 1.5,
              '& .MuiInputBase-input': { fontSize: '0.84rem' },
              '& .MuiInputLabel-root': {
                fontSize: '0.78rem',
                color: colors.grey,
                '&.Mui-focused': { color: colors.green }
              }
            }}
          />

          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 0.5 }}>
            <Button
              onClick={handleRefine}
              disabled={isRefining || isSaving || !title.trim() || !content.trim() || !category}
              colorVariant="green"
              startIcon={!isRefining ? <AutoAwesomeIcon sx={{ fontSize: 16 }} /> : undefined}
              sx={{ minWidth: 168, fontSize: '0.82rem', py: 0.7 }}
            >
              {isRefining ? (
                <>
                  <CircularProgress size={14} sx={{ color: 'white', mr: 1 }} />
                  Refining...
                </>
              ) : (
                'Refine with AI'
              )}
            </Button>
            <Button
              onClick={handleSave}
              disabled={!refined || isSaving || isRefining}
              colorVariant="green"
              sx={{ minWidth: 92, fontSize: '0.8rem', py: 0.7, px: 1.25 }}
            >
              {isSaving ? (
                <>
                  <CircularProgress size={14} sx={{ color: 'white', mr: 0.75 }} />
                  Saving
                </>
              ) : (
                'Save'
              )}
            </Button>
          </Box>
        </Box>

        {/* Refined Preview */}
        {refined && (
          <Box sx={{ mt: 1 }}>
            <Divider sx={{ mb: 1.5 }} />
            <Typography sx={{ fontWeight: 700, mb: 1.25, color: colors.green, fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: 0.4 }}>
              Refined Rule (Editable)
            </Typography>

            <TextField
              fullWidth
              size="small"
              label="Refined Title"
              value={refined.title}
              onChange={(e) => handleRefinedFieldChange('title', e.target.value)}
              disabled={isSaving}
              sx={{
                mb: 1.25,
                '& .MuiInputBase-input': { fontSize: '0.85rem' },
                '& .MuiInputLabel-root': {
                  fontSize: '0.78rem',
                  color: colors.grey,
                  '&.Mui-focused': { color: colors.green }
                }
              }}
            />

            <TextField
              fullWidth
              multiline
              rows={4}
              label="Refined Content"
              value={refined.content}
              onChange={(e) => handleRefinedFieldChange('content', e.target.value)}
              disabled={isSaving}
              sx={{
                mb: 1.25,
                '& .MuiInputBase-input': { fontSize: '0.85rem', lineHeight: 1.45 },
                '& .MuiInputLabel-root': {
                  fontSize: '0.78rem',
                  color: colors.grey,
                  '&.Mui-focused': { color: colors.green }
                }
              }}
            />

            {/* Score Badges */}
            <Box sx={{ display: 'flex', gap: 1.25, mb: 1.25, flexWrap: 'wrap' }}>
              <Box>
                <Chip
                  icon={<StarIcon sx={{ fontSize: '14px !important', color: '#fff !important' }} />}
                  label={`Confidence: ${(refined.confidence * 100).toFixed(0)}%`}
                  sx={{
                    backgroundColor: refined.confidence >= 0.8 ? colors.green : refined.confidence >= 0.6 ? '#ff9800' : '#f44336',
                    color: 'white',
                    fontSize: '11px',
                  }}
                />
                <Typography sx={{ fontSize: '10.5px', color: colors.grey, mt: 0.5, maxWidth: 280 }}>
                  {refined.confidence_reasoning}
                </Typography>
              </Box>

              <Box>
                <Chip
                  icon={<BoltIcon sx={{ fontSize: '14px !important', color: '#fff !important' }} />}
                  label={`Specificity: ${(refined.decay * 100).toFixed(0)}%`}
                  sx={{
                    backgroundColor: refined.decay > 0.6 ? colors.green : colors.grey,
                    color: 'white',
                    fontSize: '11px',
                  }}
                />
                <Typography sx={{ fontSize: '10.5px', color: colors.grey, mt: 0.5, maxWidth: 280 }}>
                  {refined.decay_reasoning}
                </Typography>
              </Box>
            </Box>

            {refined.context && (
              <Box sx={{ mb: 1.25 }}>
                <Typography sx={{ fontSize: '10.5px', fontWeight: 700, color: colors.grey }}>Context:</Typography>
                <Typography sx={{ fontSize: '12px', lineHeight: 1.4 }}>{refined.context}</Typography>
              </Box>
            )}

            {refined.evidence && (
              <Box>
                <Typography sx={{ fontSize: '10.5px', fontWeight: 700, color: colors.grey }}>Evidence:</Typography>
                <Typography sx={{ fontSize: '11.5px', fontFamily: 'monospace', bgcolor: '#fff', p: 1, borderRadius: '6px', border: '1px solid rgba(0, 0, 0, 0.06)' }}>
                  {refined.evidence}
                </Typography>
              </Box>
            )}
          </Box>
        )}

        {/* Alerts */}
        {error && (
          <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {successMessage && (
          <Alert severity="success" sx={{ mt: 2 }}>
            {successMessage}
          </Alert>
        )}
      </DialogContent>

    </Dialog>
  );
}
