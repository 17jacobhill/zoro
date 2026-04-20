import { useState, useEffect } from 'react';
import { Box, Typography, Stack, Collapse, IconButton, Chip, CircularProgress } from '@mui/material';
import { ExpandMore as ExpandMoreIcon, Refresh as RefreshIcon, Close as CloseIcon } from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import { Button } from '../../design-system/Button';
import { api, type FileSummary, type CodeBlock, type EnforcementResponse } from '../../services/api';
import { clineApi } from '../../services/clineApi';
import { colors } from '../../design-system/colors';

interface EnforcementPanelProps {
  chatId: string;
  nodeId: string;
  targetKind: 'step' | 'substep' | 'rule';
  targetId: string;
  onClose: () => void;
}

export function EnforcementPanel({ chatId, nodeId, targetKind, targetId, onClose }: EnforcementPanelProps) {
  const [verifying, setVerifying] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [verifyResult, setVerifyResult] = useState<EnforcementResponse | null>(null);
  const [doResult, setDoResult] = useState<any>(null);
  const [testResults, setTestResults] = useState<any[]>([]);
  const [testFile, setTestFile] = useState<string>('');
  const [expandedBlocks, setExpandedBlocks] = useState<Set<number>>(new Set());
  const [isCached, setIsCached] = useState(false);
  const [cacheTime, setCacheTime] = useState<string | null>(null);
  const [doError, setDoError] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const hasVerified = !!verifyResult;
  const verdict = verifyResult?.verdict;

  useEffect(() => {
    setVerifyResult(null);
    setDoResult(null);
    setTestResults([]);
    setTestFile('');
    setExpandedBlocks(new Set());

    const loadExistingRecord = async () => {
      try {
        const response = await api.getEnforcementRecord(chatId, nodeId, targetKind, targetId);
        if (response.success && response.record) {
          setIsCached(true);
          if (response.record.verify) {
            setVerifyResult({
              success: true,
              verdict: response.record.verify.verdict,
              message: response.record.verify.message,
              overview: response.record.verify.overview,
              rules_analysis: response.record.verify.rules_analysis,
              files_summary: response.record.verify.files_summary,
              code_blocks: response.record.verify.code_blocks,
            });
            setCacheTime(response.record.verify.timestamp || null);
          }
          if (response.record.do) {
            // NEW: Read verification_result from do
            if (response.record.do.verification_result) {
              setDoResult({
                success: true,
                execution_result: response.record.do.verification_result,
              });
            } else {
              // Fallback for old format
              setDoResult({
                success: true,
                task_sent: response.record.do.task_sent,
              });
            }
          }
          if (response.record.test) {
            // NEW: Read results array and error from test
            setTestResults(response.record.test.results || []);
            setTestFile(response.record.test.test_file || '');
            if (response.record.test.error) {
              setTestError(response.record.test.error);
            }
          }
        }
      } catch (error) {
        console.log('No existing enforcement record found');
      }
    };

    loadExistingRecord();
  }, [chatId, nodeId, targetKind, targetId]);

  const handleVerify = async () => {
    setVerifying(true);
    setIsCached(false);
    setCacheTime(null);
    try {
      const response = await api.postEnforcementVerify({
        chat_id: chatId,
        node_id: nodeId,
        target_kind: targetKind,
        target_id: targetId,
      });
      setVerifyResult(response);
    } catch (error) {
      console.error('Verify failed:', error);
    } finally {
      setVerifying(false);
    }
  };

  const handleRefresh = () => {
    handleVerify();
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

  const handleDo = async () => {
    if (!verifyResult || executing) return;
    
    setExecuting(true);
    setDoError(null);
    try {
      const taskText = `Fix the gaps identified in this verification result:

VERIFICATION RESULT:
${JSON.stringify(verifyResult, null, 2)}

INSTRUCTIONS:
- Analyze the verification result above
- Focus ONLY on rules that were violated (followed: false)
- Fix ONLY the missing or incomplete parts mentioned in the overview
- Use files_summary to understand what files need changes
- Do NOT redo what's already working (rules with followed: true)
- After making changes, they will be automatically verified`;
      
      const response = await api.postEnforcementDo({
        chat_id: chatId,
        node_id: nodeId,
        target_kind: targetKind,
        target_id: targetId,
        task_text: taskText,
      });
      
      if (!response.success) {
        throw new Error(response.error || 'Do action failed');
      }
      
      // Backend already executed and verified - use its response
      console.log('[DO] Response from backend:', response);
      
      // Update with the NEW verification result from backend
      if (response.verification_result) {
        setVerifyResult({
          success: true,
          verdict: response.verification_result.verdict,
          overview: response.verification_result.overview,
          rules_analysis: response.verification_result.rules_analysis || [],
          files_summary: response.verification_result.files_summary || [],
          code_blocks: response.verification_result.code_blocks || [],
        });
      }
      
      // Store the execution result for display
      setDoResult(response);
    } catch (error) {
      console.error('Do failed:', error);
      setDoError(error instanceof Error ? error.message : 'Unknown error during execution');
    } finally {
      setExecuting(false);
    }
  };

  const handleTest = async () => {
    if (!verifyResult || testing) return;
    
    setTesting(true);
    setTestError(null);
    try {
      const response = await api.postEnforcementTest({
        chat_id: chatId,
        node_id: nodeId,
        target_kind: targetKind,
        target_id: targetId,
      });
      
      console.log('[TEST] Response from backend:', response);
      
      if (response.error) {
        setTestError(response.error);
      } else {
        setTestResults(response.results || []);
        setTestFile(response.test_file || '');
      }
    } catch (error) {
      console.error('Test failed:', error);
      setTestError(error instanceof Error ? error.message : 'Unknown error during test generation');
    } finally {
      setTesting(false);
    }
  };

  const toggleBlock = (index: number) => {
    setExpandedBlocks(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
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
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="subtitle2" fontWeight={600}>
          Enforcement Panel
        </Typography>
        <IconButton onClick={onClose} size="small" sx={{ color: colors.grey }}>
          <CloseIcon />
        </IconButton>
      </Box>

      <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
        {targetKind}: {targetId}
      </Typography>

      {isCached && cacheTime && (
        <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'center' }}>
          <Chip 
            label={`Cached ${getTimeAgo(cacheTime)}`} 
            size="small" 
            sx={{ bgcolor: 'grey.200', color: 'text.secondary' }}
          />
          <IconButton onClick={handleRefresh} size="small" disabled={verifying}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Box>
      )}

      <Stack spacing={2} sx={{ mb: 2 }}>
        <Button
          onClick={handleVerify}
          disabled={verifying || executing || testing}
          colorVariant="green"
          fullWidth
          startIcon={verifying ? <CircularProgress size={16} sx={{ color: 'white' }} /> : undefined}
          sx={{ borderRadius: 0 }}
        >
          {verifying ? 'Verifying...' : 'Verify'}
        </Button>

        <Button
          onClick={handleDo}
          disabled={!hasVerified || verifying || executing || testing || !(verdict === 'partial' || verdict === 'not_done')}
          colorVariant="green"
          fullWidth
          startIcon={executing ? <CircularProgress size={16} sx={{ color: 'white' }} /> : undefined}
          sx={{ borderRadius: 0 }}
        >
          {executing ? 'Executing...' : 'Do'}
        </Button>

        {targetKind === 'substep' && (
          <Button
            onClick={handleTest}
            disabled={!hasVerified || verifying || executing || testing || !(doResult || verdict === 'done')}
            colorVariant="dark-green"
            fullWidth
            startIcon={testing ? <CircularProgress size={16} sx={{ color: 'white' }} /> : undefined}
            sx={{ borderRadius: 0 }}
          >
            {testing ? 'Testing...' : 'Test'}
          </Button>
        )}
      </Stack>

      {verifyResult && (
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
            Verdict: {verdict}
          </Typography>

          {/* Overview Section - Markdown formatted */}
          {verifyResult.overview && (
            <Box 
              sx={{ 
                mb: 2, 
                p: 1.5, 
                bgcolor: 'grey.50', 
                borderRadius: 0,
                '& h1, & h2, & h3': { fontSize: '0.875rem', fontWeight: 600, mb: 0.5, mt: 0.5 },
                '& h4, & h5, & h6': { fontSize: '0.8125rem', fontWeight: 600, mb: 0.5, mt: 0.5 },
                '& p': { fontSize: '0.75rem', mb: 0.5, mt: 0 },
                '& ul, & ol': { fontSize: '0.75rem', pl: 2, mb: 0.5, mt: 0 },
                '& li': { fontSize: '0.75rem', mb: 0.25 },
                '& code': { fontSize: '0.7rem', bgcolor: 'grey.200', px: 0.5, borderRadius: 0.5 },
                '& pre': { fontSize: '0.7rem', bgcolor: 'grey.200', p: 1, borderRadius: 0, overflow: 'auto' },
              }}
            >
              <ReactMarkdown>{verifyResult.overview}</ReactMarkdown>
            </Box>
          )}

          {/* Rules Analysis Section */}
          {verifyResult.rules_analysis && verifyResult.rules_analysis.length > 0 && (
            <Box sx={{ mt: 2, mb: 2 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                Rules Compliance ({verifyResult.rules_analysis.length})
              </Typography>
              <Stack spacing={1}>
                {verifyResult.rules_analysis.map((rule: any, index: number) => (
                  <Box
                    key={index}
                    sx={{
                      p: 1.5,
                      bgcolor: rule.followed ? 'rgba(135, 174, 115, 0.1)' : 'rgba(244, 67, 54, 0.1)',
                      border: '1px solid',
                      borderColor: rule.followed ? colors.green : '#f44336',
                      borderRadius: 0,
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                      <Chip
                        label={rule.followed ? 'FOLLOWED' : 'VIOLATED'}
                        size="small"
                        sx={{
                          bgcolor: rule.followed ? colors.green : '#f44336',
                          color: 'white',
                          mr: 1,
                          fontWeight: 'bold',
                        }}
                      />
                      <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
                        {rule.rule_id}
                      </Typography>
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 0.5 }}>
                      {rule.rule_text}
                    </Typography>
                    <Box 
                      sx={{ 
                        fontStyle: 'italic',
                        '& p': { fontSize: '0.75rem', mb: 0, mt: 0, color: 'text.secondary' },
                        '& ul, & ol': { fontSize: '0.75rem', pl: 2, mb: 0, mt: 0, color: 'text.secondary' },
                        '& li': { fontSize: '0.75rem', mb: 0.25 },
                        '& code': { fontSize: '0.7rem', bgcolor: 'grey.200', px: 0.5, borderRadius: 0.5 },
                      }}
                    >
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'inline', mr: 0.5 }}>
                        Evidence:
                      </Typography>
                      <ReactMarkdown>{rule.evidence}</ReactMarkdown>
                    </Box>
                    {/* Show which substeps used this rule */}
                    {rule.used_in_substeps && rule.used_in_substeps.length > 0 && (
                      <Box sx={{ mt: 0.5, pt: 0.5, borderTop: '1px solid', borderColor: 'divider' }}>
                        <Typography variant="caption" color="text.secondary">
                          Used in substeps: {rule.used_in_substeps.join(', ')}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                ))}
              </Stack>
            </Box>
          )}

          {verifyResult.files_summary && verifyResult.files_summary.length > 0 && (
            <>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mt: 2, mb: 1 }}>
                Files Changed ({verifyResult.files_summary.length})
              </Typography>
              <Stack spacing={1}>
                {verifyResult.files_summary.map((file: FileSummary, index: number) => (
                  <Box
                    key={index}
                    sx={{
                      p: 1,
                      bgcolor: 'grey.100',
                      borderRadius: 0,
                      border: '1px solid',
                      borderColor: colors.green,
                    }}
                  >
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                      {file.path}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      Lines: {file.lines_changed}
                    </Typography>
                    <Box sx={{ display: 'block' }}>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'inline', mr: 0.5 }}>
                        Changes:
                      </Typography>
                      <Box 
                        component="span"
                        sx={{ 
                          display: 'inline',
                          '& p': { fontSize: '0.75rem', mb: 0, mt: 0, color: 'text.secondary', display: 'inline' },
                          '& code': { fontSize: '0.7rem', bgcolor: 'grey.200', px: 0.5, borderRadius: 0.5 },
                        }}
                      >
                        <ReactMarkdown>{file.changes}</ReactMarkdown>
                      </Box>
                    </Box>
                    <Box sx={{ display: 'block' }}>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'inline', mr: 0.5 }}>
                        Impact:
                      </Typography>
                      <Box 
                        component="span"
                        sx={{ 
                          display: 'inline',
                          '& p': { fontSize: '0.75rem', mb: 0, mt: 0, color: 'text.secondary', display: 'inline' },
                          '& code': { fontSize: '0.7rem', bgcolor: 'grey.200', px: 0.5, borderRadius: 0.5 },
                        }}
                      >
                        <ReactMarkdown>{file.impact}</ReactMarkdown>
                      </Box>
                    </Box>
                    {file.substeps_fulfilled.length > 0 && (
                      <Typography variant="caption" color="primary" display="block">
                        Substeps: {file.substeps_fulfilled.join(', ')}
                      </Typography>
                    )}
                  </Box>
                ))}
              </Stack>
            </>
          )}

          {verifyResult.code_blocks && verifyResult.code_blocks.length > 0 && (
            <>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mt: 2, mb: 1 }}>
                Code Changes ({verifyResult.code_blocks.length})
              </Typography>
              <Stack spacing={1}>
                {verifyResult.code_blocks.map((block: CodeBlock, index: number) => (
                  <Box key={index} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 0 }}>
                    <Box
                      sx={{
                        p: 1,
                        bgcolor: 'grey.200',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        cursor: 'pointer',
                      }}
                      onClick={() => toggleBlock(index)}
                    >
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        {block.file} (lines {block.lines})
                      </Typography>
                      <IconButton size="small">
                        <ExpandMoreIcon
                          sx={{
                            transform: expandedBlocks.has(index) ? 'rotate(180deg)' : 'rotate(0deg)',
                            transition: 'transform 0.3s',
                          }}
                        />
                      </IconButton>
                    </Box>
                    <Collapse in={expandedBlocks.has(index)}>
                      <Box sx={{ p: 2 }}>
                        <Box 
                          sx={{ 
                            mb: 1,
                            color: colors.green,
                            fontWeight: 'bold',
                            '& p': { fontSize: '0.75rem', mb: 0.5, mt: 0, fontWeight: 'bold', color: colors.green },
                            '& ul, & ol': { fontSize: '0.75rem', pl: 2, mb: 0.5, mt: 0 },
                            '& li': { fontSize: '0.75rem', mb: 0.25 },
                            '& code': { fontSize: '0.7rem', bgcolor: 'grey.200', px: 0.5, borderRadius: 0.5 },
                          }}
                        >
                          <ReactMarkdown>{block.annotation}</ReactMarkdown>
                        </Box>
                        <Box
                          component="pre"
                          sx={{
                            p: 1,
                            bgcolor: 'grey.100',
                            overflow: 'auto',
                            fontSize: '12px',
                            borderRadius: 0,
                            fontFamily: 'monospace',
                          }}
                        >
                          {block.code || '(no code)'}
                        </Box>
                      </Box>
                    </Collapse>
                  </Box>
                ))}
              </Stack>
            </>
          )}

          {doError && (
            <Box sx={{ mt: 2, p: 2, bgcolor: 'rgba(244, 67, 54, 0.1)', border: '1px solid #f44336', borderRadius: 0 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1, color: '#f44336' }}>
                Execution Error:
              </Typography>
              <Typography variant="body2" sx={{ color: '#f44336' }}>{doError}</Typography>
            </Box>
          )}

          {doResult && (
            <Box sx={{ mt: 2, p: 2, bgcolor: 'rgba(135, 174, 115, 0.1)', border: '1px solid', borderColor: colors.green, borderRadius: 0 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 2, color: colors.green }}>
                ✅ Execution Complete
              </Typography>
              
              {(doResult as any).execution_result && (
                <Box>
                  <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                    New Verdict: {(doResult as any).execution_result.verdict}
                  </Typography>
                  
                  {(doResult as any).execution_result.overview && (
                    <Box 
                      sx={{ 
                        mt: 1, 
                        p: 1, 
                        bgcolor: 'white', 
                        borderRadius: 0,
                        border: '1px solid',
                        borderColor: 'divider',
                        '& h1, & h2, & h3': { fontSize: '0.875rem', fontWeight: 600, mb: 0.5, mt: 0.5 },
                        '& p': { fontSize: '0.75rem', mb: 0.5, mt: 0 },
                        '& ul, & ol': { fontSize: '0.75rem', pl: 2, mb: 0.5, mt: 0 },
                        '& li': { fontSize: '0.75rem', mb: 0.25 },
                      }}
                    >
                      <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block', mb: 0.5 }}>
                        Execution Overview:
                      </Typography>
                      <ReactMarkdown>{(doResult as any).execution_result.overview}</ReactMarkdown>
                    </Box>
                  )}
                  
                  {(doResult as any).execution_result.files_summary && (doResult as any).execution_result.files_summary.length > 0 && (
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block', mb: 0.5 }}>
                        Files Modified ({(doResult as any).execution_result.files_summary.length}):
                      </Typography>
                      <Stack spacing={0.5}>
                        {(doResult as any).execution_result.files_summary.map((file: FileSummary, index: number) => (
                          <Box key={index} sx={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>
                            • {file.path}
                          </Box>
                        ))}
                      </Stack>
                    </Box>
                  )}
                </Box>
              )}
              
              <Box sx={{ mt: 2, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.7rem' }}>
                  Task sent to Cline
                </Typography>
              </Box>
            </Box>
          )}

          {testError && (
            <Box sx={{ mt: 2, p: 2, bgcolor: 'rgba(244, 67, 54, 0.1)', border: '1px solid #f44336', borderRadius: 0 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1, color: '#f44336' }}>
                Test Generation Error:
              </Typography>
              <Typography variant="body2" sx={{ color: '#f44336', mb: 2 }}>{testError}</Typography>
              <Typography variant="caption" color="text.secondary">
                Manual verification recommended
              </Typography>
            </Box>
          )}

          {testResults.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                Test Results ({testResults.length})
              </Typography>
              {testFile && (
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1, fontFamily: 'monospace' }}>
                  Test file: {testFile}
                </Typography>
              )}
              <Stack spacing={1}>
                {testResults.map((test: any, index: number) => (
                  <Box
                    key={index}
                    sx={{
                      p: 1.5,
                      bgcolor: test.status === 'pass' ? 'rgba(135, 174, 115, 0.1)' : 'rgba(244, 67, 54, 0.1)',
                      border: '1px solid',
                      borderColor: test.status === 'pass' ? colors.green : '#f44336',
                      borderRadius: 0,
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5, gap: 1 }}>
                      <Chip
                        label={test.status.toUpperCase()}
                        size="small"
                        sx={{
                          bgcolor: test.status === 'pass' ? colors.green : '#f44336',
                          color: 'white',
                          fontWeight: 'bold',
                        }}
                      />
                      <Chip
                        label={test.category}
                        size="small"
                        variant="outlined"
                        sx={{ borderColor: 'divider' }}
                      />
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 0.5 }}>
                      {test.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                      {test.description}
                    </Typography>
                    {test.rule_description && (
                      <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>
                        <strong>Rule:</strong> {test.rule_description}
                      </Typography>
                    )}
                    {test.feature_name && (
                      <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>
                        <strong>Feature:</strong> {test.feature_name}
                      </Typography>
                    )}
                    {test.output && (
                      <Box
                        component="pre"
                        sx={{
                          mt: 1,
                          p: 1,
                          bgcolor: 'grey.100',
                          fontSize: '11px',
                          borderRadius: 0,
                          overflow: 'auto',
                          maxHeight: '100px',
                        }}
                      >
                        {test.output}
                      </Box>
                    )}
                  </Box>
                ))}
              </Stack>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}
