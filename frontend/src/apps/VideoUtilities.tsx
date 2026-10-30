import { useEffect, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import { api, mediaUrl, post } from '../api';
import { Icon } from '../Icon';
import type { Asset, Job } from '../types';
import type { AppDocument } from './registry';
import { useAppDocument } from './useAppDocument';
import { renderRequest } from './renderRequest';
import {
  AssetPicker,
  ResultDialog,
  SourceSlot,
  useWorkspaceAssets,
  WorkspaceHistory,
} from './engine-apps-shared';
import type { EngineAppProps } from './engine-apps-shared';
import './video-utilities.css';

type Tool = 'trim-video' | 'video-reframe';
type State = {
  kind: Tool;
  source_asset_id: string;
  trim_start: number;
  trim_end: number;
  width: number;
  height: number;
  reframe_fit: 'crop' | 'pad';
  anchor_x: number;
  anchor_y: number;
  encoding_quality: 'legacy' | 'standard' | 'high';
  preserve_audio: boolean;
};
const defaults = (tool: Tool): State => ({
  kind: tool,
  source_asset_id: '',
  trim_start: 0,
  trim_end: 0,
  width: 1920,
  height: 1080,
  reframe_fit: 'crop',
  anchor_x: 0.5,
  anchor_y: 0.5,
  encoding_quality: 'high',
  preserve_audio: true,
});
const clamp = (value: number, minimum = 0, maximum = 1) =>
  Math.max(minimum, Math.min(maximum, value));
const even = (value: number) => Math.max(64, Math.min(4096, Math.round(value / 2) * 2));
const initialFor = (tool: Tool, asset: Asset): State => ({
  ...defaults(tool),
  source_asset_id: asset.id,
  trim_end: asset.duration || 0,
  width: even(asset.width || 1920),
  height: even(asset.height || 1080),
});
const assetIds = (value: State) => (value.source_asset_id ? [value.source_asset_id] : []);

export function TrimVideo(props: EngineAppProps) {
  return <VideoUtility {...props} tool="trim-video" />;
}
export function ReframeVideo(props: EngineAppProps) {
  return <VideoUtility {...props} tool="video-reframe" />;
}

function VideoUtility({ tool, catalog, settings, onSettings }: EngineAppProps & { tool: Tool }) {
  const initial = useRef(defaults(tool));
  const session = useAppDocument(
    'mini-apps',
    initial.current,
    assetIds,
    tool,
    tool === 'trim-video' ? 'Trim Video' : 'Crop / Pad Video',
  );
  const state = { ...initial.current, ...session.state };
  const assets = useWorkspaceAssets(assetIds(state));
  const source = assets.get(state.source_asset_id);
  const [picker, setPicker] = useState(false);
  const [selected, setSelected] = useState<Job | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [playingSelection, setPlayingSelection] = useState(false);
  const [previewTime, setPreviewTime] = useState(0);
  const video = useRef<HTMLVideoElement>(null);
  const frameTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const title = tool === 'trim-video' ? 'Trim Video' : 'Reframe';
  const model = catalog.models.find((item) => item.id === 'video-tools');
  const provider = settings.default_provider || 'local';
  const fps = source?.fps || 0;
  const frames = fps
    ? Math.max(0, Math.floor((state.trim_end - state.trim_start) * fps + 1e-6))
    : 0;
  const duration = fps ? frames / fps : 0;
  const end = state.trim_start + duration;
  const originalWidth = source?.width || 1920,
    originalHeight = source?.height || 1080;
  const outputWidth = tool === 'trim-video' ? originalWidth : state.width;
  const outputHeight = tool === 'trim-video' ? originalHeight : state.height;
  const canvasWidth = Math.max(64, Math.min(4096, state.width || 64));
  const canvasHeight = Math.max(64, Math.min(4096, state.height || 64));
  const scale = Math.max(canvasWidth / originalWidth, canvasHeight / originalHeight);
  const cropWidth = canvasWidth / scale,
    cropHeight = canvasHeight / scale;
  const cropX = (originalWidth - cropWidth) * state.anchor_x;
  const cropY = (originalHeight - cropHeight) * state.anchor_y;
  const padScale = Math.min(canvasWidth / originalWidth, canvasHeight / originalHeight);
  const padWidth = (originalWidth * padScale) / canvasWidth;
  const padHeight = (originalHeight * padScale) / canvasHeight;
  const jobs = session.jobs.filter((job) => job.request.effect_id === tool);
  const available = session.application?.operations.find((item) => item.id === tool)?.available;
  useEffect(() => {
    if (frameTimer.current) clearTimeout(frameTimer.current);
    frameTimer.current = setTimeout(() => setPreviewTime(state.trim_start), 250);
    return () => {
      if (frameTimer.current) clearTimeout(frameTimer.current);
    };
  }, [state.trim_start, state.source_asset_id]);
  useEffect(() => {
    const id = new URLSearchParams(location.search).get('source');
    if (!id || !session.ready) return;
    let active = true;
    api<Asset>(`/assets/${encodeURIComponent(id)}`)
      .then(async (asset) => {
        if (!active) return;
        if (asset.kind !== 'video') throw new Error('This tool needs a video source.');
        assets.add(asset);
        const document = await session.newDocument(initialFor(tool, asset));
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
  }, [session.ready, tool]);
  useEffect(() => {
    const id = new URLSearchParams(location.search).get('job');
    if (!id || !session.ready) return;
    let active = true;
    api<Job>(`/jobs/${encodeURIComponent(id)}`)
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
  function choose(asset: Asset) {
    assets.add(asset);
    session.update(initialFor(tool, asset));
    setError('');
    setPlayingSelection(false);
  }
  function setIn(value: number) {
    const aligned = fps ? Math.round(value * fps) / fps : value;
    session.update({ trim_start: clamp(aligned, 0, Math.max(0, state.trim_end - 1 / (fps || 1))) });
  }
  function setOut(value: number) {
    const aligned = fps ? Math.round(value * fps) / fps : value;
    session.update({
      trim_end: clamp(aligned, state.trim_start + 1 / (fps || 1), source?.duration || value),
    });
  }
  function position(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = clamp((event.clientX - rect.left) / rect.width),
      y = clamp((event.clientY - rect.top) / rect.height);
    session.update(
      state.reframe_fit === 'crop'
        ? {
            anchor_x:
              originalWidth === cropWidth
                ? 0.5
                : clamp((x * originalWidth - cropWidth / 2) / (originalWidth - cropWidth)),
            anchor_y:
              originalHeight === cropHeight
                ? 0.5
                : clamp((y * originalHeight - cropHeight / 2) / (originalHeight - cropHeight)),
          }
        : {
            anchor_x: padWidth >= 0.999999 ? 0.5 : clamp((x - padWidth / 2) / (1 - padWidth)),
            anchor_y: padHeight >= 0.999999 ? 0.5 : clamp((y - padHeight / 2) / (1 - padHeight)),
          },
    );
  }
  function setRatio(ratio: string) {
    const [w, h] = ratio.split(':').map(Number);
    const longest = Math.min(4096, Math.max(state.width, state.height));
    session.update(
      w >= h
        ? { width: even(longest), height: even((longest * h) / w) }
        : { width: even((longest * w) / h), height: even(longest) },
    );
  }
  async function generate() {
    setError('');
    if (!source || !model) return;
    setBusy(true);
    try {
      if (!available)
        throw new Error('This video operation is not available on the connected backend.');
      if (provider !== 'local')
        throw new Error('Choose Local ComfyUI for this CPU video operation.');
      if (!Number.isFinite(fps) || fps <= 0)
        throw new Error('The source frame rate is unavailable. Upload a readable video.');
      if (
        !frames ||
        !Number.isFinite(frames) ||
        state.trim_start < 0 ||
        end > (source.duration || 0) + 0.001
      )
        throw new Error('Choose an interval of at least one frame within the source video.');
      if (
        ![outputWidth, outputHeight].every(
          (value) => Number.isInteger(value) && value >= 64 && value <= 4096 && value % 2 === 0,
        )
      )
        throw new Error(
          tool === 'trim-video'
            ? 'This source has unsupported H.264 dimensions. Use Reframe to choose even dimensions between 64 and 4096 pixels.'
            : 'Use even output dimensions from 64 to 4096 pixels.',
        );
      const document = await session.save(true);
      if (!document) throw new Error('Save the draft before creating the clip.');
      const request = renderRequest(model, {
        effect_id: tool,
        provider,
        prompt: '',
        source_asset_id: source.id,
        frames,
        fps,
        trim_start: state.trim_start,
        width: outputWidth,
        height: outputHeight,
        preserve_audio: state.preserve_audio,
        reframe_fit: state.reframe_fit,
        anchor_x: state.anchor_x,
        anchor_y: state.anchor_y,
        encoding_quality: state.encoding_quality,
      });
      const job = await post<Job>(`/apps/mini-apps/documents/${document.id}/jobs`, {
        expected_revision: document.revision,
        operation: tool,
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
      if (job.request.effect_id !== tool)
        throw new Error('This result belongs to a different video tool.');
      const context = job.app_context
        ? await api<{ document_snapshot: AppDocument<State> }>(`/jobs/${job.id}/app-context`)
        : null;
      const request = job.request;
      await session.newDocument(
        context
          ? { ...initial.current, ...context.document_snapshot.state, kind: tool }
          : {
              ...defaults(tool),
              source_asset_id: request.source_asset_id || '',
              trim_start: request.trim_start,
              trim_end: request.trim_start + request.frames / request.fps,
              width: request.width,
              height: request.height,
              anchor_x: request.anchor_x ?? 0.5,
              anchor_y: request.anchor_y ?? 0.5,
              reframe_fit: request.reframe_fit || 'crop',
              encoding_quality: request.encoding_quality || 'high',
              preserve_audio: request.preserve_audio,
            },
      );
      setShowHistory(false);
    } catch (reason) {
      setError((reason as Error).message);
    }
  }
  const sourceFrame = source ? `/api/assets/${source.id}/frame?time=${previewTime.toFixed(4)}` : '';
  return (
    <main className={`video-utility ${tool}`}>
      <nav className="vu-breadcrumb">
        <a href="/apps">Apps</a>
        <span>/</span>
        <strong>{title}</strong>
        <div />
        <button
          className={showHistory ? 'active' : ''}
          onClick={() => setShowHistory((value) => !value)}
        >
          My generations
        </button>
        <button onClick={() => void session.newDocument(defaults(tool))}>New project</button>
        <button onClick={onSettings}>
          <Icon name="settings" size={16} />{' '}
          {provider === 'local'
              ? 'Local ComfyUI · CPU'
              : 'Saved connection unavailable'}
        </button>
      </nav>
      {showHistory ? (
        <section className="vu-history">
          <h1>{title} generations</h1>
          <WorkspaceHistory
            jobs={jobs}
            total={jobs.length + (session.jobs.length < session.jobTotal ? 1 : 0)}
            onSelect={setSelected}
            onMore={session.loadMoreJobs}
          />
          <p>Matching results from {session.jobs.length} loaded app generations.</p>
        </section>
      ) : (
        <div className="vu-layout">
          <aside className="vu-controls">
            <h1>{title}</h1>
            <p>
              {tool === 'trim-video'
                ? 'Select the exact part of your video to keep.'
                : 'Fit your footage to a new canvas with precise framing.'}
            </p>
            <SourceSlot
              title="Source video"
              asset={source}
              onChoose={() => setPicker(true)}
              onClear={() => session.update({ source_asset_id: '', trim_start: 0, trim_end: 0 })}
            />
            {source && (
              <div className="vu-source-info">
                {originalWidth} × {originalHeight} · {fps.toFixed(3).replace(/\.?0+$/, '')} fps ·{' '}
                {(source.duration || 0).toFixed(3)}s
              </div>
            )}
            <fieldset disabled={!source}>
              <legend>Selected interval</legend>
              <div className="vu-field-pair">
                <label>
                  Start · seconds
                  <input
                    type="number"
                    min={0}
                    max={state.trim_end}
                    step={fps ? 1 / fps : 0.01}
                    value={Number(state.trim_start.toFixed(6))}
                    onChange={(event) => setIn(Number(event.target.value))}
                  />
                </label>
                <label>
                  End · seconds
                  <input
                    type="number"
                    min={state.trim_start}
                    max={source?.duration || 0}
                    step={fps ? 1 / fps : 0.01}
                    value={Number(state.trim_end.toFixed(6))}
                    onChange={(event) => setOut(Number(event.target.value))}
                  />
                </label>
              </div>
              <label className="vu-timeline-label">
                In point
                <input
                  aria-label="In point"
                  type="range"
                  min={0}
                  max={source?.duration || 0}
                  step={fps ? 1 / fps : 0.01}
                  value={state.trim_start}
                  onChange={(event) => setIn(Number(event.target.value))}
                />
              </label>
              <label className="vu-timeline-label">
                Out point
                <input
                  aria-label="Out point"
                  type="range"
                  min={0}
                  max={source?.duration || 0}
                  step={fps ? 1 / fps : 0.01}
                  value={state.trim_end}
                  onChange={(event) => setOut(Number(event.target.value))}
                />
              </label>
              <small>
                {frames} frames · {duration.toFixed(3)} seconds · actual end {end.toFixed(3)}s
              </small>
            </fieldset>
            {tool === 'video-reframe' && (
              <fieldset>
                <legend>Canvas and framing</legend>
                <div className="vu-segmented">
                  <button
                    className={state.reframe_fit === 'crop' ? 'active' : ''}
                    onClick={() => session.update({ reframe_fit: 'crop' })}
                  >
                    Crop to fill
                  </button>
                  <button
                    className={state.reframe_fit === 'pad' ? 'active' : ''}
                    onClick={() => session.update({ reframe_fit: 'pad' })}
                  >
                    Fit with padding
                  </button>
                </div>
                <div className="vu-ratios">
                  {['16:9', '9:16', '1:1', '4:3', '3:4'].map((ratio) => (
                    <button key={ratio} onClick={() => setRatio(ratio)}>
                      {ratio}
                    </button>
                  ))}
                </div>
                <div className="vu-field-pair">
                  <label>
                    Width
                    <input
                      type="number"
                      min={64}
                      max={4096}
                      step={2}
                      value={state.width}
                      onChange={(event) => session.update({ width: Number(event.target.value) })}
                    />
                  </label>
                  <label>
                    Height
                    <input
                      type="number"
                      min={64}
                      max={4096}
                      step={2}
                      value={state.height}
                      onChange={(event) => session.update({ height: Number(event.target.value) })}
                    />
                  </label>
                </div>
                <label>
                  Horizontal · {Math.round(state.anchor_x * 100)}%
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.001}
                    value={state.anchor_x}
                    onChange={(event) => session.update({ anchor_x: Number(event.target.value) })}
                  />
                </label>
                <label>
                  Vertical · {Math.round(state.anchor_y * 100)}%
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.001}
                    value={state.anchor_y}
                    onChange={(event) => session.update({ anchor_y: Number(event.target.value) })}
                  />
                </label>
                <button
                  className="vu-reset"
                  onClick={() => session.update({ anchor_x: 0.5, anchor_y: 0.5 })}
                >
                  Centre framing
                </button>
                <small>
                  {state.reframe_fit === 'crop'
                    ? 'The highlighted area becomes the output. Framing is static throughout the clip.'
                    : 'Padding adds black canvas around the complete source. It does not generate new scenery.'}
                </small>
              </fieldset>
            )}
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
            <label className="vu-checkbox">
              <input
                type="checkbox"
                checked={state.preserve_audio}
                onChange={(event) => session.update({ preserve_audio: event.target.checked })}
              />
              Keep source audio
            </label>
            <p className="vu-note">
              Re-encodes at the source's reported frame rate. Variable-frame-rate inputs are
              normalized to that rate. No model weights or GPU are needed.
            </p>
            {(error || session.error || assets.error) && (
              <p className="ea-error" role="alert">
                {error || session.error || assets.error}
              </p>
            )}
            <button
              className="vu-generate"
              disabled={!source || !model || !available || busy || !session.ready}
              onClick={() => void generate()}
            >
              {busy ? 'Preparing…' : tool === 'trim-video' ? 'Create clip' : 'Reframe video'}
              <Icon name="arrow" size={17} />
            </button>
          </aside>
          <section className="vu-preview">
            {!source ? (
              <button className="vu-empty" onClick={() => setPicker(true)}>
                <Icon name="upload" size={40} />
                <h2>
                  {tool === 'trim-video' ? 'Choose your clip' : 'Bring a new frame to your video'}
                </h2>
                <p>Upload a video or choose from your workspace</p>
              </button>
            ) : (
              <>
                <header>
                  <h2>{tool === 'trim-video' ? 'Source preview' : 'Framing preview'}</h2>
                  <span>
                    {outputWidth} × {outputHeight}
                  </span>
                </header>
                {tool === 'trim-video' ? (
                  <>
                    <video
                      key={source.id}
                      ref={video}
                      src={mediaUrl(source)}
                      controls
                      playsInline
                      onTimeUpdate={() => {
                        if (playingSelection && video.current && video.current.currentTime >= end) {
                          video.current.pause();
                          setPlayingSelection(false);
                          if (video.current.currentTime > end) video.current.currentTime = end;
                        }
                      }}
                    />
                    <div className="vu-player-actions">
                      <button
                        onClick={() => {
                          if (video.current) {
                            video.current.currentTime = state.trim_start;
                            setPlayingSelection(true);
                            void video.current.play().catch(() => setPlayingSelection(false));
                          }
                        }}
                      >
                        <Icon name="play" size={16} />
                        Play selection
                      </button>
                      <button onClick={() => setIn(video.current?.currentTime || 0)}>
                        Mark start here
                      </button>
                      <button onClick={() => setOut(video.current?.currentTime || 0)}>
                        Mark end here
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="vu-framing-stage">
                      <div
                        className="vu-framing-plane"
                        style={{
                          aspectRatio:
                            state.reframe_fit === 'crop'
                              ? `${originalWidth}/${originalHeight}`
                              : `${canvasWidth}/${canvasHeight}`,
                          width: `min(100%, ${480 * (state.reframe_fit === 'crop' ? originalWidth / originalHeight : canvasWidth / canvasHeight)}px)`,
                        }}
                        onPointerDown={(event) => {
                          event.currentTarget.setPointerCapture(event.pointerId);
                          position(event);
                        }}
                        onPointerMove={(event) => {
                          if (event.buttons === 1) position(event);
                        }}
                      >
                        {state.reframe_fit === 'crop' ? (
                          <>
                            <img
                              src={sourceFrame}
                              alt="Source frame with selected crop"
                              draggable={false}
                            />
                            <svg
                              viewBox={`0 0 ${originalWidth} ${originalHeight}`}
                              preserveAspectRatio="none"
                            >
                              <defs>
                                <mask id="vu-crop-mask">
                                  <rect
                                    width={originalWidth}
                                    height={originalHeight}
                                    fill="white"
                                  />
                                  <rect
                                    x={cropX}
                                    y={cropY}
                                    width={cropWidth}
                                    height={cropHeight}
                                    fill="black"
                                  />
                                </mask>
                              </defs>
                              <rect
                                width={originalWidth}
                                height={originalHeight}
                                fill="#0009"
                                mask="url(#vu-crop-mask)"
                              />
                              <rect
                                x={cropX}
                                y={cropY}
                                width={cropWidth}
                                height={cropHeight}
                                fill="none"
                                stroke="#d1fe17"
                                strokeWidth={2}
                                vectorEffect="non-scaling-stroke"
                              />
                            </svg>
                          </>
                        ) : (
                          <img
                            src={sourceFrame}
                            alt="Source fitted on black padded canvas"
                            draggable={false}
                            style={{
                              position: 'absolute',
                              width: `${padWidth * 100}%`,
                              height: `${padHeight * 100}%`,
                              left: `${(1 - padWidth) * state.anchor_x * 100}%`,
                              top: `${(1 - padHeight) * state.anchor_y * 100}%`,
                            }}
                          />
                        )}
                      </div>
                    </div>
                    <p>
                      Drag to position the {state.reframe_fit === 'crop' ? 'crop' : 'source'}.
                      Preview shows the first selected source frame.
                    </p>
                  </>
                )}
                <div className="vu-output-summary">
                  <strong>{frames} frames</strong>
                  <span>
                    {state.trim_start.toFixed(3)}s → {end.toFixed(3)}s
                  </span>
                  <span>
                    {state.preserve_audio
                      ? 'Original audio retained when present'
                      : 'Silent output'}
                  </span>
                </div>
                {tool === 'trim-video' && (
                  <a href={`/apps/video-reframe?source=${source.id}`}>
                    Need a different aspect ratio? Open Reframe <Icon name="arrow" size={14} />
                  </a>
                )}
              </>
            )}
          </section>
        </div>
      )}
      {picker && (
        <AssetPicker
          kind="video"
          title="Choose source video"
          assets={assets.assets}
          onAdded={assets.add}
          jobs={session.jobs}
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
