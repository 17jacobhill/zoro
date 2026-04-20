import { useState } from 'react';
import { Box, CircularProgress, Typography, Stack } from '@mui/material';
import { UploadFile, Send } from '@mui/icons-material';
import { Button } from '../../../design-system/Button';
import { api, type Task, type LogEntry } from '../../../services/api';

interface FileUploadProps {
  onTasksLoaded: (tasks: Task[], chatName: string, logs?: LogEntry[]) => void;
  onProcessStart: () => void;
  onProcessError: (error: string) => void;
}

export function FileUpload({ onTasksLoaded, onProcessStart, onProcessError }: FileUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleProcess = async () => {
    if (!selectedFile) return;

    setLoading(true);
    onProcessStart();
    
    // Extract chat name from filename (remove extension)
    const chatName = selectedFile.name.replace(/\.md$/, '');
    
    try {
      const parseResponse = await api.parseChat(selectedFile);
      
      if (parseResponse.success) {
        const tasks = parseResponse.tasks;
        
        try {
          const categorizeResponse = await api.categorize(tasks);
          
          if (categorizeResponse.success) {
            const suggestions = categorizeResponse.suggestions;
            const suggestionMap = new Map(
              suggestions.map((s: any) => [s.task_id, s.type])
            );
            
            const categorizedTasks = tasks.map((task: any) => ({
              ...task,
              suggested_type: suggestionMap.get(task.task_id) || 'uncategorized'
            }));
            
            onTasksLoaded(categorizedTasks, chatName, parseResponse.logs);
          } else {
            onTasksLoaded(tasks, chatName, parseResponse.logs);
          }
        } catch (categorizationError) {
          console.error('Categorization failed:', categorizationError);
          onTasksLoaded(tasks, chatName, parseResponse.logs);
        }
      }
    } catch (error: any) {
      console.error('Upload failed:', error);
      onProcessError(error.message || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ p: 2 }}>
      <Stack direction="row" spacing={2} alignItems="center">
        <Button
          component="label"
          startIcon={<UploadFile />}
          disabled={loading}
          colorVariant="green"
        >
          Select File
          <input type="file" accept=".md" hidden onChange={handleFileSelect} />
        </Button>

        {selectedFile && (
          <>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              {selectedFile.name}
            </Typography>
            
            <Button
              onClick={handleProcess}
              startIcon={loading ? <CircularProgress size={20} /> : <Send />}
              disabled={loading}
              colorVariant="green"
            >
              {loading ? 'Processing...' : 'Process File'}
            </Button>
          </>
        )}
      </Stack>
    </Box>
  );
}
