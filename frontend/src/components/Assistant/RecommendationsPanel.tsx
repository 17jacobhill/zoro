import { useEffect, useState } from 'react';
import { Box, Typography, Divider } from '@mui/material';
import { Button } from '../../design-system/Button';
import { Accordion } from '../../design-system/Accordion';
import { api } from '../../services/api';

type Recommendation = {
  text: string;
  reason?: string;
};

type SourceMeta = {
  path: string;
  mtime: string;
  message_count: number;
  truncated: boolean;
};

export function RecommendationsPanel({ chatId }: { chatId: string | null }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [source, setSource] = useState<SourceMeta | null>(null);

  useEffect(() => {
    if (!chatId) {
      setLoading(false);
      setError(null);
      setRecommendations([]);
      setSource(null);
    }
  }, [chatId]);

  const handleCheck = async () => {
    if (!chatId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.getChatRecommendations({ chat_id: chatId, limit: 100 });
      if (!res?.success) {
        setError(res?.error || 'Failed to fetch recommendations');
        return;
      }
      setRecommendations(res.recommendations || []);
      setSource(res.source || null);
    } catch (e: any) {
      setError(e?.response?.data?.error || e?.message || 'Failed to fetch recommendations');
    } finally {
      setLoading(false);
    }
  };

  if (!chatId) return null;

  return (
    <Accordion
      title={
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <Typography variant="subtitle2" fontWeight={600}>
            Recommendations
          </Typography>
          <Button
            size="small"
            colorVariant="green"
            disabled={loading}
            onClick={(e) => {
              e.stopPropagation();
              void handleCheck();
            }}
          >
            {loading ? 'Checking…' : 'Check'}
          </Button>
        </Box>
      }
      defaultOpen
    >
      <Box sx={{ p: 2 }}>
        {error && (
          <Typography variant="caption" color="error" sx={{ display: 'block', mb: 1 }}>
            {error}
          </Typography>
        )}

        {recommendations.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Click “Check” to get 1–2 lightweight recommendations.
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {recommendations.slice(0, 2).map((rec, idx) => (
              <Box
                key={idx}
                sx={{
                  p: 1.5,
                  bgcolor: 'action.hover',
                  borderRadius: 1,
                }}
              >
                <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
                  {idx + 1}. {rec.text}
                </Typography>
                {rec.reason && (
                  <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                    {rec.reason}
                  </Typography>
                )}
              </Box>
            ))}
          </Box>
        )}

        {source && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontWeight: 600 }}>
              Source
            </Typography>
            <Typography variant="caption" sx={{ display: 'block', fontFamily: 'monospace' }}>
              {source.path}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              Updated: {new Date(source.mtime).toLocaleString()} · Messages: {source.message_count} · Truncated: {String(source.truncated)}
            </Typography>
          </>
        )}
      </Box>
    </Accordion>
  );
}
