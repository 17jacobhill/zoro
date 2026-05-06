import { useState } from 'react';
import { Handle, Position } from 'reactflow';
import { Paper, Typography, IconButton, Box, alpha } from '@mui/material';
import { Check, Close, Delete } from '@mui/icons-material';

import { CompactIconButton } from './CompactIconButton';
import { colors } from './colors';

interface FlowNodeData {
  label: string;
  isAnalyzing?: boolean;
  selected?: boolean;
  status?: 'pending' | 'in_progress' | 'completed' | 'blocked';
  onDelete?: () => void;
}

export function FlowNode({ data, selected }: { data: FlowNodeData; selected?: boolean }) {
  const { label, isAnalyzing, status, onDelete } = data;
  const isSelected = selected || data.selected;
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  // Status-based styling
  const getStatusStyle = () => {
    // Get base style from status
    let baseStyle;
    
    if (isAnalyzing) {
      baseStyle = {
        backgroundColor: 'warning.light',
        border: '2px solid',
        borderColor: 'warning.main',
      };
    } else {
      switch (status) {
        case 'completed':
          baseStyle = {
            background: `repeating-linear-gradient(45deg, ${colors.dividerMuted}, ${colors.dividerMuted} 10px, ${colors.surfaceMuted} 10px, ${colors.surfaceMuted} 20px)`,
            border: '1px solid',
            borderColor: colors.grey,
            opacity: 0.7,
          };
          break;
        case 'in_progress':
          baseStyle = {
            backgroundColor: 'rgba(255, 193, 7, 0.1)',
            border: '2px solid',
            borderColor: 'warning.main',
          };
          break;
        case 'blocked':
          baseStyle = {
            backgroundColor: 'rgba(244, 67, 54, 0.1)',
            border: '2px solid',
            borderColor: 'error.main',
          };
          break;
        default:
          baseStyle = {
            backgroundColor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
          };
      }
    }

    // If selected, add selection border while preserving status styling
    if (isSelected) {
      return {
        ...baseStyle,
        border: '3px solid',
        borderColor: colors.green,
      };
    }

    return baseStyle;
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onDelete) {
      onDelete();
    }
    setConfirmingDelete(false);
  };

  return (
    <Paper 
      elevation={0}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setConfirmingDelete(false);
      }}
      sx={{ 
        p: 2, 
        minWidth: 120,
        maxWidth: 200,
        textAlign: 'center',
        cursor: 'pointer',
        position: 'relative',
        ...getStatusStyle(),
        transition: 'all 0.3s ease',
        animation: isAnalyzing ? 'pulse 1.5s ease-in-out infinite' : 'none',
        '@keyframes pulse': {
          '0%, 100%': {
            transform: 'scale(1)',
          },
          '50%': {
            transform: 'scale(1.05)',
          },
        },
      }}
    >
      <Handle type="target" position={Position.Top} />
      
      {onDelete && isHovered && !confirmingDelete && (
        <IconButton
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            setConfirmingDelete(true);
          }}
          sx={{
            position: 'absolute',
            top: 4,
            right: 4,
            p: 0.5,
            backgroundColor: 'background.paper',
            '&:hover': {
              backgroundColor: 'error.light',
            },
          }}
        >
          <Delete fontSize="small" />
        </IconButton>
      )}

      {confirmingDelete && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 0.5,
            backgroundColor: alpha(colors.white, 0.95),
            zIndex: 1,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <CompactIconButton
              label="Confirm delete"
              icon={<Check fontSize="small" />}
              size="small"
              tone="red"
              onClick={handleDelete}
            />
            <CompactIconButton
              label="Cancel delete"
              icon={<Close fontSize="small" />}
              size="small"
              tone="grey"
              onClick={(e) => {
                e.stopPropagation();
                setConfirmingDelete(false);
              }}
            />
          </Box>
        </Box>
      )}
      
      <Typography 
        variant="body2" 
        fontWeight={600}
        sx={{ 
          textTransform: 'capitalize',
        }}
      >
        {label}
      </Typography>
      
      <Handle type="source" position={Position.Bottom} />
    </Paper>
  );
}
