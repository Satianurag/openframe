import { useRef, useState, type CSSProperties } from 'react';
import type { Asset, Job } from './types';
import { Icon } from './Icon';
import { mediaUrl, markDownloaded } from './api';
export function JobResult({
  job,
  source,
  onReuse,
  onExport,
  onFavorite,
  onError,
}: {
  job: Job;
  source?: Asset;
  onReuse: () => void;
  onExport: (kind: 'workflow' | 'canvas' | 'bundle') => void;
  onFavorite: () => void;
  onError: (error: string) => void;
}) {
  const [compare, setCompare] = useState(false);
  const [split, setSplit] = useState(50);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [length, setLength] = useState(job.request.frames / job.request.fps);
  const [muted, setMuted] = useState(false);
  const [speed, setSpeed] = useState(1);
  const player = useRef<HTMLDivElement>(null);
  const before = useRef<HTMLVideoElement>(null);
  const after = useRef<HTMLVideoElement>(null);
  const output =
    job.outputs.find((x) => x.role === 'result') ||
    job.outputs.find((x) => x.kind === 'video') ||
    job.outputs[0];
  if (!output) return null;
  const video = output.kind === 'video';
  const outputRatio = (output.width || job.request.width) / (output.height || job.request.height);
  const sync = () => {
    if (!after.current || !before.current) return;
    const sourceTime = after.current.currentTime + (job.request.trim_start || 0);
    if (Math.abs(sourceTime - before.current.currentTime) > 1 / (job.request.fps || 24)) {
      before.current.currentTime = sourceTime;
    }
    before.current.playbackRate = after.current.playbackRate;
  };
  return (
    <div className="result-view">
      <div className="result-heading">
        <div>
          <span className="eyebrow">RENDER COMPLETE</span>
          <h2 title={job.request.prompt} aria-label={job.request.prompt}>
            {job.request.prompt
              ? job.request.prompt.slice(0, 90) + (job.request.prompt.length > 90 ? '…' : '')
              : 'Your new video'}
          </h2>
        </div>
        <button
          className={`icon-button ${job.favorite ? 'favorited' : ''}`}
          aria-label={job.favorite ? 'Remove from favorites' : 'Add to favorites'}
          onClick={onFavorite}
        >
          <Icon name="heart" />
        </button>
      </div>
      <div
        className={`result-player ${compare ? 'comparing' : ''}`}
        ref={player}
        style={{ maxWidth: `${55 * outputRatio}vh`, '--media-ratio': outputRatio } as CSSProperties}
      >
        <div
          className="result-media"
          style={{
            aspectRatio: `${output.width || job.request.width}/${output.height || job.request.height}`,
          }}
        >
          {video ? (
            <video
              ref={after}
              src={mediaUrl(output)}
              poster={output.thumbnail_url || undefined}
              preload="auto"
              controls={!compare}
              playsInline
              onTimeUpdate={() => {
                setTime(after.current?.currentTime || 0);
                sync();
              }}
              onLoadedMetadata={() => setLength(after.current?.duration || length)}
              onVolumeChange={() => setMuted(!!after.current?.muted)}
              onPlay={() => {
                setPlaying(true);
                sync();
                if (compare) before.current?.play().catch(() => {});
              }}
              onPause={() => {
                setPlaying(false);
                before.current?.pause();
              }}
              onEnded={() => {
                setPlaying(false);
                before.current?.pause();
              }}
              onRateChange={() => {
                setSpeed(after.current?.playbackRate || 1);
                sync();
              }}
              onSeeked={sync}
              onError={() =>
                onError('The video could not be loaded. Download it to check the exported file.')
              }
            />
          ) : (
            <img src={mediaUrl(output)} alt="Generated output" />
          )}
          {compare && source && (
            <div className="before-media" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}>
              {source.kind === 'video' ? (
                <video
                  ref={before}
                  src={mediaUrl(source)}
                  muted
                  playsInline
                  onLoadedMetadata={sync}
                />
              ) : (
                <img src={mediaUrl(source)} alt="Original source" />
              )}
              <span className="compare-label">Original</span>
            </div>
          )}
          {compare && (
            <>
              <span className="compare-label after-label">Generated</span>
              <div className="compare-line" style={{ left: `${split}%` }}>
                <Icon name="split" />
              </div>
              <input
                className="compare-range"
                type="range"
                min="0"
                max="100"
                value={split}
                onChange={(e) => setSplit(+e.target.value)}
                aria-label="Before and after comparison"
              />
            </>
          )}
        </div>
        {compare && video && (
          <div className="comparison-playback">
            <button
              className="icon-button"
              aria-label={playing ? 'Pause comparison' : 'Play comparison'}
              onClick={() => {
                if (playing) after.current?.pause();
                else after.current?.play().catch((e) => onError(e.message));
              }}
            >
              <Icon name={playing ? 'pause' : 'play'} size={17} />
            </button>
            <input
              aria-label="Seek comparison"
              type="range"
              min={0}
              max={length || 1}
              step={0.01}
              value={time}
              onChange={(e) => {
                if (after.current) {
                  after.current.currentTime = +e.target.value;
                  setTime(+e.target.value);
                  sync();
                }
              }}
            />
            <span>
              {time.toFixed(1)} / {length.toFixed(1)}s
            </span>
            <button
              className="icon-button"
              aria-label={muted ? 'Unmute comparison' : 'Mute comparison'}
              aria-pressed={!muted}
              onClick={() => {
                if (after.current) after.current.muted = !muted;
              }}
            >
              <Icon name="sound" size={16} />
            </button>
            <select
              aria-label="Playback speed"
              value={speed}
              onChange={(e) => {
                if (after.current) after.current.playbackRate = +e.target.value;
              }}
            >
              {[0.5, 1, 1.5, 2].map((n) => (
                <option key={n} value={n}>
                  {n}×
                </option>
              ))}
            </select>
            <button
              className="icon-button"
              aria-label="Fullscreen comparison"
              onClick={() => player.current?.requestFullscreen().catch((e) => onError(e.message))}
            >
              <Icon name="fullscreen" size={16} />
            </button>
          </div>
        )}
      </div>
      <div className="result-actions">
        <div>
          {source && (
            <button
              className={`secondary ${compare ? 'selected' : ''}`}
              onClick={() => {
                setCompare(!compare);
                after.current?.pause();
              }}
            >
              <Icon name="split" />
              {compare ? 'Hide comparison' : 'Compare'}
            </button>
          )}
          <button className="secondary" onClick={onReuse}>
            <Icon name="refresh" />
            Reuse settings
          </button>
        </div>
        <a
          className="primary"
          href={mediaUrl(output)}
          download={output.name}
          onClick={() => markDownloaded(job.id)}
        >
          <Icon name="download" />
          Download video
        </a>
      </div>
      {job.outputs.length > 1 && (
        <div className="additional-outputs">
          {job.outputs
            .filter((a) => a.id !== output.id)
            .map((a) => (
              <a className="secondary" key={a.id} href={mediaUrl(a)} download={a.name}>
                <Icon
                  name={a.name.toLowerCase().includes('mask') ? 'mask' : 'download'}
                  size={15}
                />
                {a.name.toLowerCase().includes('mask') ? 'Download tracked mask' : a.name}
              </a>
            ))}
        </div>
      )}
      <div className="result-meta">
        <span>{job.request.model_id}</span>
        <span>
          {job.metadata?.execution === 'hosted-cloud-diffusion-local-media'
            ? 'Comfy Cloud + local processing'
            : job.request.provider === 'comfy-cloud'
              ? 'Comfy Cloud'
              : job.request.provider === 'modal'
                ? 'Modal GPU'
                : 'Local ComfyUI'}
        </span>
        <span>
          {job.request.width} × {job.request.height}
        </span>
        <span>
          {job.request.frames} frames · {job.request.fps} fps
        </span>
        <span>Seed {job.request.seed}</span>
        {job.metadata?.execution !== 'hosted-cloud-diffusion-local-media' && (
          <button onClick={() => onExport('canvas')}>
            <Icon name="grid" size={14} />
            ComfyUI canvas
          </button>
        )}
        <button onClick={() => onExport('workflow')}>
          <Icon name="code" size={14} />
          Workflow
        </button>
        <button onClick={() => onExport('bundle')}>
          <Icon name="folder" size={14} />
          Full project
        </button>
      </div>
    </div>
  );
}
