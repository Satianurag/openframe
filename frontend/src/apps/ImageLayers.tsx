import { useState } from 'react';
import type { CSSProperties } from 'react';
import { api, mediaUrl, post } from '../api';
import { Icon } from '../Icon';
import type { Asset, Job } from '../types';
import type { AppDocument } from './registry';
import { useAppDocument } from './useAppDocument';
import { renderRequest, renderSize } from './renderRequest';
import {
  AssetPicker,
  ReferenceMedia,
  ResultDialog,
  useWorkspaceAssets,
  WorkspaceDialog,
  WorkspaceHistory,
} from './engine-apps-shared';
import type { EngineAppProps } from './engine-apps-shared';
import { LayerEditor } from './LayerEditor';
import './image-layers.css';

type State = {
  kind: 'image-layers';
  source_asset_id: string;
  model_id: string;
  layer_count: number;
  longest_side: number;
  seed: number;
};
const initial: State = {
  kind: 'image-layers',
  source_asset_id: '',
  model_id: '',
  layer_count: 4,
  longest_side: 640,
  seed: -1,
};
const assetIds = (value: State) => (value.source_asset_id ? [value.source_asset_id] : []);
const examples = [
  { title: 'Relight', slug: 'relight' },
  { title: 'Inpaint', slug: 'inpaint' },
  { title: 'Layer Decomposition', slug: 'layers' },
  { title: 'Edit text', slug: 'edittext' },
  { title: 'Effects', slug: 'effects' },
].map((item) => ({
  ...item,
  poster: `https://static.higgsfield.ai/public/edit/hero/${item.slug}-video.webp`,
  video: `https://static.higgsfield.ai/public/edit/hero/${item.slug}-video.mp4`,
}));

export function ImageLayers({ catalog, settings, onSettings }: EngineAppProps) {
  const session = useAppDocument('mini-apps', initial, assetIds, 'image-layers', 'Layers');
  const state = { ...initial, ...session.state };
  const assets = useWorkspaceAssets(assetIds(state));
  const source = assets.get(state.source_asset_id);
  const models = catalog.models.filter((item) =>
    catalog.effects.find((effect) => effect.id === 'decompose-image')?.model_ids.includes(item.id),
  );
  const model =
    models.find((item) => item.id === state.model_id) || (!state.model_id ? models[0] : undefined);
  const provider = settings.default_provider || 'local';
  const [picker, setPicker] = useState(false);
  const [configure, setConfigure] = useState(false);
  const [active, setActive] = useState(2);
  const [selected, setSelected] = useState<Job | null>(null);
  const [editor, setEditor] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const jobs = session.jobs.filter((job) => job.request.effect_id === 'decompose-image');
  const documents = session.documents.filter((item) => item.state.kind === 'image-layers');
  const size = model
    ? renderSize(model, `${source?.width || 1}:${source?.height || 1}`, state.longest_side)
    : { width: 640, height: 640 };
  const currentJob = selected && (session.jobs.find((job) => job.id === selected.id) || selected);

  function choose(asset: Asset) {
    assets.add(asset);
    session.update({ source_asset_id: asset.id });
    setConfigure(true);
    setError('');
  }
  async function generate() {
    setBusy(true);
    setError('');
    try {
      if (!source || source.kind !== 'image') throw new Error('Choose an image first.');
      if (!model) throw new Error('Choose a compatible layer decomposition model.');
      if (!['local'].includes(provider))
        throw new Error(
          'Choose a supported local ComfyUI connection for Layers.',
        );
      const document = await session.save(true);
      if (!document) throw new Error('Save the project before separating layers.');
      const request = renderRequest(model, {
        effect_id: 'decompose-image',
        provider,
        prompt: '',
        source_asset_id: source.id,
        ...size,
        frames: 1,
        fps: 1,
        batch_size: 1,
        layer_count: state.layer_count,
        seed: state.seed,
      });
      const job = await post<Job>(`/apps/mini-apps/documents/${document.id}/jobs`, {
        expected_revision: document.revision,
        operation: 'decompose-image',
        request,
      });
      setSelected(job);
      setConfigure(false);
      await session.refreshJobs();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reuse(job: Job) {
    try {
      const context = job.app_context
        ? await api<{ document_snapshot: AppDocument<State> }>(`/jobs/${job.id}/app-context`)
        : null;
      const request = job.request;
      const opened = await session.newDocument(
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
              longest_side: Math.max(request.width, request.height),
              layer_count: request.layer_count || 4,
              seed: request.seed,
            },
      );
      if (opened) setConfigure(true);
    } catch (reason) {
      setError((reason as Error).message);
    }
  }

  return (
    <main className="layers-app">
      <div className="layers-app-actions">
        <a href="/apps">
          <Icon name="chevron" size={14} />
          All apps
        </a>
        <button onClick={onSettings}>
          {catalog.providers.find((item) => item.id === provider)?.name || provider}
          <Icon name="settings" size={15} />
        </button>
      </div>
      <section className="layers-landing">
        <div className="layers-carousel" aria-label="Higgsfield reference examples">
          {examples.map((example, index) => {
            const position = ((index - active + examples.length + 2) % examples.length) - 2;
            return (
              <button
                key={example.slug}
                className={position === 0 ? 'active' : ''}
                style={
                  {
                    '--layer-position': position,
                    '--layer-depth': Math.abs(position),
                  } as CSSProperties
                }
                onClick={() => setActive(index)}
                aria-label={`View ${example.title} reference example`}
              >
                <ReferenceMedia item={example} />
                <span>{example.title}</span>
              </button>
            );
          })}
        </div>
        <div className="layers-carousel-controls">
          <button onClick={() => setActive((active + 4) % 5)} aria-label="Previous reference">
            <Icon name="chevron" size={17} />
          </button>
          <button onClick={() => setActive((active + 1) % 5)} aria-label="Next reference">
            <Icon name="chevron" size={17} />
          </button>
        </div>
        <a
          className="layers-example-credit"
          href="https://higgsfield.ai/layers"
          target="_blank"
          rel="noreferrer"
        >
          Higgsfield reference examples
        </a>
        <span className="layers-badge">
          <Icon name="layers" size={13} />
          OpenFrame Layers
        </span>
        <h1>
          Turn flat images
          <br />
          <span>into editable layers.</span>
        </h1>
        <p>
          Separate an image into transparent layers, then adjust their visibility, position and
          order.
        </p>
        <button className="layers-upload" onClick={() => setPicker(true)}>
          <Icon name="plus" size={22} />
          Upload Media
        </button>
        <small>
          Model-generated layers may differ from the original. They are not guaranteed object
          cutouts.
        </small>
      </section>
      {(error || session.error || assets.error) && (
        <p className="layers-error" role="alert">
          {error || session.error || assets.error}
        </p>
      )}
      <section className="layers-projects">
        <header>
          <h2>My projects</h2>
          <button
            onClick={async () => {
              if (await session.newDocument(initial)) setPicker(true);
            }}
          >
            New project
            <Icon name="plus" size={15} />
          </button>
        </header>
        {!jobs.length && !documents.length ? (
          <div className="layers-empty">
            <strong>Your edit projects will appear here</strong>
            <p>
              Upload an image to separate it into editable layers. Your source, settings and results
              stay with the project.
            </p>
          </div>
        ) : (
          <>
            {!!documents.length && (
              <div className="layers-drafts">
                {documents.map((document) => (
                  <button
                    key={document.id}
                    onClick={async () => {
                      if (await session.openDocument(document)) setConfigure(true);
                    }}
                  >
                    <Icon name="image" size={20} />
                    <span>
                      {document.title}
                      <small>
                        {document.state.layer_count || 4} layers ·{' '}
                        {new Date(document.updated_at).toLocaleDateString()}
                      </small>
                    </span>
                    <Icon name="arrow" size={15} />
                  </button>
                ))}
              </div>
            )}
            <WorkspaceHistory
              jobs={jobs}
              total={jobs.length + (session.jobs.length < session.jobTotal ? 1 : 0)}
              onSelect={setSelected}
              onMore={session.loadMoreJobs}
            />
            <p className="layers-loaded">
              Matching results from {session.jobs.length} loaded app generations.
            </p>
          </>
        )}
      </section>
      {picker && (
        <AssetPicker
          title="Choose image to separate into layers"
          kind="image"
          assets={assets.assets}
          jobs={session.jobs}
          onAdded={assets.add}
          onSelect={choose}
          onClose={() => setPicker(false)}
        />
      )}
      {configure && (
        <WorkspaceDialog
          title="Separate image into layers"
          onClose={() => setConfigure(false)}
          className="layers-configure"
        >
          <div className="layers-configure-grid">
            <div className="layers-source">
              {source ? (
                <img src={mediaUrl(source)} alt={source.name} />
              ) : (
                <Icon name="image" size={48} />
              )}
              <button onClick={() => setPicker(true)}>Choose another image</button>
            </div>
            <div>
              <label>
                Model
                <select
                  value={model?.id || state.model_id}
                  onChange={(event) => session.update({ model_id: event.target.value })}
                >
                  {!model && <option value={state.model_id}>Choose a layer model</option>}
                  {models.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Layer count · {state.layer_count}
                <input
                  type="range"
                  min={2}
                  max={8}
                  step={1}
                  value={state.layer_count}
                  onChange={(event) => session.update({ layer_count: Number(event.target.value) })}
                />
              </label>
              <label>
                Resolution
                <select
                  value={state.longest_side}
                  onChange={(event) => session.update({ longest_side: Number(event.target.value) })}
                >
                  {[640, 768, 1024].map((n) => (
                    <option key={n} value={n}>
                      {n}px longest side{n === 640 ? ' · recommended' : ''}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Seed · −1 random
                <input
                  type="number"
                  min={-1}
                  max={Number.MAX_SAFE_INTEGER}
                  value={state.seed}
                  onChange={(event) => session.update({ seed: Number(event.target.value) })}
                />
              </label>
              <p>
                {size.width} × {size.height} · {Number(model?.default_steps || 50)} steps. Outputs
                include the composite, reconstruction and each transparent layer, ordered back to
                front.
              </p>
              <button
                className="ea-lime"
                disabled={busy || !source || !model || !session.ready}
                onClick={() => void generate()}
              >
                {busy ? 'Preparing…' : 'Separate layers'}
                <Icon name="layers" size={16} />
              </button>
              <button className="layers-provider" onClick={onSettings}>
                Compute: {catalog.providers.find((item) => item.id === provider)?.name || provider}
              </button>
              {error && (
                <p className="layers-error" role="alert">
                  {error}
                </p>
              )}
            </div>
          </div>
        </WorkspaceDialog>
      )}
      {currentJob && (
        <ResultDialog
          job={currentJob}
          onClose={() => setSelected(null)}
          onRefresh={() => void session.refreshJobs()}
          onReuse={() => void reuse(currentJob)}
          useKind="image"
          useLabel="Edit layers"
          onUse={currentJob.status === 'succeeded' ? () => setEditor(currentJob) : undefined}
        />
      )}
      {editor?.status === 'succeeded' && (
        <LayerEditor key={editor.id} job={editor} onClose={() => setEditor(null)} />
      )}
    </main>
  );
}
