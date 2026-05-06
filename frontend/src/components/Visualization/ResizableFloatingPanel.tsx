import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Box, Typography } from '@mui/material';

import { colors } from '../../design-system/colors';

interface ResizableFloatingPanelProps {
  title: string;
  collapsedTop: string;
  panelZIndex: number;
  initialY: number;
  children: ReactNode;
}

type DragState = { offsetX: number; offsetY: number } | null;
type ResizeState = { startX: number; startWidth: number } | null;
type ResizeYState = { startY: number; startHeight: number } | null;

const PANEL_MARGIN = 8;
const PANEL_MIN_WIDTH = 260;
const PANEL_MIN_HEIGHT = 320;
const PANEL_MAX_WIDTH = 1200;
const PANEL_MAX_HEIGHT = 1200;

export function ResizableFloatingPanel({
  title,
  collapsedTop,
  panelZIndex,
  initialY,
  children,
}: ResizableFloatingPanelProps) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: initialY });
  const [drag, setDrag] = useState<DragState>(null);
  const [width, setWidth] = useState(360);
  const [resize, setResize] = useState<ResizeState>(null);
  const [height, setHeight] = useState(520);
  const [resizeY, setResizeY] = useState<ResizeYState>(null);
  const positioned = useRef(false);

  useLayoutEffect(() => {
    if (open && !positioned.current) {
      const x = Math.max(PANEL_MARGIN, window.innerWidth - width - 16);
      const y = Math.max(PANEL_MARGIN, Math.min(initialY, window.innerHeight - height - PANEL_MARGIN));
      setPosition({ x, y });
      positioned.current = true;
    }
  }, [height, initialY, open, width]);

  useEffect(() => {
    if (!drag && !resize && !resizeY) return;

    const handleMove = (event: MouseEvent) => {
      const viewWidth = window.innerWidth;
      const viewHeight = window.innerHeight;
      const maxX = Math.max(PANEL_MARGIN, viewWidth - width - PANEL_MARGIN);
      const maxY = Math.max(PANEL_MARGIN, viewHeight - height - PANEL_MARGIN);

      if (drag) {
        const nextX = Math.min(Math.max(PANEL_MARGIN, event.clientX - drag.offsetX), maxX);
        const nextY = Math.min(Math.max(PANEL_MARGIN, event.clientY - drag.offsetY), maxY);
        setPosition({ x: nextX, y: nextY });
      }

      if (resize) {
        const delta = event.clientX - resize.startX;
        const maxWidthByViewport = Math.max(
          PANEL_MIN_WIDTH,
          Math.min(PANEL_MAX_WIDTH, viewWidth - position.x - PANEL_MARGIN)
        );
        const nextWidth = Math.min(Math.max(PANEL_MIN_WIDTH, resize.startWidth + delta), maxWidthByViewport);
        setWidth(nextWidth);
      }

      if (resizeY) {
        const deltaY = event.clientY - resizeY.startY;
        const maxHeightByViewport = Math.max(
          PANEL_MIN_HEIGHT,
          Math.min(PANEL_MAX_HEIGHT, viewHeight - position.y - PANEL_MARGIN)
        );
        const nextHeight = Math.min(Math.max(PANEL_MIN_HEIGHT, resizeY.startHeight + deltaY), maxHeightByViewport);
        setHeight(nextHeight);
      }
    };

    const handleUp = () => {
      setDrag(null);
      setResize(null);
      setResizeY(null);
    };

    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [drag, height, position.x, position.y, resize, resizeY, width]);

  return (
    <>
      <Box
        sx={{
          position: 'fixed',
          left: position.x,
          top: position.y,
          zIndex: panelZIndex,
          display: 'flex',
          alignItems: 'stretch',
          pointerEvents: open ? 'auto' : 'none',
        }}
      >
        {open && (
          <Box
            sx={{
              position: 'relative',
              width,
              height,
              bgcolor: 'background.paper',
              border: '1px solid',
              borderColor: 'divider',
              boxShadow: '0 10px 30px rgba(0,0,0,0.12)',
              pointerEvents: 'auto',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <Box
              onMouseDown={(event) => {
                event.preventDefault();
                setResize({
                  startX: event.clientX,
                  startWidth: width,
                });
              }}
              sx={{
                position: 'absolute',
                right: 0,
                top: 0,
                width: 10,
                height: '100%',
                cursor: 'ew-resize',
                zIndex: 3,
                bgcolor: 'rgba(135, 174, 115, 0.12)',
                borderLeft: '1px solid',
                borderColor: 'divider',
              }}
            />
            <Box
              onMouseDown={(event) => {
                event.preventDefault();
                setResizeY({
                  startY: event.clientY,
                  startHeight: height,
                });
              }}
              sx={{
                position: 'absolute',
                left: 0,
                right: 0,
                bottom: 0,
                height: 8,
                cursor: 'ns-resize',
                zIndex: 3,
                bgcolor: 'rgba(135, 174, 115, 0.12)',
                borderTop: '1px solid',
                borderColor: 'divider',
              }}
            />
            <Box
              onMouseDown={(event) => {
                event.preventDefault();
                setResize({
                  startX: event.clientX,
                  startWidth: width,
                });
                setResizeY({
                  startY: event.clientY,
                  startHeight: height,
                });
              }}
              sx={{
                position: 'absolute',
                right: 0,
                bottom: 0,
                width: 16,
                height: 16,
                cursor: 'nwse-resize',
                zIndex: 4,
                bgcolor: 'rgba(135, 174, 115, 0.2)',
                borderLeft: '1px solid',
                borderTop: '1px solid',
                borderColor: 'divider',
              }}
            />
            <Box
              onMouseDown={(event) => {
                event.preventDefault();
                setDrag({
                  offsetX: event.clientX - position.x,
                  offsetY: event.clientY - position.y,
                });
              }}
              sx={{
                cursor: 'move',
                userSelect: 'none',
                px: 1.5,
                py: 1,
                bgcolor: colors.green,
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <Typography variant="caption" sx={{ fontWeight: 600, letterSpacing: '0.08em' }}>
                {title}
              </Typography>
              <Box
                onClick={(event) => {
                  event.stopPropagation();
                  setOpen(false);
                }}
                sx={{
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  px: 0.75,
                  py: 0.25,
                  borderRadius: 1,
                  bgcolor: colors.darkGreen,
                }}
              >
                Collapse
              </Box>
            </Box>
            <Box
              sx={{
                flex: 1,
                minHeight: 0,
                overflow: 'hidden',
                pb: 1,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {children}
            </Box>
          </Box>
        )}
      </Box>

      {!open && (
        <Box
          onClick={() => setOpen(true)}
          sx={{
            position: 'fixed',
            right: 0,
            top: collapsedTop,
            transform: 'translateY(-50%)',
            bgcolor: colors.green,
            color: 'white',
            border: '1px solid',
            borderColor: colors.green,
            py: 2,
            px: 0.75,
            cursor: 'pointer',
            writingMode: 'vertical-rl',
            textOrientation: 'mixed',
            fontSize: '0.72rem',
            fontWeight: 600,
            letterSpacing: '0.08em',
            borderTopLeftRadius: 6,
            borderBottomLeftRadius: 6,
            boxShadow: '0 6px 18px rgba(0,0,0,0.12)',
            zIndex: panelZIndex + 1,
            '&:hover': {
              bgcolor: colors.darkGreen,
              borderColor: colors.darkGreen,
            },
          }}
        >
          {title}
        </Box>
      )}
    </>
  );
}
