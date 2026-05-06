import { type ComponentProps, type ReactElement } from 'react';
import { PanelResizeHandle as BasePanelResizeHandle } from 'react-resizable-panels';

import { colors } from './colors';

interface PanelResizeHandleProps extends Omit<ComponentProps<typeof BasePanelResizeHandle>, 'style'> {
  direction?: 'horizontal' | 'vertical';
  thickness?: number;
}

const PanelResizeHandle = ({
  direction = 'horizontal',
  thickness = 1,
  ...props
}: PanelResizeHandleProps): ReactElement => {
  const isHorizontal = direction === 'horizontal';

  return (
    <BasePanelResizeHandle
      style={{
        flexShrink: 0,
        width: isHorizontal ? `${thickness}px` : '100%',
        height: isHorizontal ? '100%' : `${thickness}px`,
        backgroundColor: colors.divider,
        cursor: isHorizontal ? 'col-resize' : 'row-resize',
      }}
      {...props}
    />
  );
};

export { PanelResizeHandle };
