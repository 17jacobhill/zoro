import { useState } from 'react';
import { Box, Typography, Chip, Tooltip } from '@mui/material';
import StarIcon from '@mui/icons-material/Star';
import StarBorderIcon from '@mui/icons-material/StarBorder';
import DeleteIcon from '@mui/icons-material/Delete';
import BoltIcon from '@mui/icons-material/Bolt';
import ScienceIcon from '@mui/icons-material/Science';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import { ToggleOn, ToggleOff } from '@mui/icons-material';
import { colors } from '../../design-system/colors';
import { IconActionButton } from '../../design-system/IconActionButton';
import type { KnowledgeItem } from '../../types/knowledge';

interface RuleCardProps {
  item: KnowledgeItem;
  isSelected: boolean;
  isNew?: boolean;
  onSelect: () => void;
  onFavoriteToggle: () => void;
  onEdit?: () => void;
  onDelete: () => void;
  onStrictToggle?: () => void;
  onTestableToggle?: () => void;
}

export const RuleCard: React.FC<RuleCardProps> = ({
  item,
  isSelected,
  isNew = false,
  onSelect,
  onFavoriteToggle,
  onEdit,
  onDelete,
  onStrictToggle,
  onTestableToggle,
}) => {
  const [expanded, setExpanded] = useState(false);

  const preview = item.content.length > 100 
    ? `${item.content.substring(0, 100)}...` 
    : item.content;

  return (
    <Box
      sx={{
        position: 'relative',
        borderLeft: isSelected ? `3px solid ${colors.green}` : '3px solid transparent',
        borderBottom: `1px solid ${colors.divider}`,
        borderRadius: 0,
        padding: '10px 10px 10px 12px',
        marginBottom: 0,
        cursor: 'pointer',
        backgroundColor: isSelected ? colors.surfaceTint : 'transparent',
        '&:hover': {
          backgroundColor: isSelected ? colors.surfaceTint : colors.surfaceSubtle,
        },
      }}
      onClick={() => {
        onSelect();
        setExpanded(!expanded);
      }}
    >
      {isNew && (
        <Box
          sx={{
            position: 'absolute',
            top: 6,
            right: 8,
            backgroundColor: colors.green,
            color: colors.white,
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 'bold',
            zIndex: 1,
          }}
        >
          NEW
        </Box>
      )}

      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1 }}>
        <Box sx={{ flex: 1 }}>
          <Typography sx={{ fontWeight: 600, fontSize: '0.86rem', mb: 0.4 }}>
            {item.title}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Chip
              label={item.category}
              size="small"
              sx={{
                backgroundColor: colors.green,
                color: colors.white,
                fontSize: '11px',
                height: '20px',
              }}
            />
            <Chip
              label={item.type}
              size="small"
              sx={{
                backgroundColor: colors.grey,
                color: colors.white,
                fontSize: '11px',
                height: '20px',
              }}
            />
            {item.confidence !== undefined && (
              <Chip
                icon={<StarIcon sx={{ fontSize: '11px !important', color: `${colors.white} !important` }} />}
                label={`${(item.confidence * 100).toFixed(0)}%`}
                size="small"
                sx={{
                  backgroundColor: item.confidence >= 0.8 ? colors.green : item.confidence >= 0.6 ? colors.confidenceMedium : colors.confidenceLow,
                  color: colors.white,
                  fontSize: '11px',
                  height: '20px',
                }}
              />
            )}
            {item.decay !== undefined && (
              <Chip
                icon={<BoltIcon sx={{ fontSize: '11px !important', color: `${colors.white} !important` }} />}
                label={`${(item.decay * 100).toFixed(0)}%`}
                size="small"
                sx={{
                  backgroundColor: item.decay > 0.6 ? colors.green : colors.grey,
                  color: colors.white,
                  fontSize: '11px',
                  height: '20px',
                }}
              />
            )}
            {item.usage_count > 0 && (
              <Typography sx={{ fontSize: '11px', color: colors.grey }}>
                Used {item.usage_count}x
              </Typography>
            )}
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 0.5 }} onClick={(e) => e.stopPropagation()}>
          {item.type === 'rule' && onStrictToggle && (
            <Tooltip title={item.is_strict ? "Remove strict enforcement" : "Mark for strict enforcement"}>
              <IconActionButton
                tone={item.is_strict ? 'green' : 'grey'}
                active={item.is_strict}
                onClick={(e) => {
                  e.stopPropagation();
                  onStrictToggle();
                }}
              >
                {item.is_strict ? <ToggleOn fontSize="small" /> : <ToggleOff fontSize="small" />}
              </IconActionButton>
            </Tooltip>
          )}
          {item.type === 'rule' && onTestableToggle && (
            <Tooltip title={!item.is_strict ? "Mark as strict first to enable testing" : item.is_testable ? "Remove testable marking" : "Mark as testable (requires test evidence)"}>
              <span>
                <IconActionButton
                  disableRipple
                  disabled={!item.is_strict}
                  tone={item.is_testable ? 'blue' : 'grey'}
                  active={item.is_testable}
                  onClick={(e) => {
                    e.stopPropagation();
                    onTestableToggle();
                  }}
                  sx={{
                    opacity: !item.is_strict ? 0.3 : 1,
                  }}
                >
                  <ScienceIcon fontSize="small" />
                </IconActionButton>
              </span>
            </Tooltip>
          )}
          {onEdit && (
            <Tooltip title="Edit rule">
              <IconActionButton
                tone="grey"
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit();
                }}
              >
                <EditOutlinedIcon sx={{ fontSize: '17px', color: colors.grey }} />
              </IconActionButton>
            </Tooltip>
          )}
          <IconActionButton
            tone={item.is_favorite ? 'gold' : 'grey'}
            active={item.is_favorite}
            onClick={(e) => {
              e.stopPropagation();
              onFavoriteToggle();
            }}
          >
            {item.is_favorite ? (
              <StarIcon sx={{ fontSize: '18px', color: colors.gold }} />
            ) : (
              <StarBorderIcon sx={{ fontSize: '18px', color: colors.grey }} />
            )}
          </IconActionButton>
          <IconActionButton
            tone="red"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
          >
            <DeleteIcon sx={{ fontSize: '18px', color: colors.red }} />
          </IconActionButton>
        </Box>
      </Box>

      {!expanded ? (
        <Typography sx={{ fontSize: '0.78rem', color: colors.subtleText, mt: 0.75, lineHeight: 1.35 }}>
          {preview}
        </Typography>
      ) : (
        <Box sx={{ mt: 1.25 }}>
          <Box sx={{ mb: 1.25 }}>
            <Typography sx={{ fontWeight: 'bold', fontSize: '12px', color: colors.grey, mb: 0.5 }}>
              Content
            </Typography>
            <Typography sx={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap', lineHeight: 1.4 }}>
              {item.content}
            </Typography>
          </Box>

          {item.context && (
            <Box sx={{ mb: 1.25 }}>
              <Typography sx={{ fontWeight: 'bold', fontSize: '12px', color: colors.grey, mb: 0.5 }}>
                Context
              </Typography>
              <Typography sx={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap', lineHeight: 1.4 }}>
                {item.context}
              </Typography>
            </Box>
          )}

          {item.evidence && (
            <Box sx={{ mb: 1.25 }}>
              <Typography sx={{ fontWeight: 'bold', fontSize: '12px', color: colors.grey, mb: 0.5 }}>
                Evidence
              </Typography>
              <Typography
                sx={{
                  fontSize: '12px',
                  fontFamily: 'monospace',
                  backgroundColor: colors.surfaceMuted,
                  padding: '8px',
                  borderRadius: '4px',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {item.evidence}
              </Typography>
            </Box>
          )}

          {item.confidence_reasoning && (
            <Box sx={{ mb: 1.25 }}>
              <Typography sx={{ fontWeight: 'bold', fontSize: '12px', color: colors.grey, mb: 0.5 }}>
                Confidence Reasoning
              </Typography>
              <Typography sx={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap', lineHeight: 1.4 }}>
                {item.confidence_reasoning}
              </Typography>
            </Box>
          )}

          {item.decay_reasoning && (
            <Box sx={{ mb: 1.25 }}>
              <Typography sx={{ fontWeight: 'bold', fontSize: '12px', color: colors.grey, mb: 0.5 }}>
                Specificity Reasoning
              </Typography>
              <Typography sx={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap', lineHeight: 1.4 }}>
                {item.decay_reasoning}
              </Typography>
            </Box>
          )}

          <Box sx={{ mt: 1.25, pt: 1.25, borderTop: `1px solid ${colors.divider}` }}>
            <Typography sx={{ fontSize: '11px', color: colors.grey }}>
              Source: {item.source_file}
            </Typography>
            <Typography sx={{ fontSize: '11px', color: colors.grey }}>
              Created: {new Date(item.created_at).toLocaleDateString()}
            </Typography>
          </Box>
        </Box>
      )}
    </Box>
  );
};
