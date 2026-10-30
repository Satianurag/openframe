import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { AppDocument, Application, ApplicationId } from './registry';
import type { Job } from '../types';

export function useAppDocument<T extends Record<string, unknown>>(
  appId: ApplicationId,
  initial: T,
  assetIds: (state: T) => string[],
  documentKind?: string,
  defaultTitle?: string | ((state: T) => string),
) {
  const [state, setState] = useState<T>(initial);
  const [document, setDocument] = useState<AppDocument<T> | null>(null);
  const [documents, setDocuments] = useState<AppDocument<T>[]>([]);
  const [application, setApplication] = useState<Application | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobTotal, setJobTotal] = useState(0);
  const [jobLimit, setJobLimit] = useState(100);
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const latest = useRef(state);
  const record = useRef<AppDocument<T> | null>(null);
  const saved = useRef(JSON.stringify(initial));
  const inFlight = useRef<Promise<AppDocument<T> | null> | null>(null);
  const blocked = useRef(false);
  latest.current = state;

  const matchesKind = (value: Record<string, unknown>) =>
    documentKind
      ? value.kind === documentKind ||
        (appId === 'soul-id-cast' &&
          documentKind === 'reference-set' &&
          !value.kind &&
          Array.isArray(value.reference_asset_ids))
      : appId !== 'mini-apps' || !value.kind || value.kind === 'preset';

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api<{ items: Application[] }>('/apps'),
      api<{ items: AppDocument<T>[] }>(`/apps/${appId}/documents?limit=100`),
      api<{ items: Job[]; total: number }>(`/apps/${appId}/jobs?limit=100`),
    ])
      .then(async ([apps, documents, history]) => {
        if (cancelled) return;
        setApplication(apps.items.find((app) => app.id === appId) || null);
        setDocuments(documents.items);
        const id = new URLSearchParams(location.search).get('document');
        const current = id
          ? documents.items.find((item) => item.id === id) ||
            (await api<AppDocument<T>>(`/apps/${appId}/documents/${encodeURIComponent(id)}`))
          : documents.items.find(
              (item) =>
                matchesKind(item.state) &&
                (appId !== 'supercomputer' ||
                  !['project', 'skill'].includes(String(item.state.kind))),
            );
        if (cancelled) return;
        if (current && !matchesKind(current.state))
          throw new Error(
            'This saved document belongs to a different tool. Open it in its original app or start a new document.',
          );
        if (current && JSON.stringify(latest.current) === JSON.stringify(initial)) {
          record.current = current;
          latest.current = current.state;
          saved.current = JSON.stringify(current.state);
          setDocument(current);
          setState(current.state);
        }
        setJobs(history.items);
        setJobTotal(history.total);
        setReady(true);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, [appId, documentKind]);

  const save = useCallback(
    async (forceCreate = false): Promise<AppDocument<T> | null> => {
      if (!ready || blocked.current) return null;
      if ((!forceCreate || record.current) && JSON.stringify(latest.current) === saved.current)
        return record.current;
      if (inFlight.current) return inFlight.current;
      const work = async () => {
        setSaving(true);
        try {
          while (
            JSON.stringify(latest.current) !== saved.current ||
            (forceCreate && !record.current)
          ) {
            const snapshot = latest.current;
            const serialized = JSON.stringify(snapshot);
            const current = record.current;
            const body = {
              title: String(
                snapshot.title ||
                  (defaultTitle
                    ? current?.title ||
                      (typeof defaultTitle === 'function' ? defaultTitle(snapshot) : defaultTitle)
                    : snapshot.prompt || application?.name || appId),
              ).slice(0, 120),
              schema_version: 1,
              state: snapshot,
              asset_ids: [...new Set(assetIds(snapshot))],
              ...(current ? { expected_revision: current.revision } : {}),
            };
            const result = await api<AppDocument<T>>(
              `/apps/${appId}/documents${current ? `/${current.id}` : ''}`,
              {
                method: current ? 'PATCH' : 'POST',
                body: JSON.stringify(body),
                keepalive: new Blob([JSON.stringify(body)]).size <= 60000,
              },
            );
            record.current = result;
            saved.current = serialized;
            setDocument(result);
            setDocuments((items) => [result, ...items.filter((item) => item.id !== result.id)]);
          }
          setError('');
        } catch (reason) {
          blocked.current = (reason as Error & { status?: number }).status === 409;
          setError(
            `${(reason as Error).message}${blocked.current ? ' Your current changes remain on this screen; reload before editing another revision.' : ' Your changes have not been saved. Correct the input or try saving again.'}`,
          );
          return null;
        } finally {
          setSaving(false);
          inFlight.current = null;
        }
        return record.current;
      };
      inFlight.current = work();
      return inFlight.current;
    },
    [appId, application?.name, assetIds, ready, defaultTitle],
  );

  useEffect(() => {
    if (!ready) return;
    const timeout = setTimeout(() => {
      void save();
    }, 750);
    const leave = () => {
      void save();
    };
    window.addEventListener('pagehide', leave);
    return () => {
      clearTimeout(timeout);
      window.removeEventListener('pagehide', leave);
    };
  }, [ready, state, save]);

  const refreshJobs = useCallback(async () => {
    const pages = await Promise.all(
      Array.from({ length: Math.ceil(jobLimit / 500) }, (_, index) =>
        api<{ items: Job[]; total: number }>(
          `/apps/${appId}/jobs?limit=${Math.min(500, jobLimit - index * 500)}&offset=${index * 500}`,
        ),
      ),
    );
    setJobs(pages.flatMap((page) => page.items));
    setJobTotal(pages[0]?.total || 0);
  }, [appId, jobLimit]);
  useEffect(() => {
    if (!ready) return;
    void refreshJobs().catch(() => {});
    if (!jobs.some((job) => job.status === 'queued' || job.status === 'running')) return;
    const timer = setInterval(() => {
      void refreshJobs().catch(() => {});
    }, 2000);
    return () => clearInterval(timer);
  }, [ready, refreshJobs, jobs.some((job) => job.status === 'queued' || job.status === 'running')]);

  const refreshDocuments = async () => {
    const result = await api<{ items: AppDocument<T>[] }>(`/apps/${appId}/documents?limit=100`);
    setDocuments(result.items);
  };
  const update = (changes: Partial<T>) => setState((current) => ({ ...current, ...changes }));
  async function updateAndSave(changes: Partial<T>, forceCreate = true) {
    const next = { ...latest.current, ...changes };
    latest.current = next;
    setState(next);
    return save(forceCreate);
  }
  async function openDocument(next: AppDocument<T>) {
    const dirty = JSON.stringify(latest.current) !== saved.current;
    const result = await save();
    if (blocked.current || (dirty && !result)) return false;
    if (next.id === record.current?.id) next = record.current;
    record.current = next;
    latest.current = next.state;
    saved.current = JSON.stringify(next.state);
    setDocument(next);
    setState(next.state);
    return true;
  }
  async function newDocument(next: T = initial) {
    const dirty = JSON.stringify(latest.current) !== saved.current;
    const result = await save();
    if (blocked.current || (dirty && !result)) return false;
    record.current = null;
    latest.current = next;
    saved.current = JSON.stringify(initial);
    setDocument(null);
    setState(next);
    return true;
  }
  return {
    state,
    update,
    updateAndSave,
    document,
    documents,
    refreshDocuments,
    application,
    jobs,
    jobTotal,
    refreshJobs,
    loadMoreJobs: () => setJobLimit((limit) => limit + 100),
    ready,
    saving,
    error,
    save,
    openDocument,
    newDocument,
  };
}
