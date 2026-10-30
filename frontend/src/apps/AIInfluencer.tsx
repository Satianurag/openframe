import { useEffect, useRef, useState } from 'react';
import { post } from '../api';
import { Icon } from '../Icon';
import { MaskEditor } from '../MaskEditor';
import { AnchoredPopover } from '../Popovers';
import type { Asset, Job, Model } from '../types';
import { useAppDocument } from './useAppDocument';
import { loadProjectSnapshot, missingProjectSnapshot, projectReuseDescription, showProjectDraft } from './projectReuse';
import { modelSupportsReference, renderRequest, renderSize } from './renderRequest';
import { buildMotionRequest } from './motionRequest';
import { officialRecastAvailable, preferredRecastSupport, recastSupportIssue, recastReferenceCleanupAvailable, recastReferenceCleanupIssue } from './recastSupport';
import { MotionControls, motionDefaults } from './MotionControls';
import type { MotionConditioning } from './MotionControls';
import {
  AssetPicker,
  boundedVideoFrames,
  videoIntervalIssue,
  importReference,
  ReferenceDialog,
  ReferenceMedia,
  ResultDialog,
  SourceSlot,
  useReferenceLibrary,
  useWorkspaceAssets,
  WorkspaceHistory,
} from './engine-apps-shared';
import type { EngineAppProps, ReferenceItem } from './engine-apps-shared';
import './engine-apps.css';

type InfluencerState = MotionConditioning & {
  enhance_prompt?: boolean;
  image_model_id?: string;
  style_preparation_model_id?: string;
  prompt: string;
  mode: 'create' | 'motion';
  character: Record<string, string[]>;
  photo_asset_id: string;
  video_asset_id: string;
  mask_asset_id: string;
  motion_operation: 'motion-transfer' | 'character-replacement' | 'replace-object';
  swap_model_id: string;
  motion_model_id: string;
  motion_scene?: 'reference' | 'source';
  recast_model_id?: string;
  recast_composite_tracking?: 'native' | 'official' | 'official-union';
  recast_reference_cleanup?: boolean;
  prompt_enabled: boolean;
  style_name: string;
  style_custom: string;
  style_asset_id: string;
  styled_asset_id: string;
  duration: number;
  fps?: number;
  seed?: number;
  trim_start: number;
  quality: number;
  provider: string;
};
const initial: InfluencerState = {
  recast_reference_cleanup: true,
  image_model_id: 'flux3-klein',
  style_preparation_model_id: 'flux3-klein',
  ...motionDefaults,
  motion_model_id: 'wan-animate',
  prompt: '',
  mode: 'create',
  character: { 'character-type': ['Average'], age: ['Adult'] },
  photo_asset_id: '',
  video_asset_id: '',
  mask_asset_id: '',
  motion_operation: 'motion-transfer',
  swap_model_id: 'wan-vace',
  prompt_enabled: false,
  style_name: '',
  style_custom: '',
  style_asset_id: '',
  styled_asset_id: '',
  duration: 5,
  trim_start: 0,
  quality: 768,
  provider: '',
};
const assetIds = (state: InfluencerState) =>
  [
    state.photo_asset_id,
    state.video_asset_id,
    state.mask_asset_id,
    state.style_asset_id,
    state.styled_asset_id,
  ].filter(Boolean);

export function AIInfluencer({ catalog, settings, onSettings }: EngineAppProps) {
  const session = useAppDocument('ai-influencer', initial, assetIds);
  const { state, update } = session;
  const library = useReferenceLibrary('ai-influencer');
  const assets = useWorkspaceAssets(assetIds(state));
  const [view, setView] = useState<'Explore' | 'History'>('Explore');
  const [source, setSource] = useState<'characters' | 'motion' | 'trends'>('characters');
  const [opened, setOpened] = useState<string[]>(['character-type']);
  const [picker, setPicker] = useState<'photo' | 'video' | 'style' | null>(null);
  const [painting, setPainting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<Job | null>(null);
  const [preview, setPreview] = useState<ReferenceItem | null>(null);
  const [styleOpen, setStyleOpen] = useState(false),
    [styleTab, setStyleTab] = useState<'Higgsfield' | 'Custom'>('Higgsfield');
  const [menu, setMenu] = useState<{ name: 'Model' | 'Quality'; anchor: HTMLElement } | null>(null);
  const styleDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (styleOpen) styleDialog.current?.showModal();
    else styleDialog.current?.close();
  }, [styleOpen]);
  const photo = assets.get(state.photo_asset_id),
    styledPhoto = assets.get(state.styled_asset_id),
    stylePhoto = assets.get(state.style_asset_id),
    video = assets.get(state.video_asset_id);
  const effectId =
    state.mode === 'create'
      ? state.photo_asset_id
        ? 'edit-image'
        : 'create-image'
      : state.motion_operation;
  const sourceSceneMotion = state.motion_scene === 'source' && state.motion_operation === 'character-replacement';
  const performerMotion = state.motion_operation === 'motion-transfer' || sourceSceneMotion;
  const model = catalog.models.find(
    (item) =>
      item.id ===
      (state.mode === 'create'
        ? state.image_model_id || 'flux-klein-4b'
        : state.motion_operation === 'replace-object'
          ? state.swap_model_id || 'wan-vace'
          : state.motion_operation === 'character-replacement'
            ? state.recast_model_id || 'wan-animate'
            : state.motion_model_id || 'wan-animate'),
  );
  const provider = state.provider || settings.default_provider || 'local';
  const cleanupAvailable = recastReferenceCleanupAvailable(catalog, provider);
  const cleanupIssue = model?.id === 'scail-2' ? recastReferenceCleanupIssue(catalog, provider, state.recast_reference_cleanup ?? false) : '';
  const officialSupportAvailable = officialRecastAvailable(catalog, provider);
  const unionSupportAvailable = officialRecastAvailable(catalog, provider, 'official-union');
  const supportIssue = model?.id === 'scail-2' && !state.mask_asset_id
    ? recastSupportIssue(catalog, provider, state.recast_composite_tracking) : '';
  const frames =
    model && state.mode === 'motion'
      ? boundedVideoFrames(model, state.duration, video, state.trim_start, state.fps)
      : 1;
  const intervalIssue = model && state.mode === 'motion' ? videoIntervalIssue(model, state.duration, video, state.trim_start, state.fps) : '';
  const prepareStyle =
    state.mode === 'motion' &&
    state.motion_operation === 'motion-transfer' &&
    state.style_name === 'Custom' &&
    !!state.style_asset_id &&
    !state.styled_asset_id;
  const selectedStylePreparation =
    state.mode === 'motion' &&
    state.style_name === 'Custom' &&
    !!state.style_asset_id &&
    selected?.request.effect_id === 'edit-image' &&
    selected.request.source_asset_id === state.photo_asset_id &&
    selected.request.reference_asset_id === state.style_asset_id;
  const supportsAppearance = (item: Model) =>
    modelSupportsReference(
      item,
      state.motion_operation === 'motion-transfer'
        ? 'motion-transfer'
        : item.tasks.includes('character-replacement')
          ? 'character-replacement'
          : 'inpaint',
    );
  const galleries = library[source] || [];

  function choose(group: string, title: string, multiple?: boolean) {
    const selected = state.character[group] || [];
    update({
      character: {
        ...state.character,
        [group]: multiple
          ? selected.includes(title)
            ? selected.filter((item) => item !== title)
            : [...selected, title]
          : selected.includes(title)
            ? []
            : [title],
      },
    });
  }
  function randomize() {
    const character = Object.fromEntries(
      (library.groups || [])
        .filter((group) => group.options.length)
        .map((group) => [
          group.id,
          [group.options[Math.floor(Math.random() * group.options.length)].title],
        ]),
    );
    update({ character });
  }
  async function useExample(item: ReferenceItem) {
    setSubmitting(true);
    setError('');
    try {
      const kind = item.video && (source !== 'characters' || !item.poster) ? 'video' : 'image';
      const asset = await importReference(item, kind);
      assets.add(asset);
      update(
        kind === 'image'
          ? { photo_asset_id: asset.id, styled_asset_id: '', mode: 'create' }
          : { video_asset_id: asset.id, mode: 'motion', mask_asset_id: '', trim_start: 0 },
      );
      setPreview(null);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  async function reuseProject(job: Job) {
    setSubmitting(true);
    setError('');
    try {
      const snapshot = await loadProjectSnapshot<InfluencerState>(job, 'ai-influencer', catalog, assetIds);
      if (!['create', 'motion'].includes(snapshot.state.mode)) throw new Error(missingProjectSnapshot);
      const next = { ...initial, ...snapshot.state, title: snapshot.title, provider: job.request.provider,
        enhance_prompt: job.request.enhance_prompt, recast_reference_cleanup: job.request.recast_reference_cleanup ?? false, recast_composite_tracking: job.request.recast_composite_tracking || 'native', fps: job.request.fps, seed: job.request.seed };
      const operation = job.request.effect_id;
      if (next.mode === 'create' && ['create-image', 'edit-image'].includes(operation))
        next.image_model_id = job.request.model_id;
      else if (next.mode === 'motion' && operation === 'edit-image' && next.style_name === 'Custom' && next.style_asset_id)
        next.style_preparation_model_id = job.request.model_id;
      else if (next.mode === 'motion' && next.motion_operation === operation) {
        if (operation === 'motion-transfer') next.motion_model_id = job.request.model_id;
        else if (operation === 'replace-object') next.swap_model_id = job.request.model_id;
        else if (operation === 'character-replacement') next.recast_model_id = job.request.model_id;
        else
          throw new Error('This recorded character workflow cannot be restored here. No model was substituted; use its workflow export.');
      } else throw new Error(missingProjectSnapshot);
      if (!await session.newDocument(next)) return;
      const draft = await session.save(true);
      if (!draft) throw new Error('The reused project could not be saved.');
      showProjectDraft(draft.id, '/ai-influencer-studio');
      setView('Explore'); setStyleOpen(false); setMenu(null);
    } catch (reason) { setError((reason as Error).message); }
    finally { setSubmitting(false); }
  }
  async function persistStage(changes: Partial<InfluencerState>) {
    setSubmitting(true);
    setError('');
    try {
      const document = await session.updateAndSave(changes);
      if (!document) throw new Error('The selected workflow could not be saved. Resolve the save error before generating.');
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  async function generate() {
    if (!model || submitting) return;
    if (supportIssue || cleanupIssue || intervalIssue) { setError(supportIssue || cleanupIssue || intervalIssue); return; }
    setSubmitting(true);
    setError('');
    try {
      const attributes = (library.groups || [])
        .map((group) =>
          state.character[group.id]?.length
            ? `${group.title}: ${state.character[group.id].join(', ')}`
            : '',
        )
        .filter(Boolean)
        .join('. ');
      const motion =
        state.mode === 'motion'
          ? buildMotionRequest(catalog, {
              operation: state.motion_operation,
              modelId: model.id,
              provider,
              source: video,
              reference: photo,
              maskAssetId: state.mask_asset_id,
              recastCompositeTracking: state.recast_composite_tracking,
              recastReferenceCleanup: state.recast_reference_cleanup ?? false,
              styleName: state.style_name,
              stylePrompt: state.style_custom,
              styleAssetId: state.style_asset_id,
              styleModelId: state.style_preparation_model_id,
              preparedCharacterId: state.styled_asset_id,
              prompt: state.prompt,
              promptEnabled: !!state.prompt_enabled,
              enhancePrompt: state.enhance_prompt,
              duration: state.duration,
              fps: state.fps,
              seed: state.seed,
              trimStart: state.trim_start,
              longestSide: state.quality,
              conditioning: state,
            })
          : null;
      const operationId = motion?.operation || effectId;
      const operation = session.application?.operations.find((item) => item.id === operationId);
      if (!operation?.available)
        throw new Error(operation?.reason || 'This operation is not installed.');
      if (state.mode === 'create' && provider === 'comfy-cloud')
        throw new Error('Choose Local ComfyUI for this image workflow.');
      const request =
        motion?.request ||
        renderRequest(model, {
          effect_id: effectId,
          prompt: `Create a full-body character portrait for an AI influencer. A clearly visible face and complete figure, natural studio lighting, clean neutral background, detailed clothing. ${attributes}. ${state.prompt || 'Expressive, confident pose. No text or watermark.'}`,
          provider,
          ...renderSize(model, '3:4', state.quality),
          frames: 1,
          fps: 1,
          source_asset_id: state.photo_asset_id || undefined,
        });
      const document = await session.save(true);
      if (!document)
        throw new Error(
          'The project could not be saved. Resolve the save error before generating.',
        );
      // Bind the operation to the same visible editor state that was saved.
      // A user change while awaiting persistence must not enqueue a stale stage.
      if (JSON.stringify(document.state) !== JSON.stringify(state))
        throw new Error('The project changed while preparing. Review the selected workflow and generate again.');
      const job = await post<Job>(`/apps/ai-influencer/documents/${document.id}/jobs`, {
        expected_revision: document.revision,
        operation: operationId,
        request,
      });
      setSelected(job);
      setView('History');
      await session.refreshJobs();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <main
      className={`influencer-app ea-app ${state.mode === 'motion' ? 'influencer-motion-mode' : ''}`}
    >
      <aside className="influencer-settings">
        {state.mode === 'create' && (
          <header>
            <p>Create your own character with</p>
            <h1>AI INFLUENCER</h1>
          </header>
        )}
        <div className="influencer-mode" role="tablist" aria-label="Creation mode">
          <button
            role="tab"
            aria-selected={state.mode === 'create'}
            className={state.mode === 'create' ? 'active' : ''}
            disabled={submitting}
            onClick={() => void persistStage({ mode: 'create' })}
          >
            Create Influencer
          </button>
          <button
            role="tab"
            aria-selected={state.mode === 'motion'}
            className={state.mode === 'motion' ? 'active' : ''}
            disabled={submitting}
            onClick={() => void persistStage({ mode: 'motion' })}
          >
            Motion
          </button>
        </div>
        <div className="influencer-controls">
          {state.mode === 'create' && (
            <SourceSlot
              title="Upload your photo"
              optional
              asset={photo}
              onChoose={() => setPicker('photo')}
              onClear={() => update({ photo_asset_id: '', styled_asset_id: '' })}
            />
          )}
          {state.mode === 'create' ? (
            <>
              {(library.groups || []).map((group) => (
                <section
                  className={`influencer-group ${opened.includes(group.id) ? 'open' : ''}`}
                  key={group.id}
                >
                  <button
                    className="influencer-group-toggle"
                    aria-expanded={opened.includes(group.id)}
                    onClick={() =>
                      setOpened((items) =>
                        items.includes(group.id)
                          ? items.filter((item) => item !== group.id)
                          : [...items, group.id],
                      )
                    }
                  >
                    <Icon name="plus" size={13} />
                    <span>
                      {group.title}
                      <small> · {group.options.length}</small>
                    </span>
                    <Icon name="down" size={14} />
                  </button>
                  {opened.includes(group.id) && (
                    <div
                      className={`influencer-options ${group.options.some((item) => item.swatch) ? 'swatches' : ''}`}
                    >
                      {group.options.map((item) => (
                        <button
                          className={
                            state.character[group.id]?.includes(item.title) ? 'selected' : ''
                          }
                          key={item.title}
                          aria-pressed={state.character[group.id]?.includes(item.title) || false}
                          onClick={() => choose(group.id, item.title, group.multiple)}
                        >
                          {item.poster && <img src={item.poster} alt="" loading="lazy" />}
                          {item.swatch && <i style={{ background: item.swatch }} />}
                          <span>{item.title}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </section>
              ))}
              <label className="ea-field influencer-instructions">
                Additional details
                <textarea
                  value={state.prompt}
                  onChange={(event) => update({ prompt: event.target.value })}
                  placeholder="Clothes, personality, setting…"
                />
              </label>
            </>
          ) : (
            <>
              <div className="influencer-motion-tabs" role="tablist" aria-label="Motion operation">
                <button
                  role="tab"
                  aria-selected={performerMotion}
                  className={performerMotion ? 'active' : ''}
                  onClick={() => update({ motion_operation: state.motion_scene === 'source' ? 'character-replacement' : 'motion-transfer',
                    ...(state.motion_scene === 'source' ? { recast_model_id: state.recast_model_id || 'scail-2' } : {}) })}
                >
                  <Icon name="video" size={14} />
                  Motion transfer
                </button>
                <button
                  role="tab"
                  aria-selected={!performerMotion}
                  className={!performerMotion ? 'active' : ''}
                  onClick={() => update({ motion_operation: 'replace-object', motion_scene: 'reference' })}
                >
                  <Icon name="copy" size={14} />
                  Objects swap
                </button>
              </div>
              {performerMotion && (
                <label className="ea-field">
                  Scene
                  <select
                    value={sourceSceneMotion ? 'source' : 'reference'}
                    onChange={(event) => update(event.target.value === 'source'
                      ? { motion_scene: 'source', motion_operation: 'character-replacement', recast_model_id: state.recast_model_id || 'scail-2', recast_composite_tracking: state.mask_asset_id ? 'native' : state.recast_composite_tracking ?? preferredRecastSupport(catalog, provider) }
                      : { motion_scene: 'reference', motion_operation: 'motion-transfer' })}
                  >
                    <option value="reference">Animate character / reference scene</option>
                    <option value="source">Keep source scene — performer replacement</option>
                  </select>
                  <small>{sourceSceneMotion
                    ? 'Uses the selected driving-video interval, tracked performer mask and original background/audio. Review hands, held objects and mask continuity; exact preservation inside the performer is not guaranteed.'
                    : 'Transfers the performance to your character. The generated scene and held objects can change.'}</small>
                </label>
              )}
              {state.motion_operation === 'motion-transfer' && (
                <button className="influencer-style-card" onClick={() => setStyleOpen(true)}>
                  <span className="influencer-style-stack">
                    {library.styles?.slice(0, 3).map((item, index) => (
                      <ReferenceMedia key={index} item={item} />
                    ))}
                  </span>
                  <strong>Style</strong>
                  <small>{state.style_name || 'Apply'}</small>
                  <Icon name="chevron" size={14} />
                </button>
              )}
              <SourceSlot
                title={
                  state.motion_operation === 'motion-transfer'
                    ? 'Add a reference video to extract motion'
                    : 'Add a reference video to edit'
                }
                detail="Select a source interval of up to 10 seconds"
                asset={video}
                onChoose={() => setPicker('video')}
                onClear={() => update({ video_asset_id: '', mask_asset_id: '' })}
              />
              <SourceSlot
                title={
                  state.motion_operation === 'motion-transfer'
                    ? 'Add your character'
                    : 'Add your character or product'
                }
                detail={
                  state.motion_operation === 'motion-transfer'
                    ? 'One character reference image'
                    : 'One optional appearance reference'
                }
                optional={state.motion_operation === 'replace-object'}
                asset={styledPhoto || photo}
                onChoose={() => setPicker('photo')}
                onClear={() => update({ photo_asset_id: '', styled_asset_id: '' })}
              />
              <button
                className="influencer-value-card"
                onClick={(event) => setMenu({ name: 'Model', anchor: event.currentTarget })}
              >
                <span>
                  <small>Model</small>
                  {model?.name || 'Choose model'}
                </span>
                <Icon name="chevron" size={14} />
              </button>
              {state.motion_operation !== 'motion-transfer' && (
                <button className="ea-outline" disabled={!video} onClick={() => setPainting(true)}>
                  <Icon name="brush" size={16} />
                  {state.mask_asset_id ? 'Edit subject mask' : model?.mask_optional ? 'Optional performer mask override' : 'Paint the subject'}
                </button>
              )}
              {!!model?.native_mask_tracking && (
                <>
                  <small className="ea-muted">Native SAM3.1 selects one person automatically. An optional first-frame mask overrides that selection.</small>
                  {state.mask_asset_id && <button className="ea-outline" onClick={() => update({ mask_asset_id: '' })}>Use automatic performer selection</button>}
                </>
              )}
              {model?.id === 'scail-2' && <label className="ea-muted">
                <input type="checkbox" aria-label="Clean reference edges" checked={state.recast_reference_cleanup ?? false}
                  disabled={!cleanupAvailable && !state.recast_reference_cleanup}
                  onChange={event => update({ recast_reference_cleanup: event.target.checked })} /> Clean reference edges<br/>
                <small>Removes background color from the character reference edge before generation. Adds CPU matting; hands and fine details can still change.</small>
                {cleanupIssue && <small role="alert">{cleanupIssue}</small>}
              </label>}
              {model?.id === 'scail-2' && (
                <label className="ea-muted">Final composite tracking
                  <select value={state.mask_asset_id ? 'native' : state.recast_composite_tracking || 'native'}
                    disabled={!!state.mask_asset_id} onChange={e => update({ recast_composite_tracking: e.target.value as 'native' | 'official' | 'official-union' })}>
                    <option value="official-union" disabled={!unionSupportAvailable}>Source + generated performer support</option>
                    <option value="official" disabled={!officialSupportAvailable}>Official source performer support · legacy</option>
                    <option value="native">Native SAM3.1 · original / manual mask</option>
                  </select>
                  <small>Source + generated support combines both performer silhouettes for final compositing. Native SCAIL conditioning and generated detail stay unchanged; halos already present in the generated video may remain. A painted override uses native support.</small>
                  {supportIssue && <small role="alert">{supportIssue}</small>}
                  {!state.mask_asset_id && !officialSupportAvailable && !supportIssue && <small>Official support needs the isolated Linux CUDA runtime and a successful Local connection check in Settings.</small>}
                </label>
              )}
              <div className="katana-instructions-toggle">
                <span>Prompt</span>
                <button
                  role="switch"
                  aria-label="Toggle prompt"
                  aria-checked={!!state.prompt_enabled}
                  className={state.prompt_enabled ? 'on' : ''}
                  onClick={() => update({ prompt_enabled: !state.prompt_enabled })}
                >
                  <i />
                </button>
              </div>
              {state.prompt_enabled && (
                <label className="ea-field">
                  <textarea
                    aria-label="Motion instructions"
                    value={state.prompt}
                    onChange={(event) => update({ prompt: event.target.value })}
                    placeholder="Describe the performance or what to change…"
                  />
                </label>
              )}
              <button
                className="influencer-value-card"
                onClick={(event) => setMenu({ name: 'Quality', anchor: event.currentTarget })}
              >
                <span>
                  <small>Quality</small>
                  {state.quality}px longest side
                </span>
                <Icon name="chevron" size={14} />
              </button>
              {model?.supports_motion_controls ? (
                <MotionControls value={state} onChange={update} />
              ) : null}
              <div className="ea-field-pair">
                <label className="ea-field">
                  Start at
                  <input
                    type="number"
                    min="0"
                    max={video?.duration || 0}
                    step=".1"
                    value={state.trim_start}
                    onChange={(event) =>
                      update({ trim_start: Number(event.target.value), mask_asset_id: '' })
                    }
                  />
                </label>
                <label className="ea-field">
                  Duration
                  <select
                    value={state.duration}
                    onChange={(event) => update({ duration: Number(event.target.value) })}
                  >
                    {![2, 3, 5, 8, 10].includes(state.duration) && <option value={state.duration}>{state.duration}s · recorded</option>}
                    {[2, 3, 5, 8, 10].map((value) => (
                      <option value={value} key={value}>
                        {value}s
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="ea-controls-row">
                <label className="ea-field">Frames per second
                  <input type="number" min="1" max="120" step="1" disabled={!!model?.fixed_fps}
                    value={Number(model?.fixed_fps || state.fps || model?.default_fps || 16)}
                    onChange={event => update({ fps: Number(event.target.value), mask_asset_id: '' })} />
                </label>
                <label className="ea-field">Seed · -1 for random
                  <input type="number" min="-1" max="4294967295" step="1" value={state.seed ?? -1}
                    onChange={event => update({ seed: Number(event.target.value) })} />
                </label>
              </div>
              {model && video?.duration !== undefined && <button type="button" className="ea-outline" onClick={() => update({ duration: Math.max(0, Math.min(video.duration! - state.trim_start, Number(model.max_frames || 241) / Number(model.fixed_fps ?? state.fps ?? model.default_fps ?? 16))) })}>Fit source / model limit</button>}
              <small className="ea-muted">
                {frames > 0 && model
                  ? `Selected from ${state.trim_start.toFixed(2)}s · ${frames} frames / ${(frames / Number(model.fixed_fps || state.fps || model.default_fps || 16)).toFixed(2)}s actual. Source: ${video?.duration?.toFixed(2) ?? 'unknown'}s. Rounded down to supported frames.`
                  : 'Select a valid source range'}
              </small>
            </>
          )}

          {(intervalIssue || error || session.error || assets.error) && (
            <p className="ea-error" role="alert">
              {intervalIssue || error || session.error || assets.error}
            </p>
          )}
        </div>
        <footer className="influencer-generate">
          <div>
            <button onClick={onSettings}>
              <Icon name="cloud" size={13} />
              {provider === 'local'
                  ? 'Local ComfyUI'
                  : 'Choose compute'}
            </button>
            <small>{model?.name || 'Loading model…'}</small>
          </div>
          <div>
            {state.mode === 'create' && (
              <button
                className="influencer-random"
                aria-label="Randomize character"
                disabled={!library.groups?.length}
                onClick={randomize}
              >
                <Icon name="refresh" size={21} />
              </button>
            )}
            <button
              className="influencer-submit"
              disabled={!session.ready || submitting || !model || !!intervalIssue || !!cleanupIssue}
              onClick={() => void generate()}
            >
              {submitting ? 'Preparing…' : prepareStyle ? 'Prepare styled character' : 'Generate'}
              <Icon name="spark" size={18} />
            </button>
          </div>
        </footer>
      </aside>
      <section className="influencer-workspace">
        <nav className="ea-workspace-tabs">
          {(['Explore', 'History'] as const).map((item) => (
            <button
              key={item}
              className={view === item ? 'active' : ''}
              onClick={() => setView(item)}
            >
              <Icon name={item === 'Explore' ? 'grid' : 'clock'} size={15} />
              {item}
            </button>
          ))}
          <span>{session.saving ? 'Saving…' : session.document ? 'Saved' : ''}</span>
          <button onClick={() => void session.newDocument()}>New character</button>
        </nav>
        {view === 'Explore' ? (
          <>
            <div className="influencer-hero">
              <div className="influencer-hero-cards">
                {library.hero?.slice(0, 5).map((item, index) => (
                  <button
                    key={item.id || index}
                    className={`card-${index}`}
                    onClick={() => setPreview(item)}
                    aria-label={`Preview ${item.title}`}
                  >
                    <ReferenceMedia item={item} />
                  </button>
                ))}
              </div>
              <h2>
                YOUR INFLUENCER,
                <br />
                YOUR VIRAL HIT
              </h2>
              <p>
                Build your AI influencer with the face, body, and style you want. Choose a motion
                reference and watch them perform it in a video ready to share.
              </p>
            </div>
            <div className="influencer-gallery-tabs" role="tablist" aria-label="Preset source">
              {(
                [
                  ['characters', 'AI Influencers'],
                  ['motion', 'Higgsfield Presets'],
                  ['trends', 'Community Trends'],
                ] as const
              ).map(([key, label]) => (
                <button
                  role="tab"
                  aria-selected={source === key}
                  className={source === key ? 'active' : ''}
                  key={key}
                  onClick={() => setSource(key)}
                >
                  <Icon name={key === 'characters' ? 'image' : 'video'} size={16} />
                  {label}
                </button>
              ))}
            </div>
            <div className="influencer-gallery">
              {galleries.map((item, index) => (
                <article key={item.id || index}>
                  <button
                    className="influencer-card-preview"
                    onClick={() => setPreview(item)}
                    aria-label={`View ${item.title}`}
                  >
                    <ReferenceMedia item={item} />
                  </button>
                  <button
                    className="influencer-recreate"
                    disabled={submitting}
                    onClick={() => void useExample(item)}
                  >
                    <Icon name="refresh" size={13} />
                    Recreate
                  </button>
                </article>
              ))}
            </div>
            <p className="ea-reference-credit">
              Public Higgsfield reference examples. Your generated characters are in History.
            </p>
          </>
        ) : (
          <WorkspaceHistory
            jobs={session.jobs}
            total={session.jobTotal}
            onSelect={setSelected}
            onMore={session.loadMoreJobs}
          />
        )}
      </section>
      {picker && (
        <AssetPicker
          variant="influencer"
          jobs={session.jobs}
          title={
            picker === 'photo'
              ? 'Choose your character image'
              : picker === 'style'
                ? 'Choose your style image'
                : 'Choose a motion video'
          }
          kind={picker === 'video' ? 'video' : 'image'}
          assets={assets.assets}
          onAdded={assets.add}
          onClose={() => setPicker(null)}
          onSelect={(asset) =>
            void persistStage(
              picker === 'style'
                ? { style_asset_id: asset.id, styled_asset_id: '', style_name: 'Custom' }
                : picker === 'photo'
                  ? { photo_asset_id: asset.id, styled_asset_id: '' }
                  : { video_asset_id: asset.id, mode: 'motion', mask_asset_id: '', trim_start: 0 },
            )
          }
        />
      )}
      {painting && video && (
        <MaskEditor
          asset={video}
          existingMask={assets.get(state.mask_asset_id)}
          startTime={state.trim_start}
          onClose={() => setPainting(false)}
          onSave={(mask) => {
            assets.add(mask);
            update({ mask_asset_id: mask.id, recast_composite_tracking: 'native' });
            setPainting(false);
          }}
        />
      )}
      {selected && (
        <ResultDialog
          job={session.jobs.find((item) => item.id === selected.id) || selected}
          onClose={() => setSelected(null)}
          onRefresh={() => void session.refreshJobs()}
          onReuse={() => void reuseProject(selected)}
          reuseLabel="Reuse project"
          reuseDescription={projectReuseDescription}
          useLabel={
            selectedStylePreparation
              ? 'Use styled character'
              : 'Use as character'
          }
          useKind="image"
          onUse={(asset: Asset) => {
            assets.add(asset);
            void persistStage(
              selectedStylePreparation
                ? { styled_asset_id: asset.id, mode: 'motion' }
                : { photo_asset_id: asset.id, styled_asset_id: '', mode: 'motion' },
            );
            setView('Explore');
          }}
        />
      )}
      {preview && (
        <ReferenceDialog
          item={preview}
          onClose={() => setPreview(null)}
          busy={submitting}
          onUse={() => void useExample(preview)}
        />
      )}
      {menu && (
        <AnchoredPopover
          anchor={menu.anchor}
          onClose={() => setMenu(null)}
          width={menu.name === 'Model' ? 300 : 220}
          label={menu.name}
          className="ea-model-menu"
        >
          <h3>{menu.name}</h3>
          {menu.name === 'Quality'
            ? [512, 768, 1024].map((value) => (
                <button
                  key={value}
                  onClick={() => {
                    update({ quality: value });
                    setMenu(null);
                  }}
                >
                  <span>{value}px longest side</span>
                  {state.quality === value && <Icon name="check" size={14} />}
                </button>
              ))
            : catalog.models
                .filter((item) =>
                  state.motion_operation === 'motion-transfer'
                    ? catalog.effects
                        .find((effect) => effect.id === 'motion-transfer')
                        ?.model_ids.includes(item.id)
                    : sourceSceneMotion
                      ? catalog.effects.find((effect) => effect.id === 'character-replacement')?.model_ids.includes(item.id)
                    : catalog.effects.some(
                        (effect) =>
                          ['replace-object', 'character-replacement'].includes(effect.id) &&
                          effect.model_ids.includes(item.id),
                      ),
                )
                .map((item) => (
                  <button
                    key={item.id}
                    disabled={!!photo && !supportsAppearance(item)}
                    title={
                      photo && !supportsAppearance(item)
                        ? 'Remove the reference image to use this text-conditioned model'
                        : item.description
                    }
                    onClick={() => {
                      update(
                        state.motion_operation === 'motion-transfer'
                          ? { motion_operation: 'motion-transfer', motion_model_id: item.id }
                          : item.tasks.includes('character-replacement')
                            ? { motion_operation: 'character-replacement', recast_model_id: item.id }
                            : {
                                motion_operation: 'replace-object',
                                swap_model_id: item.id,
                                prompt_enabled: true,
                              },
                      );
                      setMenu(null);
                    }}
                  >
                    <span>
                      {item.name}
                      <small>
                        {item.supports_motion_controls
                          ? 'Native driving-video and appearance conditioning'
                          : item.id === 'wan-animate'
                            ? 'Human pose and face motion'
                            : supportsAppearance(item)
                              ? 'Masked reference-guided editing'
                              : 'Masked text-guided editing'}
                      </small>
                    </span>
                    {model?.id === item.id && <Icon name="check" size={14} />}
                  </button>
                ))}
        </AnchoredPopover>
      )}
      <dialog
        ref={styleDialog}
        className="ea-dialog influencer-style-dialog"
        onCancel={() => setStyleOpen(false)}
        onClick={(event) => {
          if (event.target === event.currentTarget) setStyleOpen(false);
        }}
      >
        <header>
          <h2>Style</h2>
          <button aria-label="Close style" onClick={() => setStyleOpen(false)}>
            <Icon name="close" />
          </button>
        </header>
        <nav>
          {(['Higgsfield', 'Custom'] as const).map((value) => (
            <button
              key={value}
              className={styleTab === value ? 'active' : ''}
              onClick={() => setStyleTab(value)}
            >
              {value}
            </button>
          ))}
        </nav>
        {styleTab === 'Higgsfield' ? (
          <div className="influencer-style-grid">
            {library.styles?.map((item) => (
              <button
                key={item.title}
                className={state.style_name === item.title ? 'selected' : ''}
                onClick={() => {
                  update({
                    style_name: state.style_name === item.title ? '' : item.title,
                    styled_asset_id: '',
                  });
                  setStyleOpen(false);
                }}
              >
                <ReferenceMedia item={item} />
                <strong>{item.title.toUpperCase()}</strong>
              </button>
            ))}
          </div>
        ) : (
          <div className="influencer-custom-style">
            <SourceSlot
              title="Upload your style"
              detail="Use an image to guide the character’s visual style"
              asset={stylePhoto}
              onChoose={() => {
                setStyleOpen(false);
                setPicker('style');
              }}
              onClear={() => update({ style_asset_id: '', styled_asset_id: '' })}
            />
            <p className="ea-muted">
              Prepare a styled character image first, review it, then animate that result.
            </p>
            <label className="ea-field">
              Additional style direction
              <textarea
                value={state.style_custom || ''}
                onChange={(event) =>
                  update({ style_custom: event.target.value, styled_asset_id: '' })
                }
                placeholder="Materials, color palette, rendering style…"
              />
            </label>
            <button
              className="ea-lime"
              onClick={() => {
                update({
                  style_name: state.style_asset_id || state.style_custom?.trim() ? 'Custom' : '',
                  styled_asset_id: '',
                });
                setStyleOpen(false);
              }}
            >
              Apply style
            </button>
          </div>
        )}
        <p className="ea-reference-credit">
          Preset styles add prompt direction. A custom style image creates a reviewed character
          image before motion transfer.
        </p>
      </dialog>
    </main>
  );
}
