import { useEffect, useRef, useState } from 'react';
import { HistoryToolbar } from './HistoryToolbar';
import type { HistoryView } from './HistoryToolbar';
import { AnchoredPopover } from './Popovers';
import type { Dispatch, SetStateAction, DragEvent } from 'react';
import { previewSources, previewVideos, previewDescriptions, previewLabels } from './previews';
import type { Asset, Catalog, Effect, Job, JobRequest } from './types';
import { api, mediaUrl, downloadedJobs } from './api';
import { Icon } from './Icon';
import { EmptyState, renderStage } from './ui';
import { SceneArt } from './SceneArt';
function relativeDate(date: string) {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(date).getTime()) / 60000));
  return minutes < 1
    ? 'Just now'
    : minutes < 60
      ? `${minutes}m ago`
      : minutes < 1440
        ? `${Math.floor(minutes / 60)}h ago`
        : new Date(date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
export function EffectsPanel({
  catalog,
  draft,
  query,
  setQuery,
  filteredEffects,
  loading,
  chooseEffect,
  onClose,
  onModelSelect,
}: {
  catalog: Catalog;
  draft: JobRequest;
  category: string;
  setCategory: (v: string) => void;
  query: string;
  setQuery: (v: string) => void;
  filteredEffects: Effect[];
  loading: boolean;
  chooseEffect: (e: Effect) => void;
  onPresets: () => void;
  exportWorkflow: () => void;
  onClose: () => void;
  onModelSelect: (id: string) => void;
}) {
  const current = catalog.effects.find((e) => e.id === draft.effect_id);
  return (
    <div className="effects-content reference-picker">
      <div className="preset-picker-header">
        <div className="preset-model-tabs">
          {catalog.models
            .filter((m) => current?.model_ids.includes(m.id))
            .map((m) => (
              <button
                className={draft.model_id === m.id ? 'active' : ''}
                key={m.id}
                onClick={() => onModelSelect(m.id)}
              >
                <Icon name="film" size={20} />
                {m.name}
                <em>OPEN</em>
              </button>
            ))}
        </div>
        <input
          aria-label="Search effects"
          placeholder="Search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="icon-button" aria-label="Close presets" onClick={onClose}>
          <Icon name="close" size={20} />
        </button>
      </div>
      <div className="effects-grid">
        {filteredEffects.map((e) => (
            <button
              className={`effect-card ${e.id === draft.effect_id ? 'chosen' : ''}`}
              key={e.id}
              onClick={() => chooseEffect(e)}
              title={e.description}
            >
              <SceneArt id={e.id}>
                <span className="preview-origin">
                  {previewLabels[e.id] || 'No reference preview'}
                </span>
                <div className="card-title">
                  <h3>{e.id === 'text-to-video' ? 'GENERAL' : e.name.toUpperCase()}</h3>
                </div>
              </SceneArt>
            </button>
          ))}
      </div>
      {!filteredEffects.length && !loading && (
        <EmptyState
          title="No presets match"
          description="Try another name."
          action={
            <button className="secondary" onClick={() => setQuery('')}>
              Clear search
            </button>
          }
        />
      )}
      <p className="preset-provenance">
        Public Higgsfield examples illustrate the controls. They are external references, not
        OpenFrame generation results.
      </p>
    </div>
  );
}

export function HistoryPanel({
  jobTotal,
  onLoadMore,
  loadingMore,
  catalog,
  historyFilter,
  setHistoryFilter,
  jobs,
  selectedJob,
  setSelectedJob,
  setPanel,
  jobAction,
  reuse,
  exportWorkflow,
}: {
  catalog: Catalog;
  jobTotal: number;
  onLoadMore: () => void;
  loadingMore: boolean;
  filteredJobs: Job[];
  historyFilter: string;
  setHistoryFilter: (v: string) => void;
  activeJobs: Job[];
  jobs: Job[];
  selectedJob: string | null;
  setSelectedJob: (v: string | null) => void;
  setPanel: (v: string) => void;
  refresh: () => void;
  jobAction: (j: Job, a: 'cancel' | 'retry' | 'favorite' | 'delete') => void;
  reuse: (j: Job) => void;
  exportWorkflow: (j: Job) => void;
}) {
  const [filters, setFilters] = useState<HistoryView>(() => {
    const defaults: HistoryView = {
      model: 'all',
      dateFrom: '',
      dateTo: '',
      hideFailed: false,
      liked: false,
      downloaded: false,
      status: 'all',
      layout: 'grid',
      size: 3,
      fill: true,
    };
    try {
      return { ...defaults, ...JSON.parse(localStorage.getItem('openframe:history-view') || '{}') };
    } catch {
      return defaults;
    }
  });
  useEffect(() => {
    if (historyFilter !== 'All') {
      setFilters((v) => ({
        ...v,
        status:
          historyFilter === 'Active'
            ? 'active'
            : historyFilter === 'Completed'
              ? 'succeeded'
              : historyFilter === 'Failed'
                ? 'failed'
                : 'all',
        liked: historyFilter === 'Favorites',
      }));
      setHistoryFilter('All');
    }
  }, [historyFilter, setHistoryFilter]);
  const downloaded = new Set(downloadedJobs());
  const shown = jobs.filter((job) => {
    const d = new Date(job.created_at);
    const day = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return (
      (!filters.model || filters.model === 'all' || job.request.model_id === filters.model) &&
      (!filters.dateFrom || day >= filters.dateFrom) &&
      (!filters.dateTo || day <= filters.dateTo) &&
      (!filters.hideFailed || job.status !== 'failed') &&
      (!filters.liked || job.favorite) &&
      (!filters.downloaded || downloaded.has(job.id)) &&
      (!filters.status ||
        filters.status === 'all' ||
        (filters.status === 'active'
          ? ['queued', 'running'].includes(job.status)
          : job.status === filters.status))
    );
  });
  const cardWidth = [160, 200, 250, 320, 400][Math.max(0, Math.min(4, filters.size - 1))];
  return (
    <div className="history-content">
      <HistoryToolbar
        models={catalog.models}
        value={filters}
        onChange={(patch) =>
          setFilters((v) => {
            const next = { ...v, ...patch };
            try {
              localStorage.setItem('openframe:history-view', JSON.stringify(next));
            } catch {
              /* Optional view preferences. */
            }
            return next;
          })
        }
      />
      {!shown.length ? (
        <EmptyState
          icon="folder"
          title={jobs.length ? 'No renders in this view' : 'Your first shot starts here'}
          description={
            jobs.length
              ? 'Try another filter to find your creations.'
              : 'Choose an effect, describe your scene, and generate. Your videos and settings will be saved here.'
          }
          action={
            <button className="primary" onClick={() => setPanel('effects')}>
              Explore effects
              <Icon name="arrow" />
            </button>
          }
        />
      ) : (
        <div
          className={`job-grid history-layout-${filters.layout} ${filters.fill ? 'fill-previews' : 'fit-previews'}`}
          style={{ '--card-width': `${cardWidth}px` } as React.CSSProperties}
        >
          {shown.map((job) => (
            <article
              className={`job-card ${job.id === selectedJob ? 'selected' : ''}`}
              key={job.id}
              data-job-id={job.id}
            >
              <button
                className="job-open"
                onClick={() => {
                  setSelectedJob(job.id);
                  setPanel('history');
                }}
                aria-label={`Open render: ${job.request.prompt}`}
              >
                <div className="job-thumbnail">
                  {job.outputs[0] ? (
                    job.outputs[0].thumbnail_url ? (
                      <img src={job.outputs[0].thumbnail_url} alt="Generated video preview" />
                    ) : job.outputs[0].kind === 'video' ? (
                      <video src={mediaUrl(job.outputs[0])} preload="metadata" muted />
                    ) : job.outputs[0].kind === 'audio' ? (
                      <Icon name="sound" size={36} />
                    ) : (
                      <img src={mediaUrl(job.outputs[0])} alt="Generated output" />
                    )
                  ) : (
                    <SceneArt id={job.request.effect_id}>
                      <Icon
                        name={
                          job.status === 'failed'
                            ? 'info'
                            : job.status === 'cancelled'
                              ? 'stop'
                              : 'film'
                        }
                        size={32}
                      />
                    </SceneArt>
                  )}
                  <span className={`job-status status-${job.status}`}>
                    {job.status === 'running'
                      ? `${Math.round(job.progress * 100)}% · ${renderStage(job.stage)}`
                      : job.status}
                  </span>
                  {job.status === 'running' && (
                    <div className="progress-bar">
                      <i style={{ width: `${Math.max(1, job.progress * 100)}%` }} />
                    </div>
                  )}
                </div>
                <div className="job-description">
                  <p>{job.request.prompt}</p>
                  <span>
                    {catalog.models.find((m) => m.id === job.request.model_id)?.name ||
                      job.request.model_id}{' '}
                    · {relativeDate(job.created_at)}
                  </span>
                </div>
              </button>
              <div className="job-actions">
                <button
                  title="Reuse settings"
                  aria-label="Reuse settings"
                  onClick={() => reuse(job)}
                >
                  <Icon name="refresh" size={16} />
                </button>
                <button
                  title="Favorite"
                  aria-label={job.favorite ? 'Remove favorite' : 'Favorite render'}
                  className={job.favorite ? 'favorited' : ''}
                  onClick={() => jobAction(job, 'favorite')}
                >
                  <Icon name="heart" size={16} />
                </button>
                {['queued', 'running'].includes(job.status) ? (
                  <button onClick={() => jobAction(job, 'cancel')}>Cancel</button>
                ) : (
                  <>
                    <button
                      title="Download workflow"
                      aria-label="Download workflow"
                      onClick={() => exportWorkflow(job)}
                    >
                      <Icon name="code" size={16} />
                    </button>
                    <button
                      title="Delete render"
                      aria-label="Delete render"
                      onClick={() => jobAction(job, 'delete')}
                    >
                      <Icon name="trash" size={16} />
                    </button>
                  </>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      <div className="pagination-note">
        <span>
          {shown.length} matches · {jobs.length} of {jobTotal} renders loaded
          {jobs.length < jobTotal ? ' · Filters apply to loaded renders.' : ''}
        </span>
        {jobs.length < jobTotal && (
          <button className="secondary" onClick={onLoadMore} disabled={loadingMore}>
            {loadingMore ? 'Loading…' : 'Load more renders'}
          </button>
        )}
      </div>
    </div>
  );
}

export function MediaLibrary({
  assetTotal,
  onLoadMoreAssets,
  loadingAssets,
  assets,
  picker,
  assetFilter,
  setAssetFilter,
  browse,
  selectAsset,
  setModal,
  navigate,
  drop,
  setAssets,
  update,
  draft,
  setError,
}: {
  assetTotal: number;
  onLoadMoreAssets: () => void;
  loadingAssets: boolean;
  assets: Asset[];
  picker?: 'source' | 'reference';
  assetFilter: string;
  setAssetFilter: (v: string) => void;
  browse: (r: 'source' | 'reference' | 'library') => void;
  selectAsset: (a: Asset, r: 'source' | 'reference') => void;
  setModal: (v: null) => void;
  navigate: (v: string, p?: string) => void;
  drop: (e: DragEvent, r: 'source' | 'reference' | 'library') => void;
  setAssets: Dispatch<SetStateAction<Asset[]>>;
  update: (r: Partial<JobRequest>) => void;
  draft: JobRequest;
  setError: (v: string) => void;
}) {
  const [filterOpen, setFilterOpen] = useState(false);
  const filterAnchor = useRef<HTMLButtonElement>(null);
  const shown = assets.filter(
    (a) =>
      (a.kind === 'image' || a.kind === 'video') &&
      (!picker || picker !== 'reference' || a.kind === 'image') &&
      (assetFilter === 'All' || a.kind === assetFilter.toLowerCase()),
  );
  return (
    <div className={`library-content ${picker ? 'library-picker' : ''}`}>
      {!picker && (
        <>
          {' '}
          <div className="section-heading">
            <div>
              <h1>{picker ? 'CHOOSE YOUR MEDIA' : 'YOUR MEDIA'}</h1>
              <p>Source footage, reference images and finished creations.</p>
            </div>
            <button className="primary" onClick={() => browse(picker || 'library')}>
              <Icon name="upload" />
              Upload media
            </button>
          </div>
          <div className="chips">
            {['All', 'Video', 'Image'].map((f) => (
              <button
                key={f}
                className={assetFilter === f ? 'active' : ''}
                onClick={() => setAssetFilter(f)}
              >
                {f}
              </button>
            ))}
          </div>
        </>
      )}
      {picker && (
        <div className="asset-picker-toolbar">
          <span>Uploads</span>
          <button
            ref={filterAnchor}
            onClick={() => setFilterOpen((v) => !v)}
            aria-label="Filter media"
          >
            <Icon name="sliders" size={16} />
            Filter
          </button>
        </div>
      )}
      {filterOpen && (
        <AnchoredPopover
          anchor={filterAnchor.current}
          placement="bottom-end"
          width={160}
          label="Filter media"
          onClose={() => setFilterOpen(false)}
        >
          <div className="option-menu">
            {['All', 'Image', 'Video']
              .filter((f) => picker !== 'reference' || f !== 'Video')
              .map((f) => (
                <button
                  key={f}
                  role="menuitemradio"
                  aria-checked={assetFilter === f}
                  onClick={() => {
                    setAssetFilter(f);
                    setFilterOpen(false);
                  }}
                >
                  {f === 'All' ? 'All media' : f + 's'}
                  {assetFilter === f && <Icon name="check" size={16} />}
                </button>
              ))}
          </div>
        </AnchoredPopover>
      )}
      {shown.length || picker ? (
        <div className="asset-grid">
          {picker && (
            <button
              className="asset-upload-tile"
              onClick={() => browse(picker)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => drop(e, picker)}
            >
              <span>
                <Icon name="upload" size={20} />
              </span>
              Upload file
            </button>
          )}
          {shown.map((a) => (
            <article className="asset-card" data-asset-id={a.id} key={a.id}>
              <button
                className="asset-select"
                onClick={() => {
                  setModal(null);
                  selectAsset(a, picker || 'source');
                  navigate('studio', 'help');
                }}
              >
                <div className="asset-thumb">
                  {a.thumbnail_url ? (
                    <img src={a.thumbnail_url} alt={a.name} />
                  ) : a.kind === 'video' ? (
                    <video src={mediaUrl(a)} muted preload="metadata" />
                  ) : (
                    <img src={mediaUrl(a)} alt={a.name} />
                  )}
                  <span>
                    {a.kind === 'video' ? (
                      <>
                        <Icon name="video" size={13} />
                        {a.duration?.toFixed(1)}s
                      </>
                    ) : (
                      <Icon name="image" size={13} />
                    )}
                  </span>
                </div>
                <strong>{a.name}</strong>
                <small>{a.width && a.height ? `${a.width} × ${a.height}` : a.kind}</small>
              </button>
              <div className="asset-actions">
                <a href={mediaUrl(a)} download={a.name} aria-label={`Download ${a.name}`}>
                  <Icon name="download" size={16} />
                </a>
                <button
                  aria-label={`Delete ${a.name}`}
                  onClick={async () => {
                    if (!confirm(`Delete “${a.name}”?`)) return;
                    try {
                      await api(`/assets/${a.id}`, { method: 'DELETE' });
                      setAssets((s) => s.filter((x) => x.id !== a.id));
                      if (draft.source_asset_id === a.id)
                        update({ source_asset_id: undefined, mask_asset_id: undefined, ...(draft.inpaint_reference_mode === 'edited-first-frame' ? { reference_asset_id: undefined, inpaint_reference_mode: undefined } : {}) });
                      if (draft.reference_asset_id === a.id)
                        update({ reference_asset_id: undefined, inpaint_reference_mode: undefined });
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  <Icon name="trash" size={16} />
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => drop(e, picker || 'library')}>
          <EmptyState
            icon="upload"
            title="Bring your scene"
            description="Drop an image or video here, or upload from your device."
            action={
              <button className="secondary" onClick={() => browse(picker || 'library')}>
                Choose a file
              </button>
            }
          />
        </div>
      )}
      <div className="pagination-note">
        <span>
          {shown.length} matches · {assets.length} of {assetTotal} files loaded
        </span>
        {assets.length < assetTotal && (
          <button className="secondary" onClick={onLoadMoreAssets} disabled={loadingAssets}>
            {loadingAssets ? 'Loading…' : 'Load more files'}
          </button>
        )}
      </div>
    </div>
  );
}

export function HelpPanel({
  onSettings,
  onUpload,
  onPresets,
  editing,
  effectId,
  sourceAssetId,
}: {
  onSettings: () => void;
  onUpload: () => void;
  onPresets: () => void;
  editing: boolean;
  effectId: string;
  sourceAssetId?: string;
}) {
  const examples = [
    [
      'remove-object',
      'REMOVE OBJECT',
      'Select a subject, track its mask, and fill the area while preserving the rest of your video.',
    ],
    [
      'replace-object',
      'REPLACE & TRANSFORM',
      'Paint an area and describe the object you want in its place.',
    ],
    [
      'restyle',
      'RESTYLE YOUR VIDEO',
      'Change the scene with an editable prompt and a model of your choice.',
    ],
    ['cinematic', 'LIGHT & ATMOSPHERE', 'Describe a new lighting treatment for the scene.'],
    ['weather', 'CHANGE THE WEATHER', 'Explore a new atmosphere using a video-to-video workflow.'],
    ['video-outpaint', 'RE-FRAME & COMPOSITION', 'Place your source inside a new canvas and generate the surrounding scene.'],
  ];
  const initialSlide = Math.max(0, examples.findIndex(([id]) => id === (effectId === 'relight' ? 'cinematic' : effectId)));
  const [slide, setSlide] = useState(initialSlide);
  useEffect(() => setSlide(initialSlide), [initialSlide]);
  const example = examples[slide];
  const bottom = (
    <button className="help-bottom reference-help-bottom" onClick={onSettings}>
      <span className="help-bottom-art">
        <img src={previewSources['image-to-video']} alt="Higgsfield input-image example" />
        <img src={previewSources['image-to-video']} alt="" />
      </span>
      <span>
        <strong>Don’t know where to start?</strong>
        <small>Connect local ComfyUI or Comfy Cloud.</small>
      </span>
    </button>
  );
  if (editing)
    return (
      <div className="reference-edit-help">
        <div className="edit-example">
          <div className="edit-example-media">
            <SceneArt id={example[0]} />
          </div>
          <h1>{example[1]}</h1>
          <p>{example[2]}</p>
          {example[0] === 'video-outpaint' && (
            <a className="secondary" href={`/apps/video-outpaint${sourceAssetId ? `?source=${encodeURIComponent(sourceAssetId)}` : ''}`}>
              Open AI Reframe
            </a>
          )}
          <small className="example-kind">
            {previewDescriptions[example[0]] || 'Choose a source video to make your own'}
          </small>
          <div className="example-carousel">
            <button
              aria-label="Previous example"
              onClick={() => setSlide((slide + examples.length - 1) % examples.length)}
            >
              <Icon name="chevron" />
            </button>
            <div>
              {examples.map((e, i) => (
                <button
                  key={e[0]}
                  className={slide === i ? 'active' : ''}
                  aria-label={e[1]}
                  onClick={() => setSlide(i)}
                >
                  <SceneArt id={e[0]} />
                </button>
              ))}
            </div>
            <button
              aria-label="Next example"
              onClick={() => setSlide((slide + 1) % examples.length)}
            >
              <Icon name="chevron" />
            </button>
          </div>
        </div>
        {bottom}
      </div>
    );
  return (
    <div className="help-content reference-help">
      <div className="tutorial-main">
        <h1>MAKE VIDEOS IN ONE CLICK</h1>
        <p className="help-intro">
          Presets for video creation, framing, and VFX — or use the general preset for manual
          control.
        </p>
        <div className="help-grid">
          <article>
            <button
              className="tutorial-media tutorial-upload"
              aria-label="Choose source media"
              onClick={onUpload}
            >
              <Icon name="image" size={26} />
              <strong>UPLOAD IMAGE</strong>
              <small>or choose from your media</small>
              <img src={previewSources['image-to-video']} alt="Higgsfield input-image example" />
            </button>
            <h2>ADD IMAGE</h2>
            <p>Upload or generate an image to start your animation</p>
          </article>
          <article>
            <button
              className="tutorial-media tutorial-presets"
              aria-label="Browse workflow presets"
              onClick={onPresets}
            >
              <span>
                <SceneArt id="cinematic" />
                <b>CINEMATIC</b>
              </span>
              <span>
                <SceneArt id="text-to-video" />
                <b>GENERAL</b>
              </span>
              <span>
                <SceneArt id="restyle" />
                <b>RESTYLE</b>
              </span>
            </button>
            <h2>CHOOSE PRESET</h2>
            <p>Pick a preset to control your image movement</p>
          </article>
          <article>
            <div
              className="tutorial-media tutorial-result"
              title="Public Higgsfield video example, not an OpenFrame output"
            >
              <video
                src={previewVideos['text-to-video']}
                poster={previewSources['text-to-video']}
                muted
                autoPlay={!matchMedia('(prefers-reduced-motion: reduce)').matches}
                loop
                playsInline
              />
            </div>
            <h2>GET VIDEO</h2>
            <p>Click generate to create your final animated video!</p>
          </article>
        </div>
      </div>
      {bottom}
    </div>
  );
}
