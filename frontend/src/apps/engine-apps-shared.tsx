import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { api, mediaUrl, post, upload } from '../api';
import { Icon } from '../Icon';
import { renderStage, resultUsesSeed } from '../ui';
import type { Asset, Catalog, Job, Model, Settings } from '../types';
import referenceInventoryUrl from '../../../docs/reference-assets.json?url';
import { loadReferenceLibraries } from './referenceLibrary';
import { ImagePromptDetails } from './ImagePromptDetails';

export type EngineAppProps = { catalog: Catalog; settings: Settings; onSettings: () => void };
export type ReferenceItem = {
  id?: string;
  title: string;
  poster?: string;
  video?: string;
  source_url?: string;
  category?: string;
  prompt?: string;
  swatch?: string;
};
export type CharacterGroup = {
  id: string;
  title: string;
  multiple?: boolean;
  options: ReferenceItem[];
};
export type ReferenceLibrary = {
  effects?: ReferenceItem[];
  link_preview?: string;
  wordmark?: string;
  hero?: ReferenceItem[];
  presets?: ReferenceItem[];
  characters?: ReferenceItem[];
  motion?: ReferenceItem[];
  trends?: ReferenceItem[];
  styles?: ReferenceItem[];
  groups?: CharacterGroup[];
  banner?: ReferenceItem[];
};

export function WorkspaceDialog({
  title,
  onClose,
  className = '',
  children,
}: {
  title: string;
  onClose: () => void;
  className?: string;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  return (
    <dialog
      className={`ea-dialog ${className}`}
      ref={dialog}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <header>
        <h2>{title}</h2>
        <button onClick={onClose} aria-label={`Close ${title}`}>
          <Icon name="close" />
        </button>
      </header>
      {children}
    </dialog>
  );
}

let referenceLibraries: ReturnType<typeof loadReferenceLibraries> | undefined;

export function useReferenceLibrary(app: string) {
  const [library, setLibrary] = useState<ReferenceLibrary>({});
  useEffect(() => {
    let active = true;
    referenceLibraries ||= loadReferenceLibraries(referenceInventoryUrl);
    referenceLibraries
      .then(async (value) =>
        value.apps[app] ? value : loadReferenceLibraries(referenceInventoryUrl, fetch, app),
      )
      .then((value) => {
        if (active) setLibrary((value.apps[app] || {}) as ReferenceLibrary);
      })
      .catch(() => {
        referenceLibraries = undefined;
      });
    return () => {
      active = false;
    };
  }, [app]);
  return library;
}

export function useWorkspaceAssets(ids: string[]) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState('');
  const add = (asset: Asset) =>
    setAssets((items) => [asset, ...items.filter((item) => item.id !== asset.id)]);
  useEffect(() => {
    api<{ items: Asset[] }>('/assets?limit=100')
      .then((value) => setAssets(value.items))
      .catch((reason) => setError(reason.message));
  }, []);
  useEffect(() => {
    for (const id of ids.filter(Boolean))
      if (!assets.some((asset) => asset.id === id))
        void api<Asset>(`/assets/${id}`)
          .then(add)
          .catch((reason) => setError(reason.message));
  }, [ids.join(','), assets.length]);
  return { assets, add, error, get: (id: string) => assets.find((asset) => asset.id === id) };
}

export function ReferenceMedia({
  item,
  className = '',
}: {
  item?: ReferenceItem;
  className?: string;
}) {
  if (!item) return null;
  return item.video ? (
    <video
      className={className}
      src={item.video}
      poster={item.poster}
      muted
      playsInline
      loop
      preload={item.poster ? 'none' : 'metadata'}
      onMouseEnter={(event) => {
        if (!matchMedia('(prefers-reduced-motion: reduce)').matches)
          void event.currentTarget.play().catch(() => {});
      }}
      onMouseLeave={(event) => event.currentTarget.pause()}
    />
  ) : item.poster ? (
    <img className={className} src={item.poster} alt={item.title} loading="lazy" />
  ) : null;
}

export function SourceSlot({
  asset,
  title,
  detail,
  optional,
  onChoose,
  onClear,
  compact = false,
}: {
  asset?: Asset;
  title: string;
  detail?: string;
  optional?: boolean;
  onChoose: () => void;
  onClear?: () => void;
  compact?: boolean;
}) {
  return (
    <div className={`ea-source-slot ${compact ? 'compact' : ''} ${asset ? 'has-media' : ''}`}>
      <button onClick={onChoose}>
        {asset ? (
          <>
            {asset.kind === 'audio' || asset.kind === 'archive' ? (
              <i>
                <Icon name={asset.kind === 'audio' ? 'volume' : 'download'} size={24} />
              </i>
            ) : (
              <img
                src={
                  asset.thumbnail_url ||
                  (asset.kind === 'image'
                    ? mediaUrl(asset)
                    : `/api/assets/${asset.id}/frame?time=0`)
                }
                alt={asset.name}
              />
            )}
            <span>
              {title}
              <small>{asset.name}</small>
            </span>
          </>
        ) : (
          <>
            {optional && <small className="ea-optional">Optional</small>}
            <i>
              <Icon name={title.toLowerCase().includes('video') ? 'video' : 'image'} size={20} />
            </i>
            <strong>{title}</strong>
            {detail && <small>{detail}</small>}
          </>
        )}
      </button>
      {asset?.kind === 'audio' && (
        <audio
          className="ea-source-audio"
          controls
          preload="metadata"
          src={mediaUrl(asset)}
          aria-label={asset.name}
        />
      )}
      {asset?.kind === 'archive' && (
        <a className="ea-source-download" href={mediaUrl(asset)} download={asset.name}>
          Download archive
        </a>
      )}
      {asset && onClear && (
        <button
          className="ea-clear-source"
          onClick={onClear}
          aria-label={`Remove ${title.toLowerCase()}`}
        >
          <Icon name="close" size={13} />
        </button>
      )}
    </div>
  );
}

export function AssetPicker({
  title,
  kind,
  assets,
  onSelect,
  onClose,
  onAdded,
  variant,
  jobs = [],
  initialTab = 'Uploads',
  includeWorkspaceGenerations = false,
  productIds = [],
  onProductLink,
  presets = [],
}: {
  title: string;
  kind: 'image' | 'video' | 'audio';
  assets: Asset[];
  onSelect: (asset: Asset) => void;
  onClose: () => void;
  onAdded: (asset: Asset) => void;
  variant?: 'influencer' | 'marketing' | 'genjutsu';
  jobs?: Job[];
  initialTab?: string;
  includeWorkspaceGenerations?: boolean;
  productIds?: string[];
  onProductLink?: () => void;
  presets?: ReferenceItem[];
}) {
  const dialog = useRef<HTMLDialogElement>(null),
    file = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [tab, setTab] = useState(initialTab),
    [range, setRange] = useState('Recent'),
    [oldest, setOldest] = useState(false),
    [offset, setOffset] = useState(100),
    [more, setMore] = useState(assets.length >= 100);
  useEffect(() => {
    if (offset === 100 && assets.length >= 100) setMore(true);
  }, [assets.length, offset]);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  async function addFile(value?: File) {
    if (!value) return;
    setBusy(true);
    setError('');
    try {
      const asset = await upload(value);
      if (asset.kind !== kind) throw new Error(`Choose a ${kind} file.`);
      onAdded(asset);
      onSelect(asset);
      onClose();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function addPreset(item: ReferenceItem) {
    if (kind === 'audio') return;
    setBusy(true);
    setError('');
    try {
      const asset = await importReference(item, kind);
      onAdded(asset);
      onSelect(asset);
      onClose();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function loadMore() {
    setBusy(true);
    try {
      const value = await api<{ items: Asset[]; total: number }>(
        `/assets?limit=100&offset=${offset}`,
      );
      value.items.forEach(onAdded);
      setOffset(offset + value.items.length);
      setMore(offset + value.items.length < value.total);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const appIds = new Set(jobs.flatMap((job) => job.outputs.map((asset) => asset.id))),
    likedIds = new Set(
      jobs.filter((job) => job.favorite).flatMap((job) => job.outputs.map((asset) => asset.id)),
    );
  const available = [
    ...new Map(
      [...assets, ...jobs.flatMap((job) => job.outputs)].map((asset) => [asset.id, asset]),
    ).values(),
  ];
  const matching = available
    .filter((asset) => {
      if (asset.kind !== kind || (asset.role && !['input', 'result'].includes(asset.role)))
        return false;
      if (!variant) return true;
      if (tab === 'Uploads') return !asset.source_job_id && (!asset.role || asset.role === 'input');
      if (tab === 'AI Influencer') return appIds.has(asset.id);
      if (tab === 'Liked') return likedIds.has(asset.id);
      if (tab === 'Products') return productIds.includes(asset.id);
      if (tab === 'Presets') return false;
      return variant === 'genjutsu' && !includeWorkspaceGenerations
        ? appIds.has(asset.id)
        : Boolean(asset.source_job_id) || asset.role === 'result';
    })
    .sort((a, b) => (oldest ? 1 : -1) * (a.created_at || '').localeCompare(b.created_at || ''));
  const shown =
    (variant === 'influencer' || variant === 'genjutsu') && range === 'Recent'
      ? matching.slice(0, 30)
      : matching;
  const presetItems = presets.filter((item) =>
    kind === 'video' ? Boolean(item.video) : kind === 'image' ? Boolean(item.poster) : false,
  );
  const presetTab = variant === 'genjutsu' && tab === 'Presets';
  return (
    <dialog
      aria-label={title}
      className={`ea-dialog ea-picker ${variant === 'influencer' ? 'influencer-picker' : variant === 'marketing' ? 'marketing-picker' : variant === 'genjutsu' ? 'genjutsu-picker' : ''}`}
      ref={dialog}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <header>
        <h2>{title}</h2>
        <button onClick={onClose} aria-label="Close asset picker">
          <Icon name="close" />
        </button>
      </header>
      {variant && (
        <nav className="influencer-picker-tabs">
          {(variant === 'marketing'
            ? ['Uploads', 'Generations', 'Liked', 'Products']
            : variant === 'genjutsu'
              ? ['Uploads', 'Presets', 'Generations', 'Liked']
              : ['Uploads', 'AI Influencer', 'Generations', 'Liked']
          ).map((value) => (
            <button
              className={tab === value ? 'active' : ''}
              key={value}
              onClick={() => setTab(value)}
            >
              {value}
            </button>
          ))}
        </nav>
      )}
      {variant ? (
        <div className="influencer-picker-toolbar">
          <div>
            {['Recent', 'All'].map((value) => (
              <button
                className={range === value ? 'active' : ''}
                onClick={() => setRange(value)}
                key={value}
              >
                {value}
              </button>
            ))}
          </div>
          <button
            onClick={() => setOldest(!oldest)}
            aria-label={`Sort ${oldest ? 'oldest' : 'newest'} first`}
          >
            {variant === 'genjutsu'
              ? `Sort by${oldest ? ' · Oldest' : ''}`
              : `Sort by: ${oldest ? 'Oldest' : 'Newest'}`}
            <Icon name="down" size={12} />
          </button>
          {variant === 'marketing' && onProductLink && (
            <button onClick={onProductLink}>Upload from link</button>
          )}
          <button disabled={busy} onClick={() => file.current?.click()}>
            <Icon name="upload" size={14} />
            {busy ? 'Uploading…' : 'Upload media'}
          </button>
        </div>
      ) : (
        <button
          className="ea-upload-zone"
          disabled={busy}
          onClick={() => file.current?.click()}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            void addFile(event.dataTransfer.files[0]);
          }}
        >
          <Icon name="upload" size={24} />
          <strong>{busy ? 'Uploading…' : `Upload ${kind}`}</strong>
          <span>Choose a file or drop it here</span>
        </button>
      )}
      <input
        ref={file}
        type="file"
        hidden
        accept={`${kind}/*`}
        onChange={(event) => void addFile(event.target.files?.[0])}
      />
      {error && (
        <p role="alert" className="ea-error">
          {error}
        </p>
      )}
      {!variant && <h3>From your workspace</h3>}
      <div className="ea-asset-grid">
        {variant === 'genjutsu' && tab === 'Uploads' && (
          <button
            className="genjutsu-upload"
            disabled={busy}
            onClick={() => file.current?.click()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              void addFile(event.dataTransfer.files[0]);
            }}
            aria-label="Upload media"
          >
            <Icon name="upload" size={40} />
            <span>{busy ? 'Uploading…' : 'Upload media'}</span>
          </button>
        )}
        {presetTab
          ? presetItems.map((item) => (
              <button
                key={item.id || item.video || item.poster}
                disabled={busy}
                onClick={() => void addPreset(item)}
                aria-label={`Import ${item.title} reference`}
              >
                <ReferenceMedia item={kind === 'image' ? { ...item, video: undefined } : item} />
                <span>{item.title}</span>
                <small>Import public reference</small>
              </button>
            ))
          : shown.map((asset) => (
              <button
                key={asset.id}
                disabled={busy}
                onClick={() => {
                  onSelect(asset);
                  onClose();
                }}
              >
                {kind === 'audio' ? (
                  <Icon name="sound" size={28} />
                ) : (
                  <img
                    src={
                      asset.thumbnail_url ||
                      (kind === 'image' ? mediaUrl(asset) : `/api/assets/${asset.id}/frame?time=0`)
                    }
                    alt={asset.name}
                  />
                )}
                <span>{asset.name}</span>
                {asset.duration && <small>{asset.duration.toFixed(1)}s</small>}
              </button>
            ))}
      </div>
      {!(presetTab ? presetItems.length : shown.length) &&
        !(variant === 'genjutsu' && tab === 'Uploads') && (
          <p className="ea-muted">
            {presetTab
              ? `No public ${kind} presets are available for this input.`
              : `No ${kind} files in this selection. Upload media or choose another source.`}
          </p>
        )}
      {presetTab && (
        <p className="ea-muted">
          Public Higgsfield references. Selecting Import adds the actual media to your workspace;
          these are not your generated results.
        </p>
      )}
      {!presetTab &&
        more &&
        (!['influencer', 'genjutsu'].includes(variant || '') || range === 'All') && (
          <button className="ea-load-more" disabled={busy} onClick={() => void loadMore()}>
            Load more media
          </button>
        )}
      {variant && tab === 'Liked' && (
        <p className="ea-muted">Favorites from this app's loaded history.</p>
      )}
    </dialog>
  );
}

export async function importReference(item: ReferenceItem, kind: 'image' | 'video') {
  const url = kind === 'video' ? item.video : item.poster;
  if (!url)
    throw new Error(`This reference has no ${kind} to import. Upload your own ${kind} instead.`);
  const response = await fetch(url);
  if (!response.ok)
    throw new Error('The reference could not be imported. Upload your own media instead.');
  const blob = await response.blob();
  const extension =
    kind === 'video'
      ? 'mp4'
      : blob.type.includes('png')
        ? 'png'
        : blob.type.includes('webp')
          ? 'webp'
          : 'jpg';
  return upload(
    new File(
      [blob],
      `${item.title.replace(/[^a-z0-9 -]/gi, '').slice(0, 60) || 'Reference'}.${extension}`,
      { type: blob.type },
    ),
  );
}

export function WorkspaceHistory({
  jobs,
  total,
  onSelect,
  onMore,
}: {
  jobs: Job[];
  total: number;
  onSelect: (job: Job) => void;
  onMore: () => void;
}) {
  return (
    <div className="ea-history">
      {jobs.map((job) => {
        const result =
          job.outputs.find((item) => item.role === 'result') ||
          job.outputs.find((item) => !item.role);
        const asset =
          job.request.effect_id === 'sdr-to-hdr'
            ? job.outputs.find((item) => item.role === 'preview') || result
            : result;
        return (
          <button key={job.id} onClick={() => onSelect(job)} className="ea-job-card">
            <div>
              {asset?.kind === 'image' ? (
                <img src={mediaUrl(asset)} alt="Generated result" />
              ) : asset?.kind === 'video' ? (
                <video
                  src={mediaUrl(asset)}
                  poster={asset.thumbnail_url || undefined}
                  muted
                  preload="metadata"
                />
              ) : (
                <Icon name={asset?.kind === 'audio' ? 'sound' : 'clock'} size={28} />
              )}
            </div>
            <strong>{job.request.prompt || job.request.effect_id.split('-').join(' ')}</strong>
            <span>
              {job.status === 'running'
                ? `${Math.round(job.progress * 100)}% · ${userStage(job)}`
                : job.status}
            </span>
          </button>
        );
      })}
      {!jobs.length && (
        <div className="ea-empty">
          <Icon name="clock" size={32} />
          <h3>No generations yet</h3>
          <p>Your real results and their workflows will appear here.</p>
        </div>
      )}
      {jobs.length < total && (
        <button className="ea-load-more" onClick={onMore}>
          Load more generations
        </button>
      )}
    </div>
  );
}

function OutputMedia({
  asset,
  label,
  transparent = false,
}: {
  asset: Asset;
  label: string;
  transparent?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  if (asset.role === 'depth')
    return (
      <p className="ea-muted">
        Download the lossless 16-bit depth file for compositing. Use the result preview above for
        browser playback; the exported metadata records its depth scale and valid-region encoding.
      </p>
    );
  if (asset.kind === 'archive')
    return (
      <p className="ea-muted">
        This output is a downloadable archive. Its original files and provenance are preserved in
        the download below.
      </p>
    );
  if (failed)
    return (
      <p className="ea-muted">
        Your browser could not display {label.toLowerCase()}. The original file remains available to
        download.
      </p>
    );
  return asset.kind === 'video' ? (
    <video
      className={transparent ? 'transparent-cutout-preview' : undefined}
      controls
      playsInline
      preload="metadata"
      src={mediaUrl(asset)}
      onError={() => setFailed(true)}
    />
  ) : asset.kind === 'audio' ? (
    <audio controls src={mediaUrl(asset)} onError={() => setFailed(true)} />
  ) : (
    <img src={mediaUrl(asset)} alt={label} onError={() => setFailed(true)} />
  );
}
const outputLabel = (role?: string) =>
  (
    ({
      result: 'Result',
      bridge: 'Generated bridge',
      preview: 'SDR preview',
      mask: 'Mask / alpha',
      depth: 'Lossless depth data',
      reconstruction: 'Regenerated full image',
      uncomposited: 'Raw generation before background preservation',
    }) as Record<string, string>
  )[role || 'result'] ||
  role ||
  'Output';
function userStage(job: Job) {
  const label = renderStage(job.stage);
  return [
    'create-image',
    'edit-image',
    'remove-background',
    'expand-image',
    'decompose-image',
  ].includes(job.request.effect_id)
    ? label.replace(/video/g, 'image')
    : label;
}

export function ResultDialog({
  job,
  onClose,
  onRefresh,
  onUse,
  useLabel,
  useKind,
  onReuse,
  reuseLabel = 'Reuse settings',
  reuseDescription,
  preferredOutputRole,
}: {
  job: Job;
  onClose: () => void;
  onRefresh: () => void;
  onUse?: (asset: Asset) => void;
  useLabel?: string;
  useKind?: string;
  onReuse?: () => void;
  reuseLabel?: string;
  reuseDescription?: string;
  preferredOutputRole?: string;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  const preferred =
    preferredOutputRole && job.outputs.find((asset) => asset.role === preferredOutputRole);
  const primary = preferred
    ? [preferred]
    : job.outputs.filter((asset) => asset.role === 'result' || !asset.role);
  const additional = job.outputs.filter((asset) => !primary.some((item) => item.id === asset.id));
  const sdr =
    job.request.effect_id === 'sdr-to-hdr'
      ? job.outputs.find((asset) => asset.role === 'preview')
      : undefined;
  const isCutout = (asset: Asset) =>
    asset.kind === 'video' &&
    asset.role === 'result' &&
    ['alpha-matte', 'semantic-matte'].includes(job.request.effect_id);
  // Correct only the known historical wording; retain the stored run's provenance.
  const warnings = job.warnings?.flatMap((message) => {
    const old = message.match(
      /^Inference uses a padded (\d+)×(\d+) canvas; final output is cropped to (\d+)×(\d+) without resizing source pixels\.$/,
    );
    if (!old) return [message];
    if (old[1] === old[3] && old[2] === old[4]) return [];
    return [
      `Inference uses a padded ${old[1]}×${old[2]} canvas; final output is cropped to ${old[3]}×${old[4]} without an additional resize.`,
    ];
  });
  const download = (asset: Asset, label: string) => (
    <a href={mediaUrl(asset)} download={asset.name}>
      <Icon name="download" size={14} />
      {label}
    </a>
  );
  return (
    <dialog
      ref={dialog}
      className="ea-dialog ea-result"
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <header>
        <h2>Generation · {job.status}</h2>
        <button onClick={onClose} aria-label="Close generation">
          <Icon name="close" />
        </button>
      </header>
      {job.request.prompt && <p className="ea-result-prompt">{job.request.prompt}</p>}
      <ImagePromptDetails job={job} />
      {primary.map((asset) => (
        <div className="ea-result-media" key={asset.id}>
          {sdr && (
            <p className="ea-muted">
              SDR viewing preview. The main download retains the HDR output.
            </p>
          )}
          {asset.role === 'mask' && (
            <p className="ea-muted">
              Alpha mask preview. The transparent cutout is included in Additional outputs.
            </p>
          )}
          <OutputMedia
            asset={sdr || asset}
            label={sdr ? 'SDR preview' : outputLabel(asset.role)}
            transparent={isCutout(asset)}
          />
          <small>
            {asset.width && asset.height ? `${asset.width} × ${asset.height}` : ''}
            {asset.duration ? ` · ${asset.duration.toFixed(3)}s` : ''}
          </small>
          <div>
            {download(asset, sdr ? 'Download HDR result' : 'Download')}
            {onUse && (!useKind || asset.kind === useKind) && (
              <button
                onClick={() => {
                  onUse(asset);
                  onClose();
                }}
              >
                {useLabel || 'Use result'}
              </button>
            )}
          </div>
        </div>
      ))}
      {additional.length > 0 && (
        <details className="ea-extra-outputs">
          <summary>Additional outputs · {additional.length}</summary>
          {additional.map((asset) => (
            <div className="ea-result-media" key={asset.id}>
              <h3>{outputLabel(asset.role)}</h3>
              <OutputMedia
                asset={asset}
                label={outputLabel(asset.role)}
                transparent={isCutout(asset)}
              />
              <div>{download(asset, `Download ${outputLabel(asset.role).toLowerCase()}`)}</div>
            </div>
          ))}
        </details>
      )}
      {(job.status === 'queued' || job.status === 'running') && (
        <>
          <progress value={job.progress} max="1" />
          <p>{userStage(job)}</p>
          <button
            onClick={() =>
              void post(`/jobs/${job.id}/cancel`)
                .then(onRefresh)
                .catch((reason) => setError(reason.message))
            }
          >
            Cancel generation
          </button>
        </>
      )}
      {(job.error || error) && (
        <p className="ea-error" role="alert">
          {error || job.error}
        </p>
      )}
      {warnings?.map((message) => (
        <p className="ea-muted" key={message}>
          {message}
        </p>
      ))}
      <footer>
        {onReuse && (
          <button
            title={reuseDescription}
            onClick={() => {
              if (!['local', 'comfy-cloud'].includes(job.request.provider)) {
                setError('This historical job used a connection that is no longer supported. Its settings were not copied or redirected. Download its workflow to inspect the original recipe, then create a new project with an explicitly selected supported connection.');
                return;
              }
              onReuse();
              onClose();
            }}
          >
            {reuseLabel}
          </button>
        )}
        <button
          aria-pressed={job.favorite}
          onClick={() =>
            void api(`/jobs/${job.id}`, {
              method: 'PATCH',
              body: JSON.stringify({ favorite: !job.favorite }),
            })
              .then(onRefresh)
              .catch((reason) => setError(reason.message))
          }
        >
          <Icon name="heart" size={14} />
          {job.favorite ? 'Liked' : 'Like'}
        </button>
        {(job.status === 'failed' || job.status === 'cancelled') && (
          <button
            onClick={() =>
              void post(`/jobs/${job.id}/retry`)
                .then(() => {
                  onRefresh();
                  onClose();
                })
                .catch((reason) => setError(reason.message))
            }
          >
            Retry
          </button>
        )}
        <span>
          {job.request.model_id}
          {resultUsesSeed(job.request.model_id) ? ` · seed ${job.request.seed}` : ''}
        </span>
        <a href={`/api/jobs/${job.id}/workflow`} download>
          Workflow API
        </a>
        {job.status === 'succeeded' &&
          job.metadata?.execution !== 'hosted-cloud-diffusion-local-media' && (
            <a href={`/api/jobs/${job.id}/workflow?format=ui`} download>
              ComfyUI canvas
            </a>
          )}
        <a href={`/api/jobs/${job.id}/bundle?include_media=true`} download>
          Full project
        </a>
      </footer>
    </dialog>
  );
}

export function ReferenceDialog({
  item,
  onClose,
  onUse,
  busy = false,
  label = 'Use this reference',
}: {
  item: ReferenceItem;
  onClose: () => void;
  onUse?: () => void;
  busy?: boolean;
  label?: string;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="ea-dialog ea-reference-dialog"
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <header>
        <h2>{item.title}</h2>
        <button onClick={onClose} aria-label="Close reference preview">
          <Icon name="close" />
        </button>
      </header>
      {item.video ? (
        <video controls playsInline src={item.video} poster={item.poster} />
      ) : item.poster ? (
        <img src={item.poster} alt={item.title} />
      ) : (
        <p>No media is available for this reference.</p>
      )}
      <p>Public Higgsfield reference example, not a generated result from this workspace.</p>
      {onUse && (
        <button className="ea-lime" disabled={busy} onClick={onUse}>
          {busy ? 'Importing…' : label}
        </button>
      )}
    </dialog>
  );
}

export function videoIntervalIssue(model: Model, seconds: number, source?: Asset, trim = 0, fpsOverride?: number) {
  const fps = Number(model.fixed_fps ?? fpsOverride ?? model.default_fps ?? 24);
  if (!Number.isFinite(seconds) || seconds <= 0 || !Number.isFinite(trim) || trim < 0)
    return 'Choose a positive duration and a non-negative source start.';
  if (!Number.isFinite(fps) || fps <= 0) return 'Choose a valid frame rate.';
  const available = source?.duration === undefined ? undefined : Math.max(0, source.duration - trim);
  if (available !== undefined && seconds > available + 1e-6)
    return `Requested ${seconds.toFixed(2)}s, but only ${available.toFixed(2)}s remains in the source. Shorten the duration or move the start earlier.`;
  const limit = Number(model.max_frames || 241) / fps;
  return seconds > limit + 1e-6
    ? `${model.name} supports at most ${limit.toFixed(2)}s per run at ${fps} fps. Shorten the requested ${seconds.toFixed(2)}s or choose a model with a longer limit.`
    : '';
}

export function boundedVideoFrames(
  model: Model,
  seconds: number,
  source?: Asset,
  trim = 0,
  fpsOverride?: number,
) {
  const fps = Number(model.fixed_fps ?? fpsOverride ?? model.default_fps ?? 24),
    multiple = Number(model.frame_multiple || 4);
  const available = source?.duration === undefined ? seconds : Math.max(0, source.duration - trim);
  const desired = Math.min(seconds, available, Number(model.max_frames || 241) / fps);
  return Math.floor((desired * fps - 1 + 1e-6) / multiple) * multiple + 1;
}

export function exportDraft(value: unknown, filename: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }),
  );
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
