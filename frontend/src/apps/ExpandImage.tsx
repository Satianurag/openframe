import { useEffect, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import { api, mediaUrl, post, upload } from '../api';
import { Icon } from '../Icon';
import { AnchoredPopover } from '../Popovers';
import type { Asset, Job } from '../types';
import type { AppDocument } from './registry';
import { useAppDocument } from './useAppDocument';
import { renderRequest } from './renderRequest';
import {
  AssetPicker,
  ReferenceMedia,
  ResultDialog,
  useWorkspaceAssets,
  WorkspaceHistory,
} from './engine-apps-shared';
import type { EngineAppProps } from './engine-apps-shared';
import './expand-image.css';

type State = {
  kind: 'expand-image';
  source_asset_id: string;
  model_id: string;
  ratio: string;
  width: number;
  height: number;
  anchor_x: number;
  anchor_y: number;
  prompt: string;
  prompt_mode: 'expand' | 'caption';
  reference_megapixels: number;
  batch_size: number;
  seed: number;
};
const initial: State = {
  kind: 'expand-image',
  source_asset_id: '',
  model_id: '',
  ratio: '21:9',
  width: 1536,
  height: 656,
  anchor_x: 0.5,
  anchor_y: 0.5,
  prompt:
    'Continue the scene naturally beyond the original photograph. Match its perspective, lighting, materials and visual style. Keep the original picture unchanged and fill only the new surrounding area.',
  prompt_mode: 'expand',
  reference_megapixels: 1,
  batch_size: 1,
  seed: -1,
};
const ratios = ['Auto', '1:1', '3:2', '2:3', '4:3', '3:4', '4:5', '5:4', '9:16', '16:9', '21:9'];
const ids = (state: State) => (state.source_asset_id ? [state.source_asset_id] : []);
const clamp = (value: number) => Math.max(0, Math.min(1, value));
const grid = (value: number) => Math.max(256, Math.ceil(value / 16) * 16);
const example = {
  title: 'Higgsfield Expand Image reference example',
  poster: 'https://cdn.higgsfield.ai/application_detail/c77244ba-288f-409b-aa9d-8ec7617d8f7b.webp',
  video: 'https://cdn.higgsfield.ai/application_detail/af30a374-5805-45e1-ba1a-114e56bdf835.mp4',
};

function fitCanvas(asset: Asset, ratio: string) {
  const width = asset.width || 1024,
    height = asset.height || 1024;
  if (ratio === 'Auto') return { width: grid(width * 1.25), height: grid(height * 1.25) };
  const [rw, rh] = ratio.split(':').map(Number);
  let scale = Math.max(width / rw, height / rh);
  if (grid(rw * scale) === width && grid(rh * scale) === height) scale *= 1.25;
  return { width: grid(rw * scale), height: grid(rh * scale) };
}

export function ExpandImage({ catalog, settings, onSettings }: EngineAppProps) {
  const session = useAppDocument('mini-apps', initial, ids, 'expand-image', 'Expand Image');
  const state = { ...initial, ...session.state };
  const assets = useWorkspaceAssets(ids(state));
  const source = assets.get(state.source_asset_id);
  const effect = catalog.effects.find((item) => item.id === 'expand-image');
  const models = catalog.models.filter((item) => effect?.model_ids.includes(item.id));
  const model =
    models.find((item) => item.id === state.model_id) || (!state.model_id ? models[0] : undefined);
  const provider = settings.default_provider || 'local';
  const [picker, setPicker] = useState(false);
  const [ratioAnchor, setRatioAnchor] = useState<HTMLElement | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selected, setSelected] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const sourceWidth = source?.width || 0,
    sourceHeight = source?.height || 0;
  const previewWidth = Math.max(256, sourceWidth, state.width || 256);
  const previewHeight = Math.max(256, sourceHeight, state.height || 256);
  const left = Math.floor((previewWidth - sourceWidth) * state.anchor_x + 0.5);
  const top = Math.floor((previewHeight - sourceHeight) * state.anchor_y + 0.5);
  const geometryError = !source
    ? ''
    : ![state.width, state.height].every(
          (n) => Number.isInteger(n) && n >= 256 && n <= 4096 && n % 16 === 0,
        )
      ? 'Choose 16-pixel aligned dimensions between 256 and 4096.'
      : state.width < sourceWidth ||
          state.height < sourceHeight ||
          (state.width === sourceWidth && state.height === sourceHeight)
        ? 'The canvas must contain the original at its native size and add space on at least one side.'
        : '';
  const jobs = session.jobs.filter((job) => job.request.effect_id === 'expand-image');

  function choose(asset: Asset) {
    if (asset.kind !== 'image') {
      setError('Choose an image to expand.');
      return;
    }
    assets.add(asset);
    session.update({
      source_asset_id: asset.id,
      ...fitCanvas(asset, state.ratio === 'Custom' ? 'Auto' : state.ratio),
      anchor_x: 0.5,
      anchor_y: 0.5,
    });
    setError('');
  }
  async function drop(file?: File) {
    if (!file) return;
    setBusy(true);
    try {
      choose(await upload(file));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function ratio(value: string) {
    session.update({ ratio: value, ...(source ? fitCanvas(source, value) : {}) });
    setRatioAnchor(null);
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current || !source) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = drag.current.left + ((event.clientX - drag.current.x) / bounds.width) * previewWidth;
    const y = drag.current.top + ((event.clientY - drag.current.y) / bounds.height) * previewHeight;
    session.update({
      anchor_x: previewWidth === sourceWidth ? 0.5 : clamp(x / (previewWidth - sourceWidth)),
      anchor_y: previewHeight === sourceHeight ? 0.5 : clamp(y / (previewHeight - sourceHeight)),
    });
  }
  async function generate() {
    setError('');
    setBusy(true);
    try {
      if (!source || !sourceWidth || !sourceHeight) throw new Error('Upload an image first.');
      if (geometryError) throw new Error(geometryError);
      if (!model) throw new Error('Choose an available Expand Image model.');
      if (!['local'].includes(provider))
        throw new Error(
          'Expand Image currently runs on a configured Local ComfyUI. Choose a provider in settings.',
        );
      if (!state.prompt.trim())
        throw new Error('Describe the surrounding scene in Advanced controls.');
      if (state.prompt_mode === 'caption' && state.prompt.trim().length < 80)
        throw new Error('A complete caption needs at least 80 characters.');
      const document = await session.save(true);
      if (!document) throw new Error('Save the draft before generating.');
      const request = renderRequest(model, {
        effect_id: 'expand-image',
        provider,
        prompt: state.prompt,
        source_asset_id: source.id,
        width: state.width,
        height: state.height,
        frames: 1,
        fps: 1,
        batch_size: state.batch_size,
        seed: state.seed,
        guidance: 1,
        negative_prompt: '',
        image_prompt_mode: state.prompt_mode,
        image_reference_megapixels: state.reference_megapixels,
        outpaint_anchor_x: state.anchor_x,
        outpaint_anchor_y: state.anchor_y,
        image_preservation: 'inside-mask',
        mask_feather: 0,
      });
      const job = await post<Job>(`/apps/mini-apps/documents/${document.id}/jobs`, {
        expected_revision: document.revision,
        operation: 'expand-image',
        request,
      });
      setSelected(job);
      await session.refreshJobs();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reuse(job: Job) {
    try {
      if (job.request.effect_id !== 'expand-image')
        throw new Error('This result belongs to another app.');
      const context = job.app_context
        ? await api<{ document_snapshot: AppDocument<State> }>(`/jobs/${job.id}/app-context`)
        : null;
      const request = job.request;
      await session.newDocument(
        context
          ? {
              ...initial,
              ...context.document_snapshot.state,
              model_id: request.model_id,
              seed: request.seed,
            }
          : {
              ...initial,
              source_asset_id: request.source_asset_id || '',
              model_id: request.model_id,
              width: request.width,
              height: request.height,
              ratio: 'Custom',
              prompt: request.prompt,
              anchor_x: request.outpaint_anchor_x ?? 0.5,
              anchor_y: request.outpaint_anchor_y ?? 0.5,
              seed: request.seed,
              batch_size: request.batch_size || 1,
              prompt_mode: request.image_prompt_mode || 'expand',
              reference_megapixels: request.image_reference_megapixels || 1,
            },
      );
      setHistoryOpen(false);
    } catch (reason) {
      setError((reason as Error).message);
    }
  }
  useEffect(() => {
    const sourceId = new URLSearchParams(location.search).get('source');
    if (!sourceId || !session.ready) return;
    let active = true;
    void api<Asset>(`/assets/${encodeURIComponent(sourceId)}`)
      .then(async (asset) => {
        if (!active) return;
        if (asset.kind !== 'image') throw new Error('Expand Image needs an image source.');
        assets.add(asset);
        const document = await session.newDocument({
          ...initial,
          source_asset_id: asset.id,
          ...fitCanvas(asset, initial.ratio),
        });
        if (document && active) {
          const url = new URL(location.href);
          url.searchParams.delete('source');
          url.searchParams.delete('document');
          history.replaceState(null, '', url);
        }
      })
      .catch((reason) => setError(reason.message));
    return () => {
      active = false;
    };
  }, [session.ready]);

  return (
    <main className="expand-app">
      <nav className="expand-breadcrumb">
        <a href="/apps">Apps</a>
        <span>/</span>
        <strong>Expand Image</strong>
        <div />
        <button onClick={() => setHistoryOpen(!historyOpen)}>My generations</button>
        <button onClick={() => void session.newDocument(initial)}>New project</button>
        <button onClick={onSettings}>
          {catalog.providers.find((item) => item.id === provider)?.name || provider}
          <Icon name="settings" size={15} />
        </button>
      </nav>
      {historyOpen ? (
        <section className="expand-history">
          <h1>Expand Image generations</h1>
          <WorkspaceHistory
            jobs={jobs}
            total={jobs.length + (session.jobs.length < session.jobTotal ? 1 : 0)}
            onSelect={setSelected}
            onMore={session.loadMoreJobs}
          />
          <p>Matching results from {session.jobs.length} loaded app generations.</p>
        </section>
      ) : (
        <>
          <div className="expand-hero">
            <section className="expand-form">
              <h1>Expand Image</h1>
              <p>
                Expand your image beyond its edges. Fill the surrounding scene while keeping the
                original image untouched.
              </p>
              <button
                className={`expand-upload ${source ? 'has-source' : ''}`}
                disabled={busy}
                onClick={() => setPicker(true)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  void drop(event.dataTransfer.files[0]);
                }}
              >
                {source ? (
                  <>
                    <img src={mediaUrl(source)} alt={source.name} />
                    <strong>Change image</strong>
                    <small>
                      {sourceWidth} × {sourceHeight} · original resolution
                    </small>
                  </>
                ) : (
                  <>
                    <Icon name="upload" size={24} />
                    <strong>Upload Image</strong>
                    <small>PNG, JPG or WebP · choose from your workspace</small>
                  </>
                )}
              </button>
              <div className="expand-actions">
                <button
                  aria-haspopup="dialog"
                  onClick={(event) => setRatioAnchor(event.currentTarget)}
                >
                  <Icon name="square" size={17} />
                  {state.ratio}
                  <Icon name="chevron" size={12} />
                </button>
                <button
                  className="expand-generate"
                  disabled={busy || !source || !!geometryError || !session.ready}
                  onClick={() => void generate()}
                >
                  {busy ? 'Working…' : 'Generate Image'}
                  <Icon name="spark" size={16} />
                </button>
              </div>
              <button
                className="expand-advanced-toggle"
                aria-expanded={advanced}
                onClick={() => setAdvanced(!advanced)}
              >
                Advanced · canvas, placement and model <Icon name="chevron" size={12} />
              </button>
              {(error || session.error || assets.error || geometryError) && (
                <p role="alert" className="expand-error">
                  {error || session.error || assets.error || geometryError}
                </p>
              )}
            </section>
            <section className={`expand-preview ${source ? 'has-source' : ''}`}>
              {source ? (
                <>
                  <div
                    className="expand-plane"
                    style={{
                      aspectRatio: `${previewWidth}/${previewHeight}`,
                      width: `min(100%, ${(480 * previewWidth) / previewHeight}px)`,
                    }}
                    onPointerDown={(event) => {
                      event.currentTarget.setPointerCapture(event.pointerId);
                      drag.current = { x: event.clientX, y: event.clientY, left, top };
                    }}
                    onPointerMove={move}
                    onPointerUp={() => {
                      drag.current = null;
                    }}
                    onPointerCancel={() => {
                      drag.current = null;
                    }}
                  >
                    <span className="expand-fill-label">New area to generate</span>
                    <img
                      src={mediaUrl(source)}
                      alt="Original image placed on the expanded canvas"
                      draggable={false}
                      style={{
                        left: `${(left / previewWidth) * 100}%`,
                        top: `${(top / previewHeight) * 100}%`,
                        width: `${(sourceWidth / previewWidth) * 100}%`,
                        height: `${(sourceHeight / previewHeight) * 100}%`,
                      }}
                    />
                  </div>
                  <div className="expand-caption">
                    <strong>
                      {state.width} × {state.height}
                    </strong>
                    <span>
                      Drag the original to position it. This is a layout preview, not a generated
                      image.
                    </span>
                  </div>
                </>
              ) : (
                <>
                  <ReferenceMedia item={example} />
                  <a
                    className="expand-reference"
                    href="https://higgsfield.ai/apps/expand-image"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Higgsfield reference example
                  </a>
                </>
              )}
            </section>
          </div>
          {advanced && (
            <section className="expand-advanced">
              <div>
                <h2>Canvas and placement</h2>
                <div className="expand-fields">
                  <label>
                    Width
                    <input
                      type="number"
                      min={256}
                      max={4096}
                      step={16}
                      value={state.width}
                      onChange={(event) =>
                        session.update({ width: Number(event.target.value), ratio: 'Custom' })
                      }
                    />
                  </label>
                  <label>
                    Height
                    <input
                      type="number"
                      min={256}
                      max={4096}
                      step={16}
                      value={state.height}
                      onChange={(event) =>
                        session.update({ height: Number(event.target.value), ratio: 'Custom' })
                      }
                    />
                  </label>
                </div>
                <div className="expand-fields">
                  {(['x', 'y'] as const).map((axis) => (
                    <label key={axis}>
                      {axis === 'x' ? 'Horizontal' : 'Vertical'} ·{' '}
                      {Math.round(state[`anchor_${axis}`] * 100)}%
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.01}
                        value={state[`anchor_${axis}`]}
                        onChange={(event) =>
                          session.update({ [`anchor_${axis}`]: Number(event.target.value) })
                        }
                      />
                    </label>
                  ))}
                </div>
                <button onClick={() => session.update({ anchor_x: 0.5, anchor_y: 0.5 })}>
                  Centre original
                </button>
                {source && (
                  <p>
                    Added area: left {left}px · right {previewWidth - sourceWidth - left}px · top{' '}
                    {top}px · bottom {previewHeight - sourceHeight - top}px. The source is not
                    resized. Its existing transparency is retained.
                  </p>
                )}
              </div>
              <div>
                <h2>Generation</h2>
                <label>
                  Model
                  <select
                    value={model?.id || state.model_id}
                    onChange={(event) => session.update({ model_id: event.target.value })}
                  >
                    {!model && <option value={state.model_id}>Choose a compatible model</option>}
                    {models.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Surrounding scene
                  <textarea
                    value={state.prompt}
                    rows={4}
                    onChange={(event) => session.update({ prompt: event.target.value })}
                  />
                </label>
                <label>
                  Prompt preparation
                  <select
                    value={state.prompt_mode}
                    onChange={(event) =>
                      session.update({ prompt_mode: event.target.value as State['prompt_mode'] })
                    }
                  >
                    <option value="expand">Expand instructions with the reference image</option>
                    <option value="caption">Use my complete caption</option>
                  </select>
                </label>
                <div className="expand-fields">
                  <label>
                    Variants
                    <select
                      value={state.batch_size}
                      onChange={(event) =>
                        session.update({ batch_size: Number(event.target.value) })
                      }
                    >
                      {[1, 2, 3, 4].map((count) => (
                        <option key={count}>{count}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Seed · −1 random
                    <input
                      type="number"
                      min={-1}
                      max={Number.MAX_SAFE_INTEGER}
                      step={1}
                      value={state.seed}
                      onChange={(event) => session.update({ seed: Number(event.target.value) })}
                    />
                  </label>
                  <label>
                    Reference detail · megapixels
                    <select
                      value={state.reference_megapixels}
                      onChange={(event) =>
                        session.update({ reference_megapixels: Number(event.target.value) })
                      }
                    >
                      {[0.25, 0.5, 1, 2, 4].map((n) => (
                        <option key={n}>{n}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <p>
                  Generate the new surrounding area while keeping the original image at its native
                  size. Original pixels and existing transparency stay unchanged. Review the result
                  for lighting and edge consistency.
                </p>
              </div>
            </section>
          )}
          <section className="expand-steps">
            <h2>Expand Image in 3 easy steps</h2>
            <div>
              {[
                ['Upload your image', 'Keep the original at its native resolution.'],
                ['Pick your output', 'Choose a wider or taller canvas and position the image.'],
                [
                  'Get the full picture',
                  'Generate the new surroundings and download the complete workflow.',
                ],
              ].map(([title, description], index) => (
                <article key={title}>
                  <span>{index + 1}</span>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </article>
              ))}
            </div>
          </section>
        </>
      )}
      {ratioAnchor && (
        <AnchoredPopover
          anchor={ratioAnchor}
          onClose={() => setRatioAnchor(null)}
          label="Expanded image aspect ratio"
          placement="bottom-start"
          width={180}
        >
          <div className="expand-ratio-menu">
            {ratios.map((value) => (
              <button
                key={value}
                className={state.ratio === value ? 'active' : ''}
                onClick={() => ratio(value)}
              >
                <Icon name="square" size={15} />
                {value}
                {state.ratio === value && <Icon name="check" size={14} />}
              </button>
            ))}
          </div>
        </AnchoredPopover>
      )}
      {picker && (
        <AssetPicker
          title="Choose image to expand"
          kind="image"
          assets={assets.assets}
          jobs={session.jobs}
          onAdded={assets.add}
          onSelect={choose}
          onClose={() => setPicker(false)}
        />
      )}
      {selected && (
        <ResultDialog
          job={session.jobs.find((job) => job.id === selected.id) || selected}
          onClose={() => setSelected(null)}
          onRefresh={() => void session.refreshJobs()}
          onReuse={() => void reuse(selected)}
        />
      )}
    </main>
  );
}
