import { useEffect, useRef, useState } from 'react';
import { api, mediaUrl, post, upload } from '../api';
import { Icon } from '../Icon';
import type { Asset, Catalog, Job, Settings } from '../types';
import { AppSwitcher } from './AppSwitcher';
import { useAppDocument } from './useAppDocument';
import { durationFrames, renderRequest, renderSize } from './renderRequest';
import { loadProjectSnapshot, showProjectDraft } from './projectReuse';
import { AnchoredPopover } from '../Popovers';
import './cinema-studio.css';
import cinemaReferenceFallback from './cinema-reference.json';
import { LightingEditor, PaletteEditor, defaultLights } from './CinemaCreativeEditors';
import type { CinemaLight, ColorPalette, LightingPreset } from './CinemaCreativeEditors';

type CinemaState = {
  prompt: string;
  mode: 'image' | 'video';
  model_id: string;
  provider: string;
  aspect_ratio: string;
  quality: number;
  duration: number;
  variants: number;
  generate_audio: boolean;
  reference_asset_ids: string[];
  attachment_asset_ids: string[];
  film: { genre: string; era: string; tempo: string };
  camera: { body: string; lens: string; aperture: string; movements: string[] };
  palette: string;
  lighting: string;
  palette_colors: string[];
  custom_lights: CinemaLight[];
  palette_presets: ColorPalette[];
  lighting_presets: LightingPreset[];
  pinned_presets: string[];
};
type Preview = { title: string; poster?: string; video?: string; colors?: string[] };
type CinemaReference = Record<string, Preview[]>;
const initial: CinemaState = {
  prompt: '',
  mode: 'video',
  model_id: 'ltx-2.5',
  provider: '',
  aspect_ratio: '16:9',
  quality: 1024,
  duration: 5,
  variants: 1,
  generate_audio: true,
  reference_asset_ids: [],
  attachment_asset_ids: [],
  film: { genre: 'General', era: 'Auto', tempo: 'Auto' },
  camera: { body: 'Auto', lens: 'Auto', aperture: 'Auto', movements: [] },
  palette: 'Auto',
  lighting: 'Auto',
  palette_colors: [],
  custom_lights: [],
  palette_presets: [],
  lighting_presets: [],
  pinned_presets: [],
};
const assetIds = (state: CinemaState) => [
  ...state.reference_asset_ids,
  ...(state.attachment_asset_ids || []),
  ...(state.palette_presets || [])
    .map((preset) => preset.image_asset_id)
    .filter((id): id is string => !!id),
];
const filmOptions = {
  genre: ['Drama', 'Noir', 'Comedy', 'Horror', 'Action', 'General', 'Epic'],
  era: ['1960s', '1980s', '1990s', '2000s', '2020s', 'Auto'],
  tempo: ['Dynamic', 'Calm', 'Single shot', 'Auto', 'Chaotic'],
};
const cameraOptions = {
  body: ['Auto', 'Modern', '35mm Film', '8mm Film', 'DV Camcorder'],
  lens: [
    'Auto',
    'Clean Sharp',
    'Anamorphic',
    'Vintage Anamorphic',
    'Warm Vintage',
    'Halation Vintage',
  ],
  aperture: ['Auto', 'f/1.4 Wide Open', 'f/4 Moderate', 'f/11 Deep Focus'],
};
function PreviewMedia({ item }: { item?: Preview }) {
  if (!item) return null;
  return item.video ? (
    <video
      src={item.video}
      poster={item.poster}
      muted
      playsInline
      loop
      preload="none"
      onMouseEnter={(event) => void event.currentTarget.play().catch(() => {})}
      onMouseLeave={(event) => event.currentTarget.pause()}
    />
  ) : item.poster ? (
    <img src={item.poster} alt={item.title} />
  ) : null;
}
export function CinemaStudio({
  catalog,
  settings,
  onSettings,
}: {
  catalog: Catalog;
  settings: Settings;
  onSettings: () => void;
}) {
  const session = useAppDocument('cinema-studio', initial, assetIds);
  const { state, update } = session;
  const [view, setView] = useState('Home');
  const [showLearn, setShowLearn] = useState(true);
  const [panel, setPanel] = useState<string | null>(null);
  const [filmTab, setFilmTab] = useState<keyof typeof filmOptions>('genre');
  const [cameraTab, setCameraTab] = useState<'setup' | 'movement'>('setup');
  const [reference, setReference] = useState<CinemaReference>(cinemaReferenceFallback);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [presetSearch, setPresetSearch] = useState('');
  const [presetSort, setPresetSort] = useState(false);
  const [presetActions, setPresetActions] = useState<string | null>(null);
  const [editorReset, setEditorReset] = useState(0);
  const [editPalette, setEditPalette] = useState<ColorPalette | undefined>();
  const [editLights, setEditLights] = useState<CinemaLight[]>(defaultLights);
  const [movementSearch, setMovementSearch] = useState('');
  const [movementSort, setMovementSort] = useState(false);
  const [menu, setMenu] = useState<{ name: string; anchor: HTMLElement } | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [selectedJobSnapshot, setSelectedJob] = useState<Job | null>(null);
  const selectedJob =
    session.jobs.find((job) => job.id === selectedJobSnapshot?.id) || selectedJobSnapshot;
  const dialog = useRef<HTMLDialogElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const effectId =
    state.mode === 'image'
      ? state.reference_asset_ids.length
        ? 'edit-image'
        : 'create-image'
      : state.reference_asset_ids.length
        ? 'image-to-video'
        : 'text-to-video';
  const effect = catalog.effects.find((item) => item.id === effectId);
  const models = catalog.models.filter((item) => effect?.model_ids.includes(item.id));
  const model =
    models.find((item) => item.id === state.model_id) ||
    (!state.model_id
      ? models.find((item) => item.id === (state.mode === 'image' ? 'flux3-klein' : 'ltx-2.5')) || models[0]
      : undefined);
  const provider = state.provider || settings.default_provider || 'local';
  const maxReferences = state.mode === 'image' ? Number(model?.max_references || 4) : 1;
  const currentFilm = filmOptions[filmTab];
  const selectedFilm = state.film[filmTab];
  const filmIndex = Math.max(0, currentFilm.indexOf(selectedFilm));
  const selectedReferences = state.reference_asset_ids
    .map((id) => assets.find((asset) => asset.id === id))
    .filter((asset): asset is Asset => !!asset);
  useEffect(() => {
    fetch('/reference-media/components.json')
      .then((response) => (response.ok ? response.json() : null))
      .then((value) => setReference(value?.['cinema-studio'] || cinemaReferenceFallback))
      .catch(() => {});
    api<{ items: Asset[] }>('/assets?limit=100')
      .then((value) => setAssets(value.items))
      .catch((reason) => setError(reason.message));
  }, []);
  useEffect(() => {
    for (const id of state.reference_asset_ids)
      if (!assets.some((asset) => asset.id === id))
        void api<Asset>(`/assets/${id}`)
          .then((asset) =>
            setAssets((items) =>
              items.some((item) => item.id === id) ? items : [...items, asset],
            ),
          )
          .catch(() => {});
  }, [state.reference_asset_ids.join(','), assets.length]);
  useEffect(() => {
    const element = dialog.current;
    if (panel || preview || selectedJob) element?.showModal();
    return () => element?.close();
  }, [panel, preview, selectedJob?.id]);
  const close = () => {
    setPanel(null);
    setPreview(null);
    setSelectedJob(null);
  };
  const open = (name: string) => {
    setMenu(null);
    setPanel(name);
  };
  const popover = (name: string, anchor: HTMLElement) =>
    setMenu(menu?.name === name ? null : { name, anchor });
  const chooseFilm = (name: string) => update({ film: { ...state.film, [filmTab]: name } });
  const chooseCamera = (key: keyof typeof cameraOptions, name: string) =>
    update({ camera: { ...state.camera, [key]: name } });
  function changeMode(mode: 'image' | 'video') {
    const preferred = mode === 'image' ? 'flux3-klein' : 'ltx-2.5';
    const fallback = mode === 'image' ? 'flux-klein-4b' : 'ltx-2.3';
    update({ mode, model_id: catalog.models.some((item) => item.id === preferred) ? preferred : fallback });
  }
  function toggleReference(asset: Asset) {
    if (state.reference_asset_ids.includes(asset.id))
      update({ reference_asset_ids: state.reference_asset_ids.filter((id) => id !== asset.id) });
    else if (state.reference_asset_ids.length < maxReferences)
      update({ reference_asset_ids: [...state.reference_asset_ids, asset.id] });
    else
      setError(
        `This ${state.mode} workflow accepts ${maxReferences} reference image${maxReferences === 1 ? '' : 's'}. Remove one first.`,
      );
  }
  async function uploadReferences(files: FileList | null) {
    if (!files?.length) return;
    if (files.length + state.reference_asset_ids.length > maxReferences) {
      setError(`Choose up to ${maxReferences} reference image${maxReferences === 1 ? '' : 's'}.`);
      return;
    }
    setUploading(true);
    try {
      const added: Asset[] = [];
      for (const file of Array.from(files)) added.push(await upload(file));
      setAssets((items) => [...added, ...items]);
      update({
        reference_asset_ids: [...state.reference_asset_ids, ...added.map((asset) => asset.id)],
      });
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  }
  async function generate() {
    if (!model || !state.prompt.trim() || submitting) return;
    setError('');
    setSubmitting(true);
    try {
      if (state.reference_asset_ids.length > maxReferences)
        throw new Error(`Remove extra references: this workflow accepts ${maxReferences}.`);
      const operation = session.application?.operations.find((item) => item.id === effectId);
      if (!operation?.available)
        throw new Error(operation?.reason || 'This operation is not available.');
      const doc = await session.save();
      if (!doc) throw new Error('Save this project before generating.');
      const style = [
        state.film.genre !== 'General' && `${state.film.genre} film genre`,
        state.film.era !== 'Auto' && `${state.film.era} period`,
        state.film.tempo !== 'Auto' && `${state.film.tempo} pacing`,
        state.camera.body !== 'Auto' && `${state.camera.body} cinematography`,
        state.camera.lens !== 'Auto' && `${state.camera.lens} lens look`,
        state.camera.aperture !== 'Auto' && `${state.camera.aperture} depth of field`,
        ...state.camera.movements.filter((name) => !state.prompt.includes('#' + name)),
        state.palette !== 'Auto' &&
          `${state.palette} color palette${state.palette_colors?.length ? ': ' + state.palette_colors.join(', ') : ''}`,
        state.lighting !== 'Auto' &&
          `${state.lighting} lighting${state.custom_lights?.length ? ': ' + state.custom_lights.map((light, index) => `Light ${index + 1} ${light.position.toLowerCase()}, color ${light.color}, brightness ${light.brightness}%, diffusion ${light.diffuse}%`).join('; ') : ''}`,
      ]
        .filter(Boolean)
        .join('. ');
      const request = renderRequest(model, {
        effect_id: effectId,
        prompt: [state.prompt.trim(), style].filter(Boolean).join('\n'),
        provider,
        ...renderSize(model, state.aspect_ratio, state.quality),
        frames: state.mode === 'image' ? 1 : durationFrames(model, state.duration),
        fps: state.mode === 'image' ? 1 : Number(model.default_fps || 24),
        source_asset_id: state.reference_asset_ids[0],
        reference_asset_ids: state.reference_asset_ids.slice(1),
        batch_size: state.mode === 'image' ? state.variants : 1,
        generate_audio: state.mode === 'video' && state.generate_audio && !!model.supports_audio,
      });
      const group = crypto.randomUUID();
      const count = state.mode === 'image' ? 1 : state.variants;
      for (let index = 0; index < count; index++)
        await post<Job>(`/apps/cinema-studio/documents/${doc.id}/jobs`, {
          expected_revision: doc.revision,
          operation: effectId,
          request,
          group_id: group,
          step_id: `variant-${index + 1}`,
        });
      await session.refreshJobs();
      setView('My projects');
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  async function reuse(job: Job) {
    try {
      const snapshot = await loadProjectSnapshot<CinemaState>(job, 'cinema-studio', catalog, assetIds);
      if (!await session.newDocument(snapshot.state)) return;
      const draft = await session.save(true);
      if (!draft) throw new Error('The reused project could not be saved.');
      showProjectDraft(draft.id, '/generate');
      close();
      setView('Home');
    } catch (reason) {
      setError((reason as Error).message);
    }
  }
  const visibleJobs =
    view === 'My favorites'
      ? session.jobs.filter((job) => job.favorite)
      : view === 'My projects' && session.document
        ? session.jobs.filter((job) => job.app_context?.document_id === session.document?.id)
        : session.jobs;
  const presetKind = panel === 'Lighting' ? 'lighting' : 'palette';
  const customPresets: Preview[] =
    presetKind === 'lighting'
      ? (state.lighting_presets || []).map((item) => ({ title: item.name }))
      : (state.palette_presets || []).map((item) => ({
          title: item.name,
          colors: item.colors,
          poster: item.image_url,
        }));
  const presetItems = [...customPresets, ...(reference[presetKind] || [])]
    .filter((item) => item.title.toLowerCase().includes(presetSearch.toLowerCase()))
    .sort(
      (a, b) =>
        Number((state.pinned_presets || []).includes(b.title)) -
          Number((state.pinned_presets || []).includes(a.title)) ||
        (presetSort ? a.title.localeCompare(b.title) : 0),
    );
  function resetCreative() {
    if (panel === 'Film setup') update({ film: initial.film });
    else if (panel === 'Camera') update({ camera: initial.camera });
    else if (panel === 'Color palette') update({ palette: 'Auto', palette_colors: [] });
    else if (panel === 'Lighting') update({ lighting: 'Auto', custom_lights: [] });
    else {
      setEditPalette(undefined);
      setEditLights(defaultLights);
      setEditorReset((n) => n + 1);
    }
  }
  function selectPreset(item: Preview) {
    if (presetKind === 'palette')
      update({ palette: item.title, palette_colors: item.colors || [] });
    else
      update({
        lighting: item.title,
        custom_lights:
          state.lighting_presets?.find((entry) => entry.name === item.title)?.lights || [],
      });
  }
  function newCreativePreset() {
    setEditPalette(undefined);
    setEditLights(defaultLights);
    setEditorReset((n) => n + 1);
    setPanel(presetKind === 'lighting' ? 'New lighting preset' : 'New palette');
  }
  const movements = (reference['camera-movement'] || []).filter((item) =>
    item.title.toLowerCase().includes(movementSearch.toLowerCase()),
  );
  if (movementSort) movements.sort((a, b) => a.title.localeCompare(b.title));
  const icon = (index: number) => reference['control-icons']?.[index]?.poster;
  return (
    <main className="cinema-studio">
      <aside className="cin-rail">
        <AppSwitcher name="Cinema Studio" />
        <nav>
          {[
            ['Home', 'home'],
            ['My generations', 'spark'],
            ['My elements', 'grid'],
            ['My favorites', 'heart'],
            ['Community', 'globe'],
          ].map(([label, name]) => (
            <button
              key={label}
              className={view === label ? 'active' : ''}
              onClick={() => setView(label)}
            >
              <span>
                <Icon name={name} size={16} />
              </span>
              {label}
            </button>
          ))}
        </nav>
        <div className="cin-project-label">
          <span>Projects</span>
          <button aria-label="Search projects" onClick={() => open('Projects')}>
            <Icon name="search" size={14} />
          </button>
          <button aria-label="Project order" onClick={() => open('Projects')}>
            <Icon name="sliders" size={14} />
          </button>
        </div>
        <button
          className="cin-new-project"
          onClick={() => {
            void session.newDocument();
            setView('Home');
          }}
        >
          <Icon name="plus" size={16} />
          New project
        </button>
        <div className="cin-projects">
          {session.documents.map((doc) => (
            <button
              key={doc.id}
              onClick={() => {
                void session.openDocument(doc);
                setView('My projects');
              }}
            >
              {doc.title}
            </button>
          ))}
        </div>
        <div className="cin-rail-bottom">
          {showLearn && (
            <div className="cin-learn">
              <button aria-label="Dismiss learning card" onClick={() => setShowLearn(false)}>
                <Icon name="close" size={14} />
              </button>
              <small>Learn Cinema Studio</small>
              <p>
                Build a cinematic scene
                <br />
                one shot at a time
              </p>
              <a href="https://academy.higgsfield.ai/" target="_blank" rel="noreferrer">
                Learn now
                <Icon name="external" size={13} />
              </a>
            </div>
          )}
          <button className="cin-settings" onClick={onSettings}>
            <Icon name="settings" size={16} />
            Compute settings
            <Icon name="chevron" size={14} />
          </button>
        </div>
      </aside>
      <section className="cin-main">
        <div className="cin-top-actions">
          <button onClick={onSettings}>
            {catalog.providers.find((item) => item.id === provider)?.name || provider}
            <Icon name="chevron" size={12} />
          </button>
        </div>
        {view === 'Home' && (
          <>
            <div className="cin-hero-strip">
              {reference.hero?.map((item, index) => (
                <button
                  key={index}
                  className={`cin-hero-card cin-hero-${index}`}
                  onClick={() => setPreview(item)}
                >
                  <PreviewMedia item={item} />
                  <span>{item.title}</span>
                </button>
              ))}
            </div>
            <h1>BRING YOUR STORIES TO LIFE</h1>
          </>
        )}
        {view !== 'Home' && (
          <div className="cin-page-heading">
            <h1>{view}</h1>
            <p>
              {view === 'Community'
                ? 'Public reference projects. Your generations stay in this workspace.'
                : view === 'My elements'
                  ? 'Uploaded reference images in this workspace.'
                  : `${session.jobs.length} of ${session.jobTotal} generations loaded`}
            </p>
          </div>
        )}
        {view === 'My elements' && (
          <div className="cin-elements">
            {assets
              .filter((asset) => asset.kind === 'image')
              .map((asset) => (
                <button
                  key={asset.id}
                  onClick={() => {
                    toggleReference(asset);
                    setView('Home');
                  }}
                >
                  <img src={asset.thumbnail_url || mediaUrl(asset)} alt={asset.name} />
                  <span>{asset.name}</span>
                </button>
              ))}
          </div>
        )}
        {view === 'Community' && (
          <div className="cin-community">
            {reference.hero?.map((item, index) => (
              <button key={index} onClick={() => setPreview(item)}>
                <PreviewMedia item={item} />
                <span>{item.title}</span>
              </button>
            ))}
          </div>
        )}
        {(view === 'My projects' || view === 'My favorites' || view === 'My generations') && (
          <div className="cin-job-grid">
            {visibleJobs.map((job) => {
              const output = job.outputs.find((asset) => asset.role === 'result') || job.outputs[0];
              return (
                <button key={job.id} onClick={() => setSelectedJob(job)} className="cin-job">
                  <div>
                    {output?.kind === 'video' ? (
                      <video
                        src={mediaUrl(output)}
                        poster={output.thumbnail_url || undefined}
                        muted
                        preload="metadata"
                      />
                    ) : output?.kind === 'image' ? (
                      <img src={mediaUrl(output)} alt="Generated result" />
                    ) : (
                      <Icon name="film" size={32} />
                    )}
                  </div>
                  <strong>{job.request.prompt}</strong>
                  <span>
                    {job.status === 'running'
                      ? `Rendering · ${Math.round(job.progress * 100)}%`
                      : job.status}
                  </span>
                </button>
              );
            })}
            {!visibleJobs.length && <p>No generations here yet.</p>}
            {session.jobs.length < session.jobTotal && (
              <button onClick={session.loadMoreJobs}>Load more</button>
            )}
          </div>
        )}
        <div className={`cin-compose-area ${view !== 'Home' ? 'cin-compose-bottom' : ''}`}>
          <div className="cin-mode-tabs">
            <button
              className={state.mode === 'image' ? 'active' : ''}
              onClick={() => changeMode('image')}
            >
              <Icon name="image" size={22} />
              <span>Image</span>
            </button>
            <button
              className={state.mode === 'video' ? 'active' : ''}
              onClick={() => changeMode('video')}
            >
              <Icon name="video" size={22} />
              <span>Video</span>
            </button>
          </div>
          <div className="cin-composer-wrap">
            <div className="cin-creative-controls">
              <button className="cin-reference-control" onClick={() => open('References')}>
                <Icon name="image" size={20} />
                <span>
                  References
                  <small>
                    {state.reference_asset_ids.length}/{maxReferences}
                  </small>
                </span>
              </button>
              {[
                ['Film setup', 0, state.film.genre === 'General' ? 'Auto' : state.film.genre],
                ['Camera', 1, state.camera.body],
                ['Color palette', 2, state.palette],
                ['Lighting', 3, state.lighting],
              ].map(([label, index, value]) => (
                <button key={label} onClick={() => open(String(label))}>
                  {icon(Number(index)) && <img src={icon(Number(index))} alt="" />}
                  <span>
                    {label}
                    <small>{value}</small>
                  </span>
                </button>
              ))}
            </div>
            <div className="cin-prompt-box">
              <div className="cin-prompt-content">
                {selectedReferences.length > 0 && (
                  <div className="cin-selected-refs">
                    {selectedReferences.map((asset) => (
                      <button
                        key={asset.id}
                        title={`Remove ${asset.name}`}
                        onClick={() => toggleReference(asset)}
                      >
                        <img src={asset.thumbnail_url || mediaUrl(asset)} alt={asset.name} />
                        <Icon name="close" size={12} />
                      </button>
                    ))}
                  </div>
                )}
                <textarea
                  value={state.prompt}
                  onChange={(event) => update({ prompt: event.target.value })}
                  placeholder="Describe your shot. Add references or select camera movements"
                  aria-label="Describe your shot"
                />
                <div className="cin-config-row">
                  <span className="cin-variants">
                    <button
                      aria-label="Fewer variants"
                      disabled={state.variants <= 1}
                      onClick={() => update({ variants: state.variants - 1 })}
                    >
                      −
                    </button>
                    <b>{state.variants}/4</b>
                    <button
                      aria-label="More variants"
                      disabled={state.variants >= 4}
                      onClick={() => update({ variants: state.variants + 1 })}
                    >
                      +
                    </button>
                  </span>
                  <button
                    className="cin-model-choice"
                    onClick={(event) => popover('Model', event.currentTarget)}
                  >
                    <Icon name="film" size={14} />
                    {model?.name || 'Choose model'}
                    <Icon name="chevron" size={11} />
                  </button>
                  <button onClick={(event) => popover('Quality', event.currentTarget)}>
                    {state.quality}px
                    <Icon name="chevron" size={11} />
                  </button>
                  <button onClick={(event) => popover('Aspect ratio', event.currentTarget)}>
                    <Icon name="square" size={11} />
                    {state.aspect_ratio}
                    <Icon name="chevron" size={11} />
                  </button>
                  {state.mode === 'video' && (
                    <>
                      <button onClick={(event) => popover('Duration', event.currentTarget)}>
                        {state.duration}s<Icon name="chevron" size={11} />
                      </button>
                      <button
                        className={state.generate_audio ? 'enabled' : ''}
                        disabled={!model?.supports_audio}
                        title={
                          model?.supports_audio
                            ? 'Generate native audio'
                            : 'This model does not generate native audio'
                        }
                        onClick={() => update({ generate_audio: !state.generate_audio })}
                      >
                        <Icon name="sound" size={14} />
                        <span className="cin-switch" />
                      </button>
                    </>
                  )}
                </div>
              </div>
              <button
                className="cin-generate"
                disabled={!session.ready || !state.prompt.trim() || submitting || !model}
                onClick={() => void generate()}
              >
                <Icon name="spark" size={18} />
                <strong>{submitting ? 'Queueing…' : 'Generate'}</strong>
                <span>
                  {state.mode === 'image'
                    ? `${state.variants} image${state.variants > 1 ? 's' : ''}`
                    : `${state.variants} video${state.variants > 1 ? 's' : ''}`}
                </span>
              </button>
            </div>
            {(error || session.error) && (
              <p className="cin-error" role="alert">
                {error || session.error}
              </p>
            )}
            <span className="cin-save-status">
              {session.saving ? 'Saving…' : session.document ? 'Project saved' : ''}
            </span>
          </div>
        </div>
      </section>
      {menu && (
        <AnchoredPopover
          anchor={menu.anchor}
          onClose={() => setMenu(null)}
          width={menu.name === 'Model' ? 260 : 180}
          label={menu.name}
          placement="bottom-end"
          className="cin-options"
        >
          <h3>{menu.name}</h3>
          {menu.name === 'Model' ? (
            models.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  update({ model_id: item.id });
                  setMenu(null);
                }}
              >
                {item.name}
                {item.id === model?.id && <Icon name="check" size={14} />}
              </button>
            ))
          ) : menu.name === 'Quality' ? (
            [512, 768, 1024].map((value) => (
              <button
                key={value}
                onClick={() => {
                  update({ quality: value });
                  setMenu(null);
                }}
              >
                {value}px{value === state.quality && <Icon name="check" size={14} />}
              </button>
            ))
          ) : menu.name === 'Aspect ratio' ? (
            (model?.aspect_ratios || ['16:9', '9:16', '1:1']).map((value) => (
              <button
                key={value}
                onClick={() => {
                  update({ aspect_ratio: value });
                  setMenu(null);
                }}
              >
                {value}
                {value === state.aspect_ratio && <Icon name="check" size={14} />}
              </button>
            ))
          ) : (
            <>
              <label>
                {state.duration}s
                <input
                  type="range"
                  min="1"
                  max={
                    model
                      ? Math.floor(
                          Number(model.max_frames || 241) / Number(model.default_fps || 24),
                        )
                      : 10
                  }
                  step="1"
                  value={state.duration}
                  onChange={(event) => update({ duration: Number(event.target.value) })}
                />
              </label>
              <small>
                {model &&
                  `${durationFrames(model, state.duration)} frames · ${(durationFrames(model, state.duration) / Number(model.default_fps || 24)).toFixed(2)}s actual`}
              </small>
            </>
          )}
        </AnchoredPopover>
      )}
      <dialog
        ref={dialog}
        className={`cin-dialog ${['Film setup', 'Camera', 'Color palette', 'Lighting', 'New palette', 'New lighting preset'].includes(panel || '') ? 'cin-creative-dialog' : ''}`}
        onCancel={close}
        onClick={(event) => {
          if (event.target === event.currentTarget) close();
        }}
      >
        <header>
          <h2>
            {(panel === 'New palette' || panel === 'New lighting preset') && (
              <button
                aria-label="Back"
                onClick={() => setPanel(panel === 'New palette' ? 'Color palette' : 'Lighting')}
              >
                <Icon name="chevron" size={16} />
              </button>
            )}
            {panel || preview?.title || 'Generation'}
          </h2>
          <div>
            {[
              'Film setup',
              'Camera',
              'Color palette',
              'Lighting',
              'New palette',
              'New lighting preset',
            ].includes(panel || '') && <button onClick={resetCreative}>Reset all</button>}
            <button aria-label="Close dialog" onClick={close}>
              <Icon name="close" size={16} />
            </button>
          </div>
        </header>
        {panel === 'Film setup' && (
          <div className="cin-dialog-layout">
            <nav>
              {(['genre', 'era', 'tempo'] as const).map((tab) => (
                <button
                  className={filmTab === tab ? 'active' : ''}
                  key={tab}
                  onClick={() => setFilmTab(tab)}
                >
                  <Icon
                    name={tab === 'genre' ? 'film' : tab === 'era' ? 'clock' : 'bolt'}
                    size={16}
                  />
                  {tab[0].toUpperCase() + tab.slice(1)}
                  <span>{state.film[tab]}</span>
                </button>
              ))}
            </nav>
            <div className="cin-film-picker">
              <h3>
                {filmTab === 'genre'
                  ? 'Pick a genre'
                  : filmTab === 'era'
                    ? 'Set the era'
                    : 'Set the tempo'}
              </h3>
              <p>
                {filmTab === 'genre'
                  ? 'The feeling that holds your story together.'
                  : 'Added to your shot prompt as creative direction.'}
              </p>
              <div className="cin-film-carousel">
                {[-2, -1, 0, 1, 2].map((offset) => {
                  const name =
                    currentFilm[(filmIndex + offset + currentFilm.length) % currentFilm.length];
                  const item = reference[`film-${filmTab}`]?.find((entry) => entry.title === name);
                  return (
                    <button
                      key={offset}
                      className={`cin-film-option position-${offset + 2}`}
                      onClick={() => chooseFilm(name)}
                      aria-label={name}
                    >
                      <PreviewMedia item={item} />
                      {!item && <span>{name}</span>}
                    </button>
                  );
                })}
              </div>
              <div className="cin-carousel-footer">
                <button
                  aria-label={`Previous ${filmTab}`}
                  onClick={() =>
                    chooseFilm(
                      currentFilm[(filmIndex - 1 + currentFilm.length) % currentFilm.length],
                    )
                  }
                >
                  <Icon name="chevron" size={16} />
                </button>
                <strong>{selectedFilm}</strong>
                <button
                  aria-label={`Next ${filmTab}`}
                  onClick={() => chooseFilm(currentFilm[(filmIndex + 1) % currentFilm.length])}
                >
                  <Icon name="chevron" size={16} />
                </button>
              </div>
            </div>
          </div>
        )}
        {panel === 'Camera' && (
          <div className="cin-dialog-layout">
            <nav>
              <button
                className={cameraTab === 'setup' ? 'active' : ''}
                onClick={() => setCameraTab('setup')}
              >
                <Icon name="sliders" size={16} />
                Setup<span>{state.camera.body}</span>
              </button>
              <button
                className={cameraTab === 'movement' ? 'active' : ''}
                onClick={() => setCameraTab('movement')}
              >
                <Icon name="video" size={16} />
                Movement<span>{state.camera.movements.length || 'Auto'}</span>
              </button>
            </nav>
            {cameraTab === 'setup' ? (
              <div className="cin-camera-wheels">
                {(Object.keys(cameraOptions) as (keyof typeof cameraOptions)[]).map((key) => (
                  <div key={key}>
                    <h3>{key === 'body' ? 'Camera' : key[0].toUpperCase() + key.slice(1)}</h3>
                    <div className="cin-camera-wheel">
                      {cameraOptions[key].map((name) => (
                        <button
                          key={name}
                          className={state.camera[key] === name ? 'selected' : ''}
                          onClick={() => chooseCamera(key, name)}
                        >
                          <PreviewMedia
                            item={reference['camera-setup']?.find((item) => item.title === name)}
                          />
                          <span>{name}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="cin-movement-panel">
                <div>
                  <h3>Direct a camera move</h3>
                  <p>
                    Adds to the prompt box, or type # there.
                    <br />
                    Several per shot; order matters.
                  </p>
                  <div className="cin-movement-tools">
                    <button
                      aria-label="Sort movements"
                      onClick={() => setMovementSort(!movementSort)}
                    >
                      <Icon name="sliders" size={16} />
                    </button>
                    <label>
                      <Icon name="search" size={16} />
                      <input
                        aria-label="Search movements"
                        placeholder="Search"
                        value={movementSearch}
                        onChange={(event) => setMovementSearch(event.target.value)}
                      />
                    </label>
                  </div>
                </div>
                <div className="cin-movement-grid">
                  {movements.map((item) => (
                    <button
                      key={item.title}
                      className={state.camera.movements.includes(item.title) ? 'selected' : ''}
                      onClick={() =>
                        update({
                          prompt: state.camera.movements.includes(item.title)
                            ? state.prompt
                                .split('#' + item.title)
                                .join('')
                                .trim()
                            : `${state.prompt.trim()} #${item.title}`.trim(),
                          camera: {
                            ...state.camera,
                            movements: state.camera.movements.includes(item.title)
                              ? state.camera.movements.filter((name) => name !== item.title)
                              : [...state.camera.movements, item.title],
                          },
                        })
                      }
                    >
                      <div>
                        <PreviewMedia item={item} />
                        <span>Put on prompt</span>
                      </div>
                      <strong>{item.title}</strong>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {panel === 'References' && (
          <div className="cin-reference-picker">
            <button
              className="cin-upload"
              onClick={() => fileInput.current?.click()}
              disabled={uploading}
            >
              <Icon name="upload" />
              {uploading ? 'Uploading…' : 'Upload images'}
            </button>
            <p>
              {state.mode === 'image'
                ? 'Use up to four images as visual references.'
                : 'Use one opening image for image-to-video.'}
            </p>
            <div>
              {assets
                .filter((asset) => asset.kind === 'image')
                .map((asset) => (
                  <button
                    key={asset.id}
                    className={state.reference_asset_ids.includes(asset.id) ? 'selected' : ''}
                    onClick={() => toggleReference(asset)}
                  >
                    <img src={asset.thumbnail_url || mediaUrl(asset)} alt={asset.name} />
                    {state.reference_asset_ids.includes(asset.id) && (
                      <Icon name="check" size={18} />
                    )}
                  </button>
                ))}
            </div>
          </div>
        )}
        {panel === 'Projects' && (
          <div className="cin-document-picker">
            {session.documents.map((doc) => (
              <button
                key={doc.id}
                onClick={() => {
                  void session.openDocument(doc);
                  setView('My projects');
                  close();
                }}
              >
                {doc.title}
              </button>
            ))}
          </div>
        )}
        {(panel === 'Color palette' || panel === 'Lighting') && (
          <div className="cin-preset-panel">
            <div className="cin-preset-heading">
              <h3>{presetKind === 'lighting' ? 'Set up lighting' : 'Set up color palette'}</h3>
              <p>
                {presetKind === 'lighting'
                  ? 'Pick a scheme or place your own lights'
                  : 'Palette the color grade should follow'}
              </p>
              <div>
                <button onClick={() => setPresetSort(!presetSort)}>
                  <Icon name="sliders" size={14} />
                  {presetSort ? 'Name' : 'Sort by'}
                </button>
                <label>
                  <Icon name="search" size={15} />
                  <input
                    aria-label="Search presets"
                    placeholder="Search"
                    value={presetSearch}
                    onChange={(event) => setPresetSearch(event.target.value)}
                  />
                </label>
              </div>
            </div>
            <div className={`cin-preset-grid ${presetKind}`}>
              <div className="cin-preset-card cin-new-preset">
                <button onClick={newCreativePreset}>
                  <span className="cin-preset-image">
                    <Icon name="plus" size={28} />
                  </span>
                  <strong>
                    {presetKind === 'lighting' ? 'New lighting preset' : 'New palette'}
                  </strong>
                </button>
              </div>
              {presetItems.map((item, index) => (
                <div
                  className={`cin-preset-card ${(presetKind === 'lighting' ? state.lighting : state.palette) === item.title ? 'selected' : ''}`}
                  key={item.title + index}
                >
                  <button onClick={() => selectPreset(item)}>
                    <span className="cin-preset-image">
                      <PreviewMedia item={item} />
                      {item.colors && (
                        <span className="cin-preset-colors">
                          {item.colors.map((color, i) => (
                            <i key={i} style={{ background: color }} />
                          ))}
                        </span>
                      )}
                    </span>
                    <strong>{item.title}</strong>
                  </button>
                  <div className="cin-preset-card-tools">
                    <button
                      className={(state.pinned_presets || []).includes(item.title) ? 'pinned' : ''}
                      aria-label={`Pin ${item.title}`}
                      onClick={() =>
                        update({
                          pinned_presets: (state.pinned_presets || []).includes(item.title)
                            ? state.pinned_presets.filter((name) => name !== item.title)
                            : [...(state.pinned_presets || []), item.title],
                        })
                      }
                    >
                      <Icon name="pin" size={13} />
                    </button>
                    <button
                      aria-label={`${item.title} actions`}
                      onClick={() =>
                        setPresetActions(presetActions === item.title ? null : item.title)
                      }
                    >
                      <Icon name="more" size={13} />
                    </button>
                  </div>
                  {presetActions === item.title && (
                    <div className="cin-preset-actions">
                      <button
                        onClick={() => {
                          setPresetActions(null);
                          if (presetKind === 'palette') {
                            setEditPalette({
                              name: item.title + ' copy',
                              colors: item.colors || [],
                            });
                            setPanel('New palette');
                          } else {
                            setEditLights(
                              state.lighting_presets?.find((entry) => entry.name === item.title)
                                ?.lights || defaultLights,
                            );
                            setPanel('New lighting preset');
                          }
                          setEditorReset((n) => n + 1);
                        }}
                      >
                        Edit a copy
                      </button>
                      {customPresets.some((entry) => entry.title === item.title) && (
                        <button
                          onClick={() => {
                            if (presetKind === 'palette')
                              update({
                                palette_presets: state.palette_presets.filter(
                                  (entry) => entry.name !== item.title,
                                ),
                              });
                            else
                              update({
                                lighting_presets: state.lighting_presets.filter(
                                  (entry) => entry.name !== item.title,
                                ),
                              });
                            setPresetActions(null);
                          }}
                        >
                          Delete preset
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
        {panel === 'New lighting preset' && (
          <LightingEditor
            key={editorReset}
            value={editLights}
            onApply={(lights) => {
              update({ lighting: 'Custom', custom_lights: lights });
              setPanel('Lighting');
            }}
            onSave={(preset) => {
              update({
                lighting: preset.name,
                custom_lights: preset.lights,
                lighting_presets: [
                  ...(state.lighting_presets || []).filter((item) => item.name !== preset.name),
                  preset,
                ],
              });
              setPanel('Lighting');
            }}
          />
        )}
        {panel === 'New palette' && (
          <PaletteEditor
            key={editorReset}
            value={editPalette}
            onError={setError}
            onSave={(preset) => {
              update({
                palette: preset.name,
                palette_colors: preset.colors,
                palette_presets: [
                  ...(state.palette_presets || []).filter((item) => item.name !== preset.name),
                  preset,
                ],
                attachment_asset_ids: [
                  ...new Set([
                    ...(state.attachment_asset_ids || []),
                    ...(preset.image_asset_id ? [preset.image_asset_id] : []),
                  ]),
                ],
              });
              setPanel('Color palette');
            }}
          />
        )}
        {preview && (
          <div className="cin-preview">
            <video src={preview.video} poster={preview.poster} controls playsInline />
            <p>
              Public reference project from Higgsfield. This is not a generation from your
              workspace.
            </p>
          </div>
        )}
        {selectedJob && (
          <div className="cin-result">
            <p>{selectedJob.request.prompt}</p>
            {selectedJob.outputs
              .filter((asset) => asset.role !== 'mask')
              .map((asset) => (
                <div key={asset.id}>
                  {asset.kind === 'video' ? (
                    <video src={mediaUrl(asset)} controls playsInline />
                  ) : (
                    <img src={mediaUrl(asset)} alt="Generated result" />
                  )}
                  <a href={mediaUrl(asset)} download={asset.name}>
                    Download result
                  </a>
                </div>
              ))}
            {selectedJob.error && <p role="alert">{selectedJob.error}</p>}
            <div className="cin-result-actions">
              <button onClick={() => void reuse(selectedJob)}>Reuse project</button>
              <a href={`/api/jobs/${selectedJob.id}/workflow`} download>
                Workflow API
              </a>
              <a href={`/api/jobs/${selectedJob.id}/bundle?include_media=true`} download>
                Full project
              </a>
              <button
                onClick={() => {
                  void api<Job>(`/jobs/${selectedJob.id}`, {
                    method: 'PATCH',
                    body: JSON.stringify({ favorite: !selectedJob.favorite }),
                  })
                    .then((job) => {
                      setSelectedJob(job);
                      void session.refreshJobs();
                    })
                    .catch((reason) => setError(reason.message));
                }}
              >
                {selectedJob.favorite ? 'Unfavorite' : 'Favorite'}
              </button>
            </div>
          </div>
        )}
      </dialog>
      <input
        ref={fileInput}
        type="file"
        hidden
        accept="image/*"
        multiple
        onChange={(event) => void uploadReferences(event.target.files)}
      />
    </main>
  );
}
