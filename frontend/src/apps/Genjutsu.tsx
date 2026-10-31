import { useState } from 'react';
import { api, mediaUrl, post } from '../api';
import { Icon } from '../Icon';
import { MaskEditor } from '../MaskEditor';
import { RestyleFirstFrame } from './RestyleFirstFrame';
import { AnchoredPopover } from '../Popovers';
import { Toggle } from '../ui';
import type { Asset, Job, JobRequest } from '../types';
import { useAppDocument } from './useAppDocument';
import { buildMotionRequest } from './motionRequest';
import { MotionControls, motionDefaults } from './MotionControls';
import type { MotionConditioning } from './MotionControls';
import { modelProviderIssue, modelSupportsReference, providerReadinessIssue, renderRequest, renderSize, resolveProvider } from './renderRequest';
import {
  AssetPicker,
  SourceSlot,
  ReferenceDialog,
  ReferenceMedia,
  ResultDialog,
  WorkspaceHistory,
  boundedVideoFrames,
  videoIntervalIssue,
  importReference,
  useReferenceLibrary,
  useWorkspaceAssets,
} from './engine-apps-shared';
import type { EngineAppProps, ReferenceItem } from './engine-apps-shared';
import './engine-apps.css';
import './genjutsu.css';

type GenjutsuState = Record<string, unknown> &
  MotionConditioning & {
    prompt: string;
    prompt_enabled: boolean;
    enhance_prompt?: boolean;
    export_uncomposited?: boolean;
    mode: 'motion' | 'swap';
    source_asset_id: string;
    reference_asset_id: string;
    mask_asset_id: string;
    style_name: string;
    style_prompt: string;
    style_asset_id: string;
    prepared_asset_id: string;
    motion_model_id: string;
    swap_model_id: string;
    style_model_id: string;
    restyle_first_frame_asset_id?: string;
    restyle_first_frame_source_id?: string;
    restyle_first_frame_trim_start?: number;
    restyle_preparation_id?: string;
    restyle_method?: 'latent' | 'canny' | 'water';
    style_preparation_model_id?: string;
    duration: number;
    fps?: number | null;
    vace_reference_mode?: 'appearance' | 'first-frame';
    inpaint_reference_mode?: 'edited-first-frame' | null;
    inpaint_composite_mode?: 'legacy' | 'plate-fit';
    trim_start: number;
    quality: number;
    provider: string;
    strength: number;
    seed: number;
    mask_tracking_method: 'sam2' | 'flow' | 'static';
    mask_edit_margin: number;
    liked_references: string[];
  };
const initial: GenjutsuState = {
  style_preparation_model_id: 'flux3-klein',
  ...motionDefaults,
  prompt: '',
  prompt_enabled: false,
  enhance_prompt: false,
  mode: 'motion',
  source_asset_id: '',
  reference_asset_id: '',
  mask_asset_id: '',
  style_name: '',
  style_prompt: '',
  style_asset_id: '',
  prepared_asset_id: '',
  motion_model_id: 'wan-animate',
  swap_model_id: 'wan-vace',
  style_model_id: 'ltx-2.5',
  restyle_method: 'canny',
  duration: 4,
  fps: null,
  vace_reference_mode: 'appearance',
  inpaint_reference_mode: null,
  trim_start: 0,
  quality: 768,
  provider: '',
  strength: 0.4,
  seed: -1,
  mask_tracking_method: 'sam2',
  mask_edit_margin: 12,
  liked_references: [],
};
const assetIds = (state: GenjutsuState) =>
  [
    state.source_asset_id,
    state.reference_asset_id,
    state.mask_asset_id,
    state.style_asset_id,
    state.prepared_asset_id,
    state.restyle_first_frame_asset_id || '',
  ].filter(Boolean);

export function Genjutsu({ catalog, settings, onSettings }: EngineAppProps) {
  const session = useAppDocument('genjutsu', initial, assetIds),
    { state, update } = session;
  const workspace = useWorkspaceAssets(assetIds(state)),
    library = useReferenceLibrary('genjutsu');
  const [view, setView] = useState('Motion Library'),
    [styleTab, setStyleTab] = useState('Presets'),
    [libraryTab, setLibraryTab] = useState('Trending');
  const [picker, setPicker] = useState<'source' | 'reference' | 'style' | 'first-frame' | null>(null),
    [painting, setPainting] = useState(false),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState<{ name: string; anchor: HTMLElement } | null>(null),
    [search, setSearch] = useState('');
  const [preview, setPreview] = useState<ReferenceItem | null>(null),
    [selectedJobId, setSelectedJobId] = useState<string | null>(null),
    [mobileComposer, setMobileComposer] = useState(false);
  const source = workspace.get(state.source_asset_id),
    appearance = workspace.get(state.reference_asset_id),
    prepared = workspace.get(state.prepared_asset_id),
    mask = workspace.get(state.mask_asset_id),
    styleImage = workspace.get(state.style_asset_id);
  const restyling = state.mode === 'motion' && !!state.style_name && !appearance;
  const modelId = restyling
    ? state.style_model_id
    : state.mode === 'motion'
      ? state.motion_model_id
      : state.swap_model_id;
  const operation = restyling
    ? 'restyle'
    : state.mode === 'motion'
      ? 'motion-transfer'
      : modelId === 'wan-animate'
        ? 'character-replacement'
        : 'replace-object';
  const effect = catalog.effects.find((item) => item.id === operation),
    models = catalog.models.filter((item) => effect?.model_ids.includes(item.id) && (!item.app_ids || item.app_ids.includes('genjutsu')));
  const model = models.find((item) => item.id === modelId) || (!modelId ? models[0] : undefined);
  const restyleMethod = state.restyle_method || 'latent';
  const cannyRestyle = restyling && restyleMethod === 'canny' && !!model?.restyle_methods?.some((item) => item.id === 'canny');
  const firstFrame = workspace.get(state.restyle_first_frame_asset_id || '');
  const firstFrameSupported = cannyRestyle && !!model?.restyle_first_frame_effects?.includes(operation);
  const clearFirstFrame = { restyle_first_frame_asset_id: '', restyle_first_frame_source_id: '', restyle_first_frame_trim_start: 0, restyle_preparation_id: '' };
  const validRestyleMethods = model?.restyle_methods?.filter((item) => !item.effect_ids || item.effect_ids.includes(operation)) || [];
  const methodIssue = restyling && !!model?.restyle_methods && !validRestyleMethods.some((item) => item.id === restyleMethod) ? 'The saved structure method is unavailable for this operation. Choose Canny or latent editing.' : '';
  const firstFrameIssue = restyling && state.restyle_first_frame_asset_id && !firstFrame ? 'Wait for the selected starting frame to load, or clear it.' : restyling && firstFrame ? !firstFrameSupported ? 'The edited full starting frame requires the Canny method. Clear it or select that method.'
    : styleImage ? 'Clear the separate style image before using an edited full starting frame.'
    : firstFrame.width !== source?.width || firstFrame.height !== source?.height ? 'The edited starting frame must match the source video’s native dimensions.'
    : state.restyle_first_frame_source_id !== source?.id || state.restyle_first_frame_trim_start !== state.trim_start ? 'Choose the edited frame again for the current source and start time.' : '' : '';
  const rippleFirstFrame = model?.reference_image_role === 'edited-first-frame';
  const vaceFirstFrame = !!model?.reference_modes && state.vace_reference_mode === 'first-frame';
  const supportsInpaintReference = operation === 'replace-object' && !!model?.inpaint_reference_modes?.includes('edited-first-frame');
  const inpaintFirstFrame = supportsInpaintReference && state.inpaint_reference_mode === 'edited-first-frame';
  const editedFirstFrame = rippleFirstFrame || vaceFirstFrame || inpaintFirstFrame;
  const previewReference = state.mode === 'motion' ? prepared || appearance : appearance;
  const compositeModes = !restyling ? model?.inpaint_composite_modes?.filter((item) => !item.effect_ids || item.effect_ids.includes(operation)) || [] : [];
  const strengthControl = (
    model?.strength_controls as Record<string, { label: string; hint?: string }> | undefined
  )?.[effect?.task || ''];
  const provider = resolveProvider(state.provider, settings.default_provider);
  const providerIssue = providerReadinessIssue(catalog.providers.find((item) => item.id === provider)) || modelProviderIssue(model, provider, effect?.task);
  const fps = Number(model?.fixed_fps ?? state.fps ?? model?.default_fps ?? 16);
  const fpsValid = Number.isFinite(fps) && fps >= 1 && fps <= 120;
  const frames =
    model && fpsValid
      ? boundedVideoFrames(model, state.duration, source, state.trim_start, fps)
      : 0;
  const actualDuration = frames / fps;
  const intervalIssue = model ? videoIntervalIssue(model, state.duration, source, state.trim_start, fps) : '';
  const selectedJob = session.jobs.find((job) => job.id === selectedJobId);
  const selectedStyle = library.styles?.find((item) => item.title === state.style_name);
  const stylesView = view === 'Styles';
  const hero =
    (stylesView
      ? (library as typeof library & { style_hero?: ReferenceItem[] }).style_hero?.[0]
      : undefined) ||
    library.hero?.find((item) => item.category === (stylesView ? 'styles' : 'motion')) ||
    library.hero?.[stylesView ? 1 : 0];
  const references = library.trends || library.motion || library.presets || [];
  const shownReferences =
    libraryTab === 'Saved'
      ? references.filter((item) =>
          state.liked_references.includes(item.id || item.source_url || item.title),
        )
      : libraryTab === 'New'
        ? [...references].reverse()
        : references;
  const styleDescription = state.style_name === 'Custom' ? state.style_prompt : state.style_name;

  function chooseAsset(asset: Asset) {
    workspace.add(asset);
    if (picker === 'source')
      update({
        source_asset_id: asset.id,
        ...clearFirstFrame,
        ...(editedFirstFrame ? { reference_asset_id: '' } : {}),
        trim_start: 0,
        mask_asset_id: '',
        duration: Math.min(4, asset.duration || 4),
      });
    else if (picker === 'first-frame')
      update({ restyle_first_frame_asset_id: asset.id, restyle_first_frame_source_id: source?.id || '', restyle_first_frame_trim_start: state.trim_start });
    else if (picker === 'reference')
      update({ reference_asset_id: asset.id, prepared_asset_id: '', ...clearFirstFrame });
    else if (picker === 'style')
      update({
        style_asset_id: asset.id,
        style_name: 'Custom',
        prepared_asset_id: '',
        style_model_id: 'wan-vace',
        restyle_method: 'latent',
      });
    setPicker(null);
  }
  function openMenu(name: string, anchor: HTMLElement) {
    setSearch('');
    setMenu({ name, anchor });
  }
  function chooseModel(id: string) {
    update(
      restyling
        ? { style_model_id: id, restyle_method: catalog.models.find((item) => item.id === id)?.restyle_methods?.some((item) => item.id === 'canny') ? 'canny' : 'latent' }
        : state.mode === 'motion'
          ? { motion_model_id: id }
          : {
              swap_model_id: id,
              ...(id !== modelId ? { inpaint_composite_mode: undefined } : {}),
              ...(id !== modelId ? { inpaint_reference_mode: null,
                ...(supportsInpaintReference || catalog.models.find((item) => item.id === id)?.inpaint_reference_modes?.length
                  ? { reference_asset_id: '', prepared_asset_id: '' } : {}) } : {}),
              ...(id === 'ltx-ripple' ? { enhance_prompt: false } : {}),
              ...(typeof catalog.models.find((item) => item.id === id)?.default_strength ===
              'number'
                ? {
                    strength: Number(
                      catalog.models.find((item) => item.id === id)!.default_strength,
                    ),
                  }
                : {}),
              export_uncomposited:
                catalog.models.find((item) => item.id === id)?.supports_uncomposited === true,
            },
    );
    setMenu(null);
  }
  async function generate() {
    if (!model || busy) return;
    setBusy(true);
    setError('');
    try {
      if (providerIssue) throw new Error(providerIssue);
      if (!fpsValid) throw new Error('Choose a frame rate between 1 and 120 fps.');
      if (intervalIssue) throw new Error(intervalIssue);
      const seed = state.seed ?? -1;
      if (!Number.isSafeInteger(seed) || seed < -1)
        throw new Error(
          'Seed must be -1 for random, or a whole number from 0 to 9,007,199,254,740,991.',
        );
      if (!source) throw new Error('Add a source video.');
      if (methodIssue || firstFrameIssue) throw new Error(methodIssue || firstFrameIssue);
      if (operation === 'replace-object' && state.inpaint_composite_mode === 'plate-fit' && !compositeModes.some((item) => item.id === 'plate-fit'))
        throw new Error('The saved plate-lighting finish is unavailable for this model. Choose a compatible replacement profile or the original composite.');
      if (state.duration > (source.duration || 0) - state.trim_start + 0.001)
        throw new Error(
          'The selected duration extends past the source. Reduce its duration or start time.',
        );
      if (state.duration > Number(model.max_frames) / fps + 0.001)
        throw new Error('Reduce the duration to fit this model.');
      let request: JobRequest,
        jobOperation: string,
        preparingStyle = false;
      if (restyling) {
        if (styleImage && !modelSupportsReference(model, 'restyle'))
          throw new Error('Choose Wan VACE to condition the video on a custom style image.');
        if (frames < 9) throw new Error('Choose a longer source interval.');
        jobOperation = 'restyle';
        request = renderRequest(model, {
          effect_id: 'restyle',
          enhance_prompt: state.enhance_prompt,
          provider,
          prompt: [
            state.prompt_enabled ? state.prompt : '',
            `Restyle the source video in ${styleDescription || 'the visual style of the reference image'}. Preserve the scene composition, subject action, camera motion and temporal continuity.`,
          ]
            .filter(Boolean)
            .join('\n'),
          ...renderSize(model, `${source.width || 9}:${source.height || 16}`, state.quality),
          frames,
          fps,
          source_asset_id: source.id,
          reference_asset_id: firstFrame?.id || styleImage?.id,
          trim_start: state.trim_start,
          strength: cannyRestyle ? 1 : state.strength,
          restyle_method: model.restyle_methods ? restyleMethod : 'latent',
        });
      } else {
        const built = buildMotionRequest(catalog, {
          operation:
            state.mode === 'motion'
              ? 'motion-transfer'
              : model.id === 'wan-animate'
                ? 'character-replacement'
                : 'replace-object',
          modelId: model.id,
          provider,
          source,
          reference: appearance,
          maskAssetId: mask?.id,
          styleName: state.style_name,
          stylePrompt: state.style_prompt,
          styleAssetId: styleImage?.id,
          styleModelId: state.style_preparation_model_id,
          preparedCharacterId: prepared?.id,
          prompt: state.prompt,
          promptEnabled: state.prompt_enabled,
          enhancePrompt: state.enhance_prompt,
          duration: state.duration,
          fps,
          trimStart: state.trim_start,
          vaceReferenceMode: model.reference_modes ? state.vace_reference_mode || 'appearance' : undefined,
          inpaintReferenceMode: supportsInpaintReference ? state.inpaint_reference_mode : undefined,
          longestSide: state.quality,
          conditioning: state,
        });
        request = built.request;
        jobOperation = built.operation;
        preparingStyle = built.preparingStyle;
        if (!preparingStyle) {
          request.mask_tracking_method = state.mask_tracking_method;
          request.mask_tracking = state.mask_tracking_method !== 'static';
          request.mask_edit_margin = state.mask_edit_margin;
          request.strength = rippleFirstFrame ? 1 : state.strength;
          if (rippleFirstFrame) {
            request.mask_dilation = 0;
            request.video_refinement = 'single';
          }
          if (model.supports_uncomposited)
            request.export_uncomposited = !!state.export_uncomposited;
          if (compositeModes.length)
            request.inpaint_composite_mode = state.inpaint_composite_mode || 'legacy';
          if (typeof model.default_negative_prompt === 'string')
            request.negative_prompt = model.default_negative_prompt;
        }
      }
      request.seed = seed;
      const available = session.application?.operations.find((item) => item.id === jobOperation);
      if (!available?.available)
        throw new Error(available?.reason || 'This workflow is unavailable.');
      const doc = await session.save(true);
      if (!doc) throw new Error('Save this project before generating.');
      const job = await post<Job>(`/apps/genjutsu/documents/${doc.id}/jobs`, {
        expected_revision: doc.revision,
        operation: jobOperation,
        request,
        step_id: preparingStyle ? 'prepare-style' : 'generate-video',
      });
      await session.refreshJobs();
      setSelectedJobId(job.id);
      setView('History');
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function useReference() {
    if (!preview) return;
    setBusy(true);
    setError('');
    try {
      const asset = await importReference(preview, 'video');
      workspace.add(asset);
      update({
        source_asset_id: asset.id,
        ...clearFirstFrame,
        ...(editedFirstFrame ? { reference_asset_id: '' } : {}),
        trim_start: 0,
        mask_asset_id: '',
        duration: Math.min(4, asset.duration || 4),
      });
      setPreview(null);
      setMobileComposer(true);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reuse(job: Job) {
    try {
      const result = await api<{ document_snapshot: { state: GenjutsuState } }>(
        `/jobs/${job.id}/app-context`,
      );
      if (
        await session.newDocument({
          ...result.document_snapshot.state,
          enhance_prompt: job.request.enhance_prompt,
          restyle_method: job.request.restyle_method || 'latent',
          ...(job.request.model_id === 'ltx-2.5' && job.request.effect_id === 'restyle' && job.request.restyle_method === 'canny' ? { restyle_first_frame_asset_id: job.request.reference_asset_id || '', restyle_first_frame_source_id: job.request.source_asset_id, restyle_first_frame_trim_start: job.request.trim_start, style_asset_id: '' } : {}),
          seed: job.request.seed,
          fps: job.request.fps,
          vace_reference_mode: job.request.vace_reference_mode || 'appearance',
          inpaint_reference_mode: job.request.inpaint_reference_mode || null,
          inpaint_composite_mode: job.request.inpaint_composite_mode || 'legacy',
        })
      ) {
        setSelectedJobId(null);
        setView('Motion Library');
      }
    } catch (reason) {
      setError((reason as Error).message);
    }
  }
  const canGenerate =
    fpsValid &&
    !providerIssue &&
    !methodIssue &&
    !firstFrameIssue &&
    !intervalIssue &&
    !!source &&
    !!model &&
    (!(model.requires_reference || vaceFirstFrame || inpaintFirstFrame) || !!appearance) &&
    (!(supportsInpaintReference && appearance) || inpaintFirstFrame) &&
    (!(model.reference_must_match_source_dimensions || vaceFirstFrame || inpaintFirstFrame) ||
      (!!appearance && appearance.width === source.width && appearance.height === source.height)) &&
    (restyling || state.mode === 'motion'
      ? restyling || !!appearance
      : !!mask && (!!appearance || (state.prompt_enabled && !!state.prompt.trim())));
  return (
    <div className="gen-app">
      <aside
        className={`gen-composer ${mobileComposer ? 'mobile-open' : ''}`}
        aria-label="Motion and style composer"
      >
        <nav className="gen-mode-nav">
          <button className="active" onClick={() => update({ mode: 'motion' })}>
            Create Video
          </button>
          <a href="/studio/vfx?panel=tools">Edit Video</a>
          <button
            onClick={() => {
              update({ mode: 'motion' });
              setView('Motion Library');
            }}
          >
            Motion Control
          </button>
          <button
            className="gen-close-mobile"
            aria-label="Close composer"
            onClick={() => setMobileComposer(false)}
          >
            <Icon name="close" size={14} />
          </button>
        </nav>
        <div className="gen-composer-scroll">
          <button
            className="gen-model-banner"
            onClick={(event) => openMenu('model', event.currentTarget)}
          >
            <ReferenceMedia item={library.banner?.[0]} />
            <span className="gen-change">
              <Icon name="brush" size={12} />
              Change
            </span>
            <span>
              <strong>OPENFRAME GENJUTSU</strong>
              <small>Motion and style editing</small>
            </span>
          </button>
          <div className="gen-operation" role="tablist" aria-label="Editing operation">
            {(['motion', 'swap'] as const).map((value) => (
              <button
                key={value}
                role="tab"
                aria-selected={state.mode === value}
                className={state.mode === value ? 'active' : ''}
                onClick={() => {
                  update({ mode: value });
                  if (value === 'swap' && view === 'Styles') setView('Motion Library');
                }}
              >
                <Icon name={value === 'motion' ? 'refresh' : 'grid'} size={14} />
                {value === 'motion' ? 'Motion transfer' : 'Objects swap'}
              </button>
            ))}
          </div>
          {state.mode === 'motion' && (
            <div className="gen-style-row">
              <button onClick={() => setView('Styles')}>
                <span className="gen-style-mini">
                  {styleImage ? (
                    <img src={mediaUrl(styleImage)} alt="Custom style" />
                  ) : (
                    <ReferenceMedia item={selectedStyle || library.styles?.[0]} />
                  )}
                </span>
                <strong>{state.style_name || 'Style'}</strong>
                {!state.style_name && <em>New</em>}
                <span className="gen-row-end">
                  {state.style_name ? 'Change' : 'Apply'}
                  <Icon name="chevron" size={12} />
                </span>
              </button>
              {state.style_name && (
                <button
                  className="gen-clear-style"
                  aria-label="Clear style"
                  onClick={() =>
                    update({
                      style_name: '',
                      style_prompt: '',
                      style_asset_id: '',
                      prepared_asset_id: '',
                    })
                  }
                >
                  <Icon name="close" size={12} />
                </button>
              )}
            </div>
          )}
          <div className="gen-source-wrap">
            <button
              className={`gen-upload ${source ? 'has-media' : ''}`}
              onClick={() => setPicker('source')}
            >
              {source ? (
                <>
                  <video
                    src={mediaUrl(source)}
                    poster={source.thumbnail_url || undefined}
                    muted
                    preload="metadata"
                  />
                  <span className="gen-upload-caption">
                    {source.name}
                    <small>Change source video</small>
                  </span>
                </>
              ) : (
                <>
                  <i>
                    <Icon name="video" size={15} />
                  </i>
                  <strong>
                    Add a reference video
                    <br />
                    {state.mode === 'swap' ? 'to edit' : 'to extract motion'}
                  </strong>
                  <small>Choose a clip and select its time range</small>
                </>
              )}
            </button>
            {source && (
              <button
                className="gen-clear"
                aria-label="Remove source video"
                onClick={() => update({ source_asset_id: '', mask_asset_id: '', ...clearFirstFrame })}
              >
                <Icon name="close" size={12} />
              </button>
            )}
          </div>
          {restyling && (firstFrameSupported || !!firstFrame) && <section className="gen-reference-note">
            <SourceSlot title="Edited full starting frame" optional detail="A complete aligned frame, separate from style and character references" asset={firstFrame} onChoose={() => setPicker('first-frame')} onClear={() => update({...clearFirstFrame})}/>
            {source && firstFrameSupported && <RestyleFirstFrame source={source} trimStart={state.trim_start} prompt={[state.prompt_enabled ? state.prompt : '', styleDescription].filter(Boolean).join('. ')} appId="genjutsu" projectId={state.restyle_preparation_id} saveParent={() => session.save(true)} onPrepared={async id => { await session.updateAndSave({restyle_preparation_id:id}); }}/>}
            {firstFrameIssue && <p className="ea-error">{firstFrameIssue}</p>}
          </section>}
          {methodIssue && <p className="ea-error">{methodIssue}</p>}
          {supportsInpaintReference && (
            <label className="gen-reference-note">
              Replacement guide
              <select value={state.inpaint_reference_mode || ''}
                onChange={(event) => update({ inpaint_reference_mode: event.target.value === 'edited-first-frame' ? 'edited-first-frame' : null, reference_asset_id: '', prepared_asset_id: '' })}>
                <option value="">Text only · no image guide</option>
                <option value="edited-first-frame">Edited full first frame</option>
              </select>
              <small>Use a complete edited frame from the selected start, not an isolated object image.</small>
            </label>
          )}
          <div className="gen-source-wrap">
            <button
              className={`gen-upload ${appearance ? 'has-media' : ''}`}
              disabled={supportsInpaintReference && !inpaintFirstFrame}
              onClick={() => setPicker('reference')}
            >
              {appearance ? (
                <>
                  <img
                    src={mediaUrl(previewReference || appearance)}
                    alt={
                      editedFirstFrame
                        ? 'Edited starting frame'
                        : state.mode === 'motion' && prepared
                          ? 'Reviewed styled character'
                          : 'Appearance reference'
                    }
                  />
                  <span className="gen-upload-caption">
                    {state.mode === 'motion' && prepared ? 'Styled character ready' : appearance.name}
                    <small>
                      {editedFirstFrame
                        ? 'Change edited starting frame'
                        : 'Change appearance reference'}
                    </small>
                  </span>
                </>
              ) : (
                <>
                  <span className="gen-upload-icons">
                    {['user', 'image', 'square'].map((name) => (
                      <i key={name}>
                        <Icon name={name} size={15} />
                      </i>
                    ))}
                  </span>
                  <strong>
                    {editedFirstFrame ? 'Add the edited first frame' : supportsInpaintReference ? 'Text-only replacement' : 'Add your character'}
                    <br />
                    {editedFirstFrame ? 'of this selected interval' : supportsInpaintReference ? 'Image guide is off' : 'or appearance reference'}
                  </strong>
                  <small>
                    {editedFirstFrame
                      ? `${source?.width || 'Original'} × ${source?.height || 'canvas'} · required`
                      : supportsInpaintReference ? 'Choose Edited full first frame above to add one' : 'One image · optional for video restyling'}
                  </small>
                </>
              )}
            </button>
            {appearance && (
              <button
                className="gen-clear"
                aria-label="Remove appearance reference"
                onClick={() => update({ reference_asset_id: '', prepared_asset_id: '' })}
              >
                <Icon name="close" size={12} />
              </button>
            )}
          </div>
          {editedFirstFrame && (
            <p className="gen-reference-note">
              Supply the complete edited frame at {state.trim_start.toFixed(2)}s, with the same
              canvas size as the source. {vaceFirstFrame
                ? 'VACE uses it as the known first control frame, then follows the original masked footage. The painted mask still controls the final composite.'
                : inpaintFirstFrame
                  ? 'Native LTX inpainting uses it as a starting-frame guide in both sampling stages. The painted mask controls the final composite; exact object fidelity is not guaranteed.'
                  : 'Ripple carries this visible edit through the clip; the painted mask controls the final composite.'}
              {appearance &&
              source &&
              (appearance.width !== source.width || appearance.height !== source.height)
                ? ' This image has a different canvas size. Choose a matching edited frame.'
                : ''}
            </p>
          )}
          {state.mode === 'swap' && source && (
            <button className="gen-mask-button" onClick={() => setPainting(true)}>
              <Icon name="brush" size={16} />
              {mask ? 'Edit painted mask' : 'Paint the object to replace'}
              {mask && <Icon name="check" size={14} />}
            </button>
          )}
          <div className="gen-prompt">
            <div>
              <Toggle
                label="Prompt"
                checked={state.prompt_enabled}
                onChange={(value) => update({ prompt_enabled: value })}
              />
            </div>
            {state.prompt_enabled && (
              <textarea
                aria-label="Prompt"
                value={state.prompt}
                maxLength={16000}
                onChange={(event) => update({ prompt: event.target.value })}
                placeholder={
                  state.mode === 'swap'
                    ? 'Describe the replacement and its appearance…'
                    : 'Describe the scene, action and desired look…'
                }
              />
            )}
          </div>
          {model?.supports_motion_controls && state.mode === 'motion' && !restyling ? (
            <MotionControls value={state} onChange={update} />
          ) : null}
          {source && (
            <div className="gen-range">
              <label>
                Start
                <input
                  type="number"
                  min="0"
                  max={Math.max(0, (source.duration || 0) - 0.5)}
                  step="0.1"
                  value={state.trim_start}
                  onChange={(event) =>
                    update({
                      trim_start: Number(event.target.value),
                      ...clearFirstFrame,
                      mask_asset_id: '',
                      ...(editedFirstFrame ? { reference_asset_id: '' } : {}),
                    })
                  }
                />
              </label>
              <label>
                Duration
                <input
                  type="number"
                  min="0.6"
                  step="0.1"
                  max={Math.min(
                    Math.max(0, (source.duration || 0) - state.trim_start),
                    Number(model?.max_frames || 81) / fps,
                  )}
                  value={state.duration}
                  onChange={(event) => update({ duration: Number(event.target.value) })}
                />
              </label>
              {model && source.duration !== undefined && <button type="button" onClick={() => update({ duration: Math.max(0, Math.min(source.duration! - state.trim_start, Number(model.max_frames || 241) / fps)) })}>Fit source / model limit</button>}
              <small>
                {frames > 0
                  ? `Selected ${state.trim_start.toFixed(2)}–${(state.trim_start + actualDuration).toFixed(2)}s · ${frames} frames / ${actualDuration.toFixed(2)}s at ${fps} fps. Source: ${source.duration?.toFixed(2) ?? 'unknown'}s. Rounded down to supported frames.`
                  : 'Select a longer interval'}
              </small>
            </div>
          )}
          <button className="gen-field" onClick={(event) => openMenu('model', event.currentTarget)}>
            <span>
              <small>Model</small>
              {model?.name || 'Loading models…'}
            </span>
            <Icon name="chevron" size={13} />
          </button>
          <button
            className="gen-field"
            onClick={(event) => openMenu('quality', event.currentTarget)}
          >
            <span>
              <small>Quality</small>
              {state.quality}px longest side
            </span>
            <Icon name="chevron" size={13} />
          </button>
          {source && (
            <button
              className="gen-field"
              onClick={(event) => openMenu('advanced', event.currentTarget)}
            >
              <span>
                <small>Compute & advanced</small>
                {catalog.providers.find((item) => item.id === provider)?.name || provider}
              </span>
              <Icon name="settings" size={14} />
            </button>
          )}
          {(intervalIssue || error || session.error || workspace.error) && (
            <p className="ea-error" role="alert">
              {intervalIssue || error || session.error || workspace.error}
            </p>
          )}
          {providerIssue && (
            <p className="muted small" role="status">
              {providerIssue}
            </p>
          )}
        </div>
        <footer>
          <button
            className="gen-generate"
            disabled={!canGenerate || busy || !session.ready}
            onClick={() => void generate()}
          >
            {busy
              ? 'Submitting…'
              : state.mode === 'motion' &&
                  appearance &&
                  state.style_name === 'Custom' &&
                  styleImage &&
                  !prepared
                ? 'Prepare styled character'
                : 'Generate'}
          </button>
        </footer>
      </aside>
      <main className="gen-workspace">
        <nav className="gen-workspace-tabs" role="tablist" aria-label="Page view">
          {[
            'History',
            'Motion Library',
            ...(state.mode === 'motion' ? ['Styles'] : []),
            'How it works',
          ].map((name) => (
            <button
              key={name}
              role="tab"
              aria-selected={view === name}
              className={view === name ? 'active' : ''}
              onClick={() => setView(name)}
            >
              <Icon
                name={
                  name === 'History'
                    ? 'folder'
                    : name === 'Styles'
                      ? 'brush'
                      : name === 'How it works'
                        ? 'book'
                        : 'grid'
                }
                size={14}
              />
              {name}
              {name === 'Styles' && <em>New</em>}
            </button>
          ))}
        </nav>
        {view === 'History' ? (
          <WorkspaceHistory
            jobs={session.jobs}
            total={session.jobTotal}
            onMore={session.loadMoreJobs}
            onSelect={(job) => setSelectedJobId(job.id)}
          />
        ) : view === 'How it works' ? (
          <section className="gen-instructions">
            <h1>Make the motion yours</h1>
            <ol>
              <li>
                <strong>Choose a real video.</strong>
                <p>
                  Set the start time and visible frame count. Audio can follow the selected source
                  interval.
                </p>
              </li>
              <li>
                <strong>Choose motion, appearance or style.</strong>
                <p>
                  Wan Animate uses a character image and extracted motion. Video-only styles use a
                  video restyle workflow. Swaps require a painted mask.
                </p>
              </li>
              <li>
                <strong>Review before rendering.</strong>
                <p>
                  A custom character style first creates a real Klein image. Review that image
                  before starting motion generation. Paint the whole subject, edges and shadow for a
                  masked edit.
                </p>
              </li>
              <li>
                <strong>Keep the workflow.</strong>
                <p>
                  Every result retains its model, inputs, seed and downloadable ComfyUI workflow.
                  Results depend on source motion and mask quality.
                </p>
              </li>
            </ol>
            <button onClick={onSettings}>Configure compute</button>
          </section>
        ) : (
          <>
            <section className="gen-hero">
              <div className="gen-hero-video">
                <ReferenceMedia item={hero} />
              </div>
              <h1>{stylesView ? 'One video, any style' : 'Turn one video into many'}</h1>
              <p>
                {stylesView
                  ? 'Pick a style or bring your own image. Guide the look while retaining the source action. Add a character reference to transfer its motion.'
                  : 'Take the motion and recast it with a character, or swap selected objects while preserving the surrounding scene.'}
              </p>
            </section>
            {stylesView ? (
              <>
                <div className="gen-library-tabs" role="tablist" aria-label="Style source">
                  {['Presets', 'Custom'].map((name) => (
                    <button
                      key={name}
                      role="tab"
                      aria-selected={styleTab === name}
                      className={styleTab === name ? 'active' : ''}
                      onClick={() => setStyleTab(name)}
                    >
                      <Icon name={name === 'Custom' ? 'user' : 'spark'} size={13} />
                      {name}
                    </button>
                  ))}
                </div>
                {styleTab === 'Custom' ? (
                  <div className="gen-custom-style">
                    <button onClick={() => setPicker('style')}>
                      {styleImage ? (
                        <img src={mediaUrl(styleImage)} alt="Selected style reference" />
                      ) : (
                        <Icon name="plus" size={26} />
                      )}
                      <strong>
                        {styleImage ? 'Change your style image' : 'Upload your style'}
                      </strong>
                      <span>Use a visual reference to guide the look</span>
                    </button>
                    {styleImage && (
                      <label>
                        Style direction
                        <textarea
                          value={state.style_prompt}
                          maxLength={16000}
                          onChange={(event) =>
                            update({ style_prompt: event.target.value, prepared_asset_id: '' })
                          }
                          placeholder="Describe the materials, colors and rendering style to borrow…"
                        />
                      </label>
                    )}
                  </div>
                ) : (
                  <div className="gen-style-grid">
                    {library.styles?.map((item) => (
                      <button
                        className={state.style_name === item.title ? 'selected' : ''}
                        key={item.id || item.title}
                        onClick={() =>
                          update({
                            style_name: item.title,
                            style_prompt: item.prompt || item.title,
                            style_asset_id: '',
                            prepared_asset_id: '',
                          })
                        }
                      >
                        <ReferenceMedia item={item} />
                        <strong>{item.title}</strong>
                        {state.style_name === item.title && (
                          <i>
                            <Icon name="check" size={16} />
                          </i>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                <div className="gen-library-tabs" role="tablist" aria-label="Reference collection">
                  {['Trending', 'New', 'Saved'].map((name) => (
                    <button
                      key={name}
                      role="tab"
                      aria-selected={libraryTab === name}
                      className={libraryTab === name ? 'active' : ''}
                      onClick={() => setLibraryTab(name)}
                    >
                      <Icon
                        name={name === 'Saved' ? 'heart' : name === 'New' ? 'clock' : 'spark'}
                        size={13}
                      />
                      {name === 'Saved' ? 'Saved references' : `Community ${name.toLowerCase()}`}
                    </button>
                  ))}
                </div>
                <div className="gen-motion-grid">
                  {shownReferences.map((item, index) => {
                    const id = item.id || item.source_url || item.title;
                    return (
                      <article key={id + index}>
                        <button
                          className="gen-open-reference"
                          onClick={() => setPreview(item)}
                          aria-label={`Open ${item.title}`}
                        >
                          <ReferenceMedia item={item} />
                        </button>
                        <div>
                          <span>{item.category || 'Motion reference'}</span>
                          <button
                            aria-label="Save reference"
                            aria-pressed={state.liked_references.includes(id)}
                            onClick={() =>
                              update({
                                liked_references: state.liked_references.includes(id)
                                  ? state.liked_references.filter((value) => value !== id)
                                  : [...state.liked_references, id],
                              })
                            }
                          >
                            <Icon name="heart" size={14} />
                          </button>
                          <button onClick={() => setPreview(item)}>Use as source</button>
                        </div>
                      </article>
                    );
                  })}
                </div>
                {!shownReferences.length && (
                  <p className="gen-reference-note">
                    {libraryTab === 'Saved'
                      ? 'Save a reference to find it here.'
                      : 'Reference previews are not included in this installation. Upload your own video to begin.'}
                  </p>
                )}
              </>
            )}
            <p className="gen-reference-note">
              Public Higgsfield reference previews. Your generated results appear in History.
            </p>
          </>
        )}
      </main>
      <button className="gen-mobile-action" onClick={() => setMobileComposer(true)}>
        <Icon name="plus" size={16} />
        Create video
      </button>
      {menu && (
        <AnchoredPopover
          anchor={menu.anchor}
          label={
            menu.name === 'model'
              ? 'Choose model'
              : menu.name === 'quality'
                ? 'Quality'
                : 'Advanced settings'
          }
          width={menu.name === 'model' ? 400 : menu.name === 'quality' ? 160 : 310}
          className={`gen-popover gen-${menu.name}-menu`}
          onClose={() => setMenu(null)}
        >
          {menu.name === 'model' ? (
            <>
              <label className="gen-model-search">
                <Icon name="search" size={17} />
                <input
                  autoFocus
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search models…"
                />
              </label>
              <small>Compatible open models</small>
              {models
                .filter((item) => item.name.toLowerCase().includes(search.toLowerCase()))
                .map((item) => (
                  <button
                    className={model?.id === item.id ? 'selected' : ''}
                    onClick={() => chooseModel(item.id)}
                    key={item.id}
                  >
                    <i>
                      <Icon name="video" size={18} />
                    </i>
                    <span>
                      {item.name}
                      <small>
                        {item.family} · up to{' '}
                        {(Number(item.max_frames) / Number(item.default_fps || 24)).toFixed(1)}s
                      </small>
                    </span>
                    {model?.id === item.id && <Icon name="check" size={14} />}
                  </button>
                ))}
            </>
          ) : menu.name === 'quality' ? (
            <>
              <small>Quality</small>
              {[512, 768, 1024].map((value) => (
                <button
                  key={value}
                  className={state.quality === value ? 'selected' : ''}
                  onClick={() => {
                    update({ quality: value });
                    setMenu(null);
                  }}
                >
                  {value}px{state.quality === value && <Icon name="check" size={14} />}
                </button>
              ))}
            </>
          ) : (
            <>
              <label>
                Compute
                <select
                  value={provider}
                  onChange={(event) => update({ provider: event.target.value })}
                >
                  {!catalog.providers.some((item) => item.id === provider) && (
                    <option value={provider} disabled>{provider} · unavailable in this configuration</option>
                  )}
                  {catalog.providers.filter((item) => ['local', 'comfy-cloud'].includes(item.id)).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
                {providerIssue && <small role="status">{providerIssue}</small>}
              </label>
              <label>
                Frame rate
                <input
                  type="number"
                  min="1"
                  max="120"
                  step="any"
                  value={model?.fixed_fps ? Number(model.fixed_fps) : (state.fps ?? '')}
                  placeholder={`Model default (${model?.default_fps || 16} fps)`}
                  disabled={!!model?.fixed_fps}
                  onChange={(event) =>
                    update({ fps: event.target.value === '' ? null : Number(event.target.value) })
                  }
                />
                <small>
                  {model?.fixed_fps
                    ? `This model requires ${model.fixed_fps} fps.`
                    : 'Leave empty for the model default. Changing FPS changes the displayed frame count; the selected duration stays unchanged.'}
                </small>
                {!fpsValid && <small role="alert">Choose 1–120 fps.</small>}
              </label>
              <label>
                Seed
                <input
                  type="number"
                  min="-1"
                  max={Number.MAX_SAFE_INTEGER}
                  step="1"
                  value={state.seed ?? -1}
                  onChange={(event) =>
                    update({ seed: event.target.value === '' ? -1 : Number(event.target.value) })
                  }
                />
                <small>
                  -1 chooses a random seed. Reuse restores the completed job’s recorded seed.
                </small>
              </label>
              <button
                onClick={() => {
                  setMenu(null);
                  onSettings();
                }}
              >
                Connection settings
              </button>
              {state.mode === 'swap' && (
                <>
                  <label>
                    Tracking
                    <select
                      value={state.mask_tracking_method}
                      onChange={(event) =>
                        update({
                          mask_tracking_method: event.target
                            .value as GenjutsuState['mask_tracking_method'],
                        })
                      }
                    >
                      <option value="sam2">SAM2</option>
                      <option value="flow">Optical flow</option>
                      <option value="static">Static mask</option>
                    </select>
                  </label>
                  <label>
                    Edit margin
                    <input
                      type="number"
                      min="0"
                      max="64"
                      value={state.mask_edit_margin}
                      onChange={(event) => update({ mask_edit_margin: Number(event.target.value) })}
                    />
                  </label>
                  <small>
                    Includes nearby pixels around the mask, so feathering does not restore old
                    object edges.
                  </small>
                </>
              )}
              {!restyling && model?.supports_uncomposited && (
                <Toggle
                  label="Also save raw generation"
                  checked={!!state.export_uncomposited}
                  onChange={(value) => update({ export_uncomposited: value })}
                />
              )}
              {compositeModes.length > 0 && (
                <label>
                  Replacement finishing
                  <select value={state.inpaint_composite_mode || 'legacy'}
                    onChange={(event) => update({ inpaint_composite_mode: event.target.value as 'legacy' | 'plate-fit' })}>
                    {compositeModes.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                  </select>
                  <small>{compositeModes.find((item) => item.id === (state.inpaint_composite_mode || 'legacy'))?.hint || 'Match replacement lighting to the surrounding plate; this does not guarantee object geometry.'}</small>
                </label>
              )}
              {!!model?.reference_modes && (
                <label>
                  Reference role
                  <select value={state.vace_reference_mode || 'appearance'}
                    onChange={(event) => update({ vace_reference_mode: event.target.value as 'appearance' | 'first-frame', reference_asset_id: '', prepared_asset_id: '' })}>
                    <option value="appearance">Object appearance</option>
                    <option value="first-frame">Edited full first frame</option>
                  </select>
                  <small>{vaceFirstFrame
                    ? 'Upload the complete edited starting frame at the original source size. Following frames retain the source scene and tracked edit mask.'
                    : 'Use an isolated object image to guide appearance; it is not a fixed opening frame.'}</small>
                </label>
              )}
              {restyling && !!model?.restyle_methods?.length && (
                <label>
                  Source guidance
                  <select value={restyleMethod} onChange={(event) => update({ restyle_method: event.target.value as 'latent' | 'canny' | 'water' })}>
                    {!validRestyleMethods.some((item) => item.id === restyleMethod) && <option value={restyleMethod} disabled>Saved method unavailable · {restyleMethod}</option>}
                    {validRestyleMethods.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                  </select>
                  {cannyRestyle && <small>Edge guidance preserves source structure at fixed strength 1. Review faces, hands and fine detail in the result.</small>}
                </label>
              )}
              {(restyling || state.mode === 'swap') && strengthControl && !cannyRestyle && (
                <label>
                  {strengthControl.label}
                  <input
                    type="range"
                    min="0.05"
                    max="1"
                    step="0.05"
                    value={state.strength}
                    onChange={(event) => update({ strength: Number(event.target.value) })}
                  />
                  <small>{state.strength.toFixed(2)}</small>
                </label>
              )}
            </>
          )}
        </AnchoredPopover>
      )}
      {picker && (
        <AssetPicker
          variant="genjutsu"
          presets={picker === 'style' ? library.styles : references}
          jobs={session.jobs}
          includeWorkspaceGenerations={picker === 'first-frame' || (picker === 'reference' && editedFirstFrame)}
          initialTab={picker === 'first-frame' || (picker === 'reference' && editedFirstFrame) ? 'Generations' : 'Uploads'}
          title={
            picker === 'source'
              ? 'Add a reference video'
              : picker === 'first-frame'
                ? 'Select the edited full starting frame'
              : picker === 'style'
                ? 'Upload your style'
                : editedFirstFrame
                  ? 'Select the edited starting frame'
                  : 'Add an appearance reference'
          }
          kind={picker === 'source' ? 'video' : 'image'}
          assets={workspace.assets}
          onAdded={workspace.add}
          onSelect={chooseAsset}
          onClose={() => setPicker(null)}
        />
      )}
      {painting && source && (
        <MaskEditor
          asset={source}
          existingMask={mask}
          startTime={state.trim_start}
          onClose={() => setPainting(false)}
          onSave={(asset) => {
            workspace.add(asset);
            update({ mask_asset_id: asset.id });
            setPainting(false);
          }}
        />
      )}
      {preview && (
        <ReferenceDialog
          item={preview}
          onClose={() => setPreview(null)}
          onUse={() => void useReference()}
          busy={busy}
          label="Use this video as source"
        />
      )}
      {selectedJob && (
        <ResultDialog
          job={selectedJob}
          onClose={() => setSelectedJobId(null)}
          onRefresh={() => void session.refreshJobs()}
          onReuse={() => void reuse(selectedJob)}
          useKind="image"
          useLabel="Use this reviewed character"
          onUse={
            selectedJob.request.effect_id === 'edit-image'
              ? (asset) => {
                  workspace.add(asset);
                  update({ prepared_asset_id: asset.id });
                  setView('Motion Library');
                }
              : undefined
          }
        />
      )}
    </div>
  );
}
