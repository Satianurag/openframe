import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

export type TrainedCharacter = {
  id: string;
  job_id: string;
  name: string;
  status: 'queued' | 'running' | 'failed' | 'cancelled' | 'ready' | 'unavailable';
  progress: number;
  stage: string;
  error?: string | null;
  model_id: string;
  trigger_token: string;
  dataset_asset_ids: string[];
  created_at: string;
  updated_at: string;
  configuration?: { provider?: string };
  adapter?: {
    model_id: string;
    sha256: string;
    size_bytes: number;
    rank: number;
    steps: number;
  } | null;
  app_context?: { app_id: string; document_id: string };
};

export function useTrainedCharacters() {
  const [items, setItems] = useState<TrainedCharacter[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const refresh = useCallback(async (offset = 0) => {
    setLoading(true);
    try {
      const result = await api<{ items: TrainedCharacter[]; total: number }>(
        `/characters?limit=100&offset=${offset}`,
      );
      setItems((current) =>
        offset
          ? [...new Map([...current, ...result.items].map((item) => [item.id, item])).values()]
          : [
              ...result.items,
              ...(result.items.length === 100
                ? current.filter(
                    (item) =>
                      item.created_at < result.items[99].created_at &&
                      !result.items.some((entry) => entry.id === item.id),
                  )
                : []),
            ],
      );
      setTotal(result.total);
      setError('');
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const activeIds = items
    .filter((item) => ['queued', 'running'].includes(item.status))
    .map((item) => item.id)
    .join(',');
  useEffect(() => {
    if (!activeIds) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      const results = await Promise.allSettled(
        activeIds.split(',').map((id) => api<TrainedCharacter>(`/characters/${id}`)),
      );
      if (!live) return;
      const records = results.flatMap((result) =>
        result.status === 'fulfilled' ? [result.value] : [],
      );
      setItems((current) =>
        current.map((item) => records.find((record) => record.id === item.id) || item),
      );
      const failure = results.find((result) => result.status === 'rejected');
      if (failure?.status === 'rejected') setError(failure.reason.message);
      else setError('');
      timer = setTimeout(poll, 3000);
    }
    timer = setTimeout(poll, 3000);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [activeIds]);
  return {
    items,
    total,
    loading,
    error,
    refresh,
    loadMore: () => refresh(items.length),
    replace: (record: TrainedCharacter) =>
      setItems((current) =>
        current.some((item) => item.id === record.id)
          ? current.map((item) => (item.id === record.id ? record : item))
          : [record, ...current],
      ),
    remove: (id: string) => {
      setItems((current) => current.filter((item) => item.id !== id));
      setTotal((value) => Math.max(0, value - 1));
    },
  };
}
