import { Component, type ErrorInfo, type ReactNode } from 'react';
import { CssBaseline, Box, Typography } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { ProductShell } from './components/ProductShell';
import { CompactIconButton } from './design-system/CompactIconButton';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100vh',
            p: 4,
            textAlign: 'center',
          }}
        >
          <Typography variant="h4" color="error" gutterBottom>
            Something went wrong
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
            {this.state.error?.message || 'An unexpected error occurred'}
          </Typography>
          <CompactIconButton
            label="Reload page"
            icon={<RefreshIcon sx={{ fontSize: 18 }} />}
            tone="red"
            onClick={() => window.location.reload()}
          />
        </Box>
      );
    }

    return this.props.children;
  }
}

function App() {
  return (
    <ErrorBoundary>
      <CssBaseline />
      <ProductShell />
    </ErrorBoundary>
  );
}

export default App;
