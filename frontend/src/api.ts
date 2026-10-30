import type { Asset } from './types';
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch('/api' + path, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let text = await response.text();
    try {
      const json = JSON.parse(text);
      text = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail || json);
    } catch {
      /* Plain response body. */
    }
    throw Object.assign(new Error(text || `Request failed (${response.status})`), {
      status: response.status,
    });
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export const post = <T>(path: string, value?: unknown) =>
  api<T>(path, {
    method: 'POST',
    body: value === undefined ? undefined : JSON.stringify(value),
  });
export async function upload(file: File): Promise<Asset> {
  const body = new FormData();
  body.append('file', file);
  return api<Asset>('/assets', { method: 'POST', body });
}
export async function download(path: string, filename: string, body?: unknown) {
  const response = await fetch('/api' + path, {
    method: body ? 'POST' : 'GET',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    let result = await response.json().catch(() => null);
    throw new Error(result?.detail || 'Could not export this workflow.');
  }
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
export function mediaUrl(asset: Asset) {
  return asset.url || `/api/assets/${asset.id}/file`;
}

export function downloadedJobs(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem('openframe:downloaded') || '[]');
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}
export function markDownloaded(id: string) {
  const ids = downloadedJobs();
  if (!ids.includes(id)) {
    try {
      localStorage.setItem('openframe:downloaded', JSON.stringify([...ids, id]));
    } catch {
      /* Download still works when browser storage is unavailable. */
    }
  }
}

export async function listPage<T>(
  path: string,
  count = 100,
): Promise<{ items: T[]; total: number }> {
  const first = await api<{ items: T[]; total: number }>(`${path}?limit=${Math.min(500, count)}`);
  const items = [...first.items];
  while (items.length < Math.min(count, first.total)) {
    const next = await api<{ items: T[] }>(
      `${path}?limit=${Math.min(500, count - items.length)}&offset=${items.length}`,
    );
    if (!next.items.length) break;
    items.push(...next.items);
  }
  return { items, total: first.total };
}
