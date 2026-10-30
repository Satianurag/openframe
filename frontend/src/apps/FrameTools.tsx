import { useEffect, useState } from 'react';
import { api, mediaUrl, post } from '../api';
import { Icon } from '../Icon';
import { AnchoredPopover } from '../Popovers';
import type { Asset, Job, JobRequest } from '../types';
import type { AppDocument } from './registry';
import { useAppDocument } from './useAppDocument';
import { renderRequest } from './renderRequest';
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

type Tool = 'fps-boost' | 'video-depth';
type State = {
  kind: Tool;
  source_asset_id: string;
  model_id: string;
  trim_start: number;
  input_frames: number;
  output_fps: number;
  resolution: number;
  depth_colormap: NonNullable<JobRequest['depth_colormap']>;
  depth_side_by_side: boolean;
  depth_inference_mode: NonNullable<JobRequest['depth_inference_mode']>;
  preserve_audio: boolean;
  encoding_quality: 'legacy' | 'standard' | 'high';
  seed: number;
};
const defaults = (tool: Tool): State => ({
  kind: tool,
  source_asset_id: '',
  model_id: '',
  trim_start: 0,
  input_frames: tool === 'video-depth' ? 300 : 97,
  output_fps: 60,
  resolution: 0,
  depth_colormap: 'grayscale',
  depth_side_by_side: false,
  depth_inference_mode: 'chunk',
  preserve_audio: true,
  encoding_quality: 'high',
  seed: -1,
});
const ids = (value: State) => (value.source_asset_id ? [value.source_asset_id] : []);
const colors = [
  { id: 'grayscale', name: 'Grayscale', gradient: '#111,#eee' },
  { id: 'turbo', name: 'Turbo', gradient: '#30123b,#3586f5,#38df62,#f5df45,#d52e0c' },
  { id: 'inferno', name: 'Inferno', gradient: '#000004,#57106e,#bc3754,#f98e09,#fcffa4' },
  { id: 'magma', name: 'Magma', gradient: '#000004,#51127c,#b63679,#fb8861,#fcfdbf' },
  { id: 'viridis', name: 'Viridis', gradient: '#440154,#3b528b,#21918c,#5ec962,#fde725' },
] as const;
export function FPSBoost(props: EngineAppProps) {
  return <FrameTool {...props} tool="fps-boost" />;
}
export function DepthMap(props: EngineAppProps) {
  return <FrameTool {...props} tool="video-depth" />;
}

function FrameTool({ tool, catalog, settings, onSettings }: EngineAppProps & { tool: Tool }) {
  const session = useAppDocument(
    'mini-apps',
    defaults(tool),
    ids,
    tool,
    tool === 'video-depth' ? 'Depth Map' : 'FPS Boost',
  );
  const state = { ...defaults(tool), ...session.state };
  const workspace = useWorkspaceAssets(ids(state));
  const source = workspace.get(state.source_asset_id);
  const effect = catalog.effects.find((item) => item.id === tool);
  const models = catalog.models.filter((item) => effect?.model_ids.includes(item.id));
  const model =
    models.find((item) => item.id === state.model_id) ||
    (!state.model_id
      ? models.find((item) => item.id === effect?.default_model_id) || models[0]
      : undefined);
  const provider = settings.default_provider || 'local';
  const depth = tool === 'video-depth';
  const title = depth ? 'Depth Map' : 'FPS Boost';
  const description = depth
    ? 'Make a depth map from video'
    : 'Increase frame rate with interpolation';
  const [picker, setPicker] = useState(false);
  const [view, setView] = useState<'guide' | 'history' | 'source'>('guide');
  const [menu, setMenu] = useState<{
    name: 'fps' | 'resolution' | 'frames';
    anchor: HTMLElement;
  } | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<Job | null>(null);
  const sourceFps = source?.fps || 0;
  const available = Math.max(
    0,
    Math.floor(((source?.duration || 0) - state.trim_start) * sourceFps + 1e-6),
  );
  const maxInput = Number(depth ? model?.max_frames || 300 : model?.max_input_frames || 241);
  const inputFrames = Math.min(state.input_frames, available);
  const depthModes = (model?.depth_inference_modes as string[] | undefined) || [];
  const offlineLimit = Number(model?.depth_offline_max_frames || 64);
  const offline = depth && state.depth_inference_mode === 'offline';
  const selectedMaxInput = offline ? Math.min(maxInput, offlineLimit) : maxInput;
  const offlineIssue = offline
    ? !depthModes.includes('offline')
      ? 'Choose a compatible model for offline depth inference.'
      : state.input_frames > offlineLimit
        ? `Offline depth supports up to ${offlineLimit} source frames. Reduce Maximum source frames or choose Chunked mode.`
        : ''
    : '';
  const outputFrames = depth
    ? inputFrames
    : sourceFps
      ? Math.floor(((inputFrames - 1) / sourceFps) * state.output_fps + 1e-9) + 1
      : 0;
  const outputFps = depth ? sourceFps : state.output_fps;
  const inputDuration = sourceFps ? inputFrames / sourceFps : 0;
  const outputDuration = outputFps ? outputFrames / outputFps : 0;
  const limits = model?.default_task_limits as
    { max_long_side?: number; max_pixels?: number } | undefined;
  const maxSide =
    limits?.max_long_side ||
    Math.max(Number(model?.max_width || 1280), Number(model?.max_height || 1280));
  const maxPixels = limits?.max_pixels || 921600;
  function dimensions(resolution = state.resolution) {
    const w = source?.width || 1280,
      h = source?.height || 720;
    if (!depth) return { width: w, height: h };
    const scale = resolution
      ? resolution / Math.min(w, h)
      : Math.min(1, maxSide / Math.max(w, h), Math.sqrt(maxPixels / (w * h)));
    return { width: Math.round((w * scale) / 2) * 2, height: Math.round((h * scale) / 2) * 2 };
  }
  const size = dimensions();
  const validSize = (value: { width: number; height: number }) =>
    value.width >= Number(model?.min_width || 64) &&
    value.height >= Number(model?.min_height || 64) &&
    value.width <= Number(model?.max_width || 1280) &&
    value.height <= Number(model?.max_height || 1280) &&
    (!depth || value.width * value.height <= maxPixels) &&
    value.width % 2 === 0 &&
    value.height % 2 === 0;
  const jobs = session.jobs.filter((job) => job.request.effect_id === tool);
  const heroSlug = depth ? 'depth-map' : 'fps-booster';
  const hero = {
    title: `${title} reference`,
    poster: `https://static.higgsfield.ai/video-edit-form/v2/tools-hero/${heroSlug}-poster.webp`,
    video: `https://static.higgsfield.ai/video-edit-form/v2/tools-hero/${heroSlug}.mp4`,
  };
  function choose(asset: Asset) {
    workspace.add(asset);
    const fps = asset.fps || 0;
    const total = Math.floor((asset.duration || 0) * fps + 1e-6);
    session.update({
      source_asset_id: asset.id,
      trim_start: 0,
      input_frames: depth ? maxInput : Math.max(2, Math.min(97, maxInput, total)),
      output_fps: depth
        ? state.output_fps
        : [60, 90, 120].find((rate) => rate > fps && rate <= fps * 16) || 60,
    });
    setError('');
    setView('source');
  }
  async function generate() {
    setBusy(true);
    setError('');
    try {
      if (!source || source.kind !== 'video' || !sourceFps)
        throw new Error('Choose a source video with a known frame rate.');
      if (!model) throw new Error('Choose an available model for this tool.');
      if (!['local'].includes(provider))
        throw new Error(
          'Select a supported local ComfyUI connection for this tool.',
        );
      if (
        !Number.isInteger(state.input_frames) ||
        state.input_frames < 2 ||
        state.input_frames > maxInput ||
        inputFrames < 2
      )
        throw new Error(`Select from 2 to ${maxInput} source frames within the clip.`);
      if (offlineIssue) throw new Error(offlineIssue);
      if (!validSize(size))
        throw new Error(
          depth
            ? `Choose a resolution within this model’s ${maxSide}px and ${maxPixels.toLocaleString()}-pixel canvas limits.`
            : 'FPS Boost preserves native even dimensions, up to 1280 pixels per axis. Resize the source in Reframe first.',
        );
      if (
        !depth &&
        !(sourceFps < state.output_fps && state.output_fps <= Math.min(120, sourceFps * 16))
      )
        throw new Error('The output rate must exceed the source and stay within 16× and 120 FPS.');
      const document = await session.save(true);
      if (!document) throw new Error('Save the project before generating.');
      const request = renderRequest(model, {
        effect_id: tool,
        provider,
        prompt: '',
        seed: state.seed,
        source_asset_id: source.id,
        ...size,
        trim_start: state.trim_start,
        frames: outputFrames,
        fps: outputFps,
        preserve_audio: state.preserve_audio,
        encoding_quality: state.encoding_quality,
        ...(depth
          ? {
              depth_colormap: state.depth_colormap,
              depth_side_by_side: state.depth_side_by_side,
              depth_inference_mode: state.depth_inference_mode,
            }
          : { input_frames: inputFrames, input_fps: sourceFps }),
      });
      const job = await post<Job>(`/apps/mini-apps/documents/${document.id}/jobs`, {
        expected_revision: document.revision,
        operation: tool,
        request,
      });
      setSelected(job);
      setView('history');
      await session.refreshJobs();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reuse(job: Job) {
    try {
      if (job.request.effect_id !== tool) throw new Error('This result belongs to another tool.');
      const context = job.app_context
        ? await api<{ document_snapshot: AppDocument<State> }>(`/jobs/${job.id}/app-context`)
        : null;
      const r = job.request;
      await session.newDocument(
        context
          ? {
              ...defaults(tool),
              ...context.document_snapshot.state,
              model_id: r.model_id,
              seed: r.seed,
            }
          : {
              ...defaults(tool),
              source_asset_id: r.source_asset_id || '',
              model_id: r.model_id,
              seed: r.seed,
              trim_start: r.trim_start,
              input_frames: depth ? r.frames : r.input_frames || 97,
              output_fps: r.fps,
              resolution: depth ? Math.min(r.width, r.height) : 0,
              depth_colormap: r.depth_colormap || 'grayscale',
              depth_side_by_side: !!r.depth_side_by_side,
              depth_inference_mode: r.depth_inference_mode || 'chunk',
              preserve_audio: r.preserve_audio,
              encoding_quality: r.encoding_quality || 'high',
            },
      );
      setView('source');
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
        if (asset.kind !== 'video') throw new Error('Choose a video source.');
        workspace.add(asset);
        const value = {
          ...defaults(tool),
          source_asset_id: asset.id,
          input_frames: depth
            ? 300
            : Math.max(2, Math.min(97, Math.floor((asset.duration || 0) * (asset.fps || 0)))),
        };
        if (await session.newDocument(value)) {
          const url = new URL(location.href);
          url.searchParams.delete('source');
          url.searchParams.delete('document');
          history.replaceState(null, '', url);
          setView('source');
        }
      })
      .catch((reason) => setError(reason.message));
    return () => {
      active = false;
    };
  }, [session.ready, tool]);
  useEffect(() => {
    const jobId = new URLSearchParams(location.search).get('job');
    if (!jobId || !session.ready) return;
    let active = true;
    void api<Job>(`/jobs/${encodeURIComponent(jobId)}`)
      .then(async (job) => {
        if (!active) return;
        await reuse(job);
        if (active) {
          const url = new URL(location.href);
          url.searchParams.delete('job');
          history.replaceState(null, '', url);
        }
      })
      .catch((reason) => setError(reason.message));
    return () => {
      active = false;
    };
  }, [session.ready, tool]);

  return (
    <main className="frame-tool-app">
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
            <ReferenceMedia item={hero} />
            <a href="/studio/vfx?view=edit">
              <Icon name="brush" size={13} />
              Change
            </a>
            <figcaption>
              <h1>{title}</h1>
              <p>{description}</p>
            </figcaption>
          </figure>
          <SourceSlot
            title={depth ? 'Add a video to create a depth map' : 'Add video to change fps'}
            detail={`Up to ${maxInput} source frames per job`}
            asset={source}
            onChoose={() => setPicker(true)}
            onClear={() => session.update({ source_asset_id: '' })}
          />
          {depth ? (
            <>
              <fieldset className="ft-colormaps">
                <legend>Color map</legend>
                <div>
                  {colors.map((color) => (
                    <label
                      key={color.id}
                      className={state.depth_colormap === color.id ? 'active' : ''}
                    >
                      <input
                        type="radio"
                        name="depth-colormap"
                        value={color.id}
                        checked={state.depth_colormap === color.id}
                        onChange={() => session.update({ depth_colormap: color.id })}
                      />
                      <i style={{ background: `linear-gradient(100deg,${color.gradient})` }} />
                      <span>{color.name}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <button
                className="ft-value"
                onClick={(event) => setMenu({ name: 'resolution', anchor: event.currentTarget })}
              >
                <span>
                  <small>Resolution</small>
                  {state.resolution ? `${state.resolution}p` : 'Auto'}
                </span>
                <Icon name="chevron" size={15} />
              </button>
              <button
                className="ft-value"
                onClick={(event) => setMenu({ name: 'frames', anchor: event.currentTarget })}
              >
                <span>
                  <small>Max frames</small>
                  {state.input_frames}
                </span>
                <Icon name="chevron" size={15} />
              </button>
              {!depth && (
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
              <label className="ft-switch">
                Side by side
                <input
                  type="checkbox"
                  checked={state.depth_side_by_side}
                  onChange={(event) => session.update({ depth_side_by_side: event.target.checked })}
                />
              </label>
            </>
          ) : (
            <button
              className="ft-value"
              onClick={(event) => setMenu({ name: 'fps', anchor: event.currentTarget })}
            >
              <span>
                <small>Frame rate</small>
                {state.output_fps} FPS
              </span>
              <Icon name="chevron" size={15} />
            </button>
          )}
          <button
            className="ft-advanced-toggle"
            onClick={() => setAdvanced(!advanced)}
            aria-expanded={advanced}
          >
            Advanced · interval and model
            <Icon name="chevron" size={13} />
          </button>
          {advanced && (
            <section className="ft-advanced">
              <label>
                Model
                <select
                  value={model?.id || state.model_id}
                  onChange={(event) => {
                    const next = models.find((item) => item.id === event.target.value);
                    const modes = (next?.depth_inference_modes as string[] | undefined) || [];
                    session.update({
                      model_id: event.target.value,
                      depth_inference_mode: modes.includes(state.depth_inference_mode)
                        ? state.depth_inference_mode
                        : 'chunk',
                    });
                  }}
                >
                  {!model && <option value={state.model_id}>Choose a compatible model</option>}
                  {models.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              {depth && depthModes.includes('offline') && (
                <label>
                  Temporal context
                  <select
                    value={state.depth_inference_mode}
                    onChange={(event) =>
                      session.update({
                        depth_inference_mode: event.target.value as State['depth_inference_mode'],
                      })
                    }
                  >
                    <option value="chunk">Chunked · longer clips</option>
                    <option value="offline">
                      Offline · whole clip · up to {offlineLimit} frames
                    </option>
                  </select>
                  <small>
                    Offline mode considers all selected frames together. This app allows at most{' '}
                    {offlineLimit} frames to use it.
                  </small>
                </label>
              )}
              {!!model?.research_only && (
                <p className="ft-research">
                  Research / noncommercial weights · {String(model.license)}
                </p>
              )}
              <label>
                Start time · seconds
                <input
                  type="number"
                  min={0}
                  step={0.001}
                  max={source?.duration || 0}
                  value={state.trim_start}
                  onChange={(event) => session.update({ trim_start: Number(event.target.value) })}
                />
              </label>
              <label>
                {depth ? 'Maximum source frames' : 'Source frames'}
                <input
                  type="number"
                  min={2}
                  max={selectedMaxInput}
                  step={1}
                  value={state.input_frames}
                  onChange={(event) => session.update({ input_frames: Number(event.target.value) })}
                />
              </label>
              <label className="ft-switch">
                Keep source audio{depth ? ' in preview' : ''}
                <input
                  type="checkbox"
                  checked={state.preserve_audio}
                  onChange={(event) => session.update({ preserve_audio: event.target.checked })}
                />
              </label>
              <label>
                Encoding
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
                  <option value="high">High · larger file</option>
                  <option value="standard">Standard · smaller file</option>
                </select>
              </label>
              <button onClick={onSettings}>
                Compute: {catalog.providers.find((item) => item.id === provider)?.name || provider}
              </button>
            </section>
          )}
          {source && (
            <p className="ft-interval">
              {state.trim_start.toFixed(3)}–{(state.trim_start + inputDuration).toFixed(3)}s ·{' '}
              {inputFrames} source frames at {sourceFps.toFixed(3).replace(/\.?0+$/, '')} FPS
              <br />
              {outputFrames} output frames · {outputDuration.toFixed(3)}s<br />
              {size.width} × {size.height}
              {depth && state.depth_side_by_side
                ? ` map · ${size.width * 2} × ${size.height} viewing preview`
                : ''}
            </p>
          )}
          {!depth && source && !validSize(size) && (
            <a className="ft-resize-link" href={`/apps/video-reframe?source=${source.id}`}>
              Resize source in Reframe
              <Icon name="arrow" size={13} />
            </a>
          )}
          <p className="ft-limits">
            {depth
              ? `Current model limit: ${maxInput} frames, ${maxSide}px longest side. Depth is relative, not metres.`
              : 'Native even source dimensions up to 1280px per axis. Interpolation retains source motion timing; it is not slow motion.'}
          </p>
          {(offlineIssue || error || session.error || workspace.error) && (
            <p className="ft-error" role="alert">
              {offlineIssue || error || session.error || workspace.error}
            </p>
          )}
        </div>
        <footer>
          <button
            disabled={busy || !source || !model || !session.ready || !!offlineIssue}
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
              Source interval
            </button>
          )}
          <div />
          <button onClick={() => void session.newDocument(defaults(tool))}>New project</button>
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
              <video
                key={source.id}
                src={mediaUrl(source)}
                controls
                playsInline
                preload="metadata"
                onLoadedMetadata={(event) => {
                  event.currentTarget.currentTime = state.trim_start;
                }}
                onTimeUpdate={(event) => {
                  if (event.currentTarget.currentTime > state.trim_start + inputDuration)
                    event.currentTarget.pause();
                }}
              />
              <h2>{title}</h2>
              <p>
                {depth
                  ? 'The model estimates a temporally consistent relative depth map. Colormap and side-by-side controls affect the viewing preview; the raw 16-bit depth file remains separate.'
                  : 'Intermediate images are generated between the selected source frames. The exact target rate is sampled from those generated timestamps; no frames are merely duplicated.'}
              </p>
              <p>
                {depth
                  ? 'Auto resolution fits the native aspect ratio within the selected model’s size and pixel limits.'
                  : `The output ends one target-frame interval after the last selected source frame, so its duration (${outputDuration.toFixed(3)}s) may be slightly shorter than the selected input interval.`}
              </p>
            </section>
          ) : (
            <section className="ft-guide">
              <ReferenceMedia item={hero} />
              <h2>{title}</h2>
              <p>
                Higgsfield {title} reference preview. This is reference footage, not an output
                generated by OpenFrame.
              </p>
              <div className="ft-operation-note">
                <h3>{title}</h3>
                <p>
                  {depth
                    ? 'Upload your video, choose a colormap and output resolution, then generate relative depth. Download the viewing MP4 and the lossless 16-bit FFV1 depth file with clip-global scale metadata.'
                    : 'Upload your video, choose a frame rate above its original rate, then select the interval in Advanced. The actual LDF-VFI model generates intermediate frames on your Local ComfyUI host.'}
                </p>
              </div>
            </section>
          )}
        </div>
      </section>
      {picker && (
        <AssetPicker
          kind="video"
          title={`Choose video for ${title}`}
          assets={workspace.assets}
          jobs={session.jobs}
          onAdded={workspace.add}
          onSelect={choose}
          onClose={() => setPicker(false)}
        />
      )}
      {menu && (
        <AnchoredPopover
          anchor={menu.anchor}
          label={
            menu.name === 'fps'
              ? 'Frame rate'
              : menu.name === 'frames'
                ? 'Max frames'
                : 'Resolution'
          }
          onClose={() => setMenu(null)}
          width={menu.name === 'frames' ? 260 : 180}
          className="ft-popover"
        >
          {menu.name === 'fps' ? (
            [24, 30, 60, 90, 120].map((rate) => (
              <button
                key={rate}
                disabled={!!source && !(rate > sourceFps && rate <= sourceFps * 16)}
                onClick={() => {
                  session.update({ output_fps: rate });
                  setMenu(null);
                }}
              >
                {rate} FPS{state.output_fps === rate && <Icon name="check" size={14} />}
              </button>
            ))
          ) : menu.name === 'resolution' ? (
            [0, 360, 480, 720, 1080].map((value) => (
              <button
                key={value}
                disabled={!!source && !validSize(dimensions(value))}
                title={
                  value && source && !validSize(dimensions(value))
                    ? `Exceeds the selected model’s ${maxSide}px/pixel limits`
                    : undefined
                }
                onClick={() => {
                  session.update({ resolution: value });
                  setMenu(null);
                }}
              >
                {value ? `${value}p` : 'Auto'}
                {state.resolution === value && <Icon name="check" size={14} />}
              </button>
            ))
          ) : (
            <label>
              Max frames · {state.input_frames}
              <input
                type="range"
                min={2}
                max={selectedMaxInput}
                step={1}
                value={state.input_frames}
                onChange={(event) => session.update({ input_frames: Number(event.target.value) })}
              />
              <small>
                Up to {selectedMaxInput} frames in this mode; the available source interval may be
                shorter.
              </small>
            </label>
          )}
        </AnchoredPopover>
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
