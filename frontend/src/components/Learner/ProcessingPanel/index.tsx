import { Box } from '@mui/material';
import { StageProgressIndicator } from './StageProgressIndicator';
import { ParsingSection } from './ParsingSection';
import { CategorizingSection } from './CategorizingSection';
import { LearningSection } from './LearningSection';
import { LogPanel } from './LogPanel';
import { FileUpload } from './FileUpload';
import type { Task, LogEntry } from '../../../services/api';

type Stage = 'upload' | 'parsing' | 'parsed' | 'categorizing' | 'categorized' | 'learning' | 'learned';

interface ProcessingPanelProps {
  showFileUpload: boolean;
  stage: Stage;
  logs: LogEntry[];
  isProcessing: boolean;
  parsedTasks: Task[];
  pendingTasks: Task[];
  onTasksLoaded: (tasks: Task[], chatName: string, responseLogs?: LogEntry[]) => void;
  onProcessStart: () => void;
  onProcessError: (error: string) => void;
  onCategorize: () => void;
  onApprove: (taskId: string) => void;
  onApproveAll: () => void;
  onLearnRules: () => void;
  isLearning: boolean;
  currentTaskIndex?: number;
  totalTasks?: number;
  currentTaskType?: string;
}

export function ProcessingPanel({
  showFileUpload,
  stage,
  logs,
  isProcessing,
  parsedTasks,
  pendingTasks,
  onTasksLoaded,
  onProcessStart,
  onProcessError,
  onCategorize,
  onApprove,
  onApproveAll,
  onLearnRules,
  isLearning,
  currentTaskIndex,
  totalTasks,
  currentTaskType,
}: ProcessingPanelProps) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Stage Progress Indicator - Always at top */}
      <StageProgressIndicator stage={stage} />

      {/* File Upload */}
      {showFileUpload && (
        <FileUpload
          onTasksLoaded={onTasksLoaded}
          onProcessStart={onProcessStart}
          onProcessError={onProcessError}
        />
      )}

      {/* Parsing Section */}
      <ParsingSection
        stage={stage}
        parsedTasks={parsedTasks}
        onCategorize={onCategorize}
      />

      {/* Categorizing Section (includes ApprovalPanel) */}
      <CategorizingSection
        stage={stage}
        pendingTasks={pendingTasks}
        onApprove={onApprove}
        onApproveAll={onApproveAll}
      />

      {/* Learning Section */}
      <LearningSection
        stage={stage}
        onLearnRules={onLearnRules}
        isLearning={isLearning}
        currentTaskIndex={currentTaskIndex}
        totalTasks={totalTasks}
        currentTaskType={currentTaskType}
      />

      {/* Logs Panel - Underneath stages */}
      <LogPanel logs={logs} isProcessing={isProcessing} />
    </Box>
  );
}
