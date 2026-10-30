import { useEffect, useState } from 'react';
import { api, mediaUrl, post } from '../api';
import { Icon } from '../Icon';
import { AnchoredPopover } from '../Popovers';
import type { Asset, ImageLayoutRegion, Job, JobRequest } from '../types';
import { MaskEditor } from '../MaskEditor';
import { ImageRegionEditor } from './ImageRegionEditor';
import { useTrainedCharacters } from './trainedCharacters';
import type { TrainedCharacter } from './trainedCharacters';
import type { AppDocument } from './registry';
import { useAppDocument } from './useAppDocument';
import { renderRequest, renderSize } from './renderRequest';
import {
  AssetPicker,
  ReferenceMedia,
  ResultDialog,
  useReferenceLibrary,
  useWorkspaceAssets,
  WorkspaceDialog,
  WorkspaceHistory,
} from './engine-apps-shared';
import type { EngineAppProps, ReferenceItem } from './engine-apps-shared';
import './root-apps.css';

type ImageState = {
  prompt: string;
  reference_asset_ids: string[];
  style: string;
  ratio: string;
  quality: number;
  batch: number;
  seed: number;
  model_id: string;
  mode: 'image' | 'photodump';
  scenes: string[];
  image_prompt_mode: 'expand' | 'caption';
  image_reference_megapixels: number;
  image_layout: ImageLayoutRegion[];
  image_preservation: 'none' | 'outside-mask' | 'inside-mask';
  mask_asset_id: string;
  mask_feather: number;
  mask_feather_explicit?: boolean;
  prompt_is_composed?: boolean;
  character_adapter_id: string;
  character_strength: number;
};
const initial: ImageState = {
  prompt: '',
  reference_asset_ids: [],
  style: '',
  ratio: '3:4',
  quality: 1024,
  batch: 1,
  seed: -1,
  model_id: 'auto',
  image_prompt_mode: 'expand',
  image_reference_megapixels: 1,
  image_layout: [],
  image_preservation: 'none',
  mask_asset_id: '',
  mask_feather: 6,
  mask_feather_explicit: false,
  character_adapter_id: '',
  character_strength: 1,
  mode: 'image',
  scenes: [
    'A candid street portrait in soft morning light.',
    'A relaxed portrait in a sunlit cafe.',
    'An editorial full-body photograph in a minimal studio.',
    'A close-up portrait at golden hour.',
  ],
};
const ids = (state: ImageState) =>
  [...state.reference_asset_ids, state.mask_asset_id].filter(Boolean);
type Identity = { title: string; reference_asset_ids: string[]; prompt?: string };
export function SoulImage({ catalog, settings, onSettings }: EngineAppProps) {
  const session = useAppDocument('soul-image', initial, ids),
    { state, update } = session;
  const assets = useWorkspaceAssets(ids(state)),
    library = useReferenceLibrary('soul-image');
  const photoSeriesScenes = state.scenes.map((value) => value.trim()).filter(Boolean);
  const trained = useTrainedCharacters();
  const [loadedCharacter, setLoadedCharacter] = useState<TrainedCharacter | null>(null);
  const trainedCharacter =
    trained.items.find((item) => item.id === state.character_adapter_id) ||
    (loadedCharacter?.id === state.character_adapter_id ? loadedCharacter : null);
  const [view, setView] = useState<'Create' | 'Presets' | 'History'>('Create'),
    [picker, setPicker] = useState(false),
    [maskOpen, setMaskOpen] = useState(false),
    [regionOpen, setRegionOpen] = useState(false),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [selected, setSelected] = useState<Job | null>(null);
  const [dialog, setDialog] = useState<'styles' | 'characters' | 'scenes' | null>(null),
    [characters, setCharacters] = useState<AppDocument<Identity>[]>([]),
    [search, setSearch] = useState(''),
    [modelSearch, setModelSearch] = useState('');
  const [menu, setMenu] = useState<{ name: string; anchor: HTMLElement } | null>(null);
  const provider = settings.default_provider || 'local';
  const controlsReady = session.ready && catalog.models.length > 0 && catalog.effects.length > 0;
  const imageModelIds = new Set(catalog.effects.filter((item) => ['create-image', 'edit-image'].includes(item.id)).flatMap((item) => item.model_ids));
  const availableModels = catalog.models.filter((item) => imageModelIds.has(item.id));
  const compatibleModels = availableModels
    .filter(
      (item) =>
        state.reference_asset_ids.length <= Number(item.max_references || 4) &&
        (!state.character_adapter_id || item.supports_character_adapters) &&
        (!(state.image_layout || []).length || item.supports_image_layout) &&
        (!state.image_preservation ||
          state.image_preservation === 'none' ||
          item.supports_image_preservation) &&
        state.quality <=
          Math.max(Number(item.max_width || 1536), Number(item.max_height || 1536)) &&
        (!Array.isArray(item.supported_providers) || item.supported_providers.includes(provider)) &&
        (!state.reference_asset_ids.length || item.tasks.includes('image-edit')),
    )
    .sort((left, right) => {
      const preference = ['flux3-klein', 'flux3-klein-int8', 'flux-klein-4b'];
      const rank = (id: string) =>
        preference.includes(id) ? preference.indexOf(id) : preference.length;
      return rank(left.id) - rank(right.id);
    });
  const model =
    state.model_id === 'auto'
      ? compatibleModels[0]
      : availableModels.find((item) => item.id === state.model_id);
  const maxReferences = Number(model?.max_references || 4);
  const source = assets.get(state.reference_asset_ids[0]);
  const referenceAssets = state.reference_asset_ids
    .map(assets.get)
    .filter((asset): asset is Asset => !!asset);
  const referencesReady = referenceAssets.length === state.reference_asset_ids.length;
  const layout = state.image_layout || [];
  const preservation = state.image_preservation || 'none';
  const supportsLayout = Boolean(model?.supports_image_layout);
  const supportsPreservation = Boolean(model?.supports_image_preservation);
  const supportsExpansion = Boolean(model?.supports_prompt_expansion);
  const resolvedRatio =
    state.ratio === 'Auto'
      ? source?.width && source?.height
        ? `${source.width}:${source.height}`
        : '1:1'
      : state.ratio;
  const size = model
    ? preservation !== 'none' && source?.width && source.height
      ? { width: source.width, height: source.height }
      : renderSize(model, resolvedRatio, state.quality)
    : { width: 1024, height: 1024 };
  const resolutions = (
    Array.isArray(model?.resolution_presets)
      ? model.resolution_presets.map(Number)
      : [512, 768, 1024, 1536, 2048, 4096]
  ).filter(
    (value) =>
      value <= Math.max(Number(model?.max_width || 1536), Number(model?.max_height || 1536)),
  );
  const resolutionLabel = (value: number) =>
    (({ 768: '768p', 1024: '1K', 1536: '1.5K', 2048: '2K', 4096: '4K' }) as Record<number, string>)[
      value
    ] || `${value}px`;
  function removeReference(id: string) {
    const index = state.reference_asset_ids.indexOf(id);
    if (
      (index === 0 && state.mask_asset_id) ||
      layout.some((item) => item.source_reference === index)
    ) {
      setError(
        'Clear the mask or source-region instructions that use this reference before removing it.',
      );
      return;
    }
    update({
      reference_asset_ids: state.reference_asset_ids.filter((value) => value !== id),
      image_layout: layout.map((item) =>
        item.source_reference != null && item.source_reference > index
          ? { ...item, source_reference: item.source_reference - 1 }
          : item,
      ),
    });
  }
  useEffect(() => {
    api<{ items: AppDocument<Identity>[] }>('/apps/soul-id-cast/documents?limit=100')
      .then((value) => setCharacters(value.items))
      .catch((reason) => setError(reason.message));
  }, []);
  useEffect(() => {
    if (!state.character_adapter_id) {
      setLoadedCharacter(null);
      return;
    }
    let active = true;
    void api<TrainedCharacter>(`/characters/${encodeURIComponent(state.character_adapter_id)}`)
      .then((record) => {
        if (active) setLoadedCharacter(record);
      })
      .catch((reason) => {
        if (active) setError(reason.message);
      });
    return () => {
      active = false;
    };
  }, [state.character_adapter_id]);
  useEffect(() => {
    const id = new URLSearchParams(location.search).get('trained_character');
    if (!id || !session.ready) return;
    let active = true;
    void api<TrainedCharacter>(`/characters/${encodeURIComponent(id)}`)
      .then(async (record) => {
        if (!active) return;
        if (record.status !== 'ready' || !record.adapter)
          throw new Error('This character has not finished training successfully.');
        const created = await session.newDocument({
          ...initial,
          character_adapter_id: record.id,
          model_id: record.model_id,
        });
        if (created && active) {
          setLoadedCharacter(record);
          const url = new URL(location.href);
          url.searchParams.delete('trained_character');
          url.searchParams.delete('document');
          history.replaceState(null, '', url);
        }
      })
      .catch((reason) => {
        if (active) setError(reason.message);
      });
    return () => {
      active = false;
    };
  }, [session.ready]);
  useEffect(() => {
    const characterId = new URLSearchParams(location.search).get('character');
    if (
      !session.ready ||
      !characterId ||
      new URLSearchParams(location.search).has('trained_character')
    )
      return;
    let active = true;
    api<AppDocument<Identity>>(`/apps/soul-id-cast/documents/${encodeURIComponent(characterId)}`)
      .then(async (value) => {
        if (!active) return;
        const created = await session.newDocument({
          ...initial,
          reference_asset_ids: value.state.reference_asset_ids.slice(0, 4),
        });
        if (created && active) {
          const url = new URL(location.href);
          url.searchParams.delete('character');
          url.searchParams.delete('document');
          history.replaceState(null, '', url);
        }
      })
      .catch((reason) => setError(reason.message));
    return () => {
      active = false;
    };
  }, [session.ready]);
  function chooseStyle(item: ReferenceItem) {
    update({ style: item.title });
    setDialog(null);
  }
  async function generate() {
    if (!model || busy) return;
    setError('');
    setBusy(true);
    try {
      if (!state.prompt.trim()) throw new Error('Describe the image you want to create.');
      if (provider !== 'local')
        throw new Error(
          'This image workflow currently runs on Local ComfyUI. Choose a supported compute provider.',
        );
      if (state.reference_asset_ids.length > maxReferences)
        throw new Error(
          `This model accepts up to ${maxReferences} reference images. Remove references or choose a compatible model.`,
        );
      if (!referencesReady) throw new Error('Wait for reference images to load.');
      if (state.character_adapter_id) {
        if (!model.supports_character_adapters)
          throw new Error(
            'Choose the matching FLUX3 Base model for this trained adapter, or remove the adapter.',
          );
        if (!trainedCharacter || trainedCharacter.status !== 'ready')
          throw new Error('Wait for this character to finish training successfully.');
        if (provider !== (trainedCharacter.configuration?.provider || 'unavailable'))
          throw new Error('Select the compute provider that holds this trained adapter. Adapter weights are not transferred between providers.');
      }
      if (
        supportsExpansion &&
        state.image_prompt_mode === 'caption' &&
        state.prompt.trim().length < 80
      )
        throw new Error(
          'A complete caption needs at least 80 characters. Add visual detail or choose prompt expansion.',
        );
      const referenceMegapixels = state.image_reference_megapixels ?? 1;
      if (
        supportsExpansion &&
        (!Number.isFinite(referenceMegapixels) ||
          referenceMegapixels < 0.25 ||
          referenceMegapixels > 4 ||
          referenceMegapixels * state.reference_asset_ids.length > 16)
      )
        throw new Error(
          'Use 0.25–4 megapixels per reference and no more than 16 megapixels across all references.',
        );
      if (layout.length && !supportsLayout)
        throw new Error(
          'This model cannot consume the saved region layout. Choose a compatible model or clear the regions.',
        );
      if (preservation !== 'none' && !supportsPreservation)
        throw new Error(
          'This model does not support pixel preservation. Choose a compatible model or turn preservation off.',
        );
      if (preservation !== 'none' && (!source || !state.mask_asset_id))
        throw new Error('Choose a source image and paint its preservation mask.');
      if (
        size.width < Number(model.min_width || 256) ||
        size.height < Number(model.min_height || 256) ||
        size.width > Number(model.max_width || 4096) ||
        size.height > Number(model.max_height || 4096)
      )
        throw new Error(
          'These output dimensions are outside the selected model limits. Choose a different resolution or source image.',
        );
      if (
        state.mode === 'photodump' &&
        !state.reference_asset_ids.length &&
        !state.character_adapter_id
      )
        throw new Error('Choose a character reference for the photo series.');
      const operation = state.reference_asset_ids.length ? 'edit-image' : 'create-image';
      if (!session.application?.operations.find((item) => item.id === operation)?.available)
        throw new Error('The image workflow is unavailable.');
      const record = await session.save(true);
      if (!record) throw new Error('Save the draft before generating.');
      const scenes = state.mode === 'photodump' ? photoSeriesScenes : [''];
      if (!scenes.length) throw new Error('Add at least one scene to the photo series.');
      let submitted = 0;
      try {
        for (const scene of scenes) {
          const request = renderRequest(model, {
            effect_id: operation,
            prompt: [
              state.reference_asset_ids.length &&
              state.image_prompt_mode !== 'caption' &&
              !state.prompt_is_composed &&
              !state.prompt
                .trimStart()
                .startsWith(
                  'Use the supplied reference images for the same subject and appearance.',
                )
                ? 'Use the supplied reference images for the same subject and appearance.'
                : '',
              state.prompt,
              scene,
              state.style && `Visual style: ${state.style}.`,
            ]
              .filter(Boolean)
              .join('\n'),
            provider,
            ...(state.character_adapter_id
              ? {
                  character_adapter_id: state.character_adapter_id,
                  character_strength: state.character_strength ?? 1,
                }
              : {}),
            ...size,
            ...(supportsExpansion
              ? {
                  image_prompt_mode: state.image_prompt_mode || 'expand',
                  image_reference_megapixels: state.image_reference_megapixels ?? 1,
                }
              : {}),
            ...(supportsLayout ? { image_layout: layout } : {}),
            ...(supportsPreservation
              ? {
                  image_preservation: preservation,
                  mask_asset_id: preservation !== 'none' ? state.mask_asset_id : undefined,
                  mask_feather: state.mask_feather ?? 6,
                }
              : {}),
            source_asset_id: state.reference_asset_ids[0],
            reference_asset_ids: state.reference_asset_ids.slice(1),
            frames: 1,
            fps: 1,
            batch_size: state.mode === 'photodump' ? 1 : state.batch,
            seed: state.seed < 0 ? -1 : state.seed + submitted,
          });
          const job = await post<Job>(`/apps/soul-image/documents/${record.id}/jobs`, {
            expected_revision: record.revision,
            operation,
            request,
          });
          submitted++;
          setSelected(job);
          setView('History');
        }
      } catch (reason) {
        throw new Error(
          `${submitted ? `${submitted} image job(s) were submitted. ` : ''}${(reason as Error).message}`,
        );
      } finally {
        await session.refreshJobs();
      }
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reuse(job: Job) {
    try {
      const context = await api<{ document_snapshot: AppDocument<ImageState> | null }>(
        `/jobs/${job.id}/app-context`,
      );
      if (context.document_snapshot?.state) {
        await session.newDocument({
          ...initial,
          ...context.document_snapshot.state,
          ...(job.request.mask_asset_id
            ? {
                mask_feather: job.request.mask_feather,
                mask_feather_explicit: true,
              }
            : {}),
          prompt_is_composed:
            context.document_snapshot.state.prompt_is_composed ||
            context.document_snapshot.state.prompt === job.request.prompt,
          model_id: job.request.model_id,
          seed: job.request.seed,
          character_adapter_id: job.request.character_adapter_id || '',
          character_strength: job.request.character_strength ?? 1,
        });
      } else {
        const request: JobRequest = job.request;
        await session.newDocument({
          ...initial,
          prompt: request.prompt,
          prompt_is_composed: true,
          model_id: request.model_id,
          reference_asset_ids: [
            request.source_asset_id,
            ...(request.reference_asset_ids || []),
          ].filter((value): value is string => !!value),
          quality: Math.max(request.width, request.height),
          ratio: `${request.width}:${request.height}`,
          seed: request.seed,
          character_adapter_id: request.character_adapter_id || '',
          character_strength: request.character_strength ?? 1,
          batch: request.batch_size || 1,
          image_prompt_mode: request.image_prompt_mode || 'caption',
          image_reference_megapixels: request.image_reference_megapixels ?? 1,
          image_layout: request.image_layout || [],
          image_preservation: request.image_preservation || 'none',
          mask_asset_id: request.mask_asset_id || '',
          mask_feather: request.mask_feather ?? 6,
          mask_feather_explicit: true,
        });
      }
      setView('Create');
    } catch (reason) {
      setError((reason as Error).message);
    }
  }
  const presets = (library.presets || []).filter((item) =>
    `${item.title} ${item.prompt || ''}`.toLowerCase().includes(search.toLowerCase()),
  );
  const styles = (library.styles?.length ? library.styles : library.presets || [])
    .filter((item) => item.title.toLowerCase().includes(search.toLowerCase()))
    .map((item) => ({
      ...library.presets?.find((preset) => preset.title === item.title),
      ...item,
    }));
  return (
    <main className="soul-app">
      <nav className="soul-view-nav">
        {(['Create', 'Presets', 'History'] as const).map((value) => (
          <button
            className={view === value ? 'active' : ''}
            key={value}
            onClick={() => setView(value)}
          >
            {value}
          </button>
        ))}
        <span />
        {session.saving ? <small>Saving…</small> : session.document ? <small>Saved</small> : null}
        <button onClick={() => void session.newDocument()}>New image</button>
      </nav>
      {view === 'Create' ? (
        <section className="soul-hero">
          <div className="soul-hero-strip">
            {library.hero?.slice(0, 4).map((item, index) => (
              <ReferenceMedia key={index} item={item} />
            ))}
          </div>
          <h1>
            {library.wordmark ? (
              <img className="soul-wordmark" src={library.wordmark} alt="Soul" />
            ) : (
              'SOUL'
            )}
          </h1>
          <p>
            Create images with character, texture and style.
            <br />
            Guide each scene with your own references.
          </p>
          <button onClick={() => setView('Presets')}>
            Explore styles <Icon name="arrow" size={15} />
          </button>
        </section>
      ) : view === 'History' ? (
        <section className="soul-history">
          <WorkspaceHistory
            jobs={session.jobs}
            total={session.jobTotal}
            onSelect={setSelected}
            onMore={session.loadMoreJobs}
          />
        </section>
      ) : (
        <section className="soul-presets">
          <header>
            <h1>Image styles</h1>
            <label>
              <Icon name="search" size={16} />
              <input
                placeholder="Search styles and scenes"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
          </header>
          <div>
            {presets.map((item, index) => (
              <button
                key={item.id || index}
                onClick={() => {
                  update({ prompt: item.prompt || item.title, style: item.category || item.title });
                  setView('Create');
                }}
              >
                <ReferenceMedia item={item} />
                <span>{item.title}</span>
              </button>
            ))}
          </div>
          {!presets.length && (
            <p>No reference styles match. You can create directly from your own prompt.</p>
          )}
          <small>Public reference examples; generated results appear in History.</small>
        </section>
      )}
      <section className="soul-composer" aria-label="Image generation controls">
        <div className="soul-input-row">
          <textarea
            aria-label="Image prompt"
            placeholder="Describe the scene you imagine"
            value={state.prompt}
            onChange={(event) => update({ prompt: event.target.value })}
          />
          {state.reference_asset_ids.length > 0 && (
            <div className="soul-reference-chips">
              {state.reference_asset_ids.map((id, index) => (
                <div key={id}>
                  {assets.get(id) && (
                    <img src={mediaUrl(assets.get(id)!)} alt={`Reference ${index + 1}`} />
                  )}
                  <button
                    aria-label={`Remove reference ${index + 1}`}
                    onClick={() => removeReference(id)}
                  >
                    <Icon name="close" size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="soul-composer-bottom">
          <div className="soul-controls">
            <button
              title="Add reference images"
              aria-label="References"
              disabled={state.reference_asset_ids.length >= maxReferences}
              onClick={() => setPicker(true)}
            >
              <Icon name="plus" size={16} />
            </button>
            <button disabled={!controlsReady} onClick={(event) => setMenu({ name: 'Model', anchor: event.currentTarget })}>
              <Icon name="spark" size={14} />
              {!controlsReady ? 'Loading model…' : state.model_id === 'auto'
                ? `Auto · ${model?.name || 'No compatible model'}`
                : model?.name || 'Choose model'}
              <Icon name="chevron" size={12} />
            </button>
            <button
              onClick={(event) => setMenu({ name: 'Aspect ratio', anchor: event.currentTarget })}
            >
              <Icon name="square" size={13} />
              {state.ratio}
            </button>
            <button
              onClick={(event) => setMenu({ name: 'Resolution', anchor: event.currentTarget })}
            >
              {resolutionLabel(state.quality)}
            </button>
            <div className="soul-batch">
              <button
                aria-label="Decrease image count"
                disabled={state.batch === 1 || state.mode === 'photodump'}
                onClick={() => update({ batch: state.batch - 1 })}
              >
                −
              </button>
              <span>{state.mode === 'photodump' ? photoSeriesScenes.length : state.batch}/4</span>
              <button
                aria-label="Increase image count"
                disabled={state.batch === 4 || state.mode === 'photodump'}
                onClick={() => update({ batch: state.batch + 1 })}
              >
                +
              </button>
            </div>
            <button
              aria-label="Advanced image settings"
              onClick={(event) => setMenu({ name: 'Settings', anchor: event.currentTarget })}
            >
              <Icon name="sliders" size={15} />
            </button>
          </div>
          <button className="soul-character" onClick={() => setDialog('characters')}>
            {trainedCharacter?.dataset_asset_ids[0] ? (
              <img
                src={`/api/assets/${trainedCharacter.dataset_asset_ids[0]}/thumbnail`}
                alt={`Training photo for ${trainedCharacter.name}`}
              />
            ) : (
              <Icon name="plus" size={16} />
            )}
            <small>{trainedCharacter?.name || 'CHARACTER'}</small>
          </button>
          <button className="soul-style-tile" onClick={() => setDialog('styles')}>
            {state.style && <ReferenceMedia item={library.presets?.find((item) => item.title === state.style)} />}
            <span>
              <Icon name="brush" size={12} />
              {state.style ? 'Change' : 'Choose style'}
            </span>
            <small>{state.style || 'No style'}</small>
          </button>
          <button
            className="soul-generate"
            disabled={busy || !session.ready || !model || !state.prompt.trim()}
            onClick={() => void generate()}
          >
            {busy ? 'Preparing…' : 'Generate'}
            <Icon name="spark" size={17} />
          </button>
        </div>
        <div className="soul-composer-status">
          <button onClick={onSettings}>
            <Icon name="cloud" size={12} />
            {!controlsReady ? 'Loading connection…' : provider === 'local' ? 'Local ComfyUI' : provider === 'comfy-cloud' ? 'Comfy Cloud' : 'Saved connection unavailable'}
          </button>
          <span>
            {state.ratio === 'Auto' && `Auto: ${state.reference_asset_ids.length && !source ? 'loading reference…' : source ? 'reference aspect' : 'square canvas'} · `}
            {preservation !== 'none' && (model && source?.width && source.height ? `Preserved canvas ${source.width} × ${source.height} · ` : 'Loading reference canvas… · ')}
            {state.reference_asset_ids.length}/{maxReferences} references ·{' '}
            {state.mode === 'photodump' ? 'One image per scene' : 'PNG output'}
          </span>
        </div>
        {state.character_adapter_id && (
          <p className="soul-adapter-status">
            {trainedCharacter
              ? `${trainedCharacter.name} · ${trainedCharacter.status === 'ready' ? 'trained adapter' : trainedCharacter.status} · trigger ${trainedCharacter.trigger_token} is inserted by the workflow`
              : 'Loading trained character…'}
            <button onClick={() => update({ character_adapter_id: '' })}>Remove</button>
          </p>
        )}
        {controlsReady && state.model_id === 'auto' && (
          <p className="soul-auto-reason">
            {model
              ? `Auto selected ${model.name} for your reference count, region controls, resolution and compute provider. The selected profile can change when those inputs change.`
              : 'No available image model supports all selected inputs and compute settings. Change those settings or choose a model explicitly.'}
          </p>
        )}
        {(error || session.error || assets.error) && (
          <p role="alert" className="ea-error">
            {error || session.error || assets.error}
          </p>
        )}
      </section>
      {regionOpen && model && (
        <ImageRegionEditor
          regions={layout}
          references={referenceAssets}
          width={size.width}
          height={size.height}
          onApply={(value) => update({ image_layout: value })}
          onClose={() => setRegionOpen(false)}
        />
      )}
      {maskOpen && source && (
        <MaskEditor
          asset={source}
          existingMask={assets.get(state.mask_asset_id)}
          selectionMeaning={preservation === 'inside-mask' ? 'protect' : 'edit'}
          onSave={(mask) => {
            assets.add(mask);
            update({ mask_asset_id: mask.id });
          }}
          onClose={() => setMaskOpen(false)}
        />
      )}
      {picker && (
        <AssetPicker
          title="Image references"
          kind="image"
          assets={assets.assets}
          onAdded={assets.add}
          onClose={() => setPicker(false)}
          onSelect={(asset) =>
            update({
              reference_asset_ids: [...new Set([...state.reference_asset_ids, asset.id])].slice(
                0,
                maxReferences,
              ),
            })
          }
        />
      )}
      {selected && (
        <ResultDialog
          job={session.jobs.find((job) => job.id === selected.id) || selected}
          onClose={() => setSelected(null)}
          onRefresh={() => void session.refreshJobs()}
          onReuse={() => void reuse(selected)}
          onUse={(asset) => {
            assets.add(asset);
            update({
              reference_asset_ids: [asset.id],
              mask_asset_id: '',
              image_preservation: 'none',
              image_layout: [],
            });
            setView('Create');
          }}
          useKind="image"
          useLabel="Edit this image"
        />
      )}
      {menu && (
        <AnchoredPopover
          anchor={menu.anchor}
          onClose={() => setMenu(null)}
          width={menu.name === 'Settings' ? 300 : 250}
          label={menu.name}
          className="soul-popover"
        >
          <h3>{menu.name}</h3>
          {menu.name === 'Model' ? (
            <>
              <button
                onClick={() => {
                  update({ model_id: 'auto' });
                  setMenu(null);
                }}
              >
                Auto · match my inputs{state.model_id === 'auto' && <Icon name="check" size={14} />}
              </button>
              <input
                aria-label="Search image models"
                placeholder="Search models"
                value={modelSearch}
                onChange={(event) => setModelSearch(event.target.value)}
              />
              {availableModels
                .filter((item) =>
                  `${item.name} ${item.description}`
                    .toLowerCase()
                    .includes(modelSearch.toLowerCase()),
                )
                .map((item) => (
                  <button
                    key={item.id}
                    disabled={!!state.character_adapter_id && !item.supports_character_adapters}
                    title={
                      state.character_adapter_id && !item.supports_character_adapters
                        ? 'Remove the trained adapter to use an incompatible model.'
                        : item.description
                    }
                    onClick={() => {
                      update({ model_id: item.id });
                      setMenu(null);
                    }}
                  >
                    {item.name}
                    {state.model_id === item.id && <Icon name="check" size={14} />}
                  </button>
                ))}
            </>
          ) : menu.name === 'Aspect ratio' ? (
            ['Auto', ...(model?.aspect_ratios || ['1:1', '16:9', '9:16', '4:3', '3:4'])].map(
              (value) => (
                <button
                  key={value}
                  onClick={() => {
                    update({ ratio: value });
                    setMenu(null);
                  }}
                >
                  {value}
                  {state.ratio === value && <Icon name="check" size={14} />}
                </button>
              ),
            )
          ) : menu.name === 'Resolution' ? (
            resolutions.map((value) => (
              <button
                key={value}
                onClick={() => {
                  update({ quality: value });
                  setMenu(null);
                }}
              >
                {resolutionLabel(value)} · {value}px longest side
              </button>
            ))
          ) : (
            <>
              {state.character_adapter_id && (
                <label>
                  Character strength · {(state.character_strength ?? 1).toFixed(2)}
                  <input
                    type="range"
                    min={0}
                    max={2}
                    step={0.05}
                    value={state.character_strength ?? 1}
                    onChange={(event) => update({ character_strength: Number(event.target.value) })}
                  />
                  <small>
                    The actual adapter weight. Higher is not a guarantee of better resemblance.
                  </small>
                </label>
              )}
              {supportsExpansion && (
                <label>
                  Prompt mode
                  <select
                    value={state.image_prompt_mode || 'expand'}
                    onChange={(event) =>
                      update({
                        image_prompt_mode: event.target.value as ImageState['image_prompt_mode'],
                      })
                    }
                  >
                    <option value="expand">Expand my instructions</option>
                    <option value="caption">Use my complete caption</option>
                  </select>
                  <small>
                    Expansion records both submitted instructions and the model caption. Complete
                    caption bypasses expansion.
                  </small>
                </label>
              )}
              {supportsExpansion && state.reference_asset_ids.length > 0 && (
                <label>
                  Reference detail · megapixels each
                  <input
                    type="number"
                    min={0.25}
                    max={4}
                    step={0.25}
                    value={state.image_reference_megapixels ?? 1}
                    onChange={(event) =>
                      update({ image_reference_megapixels: Number(event.target.value) })
                    }
                  />
                  <small>
                    {(
                      (state.image_reference_megapixels ?? 1) * state.reference_asset_ids.length
                    ).toFixed(2)}{' '}
                    / 16 total megapixels. Original uploads are retained.
                  </small>
                </label>
              )}
              {(supportsLayout || layout.length > 0) && (
                <>
                  <button
                    disabled={!supportsLayout || !referencesReady}
                    onClick={() => {
                      setMenu(null);
                      setRegionOpen(true);
                    }}
                  >
                    Layout and regions · {layout.length}
                  </button>
                  {layout.length > 0 && (
                    <button onClick={() => update({ image_layout: [] })}>
                      Clear region instructions
                    </button>
                  )}
                </>
              )}
              {(supportsPreservation || preservation !== 'none') && (
                <>
                  <label>
                    Pixel preservation
                    <select
                      value={preservation}
                      onChange={(event) => {
                        const next = event.target.value as ImageState['image_preservation'];
                        // Older saved recipes have no choice flag; preserve their recorded value.
                        const recorded =
                          session.state.mask_feather_explicit === undefined &&
                          !!session.document &&
                          Object.hasOwn(session.document.state, 'mask_feather');
                        update({
                          image_preservation: next,
                          ...(!state.mask_feather_explicit && !recorded && next !== 'none'
                            ? { mask_feather: next === 'inside-mask' ? 0 : 6 }
                            : {}),
                        });
                      }}
                    >
                      <option value="none">Off</option>
                      <option value="outside-mask" disabled={!supportsPreservation || !source}>
                        Preserve outside painted region
                      </option>
                      <option value="inside-mask" disabled={!supportsPreservation || !source}>
                        Preserve painted product / region
                      </option>
                    </select>
                  </label>
                  {preservation !== 'none' && (
                    <>
                      <small>
                        Uses the first reference as the original canvas. {source?.width} ×{' '}
                        {source?.height}px. White means{' '}
                        {preservation === 'inside-mask' ? 'preserve original' : 'allow changes'}.
                      </small>
                      <button
                        disabled={!source || !supportsPreservation}
                        onClick={() => {
                          setMenu(null);
                          setMaskOpen(true);
                        }}
                      >
                        {state.mask_asset_id ? 'Edit mask' : 'Paint mask'}
                      </button>
                      <label>
                        Boundary softness · {state.mask_feather ?? 6}px
                        <input
                          type="range"
                          min={0}
                          max={32}
                          step={1}
                          value={state.mask_feather ?? 6}
                          onChange={(event) =>
                            update({
                              mask_feather: Number(event.target.value),
                              mask_feather_explicit: true,
                            })
                          }
                        />
                      </label>
                      {preservation === 'inside-mask' && (
                        <small>
                          Start at 0 px for a protected product. Feathering can retain a thin strip
                          of the old background around its edge.
                        </small>
                      )}
                    </>
                  )}
                  {state.mask_asset_id && (
                    <button
                      onClick={() => update({ mask_asset_id: '', image_preservation: 'none' })}
                    >
                      Remove mask
                    </button>
                  )}
                </>
              )}
              <label>
                Seed
                <input
                  type="number"
                  min="-1"
                  max="2147483647"
                  value={state.seed}
                  onChange={(event) => update({ seed: Number(event.target.value) })}
                />
              </label>
              <small>−1 chooses a new random seed.</small>
              <label>
                Mode
                <select
                  value={state.mode}
                  onChange={(event) => update({ mode: event.target.value as ImageState['mode'] })}
                >
                  <option value="image">Single scene</option>
                  <option value="photodump">Photo series</option>
                </select>
              </label>
              {state.mode === 'photodump' && (
                <button
                  onClick={() => {
                    setMenu(null);
                    setDialog('scenes');
                  }}
                >
                  Edit photo-series scenes
                </button>
              )}
            </>
          )}
        </AnchoredPopover>
      )}
      {dialog === 'styles' && (
        <WorkspaceDialog
          title="Style"
          onClose={() => setDialog(null)}
          className="soul-style-dialog"
        >
          <input
            className="soul-search"
            aria-label="Search styles"
            placeholder="Search styles"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <button
            className="ea-outline"
            onClick={() => {
              update({ style: '' });
              setDialog(null);
            }}
          >
            No style
          </button>
          <div className="soul-style-grid">
            {styles.map((item, index) => (
              <button key={item.id || index} onClick={() => chooseStyle(item)}>
                <ReferenceMedia item={item} />
                <span>{item.title}</span>
              </button>
            ))}
          </div>
          <p className="ea-muted">
            Styles add visual direction to your prompt; the selected open model creates the result.
          </p>
        </WorkspaceDialog>
      )}
      {dialog === 'characters' && (
        <WorkspaceDialog title="Choose character" onClose={() => setDialog(null)}>
          <h3>Trained characters</h3>
          <div className="soul-character-list">
            {trained.items.map((item) => (
              <button
                key={item.id}
                disabled={item.status !== 'ready'}
                onClick={() => {
                  update({
                    character_adapter_id: item.id,
                    character_strength: 1,
                    model_id: item.model_id,
                  });
                  setLoadedCharacter(item);
                  setDialog(null);
                }}
              >
                {item.dataset_asset_ids[0] && (
                  <img
                    src={`/api/assets/${item.dataset_asset_ids[0]}/thumbnail`}
                    alt={`Training photograph for ${item.name}`}
                  />
                )}
                <strong>{item.name}</strong>
                <small>{item.status === 'ready' ? `Trained adapter · ${item.configuration?.provider === 'local' ? 'Local ComfyUI' : 'Saved connection unavailable'}` : item.status}</small>
              </button>
            ))}
          </div>
          {!trained.items.length && (
            <p className="ea-muted">
              {trained.loading ? 'Loading trained characters…' : 'No trained characters yet.'}
            </p>
          )}
          {trained.items.length < trained.total && (
            <button onClick={() => void trained.loadMore()} disabled={trained.loading}>
              Load more trained characters
            </button>
          )}
          {trained.error && <p className="ea-error">{trained.error}</p>}
          {state.character_adapter_id && (
            <button onClick={() => update({ character_adapter_id: '' })}>
              Remove trained adapter
            </button>
          )}
          <a className="ea-lime" href="/soul-id?mode=training">
            Train a new character
          </a>
          <h3>Reference sets</h3>
          <div className="soul-character-list">
            {characters
              .filter((item) => item.state.reference_asset_ids?.length)
              .map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    update({
                      character_adapter_id: '',
                      reference_asset_ids: item.state.reference_asset_ids.slice(0, maxReferences),
                      mask_asset_id: '',
                      image_layout: [],
                      image_preservation: 'none',
                    });
                    setDialog(null);
                  }}
                >
                  <Icon name="image" size={24} />
                  <strong>{item.title}</strong>
                  <small>{item.state.reference_asset_ids.length} reference images</small>
                </button>
              ))}
          </div>
          <a className="ea-lime" href="/soul-id?mode=references">
            Create a character reference set
          </a>
          <p className="ea-muted">
            Reference images guide identity. This does not train a new model.
          </p>
        </WorkspaceDialog>
      )}
      {dialog === 'scenes' && (
        <WorkspaceDialog title="Photo series" onClose={() => setDialog(null)}>
          {state.scenes.map((scene, index) => (
            <label className="ea-field" key={index}>
              Scene {index + 1}
              <textarea
                value={scene}
                onChange={(event) =>
                  update({
                    scenes: state.scenes.map((value, i) =>
                      i === index ? event.target.value : value,
                    ),
                  })
                }
              />
            </label>
          ))}
          <p className="ea-muted">
            Each nonempty scene creates one image job using the same references and main prompt.
            Review each result in History.
          </p>
          <button className="ea-lime" onClick={() => setDialog(null)}>
            Apply scenes
          </button>
        </WorkspaceDialog>
      )}
    </main>
  );
}
