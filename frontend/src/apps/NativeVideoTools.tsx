import { useEffect, useState } from 'react';
import { api, mediaUrl, post } from '../api';
import { Icon } from '../Icon';
import { AnchoredPopover } from '../Popovers';
import type { Asset, Job } from '../types';
import type { AppDocument } from './registry';
import { useAppDocument } from './useAppDocument';
import { renderRequest, renderSize } from './renderRequest';
import {
  AssetPicker,
  ReferenceMedia,
  ResultDialog,
  SourceSlot,
  useWorkspaceAssets,
  WorkspaceHistory,
} from './engine-apps-shared';
import type { EngineAppProps } from './engine-apps-shared';
import './frame-tools.css';
import './native-video-tools.css';

export type NativeVideoOperation =
  | 'video-extend'
  | 'video-outpaint'
  | 'video-upscale'
  | 'alpha-matte'
  | 'semantic-matte'
  | 'clean-plate'
  | 'sdr-to-hdr';
type State = {
  kind: NativeVideoOperation;
  source_asset_id: string;
  model_id: string;
  prompt: string;
  trim_start: number;
  frames: number;
  fps: number;
  width: number;
  height: number;
  ratio: string;
  longest: number;
  seed: number;
  context_frames: number;
  extension_direction: 'sequel' | 'prequel';
  outpaint_scale: number;
  outpaint_anchor_x: number;
  outpaint_anchor_y: number;
  upscale_mode: 'pixel-2x' | 'tiled-refine';
  hdr_output_format: 'hevc10' | 'prores10' | 'exr16';
  exr_confirmed: boolean;
  trimap_radius: number;
  subject_confidence: number;
  output_view: 'result' | 'mask';
  preserve_audio: boolean;
  generate_audio: boolean;
  enhance_prompt: boolean;
  video_refinement: 'single' | 'two-stage';
  encoding_quality: 'legacy' | 'standard' | 'high';
};
const details: Record<
  NativeVideoOperation,
  { title: string; subtitle: string; explanation: string; hero?: string; poster?: string }
> = {
  'video-extend': {
    title: 'Extend video',
    subtitle: 'Generate a continuation',
    explanation:
      'The output contains the selected source context plus new footage. Sequel places the context first; Prequel places it last. The rest of a longer original is not automatically included. Keeping source audio applies only to that context. New footage is silent unless continuation audio is enabled.',
    hero: 'https://static.higgsfield.ai/seedance-2.5/video-banner-general.mp4',
    poster: 'https://static.higgsfield.ai/seedance-25-preset.webp',
  },
  'video-outpaint': {
    title: 'AI Reframe',
    subtitle: 'Generate outside the existing frame',
    explanation:
      'The fitted source region is retained and the missing canvas is generated. Source scale and anchors determine placement. This workflow does not accept side-reference images or automatically track the subject.',
    hero: 'https://static.higgsfield.ai/reframe-preset-black.mp4',
  },
  'video-upscale': {
    title: 'Upscale',
    subtitle: 'Increase resolution and refine details',
    explanation:
      'Pixel 2× uses the dedicated upscaling adapter and retains exactly twice the native source dimensions. Tiled refinement uses a separate detail adapter on the explicitly chosen canvas.',
    hero: 'https://static.higgsfield.ai/video-edit-form/v2/tools-hero/upscale.mp4',
    poster: 'https://static.higgsfield.ai/video-edit-form/v2/tools-hero/upscale-poster.webp',
  },
  'alpha-matte': {
    title: 'Automatic Alpha',
    subtitle: 'Extract the model’s foreground matte',
    explanation:
      'LTX AlphaGen automatically estimates foreground alpha. It does not use text to choose an object. Original RGB and the inferred alpha produce a transparent WebM; a grayscale mask video is also exported.',
    hero: 'https://static.higgsfield.ai/video-edit-form/v2/tools-hero/remove-background.mp4',
    poster:
      'https://static.higgsfield.ai/video-edit-form/v2/tools-hero/remove-background-poster.webp',
  },
  'semantic-matte': {
    title: 'Remove Background',
    subtitle: 'Keep the subject described in your prompt',
    explanation:
      'SAM3.1 tracks the named foreground concept. Its mask becomes an explicit trimap for ViTMatte, then alpha is combined with the original RGB. Selection mistakes and fine-edge flicker are possible; inspect the exported mask.',
    hero: 'https://static.higgsfield.ai/video-edit-form/v2/tools-hero/remove-background.mp4',
    poster:
      'https://static.higgsfield.ai/video-edit-form/v2/tools-hero/remove-background-poster.webp',
  },
  'clean-plate': {
    title: 'Clean Plate',
    subtitle: 'Reconstruct the background of a shot',
    explanation:
      'A dedicated clean-plate adapter reconstructs the scene without salient foreground subjects. This is a full-frame operation. Use Draw to Edit for a specific painted object instead.',
  },
  'sdr-to-hdr': {
    title: 'SDR to HDR',
    subtitle: 'Create a high-bit-depth HDR output',
    explanation:
      'A dedicated HDR adapter and scene embedding convert the source. The downloadable master is distinct from the SDR preview shown in browsers. An HDR-capable player and display are needed to assess the master.',
    hero: 'https://static.higgsfield.ai/video-edit-form/v2/tools-hero/sdr-to-hdr.mp4',
    poster: 'https://static.higgsfield.ai/video-edit-form/v2/tools-hero/sdr-to-hdr-poster.webp',
  },
};
const defaults = (kind: NativeVideoOperation): State => ({
  kind,
  source_asset_id: '',
  model_id: '',
  prompt:
    kind === 'video-extend'
      ? 'Continue the scene naturally with coherent motion and lighting.'
      : kind === 'clean-plate'
        ? 'The same environment without people or moving foreground subjects. Preserve the background architecture, lighting, textures and camera motion.'
        : '',
  trim_start: 0,
  frames: 97,
  fps: 24,
  width: 1024,
  height: 576,
  ratio: '16:9',
  longest: 1024,
  seed: -1,
  context_frames: 17,
  extension_direction: 'sequel',
  outpaint_scale: 1,
  outpaint_anchor_x: 0.5,
  outpaint_anchor_y: 0.5,
  upscale_mode: 'pixel-2x',
  hdr_output_format: 'hevc10',
  exr_confirmed: false,
  trimap_radius: 12,
  subject_confidence: 0.5,
  output_view: 'result',
  preserve_audio: true,
  generate_audio: false,
  enhance_prompt: true,
  video_refinement: 'two-stage',
  encoding_quality: 'high',
});
const ids = (state: State) => (state.source_asset_id ? [state.source_asset_id] : []);
export const nativeVideoRoutes: Record<string, NativeVideoOperation> = {
  '/apps/video-extend': 'video-extend',
  '/apps/video-outpaint': 'video-outpaint',
  '/apps/video-upscale': 'video-upscale',
  '/apps/alpha-matte': 'alpha-matte',
  '/apps/video-background-removal': 'semantic-matte',
  '/apps/clean-plate': 'clean-plate',
  '/apps/sdr-to-hdr': 'sdr-to-hdr',
};
export const nativeVideoCards = Object.entries(nativeVideoRoutes).map(([path, operation]) => ({
  id: path.split('/').pop()!,
  name: details[operation].title,
  description: details[operation].subtitle,
  icon: 'video',
  badge: details[operation].hero ? 'Reference preview' : 'Native model workflow',
  video: details[operation].hero,
  poster: details[operation].poster,
  category: 'Video Utilities',
}));

export function NativeVideoTool({
  operation,
  catalog,
  settings,
  onSettings,
}: EngineAppProps & { operation: NativeVideoOperation }) {
  const session = useAppDocument(
    'mini-apps',
    defaults(operation),
    ids,
    operation,
    details[operation].title,
  );
  const state = { ...defaults(operation), ...session.state };
  const assets = useWorkspaceAssets(ids(state));
  const source = assets.get(state.source_asset_id);
  const effect = catalog.effects.find((item) => item.id === operation);
  const models = catalog.models.filter((item) => effect?.model_ids.includes(item.id));
  const model =
    models.find((item) => item.id === state.model_id) || (!state.model_id ? models[0] : undefined);
  const info = details[operation],
    provider = settings.default_provider || 'local';
  const extend = operation === 'video-extend',
    outpaint = operation === 'video-outpaint',
    upscale = operation === 'video-upscale';
  const semantic = operation === 'semantic-matte',
    alpha = operation === 'alpha-matte' || semantic,
    hdr = operation === 'sdr-to-hdr';
  const fixedSize = alpha || (upscale && state.upscale_mode === 'pixel-2x');
  const fps = semantic ? source?.fps || state.fps : state.fps;
  const taskLimits = (
    model?.task_limits as
      | Record<
          string,
          {
            max_frames?: number;
            max_long_side?: number;
            max_short_side?: number;
            max_pixels?: number;
          }
        >
      | undefined
  )?.[effect?.task || operation];
  const baseLimits = model?.default_task_limits as
    { max_long_side?: number; max_short_side?: number; max_pixels?: number } | undefined;
  const maxFrames = Number(taskLimits?.max_frames || model?.max_frames || 241),
    multiple = Number(model?.frame_multiple || (semantic ? 1 : 8));
  const maxSide = Number(
    taskLimits?.max_long_side || baseLimits?.max_long_side || model?.max_width || 1920,
  );
  const maxPixels = Number(taskLimits?.max_pixels || baseLimits?.max_pixels || maxSide * 1088);
  const maxShortSide = Number(
    taskLimits?.max_short_side ||
      baseLimits?.max_short_side ||
      Math.min(Number(model?.max_width || maxSide), Number(model?.max_height || maxSide)),
  );
  const minFrames = Number(model?.min_frames ?? 9);
  const size =
    fixedSize && source
      ? {
          width: (source.width || 0) * (upscale ? 2 : 1),
          height: (source.height || 0) * (upscale ? 2 : 1),
        }
      : { width: state.width, height: state.height };
  const inferenceSize = semantic
    ? size
    : { width: Math.ceil(size.width / 32) * 32, height: Math.ceil(size.height / 32) * 32 };
  const sourceFrames = extend ? state.context_frames : state.frames;
  const sourceDuration = sourceFrames / fps,
    outputDuration = state.frames / fps;
  const exrBytes = 6 * size.width * size.height * state.frames;
  const promptVisible = !hdr && operation !== 'alpha-matte' && !outpaint;
  const [view, setView] = useState<'guide' | 'source' | 'history'>('guide'),
    [picker, setPicker] = useState(false);
  const [advanced, setAdvanced] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [selected, setSelected] = useState<Job | null>(null);
  const [menu, setMenu] = useState<{
    name: 'ratio' | 'quality' | 'duration' | 'direction' | 'model' | 'method' | 'format';
    anchor: HTMLElement;
  } | null>(null);
  const jobs = session.jobs.filter((job) => job.request.effect_id === operation);
  const scale = source
    ? Math.min(1, size.width / (source.width || 1), size.height / (source.height || 1)) *
      state.outpaint_scale
    : 1;
  const fitW = Math.round((source?.width || 0) * scale),
    fitH = Math.round((source?.height || 0) * scale);
  function resize(ratio = state.ratio, longest = state.longest) {
    if (!model) return;
    session.update({ ...renderSize(model, ratio, longest), ratio, longest, exr_confirmed: false });
  }
  function sourceState(asset: Asset): Partial<State> {
    const rate = semantic ? asset.fps || 24 : Number(model?.fixed_fps || model?.default_fps || 24);
    const available = Math.floor((asset.duration || 0) * rate + 1e-6);
    const aligned = (frames: number) =>
      semantic ? frames : Math.floor((frames - 1) / multiple) * multiple + 1;
    const context = Math.max(1, aligned(Math.min(17, available)));
    const ratio = outpaint ? state.ratio : `${asset.width || 16}:${asset.height || 9}`;
    return {
      source_asset_id: asset.id,
      fps: rate,
      trim_start:
        extend && state.extension_direction === 'sequel'
          ? Math.max(0, (asset.duration || 0) - context / rate)
          : 0,
      frames: extend
        ? Math.min(97, maxFrames)
        : Math.max(1, aligned(Math.min(97, available, maxFrames))),
      context_frames: context,
      ratio,
      ...(model && !fixedSize ? renderSize(model, ratio, state.longest) : {}),
      exr_confirmed: false,
    };
  }
  function choose(asset: Asset) {
    assets.add(asset);
    session.update(sourceState(asset));
    setView('source');
    setError('');
  }
  async function generate() {
    setBusy(true);
    setError('');
    try {
      if (!source || source.kind !== 'video' || !source.width || !source.height || !source.duration)
        throw new Error('Choose a video with known dimensions and duration.');
      if (!model) throw new Error('Choose a supported model.');
      const providers = model.supported_providers as string[] | undefined;
      if (!(providers || ['local']).includes(provider))
        throw new Error(
          'Choose a supported compute provider in connection settings. No local fallback is used.',
        );
      if (
        !Number.isInteger(state.frames) ||
        state.frames < minFrames ||
        state.frames > maxFrames ||
        (!semantic && (state.frames - 1) % multiple)
      )
        throw new Error(
          `Choose ${semantic ? 'whole frames' : `${multiple}n + 1 frames`} from ${minFrames} to ${maxFrames}.`,
        );
      if (
        !Number.isFinite(fps) ||
        fps <= 0 ||
        (!semantic && fps !== Number(model.fixed_fps || model.default_fps || 24))
      )
        throw new Error('Use the selected model’s frame rate.');
      if (
        !Number.isFinite(state.trim_start) ||
        state.trim_start < 0 ||
        state.trim_start + sourceDuration > source.duration + 0.001
      )
        throw new Error(
          'The selected source interval does not fit. Reduce frames or move its start; the request will not be silently shortened.',
        );
      if (
        extend &&
        (!Number.isInteger(state.context_frames) ||
          state.context_frames < 1 ||
          state.context_frames > 129 ||
          (state.context_frames - 1) % 8 ||
          state.context_frames >= state.frames)
      )
        throw new Error(
          'Context needs 1–129 frames in steps of 8, and fewer frames than the output.',
        );
      if (
        !Number.isInteger(size.width) ||
        !Number.isInteger(size.height) ||
        inferenceSize.width < Number(model.min_width || 64) ||
        inferenceSize.height < Number(model.min_height || 64) ||
        Math.max(inferenceSize.width, inferenceSize.height) > maxSide ||
        Math.min(inferenceSize.width, inferenceSize.height) > maxShortSide ||
        inferenceSize.width * inferenceSize.height > maxPixels ||
        (!fixedSize && (size.width % 32 || size.height % 32))
      )
        throw new Error(
          'The output canvas exceeds this model’s dimension or pixel limits. Select a smaller valid canvas.',
        );
      if (alpha && (size.width % 2 || size.height % 2))
        throw new Error(
          'Transparent video requires even source dimensions. Crop or pad the original explicitly before matting.',
        );
      if (semantic && (!state.prompt.trim() || state.prompt.trim().length > 200))
        throw new Error('Describe the foreground to keep in 1–200 characters.');
      if (outpaint && fitW === size.width && fitH === size.height)
        throw new Error(
          'Add canvas around the source, or reduce its scale to leave an area to generate.',
        );
      if (
        upscale &&
        state.upscale_mode === 'tiled-refine' &&
        (Math.max(size.width, size.height) < 1024 || Math.min(size.width, size.height) < 576)
      )
        throw new Error(
          'Tiled refinement needs at least a 1024 × 576 canvas in either orientation.',
        );
      if (
        hdr &&
        state.hdr_output_format === 'exr16' &&
        (!state.exr_confirmed || exrBytes > 4 * 1024 ** 3)
      )
        throw new Error(
          'Confirm the EXR sequence size estimate; the raw RGB estimate must be at most 4 GiB.',
        );
      const document = await session.save(true);
      if (!document) throw new Error('The project could not be saved.');
      const request = renderRequest(model, {
        effect_id: operation,
        provider,
        source_asset_id: source.id,
        prompt: hdr || operation === 'alpha-matte' ? '' : state.prompt.trim(),
        ...size,
        frames: state.frames,
        fps,
        trim_start: state.trim_start,
        seed: state.seed,
        preserve_audio: state.preserve_audio,
        generate_audio: extend && state.generate_audio,
        encoding_quality: state.encoding_quality,
        ...(semantic
          ? { trimap_radius: state.trimap_radius, subject_confidence: state.subject_confidence }
          : { enhance_prompt: state.enhance_prompt }),
        ...(extend
          ? { context_frames: state.context_frames, extension_direction: state.extension_direction }
          : {}),
        ...(outpaint
          ? {
              outpaint_scale: state.outpaint_scale,
              outpaint_anchor_x: state.outpaint_anchor_x,
              outpaint_anchor_y: state.outpaint_anchor_y,
              video_refinement: state.video_refinement,
            }
          : {}),
        ...(upscale ? { upscale_mode: state.upscale_mode } : {}),
        ...(hdr ? { hdr_output_format: state.hdr_output_format } : {}),
      });
      await post(`/apps/mini-apps/documents/${document.id}/jobs`, {
        expected_revision: document.revision,
        operation,
        request,
      });
      await session.refreshJobs();
      setView('history');
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reuse(job: Job) {
    try {
      if (job.request.effect_id !== operation)
        throw new Error('This result belongs to another tool.');
      const context = job.app_context
        ? await api<{ document_snapshot?: AppDocument<State> }>(`/jobs/${job.id}/app-context`)
        : null;
      const r = job.request;
      await session.newDocument({
        ...defaults(operation),
        ...(context?.document_snapshot?.state || {}),
        source_asset_id: r.source_asset_id || '',
        model_id: r.model_id,
        prompt: r.prompt,
        seed: r.seed,
        trim_start: r.trim_start,
        frames: r.frames,
        fps: r.fps,
        width: r.width,
        height: r.height,
        ratio: `${r.width}:${r.height}`,
        longest: Math.max(r.width, r.height),
        context_frames: r.context_frames ?? 17,
        extension_direction: r.extension_direction || 'sequel',
        outpaint_scale: r.outpaint_scale ?? 1,
        outpaint_anchor_x: r.outpaint_anchor_x ?? 0.5,
        outpaint_anchor_y: r.outpaint_anchor_y ?? 0.5,
        upscale_mode: r.upscale_mode || 'pixel-2x',
        hdr_output_format: r.hdr_output_format || 'hevc10',
        exr_confirmed: false,
        trimap_radius: r.trimap_radius ?? 12,
        subject_confidence: r.subject_confidence ?? 0.5,
        preserve_audio: r.preserve_audio,
        generate_audio: r.generate_audio,
        enhance_prompt: r.enhance_prompt ?? true,
        video_refinement: r.video_refinement || 'two-stage',
        encoding_quality: r.encoding_quality || 'high',
      });
      setView('source');
    } catch (reason) {
      setError((reason as Error).message);
    }
  }
  useEffect(() => {
    if (!session.ready || !model) return;
    const params = new URLSearchParams(location.search),
      jobId = params.get('job'),
      sourceId = params.get('source');
    if (!jobId && !sourceId) return;
    let active = true;
    const clear = () => {
      const url = new URL(location.href);
      url.searchParams.delete('job');
      url.searchParams.delete('source');
      url.searchParams.delete('document');
      history.replaceState(null, '', url);
    };
    void (
      jobId
        ? api<Job>(`/jobs/${encodeURIComponent(jobId)}`).then(async (job) => {
            if (active) {
              await reuse(job);
              clear();
            }
          })
        : api<Asset>(`/assets/${encodeURIComponent(sourceId!)}`).then(async (asset) => {
            if (!active) return;
            if (asset.kind !== 'video') throw new Error('Choose a video input.');
            assets.add(asset);
            if (await session.newDocument({ ...defaults(operation), ...sourceState(asset) })) {
              clear();
              setView('source');
            }
          })
    ).catch((reason) => setError(reason.message));
    return () => {
      active = false;
    };
  }, [session.ready, operation, !!model]);
  const popup = (name: NonNullable<typeof menu>['name'], label: string, value: string) => (
    <button
      className="ft-control"
      onClick={(event) => setMenu({ name, anchor: event.currentTarget })}
    >
      <span>{label}</span>
      <strong>{value}</strong>
      <Icon name="chevron" size={14} />
    </button>
  );
  return (
    <main className={`frame-tool-app native-video-app native-${operation}`}>
      <aside className="ft-rail">
        <nav className="ft-navigation">
          <a href="/studio/vfx?view=studio">Create Video</a>
          <a className="active" href="/studio/vfx?view=edit">
            Edit Video
          </a>
          <a href="/genjutsu">Motion Control</a>
        </nav>
        <div className="ft-controls">
          <figure className="ft-hero">
            {info.hero && (
              <ReferenceMedia item={{ title: info.title, video: info.hero, poster: info.poster }} />
            )}
            <a href="/studio/vfx?view=edit">
              <Icon name="brush" size={13} />
              Change
            </a>
            <figcaption>
              <h1>{info.title}</h1>
              <p>{info.subtitle}</p>
            </figcaption>
          </figure>
          <SourceSlot
            title={
              outpaint
                ? 'Upload a video to reframe'
                : `Add a video${extend ? ' to extend' : upscale ? ' to upscale' : ''}`
            }
            detail={
              semantic
                ? 'Original dimensions and frame rate'
                : `Selected interval · up to ${maxFrames} output frames`
            }
            asset={source}
            onChoose={() => setPicker(true)}
            onClear={() => session.update({ source_asset_id: '' })}
          />
          {extend &&
            popup(
              'direction',
              'Direction',
              state.extension_direction === 'sequel'
                ? 'Sequel · after context'
                : 'Prequel · before context',
            )}
          {upscale &&
            popup(
              'method',
              'Method',
              state.upscale_mode === 'pixel-2x' ? 'Pixel 2×' : 'Tiled detail refinement',
            )}
          {promptVisible && (
            <label className="nv-prompt">
              {semantic ? 'Foreground to keep' : 'Prompt'}
              <textarea
                value={state.prompt}
                maxLength={semantic ? 200 : 4000}
                placeholder={
                  semantic
                    ? 'Start with a short subject name, for example: person'
                    : 'Describe the intended scene and details'
                }
                onChange={(event) => session.update({ prompt: event.target.value })}
              />
            </label>
          )}
          {alpha && (
            <fieldset className="nv-output">
              <legend>Output preview</legend>
              {(['result', 'mask'] as const).map((value) => (
                <label className={state.output_view === value ? 'active' : ''} key={value}>
                  <input
                    type="radio"
                    name="matte-output"
                    checked={state.output_view === value}
                    onChange={() => session.update({ output_view: value })}
                  />
                  <img
                    src={`https://static.higgsfield.ai/video-edit-form/v2/remove-background/${value === 'result' ? 'cut-video' : 'alpha-mask'}.webp`}
                    alt="Reference output illustration"
                  />
                  <span>{value === 'result' ? 'Cutout video' : 'Alpha mask'}</span>
                </label>
              ))}
              <small>Both files are included; this chooses the primary result preview.</small>
            </fieldset>
          )}
          {hdr &&
            popup(
              'format',
              'Output format',
              {
                hevc10: 'HEVC · 10-bit HLG',
                prores10: 'ProRes · 10-bit HLG',
                exr16: 'EXR · 16-bit sequence',
              }[state.hdr_output_format],
            )}
          {popup('model', 'Model', model?.name || 'Choose model')}
          {!fixedSize && (
            <div className="ft-pair">
              {popup('ratio', 'Aspect ratio', state.ratio)}
              {popup('quality', 'Quality', `${Math.max(size.width, size.height)}px`)}
            </div>
          )}
          {fixedSize && (
            <p className="ft-limits">
              {source
                ? `${size.width} × ${size.height} · ${upscale ? 'exactly 2× source' : 'native source RGB'}`
                : 'Dimensions follow the selected source.'}
            </p>
          )}
          {popup(
            'duration',
            extend ? 'Output duration' : 'Selected duration',
            `${outputDuration.toFixed(2)}s · ${state.frames} frames`,
          )}
          {!alpha && (!hdr || state.hdr_output_format === 'hevc10') && (
            <label className="ft-select">
              Bitrate
              <select
                value={state.encoding_quality}
                onChange={(event) =>
                  session.update({
                    encoding_quality: event.target.value as State['encoding_quality'],
                  })
                }
              >
                {state.encoding_quality === 'legacy' && (
                  <option value="legacy">Default encoder</option>
                )}
                <option value="high">High</option>
                <option value="standard">Standard</option>
              </select>
            </label>
          )}
          {hdr && state.hdr_output_format === 'prores10' && (
            <p className="ft-limits">ProRes 422 HQ · fixed profile</p>
          )}
          {hdr && state.hdr_output_format === 'exr16' && (
            <label className="nv-exr">
              <input
                type="checkbox"
                checked={state.exr_confirmed}
                onChange={(event) => session.update({ exr_confirmed: event.target.checked })}
              />
              <span>
                Export EXR sequence. Estimated raw RGB: {(exrBytes / 1024 ** 3).toFixed(2)} GiB
                before compression, metadata and ZIP overhead. The image archive has no audio track.
              </span>
            </label>
          )}
          <label className="ft-toggle">
            <span>
              Keep source audio{hdr && state.hdr_output_format === 'exr16' ? ' in preview' : ''}
            </span>
            <input
              type="checkbox"
              checked={state.preserve_audio}
              onChange={(event) => session.update({ preserve_audio: event.target.checked })}
            />
          </label>
          {extend && (
            <label className="ft-toggle">
              <span>Generate continuation audio</span>
              <input
                type="checkbox"
                checked={state.generate_audio}
                onChange={(event) => session.update({ generate_audio: event.target.checked })}
              />
            </label>
          )}
          <button className="nv-advanced-toggle" onClick={() => setAdvanced(!advanced)}>
            <Icon name="sliders" size={14} />
            Advanced controls
            <Icon name="chevron" size={12} />
          </button>
          {advanced && (
            <section className="nv-advanced">
              <label>
                Source start (seconds)
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  value={state.trim_start}
                  onChange={(event) => session.update({ trim_start: Number(event.target.value) })}
                />
              </label>
              {extend && (
                <label>
                  Source context frames
                  <input
                    type="number"
                    min={1}
                    max={129}
                    step={8}
                    value={state.context_frames}
                    onChange={(event) =>
                      session.update({ context_frames: Number(event.target.value) })
                    }
                  />
                  <small>
                    {(state.context_frames / fps).toFixed(3)}s of source +{' '}
                    {((state.frames - state.context_frames) / fps).toFixed(3)}s of generated
                    footage.
                  </small>
                </label>
              )}
              {!fixedSize && (
                <div className="ft-pair">
                  <label>
                    Width
                    <input
                      type="number"
                      step={32}
                      min={256}
                      max={maxSide}
                      value={state.width}
                      onChange={(event) =>
                        session.update({ width: Number(event.target.value), exr_confirmed: false })
                      }
                    />
                  </label>
                  <label>
                    Height
                    <input
                      type="number"
                      step={32}
                      min={256}
                      max={maxSide}
                      value={state.height}
                      onChange={(event) =>
                        session.update({ height: Number(event.target.value), exr_confirmed: false })
                      }
                    />
                  </label>
                </div>
              )}
              {outpaint && (
                <>
                  <label>
                    Source scale · {Math.round(state.outpaint_scale * 100)}%
                    <input
                      type="range"
                      min={0.1}
                      max={1}
                      step={0.01}
                      value={state.outpaint_scale}
                      onChange={(event) =>
                        session.update({ outpaint_scale: Number(event.target.value) })
                      }
                    />
                  </label>
                  {(['x', 'y'] as const).map((axis) => (
                    <label key={axis}>
                      {axis === 'x' ? 'Horizontal' : 'Vertical'} anchor
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.01}
                        value={state[`outpaint_anchor_${axis}`]}
                        onChange={(event) =>
                          session.update({
                            [`outpaint_anchor_${axis}`]: Number(event.target.value),
                          })
                        }
                      />
                    </label>
                  ))}
                  <label>
                    Optional scene direction
                    <textarea
                      value={state.prompt}
                      onChange={(event) => session.update({ prompt: event.target.value })}
                    />
                  </label>
                  <label>
                    Refinement
                    <select
                      value={state.video_refinement}
                      onChange={(event) =>
                        session.update({
                          video_refinement: event.target.value as State['video_refinement'],
                        })
                      }
                    >
                      <option value="two-stage">Two stage</option>
                      <option value="single">Single stage</option>
                    </select>
                  </label>
                </>
              )}
              {semantic && (
                <>
                  <label>
                    Trimap radius · {state.trimap_radius}px
                    <input
                      type="range"
                      min={1}
                      max={64}
                      step={1}
                      value={state.trimap_radius}
                      onChange={(event) =>
                        session.update({ trimap_radius: Number(event.target.value) })
                      }
                    />
                  </label>
                  <label>
                    Subject confidence · {state.subject_confidence.toFixed(2)}
                    <input
                      type="range"
                      min={0.1}
                      max={0.9}
                      step={0.05}
                      value={state.subject_confidence}
                      onChange={(event) =>
                        session.update({ subject_confidence: Number(event.target.value) })
                      }
                    />
                  </label>
                </>
              )}
              {!hdr && !alpha && (
                <label className="ft-toggle">
                  <span>Enhance scene prompt</span>
                  <input
                    type="checkbox"
                    checked={state.enhance_prompt}
                    onChange={(event) => session.update({ enhance_prompt: event.target.checked })}
                  />
                </label>
              )}
              {!semantic && (
                <label>
                  Seed · −1 chooses a new seed
                  <input
                    type="number"
                    min={-1}
                    max={Number.MAX_SAFE_INTEGER}
                    step={1}
                    value={state.seed}
                    onChange={(event) => session.update({ seed: Number(event.target.value) })}
                  />
                </label>
              )}
            </section>
          )}
          {alpha && (
            <a
              className="nv-alternative"
              href={semantic ? '/apps/alpha-matte' : '/apps/video-background-removal'}
            >
              {semantic
                ? 'Use automatic LTX foreground matting'
                : 'Choose a foreground with a text prompt'}
              <Icon name="arrow" size={13} />
            </a>
          )}
          <p className="ft-limits">{info.explanation}</p>
          <p className="ft-limits">
            {state.frames} frames at {fps.toFixed(3).replace(/\.0+$/, '')} fps · source{' '}
            {state.trim_start.toFixed(3)}–{(state.trim_start + sourceDuration).toFixed(3)}s. Model
            limit {maxFrames} frames / {maxSide}px longest side.{' '}
            {semantic && 'Requires authorized SAM3.1 model access and a compatible enabled runtime.'}
          </p>
          <button className="nv-compute" onClick={onSettings}>
            <Icon name="cloud" size={14} />
            {provider === 'local' ? 'Local ComfyUI' : provider === 'comfy-cloud' ? 'Comfy Cloud' : 'Saved connection unavailable'}
            <Icon name="chevron" size={12} />
          </button>
          {(error || session.error || assets.error) && (
            <p role="alert" className="ft-error">
              {error || session.error || assets.error}
            </p>
          )}
        </div>
        <footer>
          <button
            disabled={busy || !source || !model || !session.ready}
            onClick={() => void generate()}
          >
            {busy ? 'Preparing…' : 'Generate'}
          </button>
        </footer>
      </aside>
      <section className="ft-workspace">
        <nav>
          <button className={view === 'history' ? 'active' : ''} onClick={() => setView('history')}>
            <Icon name="folder" size={16} />
            History
          </button>
          <button className={view === 'guide' ? 'active' : ''} onClick={() => setView('guide')}>
            <Icon name="book" size={16} />
            How it works
          </button>
          {source && (
            <button className={view === 'source' ? 'active' : ''} onClick={() => setView('source')}>
              Source & framing
            </button>
          )}
          <div />
          <button onClick={() => void session.newDocument(defaults(operation))}>New project</button>
          <button onClick={onSettings}>
            <Icon name="settings" size={15} />
          </button>
        </nav>
        <div className="ft-workspace-body">
          {view === 'history' ? (
            <>
              <WorkspaceHistory
                jobs={jobs}
                total={jobs.length + (session.jobs.length < session.jobTotal ? 1 : 0)}
                onSelect={setSelected}
                onMore={session.loadMoreJobs}
              />
              <p className="ft-limits">
                Matching results from {session.jobs.length} loaded app generations.
              </p>
            </>
          ) : view === 'source' && source ? (
            <section className="ft-source-stage">
              {outpaint ? (
                <div className="nv-canvas" style={{ aspectRatio: `${size.width}/${size.height}` }}>
                  <img
                    src={`/api/assets/${source.id}/frame?time=${state.trim_start}`}
                    alt="Selected source frame positioned on the output canvas"
                    style={{
                      width: `${(100 * fitW) / size.width}%`,
                      height: `${(100 * fitH) / size.height}%`,
                      left: `${(100 * (size.width - fitW) * state.outpaint_anchor_x) / size.width}%`,
                      top: `${(100 * (size.height - fitH) * state.outpaint_anchor_y) / size.height}%`,
                    }}
                  />
                  <span>CHECKERBOARD = AREA TO GENERATE</span>
                </div>
              ) : (
                <video
                  key={`${source.id}-${state.trim_start}`}
                  controls
                  playsInline
                  preload="metadata"
                  src={mediaUrl(source)}
                  onLoadedMetadata={(event) => {
                    event.currentTarget.currentTime = state.trim_start;
                  }}
                  onTimeUpdate={(event) => {
                    if (event.currentTarget.currentTime > state.trim_start + sourceDuration)
                      event.currentTarget.pause();
                  }}
                />
              )}
              <h2>{info.title}</h2>
              <p>{info.explanation}</p>
              <p>
                Output {size.width} × {size.height} · {outputDuration.toFixed(3)}s. This is the
                source preview; generated results appear in History.
              </p>
            </section>
          ) : outpaint ? (
            <section className="nv-reframe-guide">
              <h2>REFRAME ANY VIDEO</h2>
              <p>Generate the missing canvas while retaining the fitted source region.</p>
              <div>
                {['Upload your clip', 'Pick an aspect ratio', 'Generate & export'].map(
                  (title, index) => (
                    <article key={title}>
                      <img
                        src={`https://static.higgsfield.ai/reframe-tutor/bottompieace${index ? index + 1 : ''}.webp`}
                        alt="Higgsfield reference illustration"
                      />
                      <h3>{title.toUpperCase()}</h3>
                      <p>
                        {
                          [
                            'Choose a video and an explicit source interval.',
                            'Select the output canvas. Adjust source scale and anchors in Advanced controls.',
                            'Review the generated canvas, then export the real video and ComfyUI workflow.',
                          ][index]
                        }
                      </p>
                    </article>
                  ),
                )}
              </div>
              <small>
                Reference illustrations. OpenFrame uses the model and limits shown in the composer.
              </small>
            </section>
          ) : (
            <section className="ft-guide">
              <video
                muted
                playsInline
                controls
                preload="metadata"
                src="https://static.higgsfield.ai/video-edit-tutorial/v4/relight-and-atmosphere.mp4"
              />
              <h2>{info.title.toUpperCase()}</h2>
              <p>{info.explanation}</p>
              <small>Public Higgsfield tutorial reference, not a generated OpenFrame result.</small>
            </section>
          )}
        </div>
      </section>
      {menu && (
        <AnchoredPopover
          anchor={menu.anchor}
          label={menu.name}
          width={menu.name === 'duration' ? 300 : 230}
          onClose={() => setMenu(null)}
          className="nv-popover"
        >
          <h3>{menu.name === 'duration' ? 'Output duration' : menu.name}</h3>
          {menu.name === 'duration' ? (
            <>
              <strong>{outputDuration.toFixed(3)} seconds</strong>
              <input
                aria-label="Output frames"
                type="range"
                min={minFrames}
                max={maxFrames}
                step={multiple}
                value={state.frames}
                onChange={(event) =>
                  session.update({ frames: Number(event.target.value), exr_confirmed: false })
                }
              />
              <label>
                Exact frames
                <input
                  type="number"
                  min={minFrames}
                  max={maxFrames}
                  step={multiple}
                  value={state.frames}
                  onChange={(event) =>
                    session.update({ frames: Number(event.target.value), exr_confirmed: false })
                  }
                />
              </label>
              <small>
                {semantic
                  ? 'Source frame rate retained.'
                  : `${multiple}n + 1 frames at ${fps} fps.`}{' '}
                {extend && 'Includes source context; the remainder is new footage.'}
              </small>
            </>
          ) : (
            (menu.name === 'ratio'
              ? ['16:9', '9:16', '4:3', '3:4', '1:1', '21:9'].map((value) => ({
                  value,
                  label: value,
                }))
              : menu.name === 'quality'
                ? [512, 768, 1024, 1536, 1920, ...(maxSide > 1920 ? [2048, 3840] : [])]
                    .filter((value) => value <= maxSide)
                    .map((value) => ({ value: String(value), label: `${value}px longest side` }))
                : menu.name === 'model'
                  ? models.map((item) => ({ value: item.id, label: item.name }))
                  : menu.name === 'direction'
                    ? [
                        { value: 'sequel', label: 'Sequel · after context' },
                        { value: 'prequel', label: 'Prequel · before context' },
                      ]
                    : menu.name === 'method'
                      ? [
                          { value: 'pixel-2x', label: 'Pixel 2× · native geometry' },
                          { value: 'tiled-refine', label: 'Tiled detail refinement' },
                        ]
                      : [
                          { value: 'hevc10', label: 'HEVC · 10-bit HLG' },
                          { value: 'prores10', label: 'ProRes 422 HQ · 10-bit HLG' },
                          { value: 'exr16', label: 'EXR · 16-bit image sequence' },
                        ]
            ).map((item) => (
              <button
                key={item.value}
                onClick={() => {
                  if (menu.name === 'ratio') resize(item.value);
                  else if (menu.name === 'quality') resize(state.ratio, Number(item.value));
                  else if (menu.name === 'model') session.update({ model_id: item.value });
                  else if (menu.name === 'direction')
                    session.update({
                      extension_direction: item.value as State['extension_direction'],
                    });
                  else if (menu.name === 'method')
                    session.update({
                      upscale_mode: item.value as State['upscale_mode'],
                      ...(model ? renderSize(model, state.ratio, state.longest) : {}),
                    });
                  else
                    session.update({
                      hdr_output_format: item.value as State['hdr_output_format'],
                      exr_confirmed: false,
                    });
                  setMenu(null);
                }}
              >
                {item.label}
              </button>
            ))
          )}
        </AnchoredPopover>
      )}
      {picker && (
        <AssetPicker
          kind="video"
          title={`Choose video for ${info.title}`}
          assets={assets.assets}
          onClose={() => setPicker(false)}
          onSelect={choose}
          onAdded={assets.add}
          jobs={session.jobs}
        />
      )}
      {selected && (
        <ResultDialog
          job={session.jobs.find((item) => item.id === selected.id) || selected}
          preferredOutputRole={alpha ? state.output_view : undefined}
          onClose={() => setSelected(null)}
          onRefresh={() => void session.refreshJobs()}
          onReuse={() => void reuse(selected)}
        />
      )}
    </main>
  );
}
