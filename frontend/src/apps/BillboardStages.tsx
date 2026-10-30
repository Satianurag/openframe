import { useEffect, useRef, useState } from 'react';
import { api, mediaUrl, post } from '../api';
import type { Catalog, Job, JobRequest } from '../types';
import type { Sequence } from './SequencePlanner';
import { modelProviderIssue } from './renderRequest';
import './billboard-stages.css';

export type BillboardVideo = {
  model_id: string;
  prompt: string;
  frames: number;
  fps: number;
  seed: number;
  generate_audio: boolean;
  enhance_prompt: boolean;
};
export const defaultBillboardVideo: BillboardVideo = {
  model_id: 'ltx-2.5',
  frames: 97,
  fps: 24,
  seed: -1,
  generate_audio: false,
  enhance_prompt: true,
  prompt:
    'A locked-off cinematic timelapse of this city billboard. Keep the billboard structure, its displayed artwork, product shape and readable lettering stable throughout. Pedestrians walk along the pavement, cars move along the street, and clouds travel across the sky. Natural daylight and coherent perspective. Do not morph or replace the display, and do not move the camera.',
};
export function useBillboardSequence(documentId: string | undefined, enabled: boolean) {
  const [items, setItems] = useState<Sequence[]>([]);
  const [ready, setReady] = useState(!documentId);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const mutation = useRef(0);
  const currentDocument = useRef(documentId);
  currentDocument.current = documentId;
  const active = items.some((item) => ['queued', 'running', 'cancelling'].includes(item.status));
  useEffect(() => {
    setItems([]);
    setError('');
    setReady(!documentId || !enabled);
    if (!documentId || !enabled) return;
    let live = true;
    const version = mutation.current;
    api<{ items: Sequence[] }>(`/apps/mini-apps/sequences?document_id=${documentId}`)
      .then((value) => {
        if (live && version === mutation.current) {
          setItems(value.items);
          setReady(true);
        }
      })
      .catch((reason) => {
        if (live) setError(reason.message);
      });
    return () => {
      live = false;
    };
  }, [documentId, enabled]);
  useEffect(() => {
    if (!active || !enabled || !documentId) return;
    let live = true,
      loading = false;
    const timer = setInterval(async () => {
      if (loading) return;
      loading = true;
      const version = mutation.current;
      try {
        const value = await api<{ items: Sequence[] }>(
          `/apps/mini-apps/sequences?document_id=${documentId}`,
        );
        if (live && version === mutation.current) {
          setItems(value.items);
          setError('');
        }
      } catch (reason) {
        if (live) setError((reason as Error).message);
      } finally {
        loading = false;
      }
    }, 3000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [active, enabled, documentId]);
  function accept(value: Sequence) {
    if (currentDocument.current && currentDocument.current !== value.document_id) return;
    mutation.current += 1;
    setItems((old) => [value, ...old.filter((item) => item.id !== value.id)]);
  }
  async function start(
    document: { id: string; revision: number },
    image: JobRequest,
    video: JobRequest,
  ) {
    mutation.current += 1;
    setBusy(true);
    setError('');
    try {
      // The server list is authoritative after reload or an uncertain POST response.
      const previous = await api<{ items: Sequence[] }>(
        `/apps/mini-apps/sequences?document_id=${document.id}`,
      );
      setItems(previous.items);
      if (previous.items.some((item) => item.status !== 'succeeded'))
        throw new Error(
          'This project already has an unfinished billboard sequence. Start or resume it below; completed composition work is retained.',
        );
      const sequence = await post<Sequence>(`/apps/mini-apps/documents/${document.id}/sequences`, {
        expected_revision: document.revision,
        episodes: [
          {
            title: 'Billboard timelapse',
            target_duration: video.frames / video.fps,
            keep_shot_audio: video.generate_audio,
            transition: 'cut',
            encoding_quality: 'high',
            shots: [
              {
                id: 'composition',
                label: 'Compose the billboard image',
                preparation_only: true,
                request: image,
              },
              {
                id: 'timelapse',
                label: 'Animate the reviewed billboard instructions',
                source_from_previous: true,
                request: video,
              },
            ],
          },
        ],
      });
      accept(sequence);
      accept(
        await post<Sequence>(`/sequences/${sequence.id}/start`, {
          expected_revision: sequence.revision,
        }),
      );
      setReady(true);
    } catch (reason) {
      setError((reason as Error).message);
      // Do not retry a mutation. Recover its persisted record if creation succeeded.
      try {
        const saved = await api<{ items: Sequence[] }>(
          `/apps/mini-apps/sequences?document_id=${document.id}`,
        );
        setItems(saved.items);
        setReady(true);
      } catch {
        /* Keep the original failure visible. */
      }
      throw reason;
    } finally {
      setBusy(false);
    }
  }
  async function action(sequence: Sequence, action: 'start' | 'resume' | 'cancel') {
    setBusy(true);
    setError('');
    try {
      accept(
        await post<Sequence>(
          `/sequences/${sequence.id}/${action}`,
          action === 'start' ? { expected_revision: sequence.revision } : undefined,
        ),
      );
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return { items, ready, error, busy, start, action, active };
}
export function BillboardStages({
  value,
  onChange,
  catalog,
  provider,
  workflow,
  onJob,
}: {
  value?: BillboardVideo | null;
  onChange: (value: BillboardVideo | null) => void;
  catalog: Catalog;
  provider: string;
  workflow: ReturnType<typeof useBillboardSequence>;
  onJob: (job: Job) => void;
}) {
  const models = catalog.models.filter((model) =>
    catalog.effects.find((effect) => effect.id === 'image-to-video')?.model_ids.includes(model.id),
  );
  const model = models.find((item) => item.id === value?.model_id);
  const issue = value
    ? !model
      ? 'The saved video model is unavailable. Choose a supported model explicitly.'
      : modelProviderIssue(model, provider, 'image-to-video')
    : '';
  const [openError, setOpenError] = useState('');
  async function openJob(id: string) {
    try {
      onJob(await api<Job>(`/jobs/${id}`));
    } catch (reason) {
      setOpenError((reason as Error).message);
    }
  }
  return (
    <section className="mini-billboard-stages">
      <label>
        <input
          type="checkbox"
          checked={!!value}
          disabled={workflow.active}
          onChange={(event) => onChange(event.target.checked ? { ...defaultBillboardVideo } : null)}
        />{' '}
        Generate a timelapse video after composition
      </label>
      {!value ? (
        <small>
          This saved draft creates a still composition. Enable the video stage to produce a
          billboard timelapse.
        </small>
      ) : (
        <>
          <h3>2 · Timelapse video</h3>
          <small>
            The durable sequence renders one composition, then uses that exact image as the video
            opening frame. Resume retains a completed composition. Motion and display readability
            require reviewing the result.
          </small>
          <label>
            Video instructions
            <textarea
              rows={4}
              value={value.prompt}
              disabled={workflow.active}
              onChange={(event) => onChange({ ...value, prompt: event.target.value })}
            />
          </label>
          <div className="mini-fields">
            <label>
              Video model
              <select
                value={value.model_id}
                disabled={workflow.active}
                onChange={(event) => {
                  const next = models.find((item) => item.id === event.target.value);
                  if (next)
                    onChange({
                      ...value,
                      model_id: next.id,
                      frames: Number(next.default_frames || 97),
                      fps: Number(next.fixed_fps || next.default_fps || 24),
                      generate_audio: !!next.supports_audio && value.generate_audio,
                    });
                }}
              >
                {!model && <option value={value.model_id}>{value.model_id} · unavailable</option>}
                {models.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Video frames
              <input
                type="number"
                min={Number(model?.min_frames || 9)}
                max={Number(model?.max_frames || 241)}
                step={Number(model?.frame_multiple || 8)}
                value={value.frames}
                disabled={workflow.active}
                onChange={(event) => onChange({ ...value, frames: Number(event.target.value) })}
              />
              <small>
                {(value.frames / value.fps).toFixed(2)}s at {value.fps}fps
              </small>
            </label>
          </div>
          <label>
            Video seed
            <input
              type="number"
              min={-1}
              max={4294967295}
              value={value.seed}
              disabled={workflow.active}
              onChange={(event) => onChange({ ...value, seed: Number(event.target.value) })}
            />
          </label>
          {Array.isArray(model?.prompt_enhancement_tasks) && model.prompt_enhancement_tasks.includes('image-to-video') && (
            <label>
              <input
                type="checkbox"
                checked={value.enhance_prompt}
                disabled={workflow.active}
                onChange={(event) => onChange({ ...value, enhance_prompt: event.target.checked })}
              />{' '}
              Enhance video prompt
            </label>
          )}
          {model?.supports_audio && (
            <label>
              <input
                type="checkbox"
                checked={value.generate_audio}
                disabled={workflow.active}
                onChange={(event) => onChange({ ...value, generate_audio: event.target.checked })}
              />{' '}
              Generate video audio
            </label>
          )}
          {issue && <p className="mini-error">{issue}</p>}
        </>
      )}
      {workflow.error && <p className="mini-error">{workflow.error}</p>}
      {openError && <p className="mini-error">{openError}</p>}
      {workflow.items.map((sequence) => (
        <article key={sequence.id} className="mini-billboard-run">
          <strong>
            {sequence.status} · {Math.round(sequence.progress * 100)}%
          </strong>
          <p>{sequence.stage}</p>
          {sequence.episodes
            .flatMap((episode) => episode.shots)
            .map((shot, index) => (
              <div key={shot.id}>
                <span>
                  {index === 0 ? '1 · Composition' : '2 · Video'} — {shot.status || 'pending'}
                </span>
                {shot.job_id && (
                  <button type="button" onClick={() => void openJob(shot.job_id!)}>
                    Open result / exports
                  </button>
                )}
                {shot.error && <small role="alert">{shot.error}</small>}
              </div>
            ))}
          {sequence.error && <p className="mini-error">{sequence.error}</p>}
          {sequence.episodes[0]?.output && (
            <>
              <video
                controls
                playsInline
                preload="metadata"
                src={mediaUrl(sequence.episodes[0].output)}
              />
              <a href={mediaUrl(sequence.episodes[0].output)} download>
                Download billboard video
              </a>
            </>
          )}
          {sequence.status === 'draft' && (
            <button
              type="button"
              disabled={workflow.busy}
              onClick={() => void workflow.action(sequence, 'start')}
            >
              Start saved sequence
            </button>
          )}
          {['failed', 'cancelled'].includes(sequence.status) && (
            <button
              type="button"
              disabled={workflow.busy}
              onClick={() => void workflow.action(sequence, 'resume')}
            >
              Resume missing stage
            </button>
          )}
          {['queued', 'running'].includes(sequence.status) && (
            <button
              type="button"
              disabled={workflow.busy}
              onClick={() => void workflow.action(sequence, 'cancel')}
            >
              Cancel remaining work
            </button>
          )}
          <small>
            Saved stage requests are immutable during a run. Resume uses those settings, not later
            form edits.
          </small>
        </article>
      ))}
    </section>
  );
}
