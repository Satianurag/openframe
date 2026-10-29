import { useCallback, useEffect, useRef, useState } from 'react';
import type { DragEvent } from 'react';
import type { Asset, Catalog, Effect, Job, JobRequest, Model, Preset, Settings } from './types';
import { listPage, api, download, mediaUrl, post, upload } from './api';
import { Icon } from './Icon';
import { EmptyState, ErrorBox, FieldSelect, Modal, Toggle, renderStage } from './ui';
import { AnchoredPopover, ModelPopover } from './Popovers';
import { MaskEditor } from './MaskEditor';
import { SettingsPanel } from './SettingsPanel';
import { JobResult } from './JobResult';
import { SceneArt } from './SceneArt';
import { EffectsPanel, HistoryPanel, MediaLibrary, HelpPanel } from './StudioPanels';

const initial: JobRequest = {
  model_id: 'ltx-2.3',
  effect_id: 'text-to-video',
  provider: '',
  prompt: '',
  negative_prompt: '',
  seed: -1,
  width: 512,
  height: 288,
  frames: 97,
  fps: 24,
  steps: 8,
  guidance: 1,
  strength: 1,
  preserve_audio: true,
  preserve_outside_mask: true,
  mask_tracking: true,
  mask_tracking_method: 'sam2',
  trim_start: 0,
  mask_dilation: 8,
  mask_feather: 8,
  generate_audio: true,
};
function duration(request: JobRequest) {
  return Math.max(0, request.frames / request.fps);
}
function fitFrames(frames: number, fps: number, multiple: number, seconds: number) {
  const available = Math.floor(seconds * fps);
  return Math.max(9, Math.min(frames, Math.floor((available - 1) / multiple) * multiple + 1));
}
function alignDimensions(width: number, height: number, multiple: number) {
  const ratio = [
    [16, 9],
    [9, 16],
    [1, 1],
    [4, 3],
  ].find(([w, h]) => Math.abs(width / height - w / h) < 0.001);
  if (ratio) {
    const [w, h] = ratio;
    const scale = Math.max(
      Math.ceil(256 / (Math.min(w, h) * multiple)),
      Math.round(Math.max(width, height) / (Math.max(w, h) * multiple)),
    );
    return { width: w * multiple * scale, height: h * multiple * scale };
  }
  return {
    width: Math.max(256, Math.round(width / multiple) * multiple),
    height: Math.max(256, Math.round(height / multiple) * multiple),
  };
}
function effectDimensions(
  width: number,
  height: number,
  model: Model | undefined,
  effect: Effect | undefined,
  explicit: boolean,
) {
  const target =
    effect?.requires_video && !explicit ? Number(model?.recommended_vfx_longest_side || 0) : 0;
  const scale = target ? target / Math.max(width, height) : 1;
  return alignDimensions(width * scale, height * scale, Number(model?.dimension_multiple || 32));
}
function safeDraft() {
  try {
    const saved = JSON.parse(localStorage.getItem('openframe-draft') || 'null');
    return saved ? { ...initial, ...saved } : initial;
  } catch {
    return initial;
  }
}

export default function App() {
  const [catalog, setCatalog] = useState<Catalog>({ models: [], effects: [], providers: [] });
  const [settings, setSettings] = useState<Settings>({});
  const [assets, setAssets] = useState<Asset[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobTotal, setJobTotal] = useState(0);
  const [assetTotal, setAssetTotal] = useState(0);
  const [jobLimit, setJobLimit] = useState(100);
  const [assetLimit, setAssetLimit] = useState(100);
  const [assetCache, setAssetCache] = useState<Record<string, Asset>>({});
  const refreshSequence = useRef(0);
  const resolutionChosen = useRef(localStorage.getItem('openframe-resolution-explicit') === 'true');
  const preserveResolution = () => {
    if (!resolutionChosen.current) {
      resolutionChosen.current = true;
      localStorage.setItem('openframe-resolution-explicit', 'true');
    }
  };
  const [presets, setPresets] = useState<Preset[]>([]);
  const [draft, setDraft] = useState<JobRequest>(safeDraft);
  const [view, setView] = useState(new URLSearchParams(location.search).get('view') || 'studio');
  const [panel, setPanel] = useState(new URLSearchParams(location.search).get('panel') || 'help');
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState('');
  const [modal, setModal] = useState<
    | null
    | 'advanced'
    | 'model'
    | 'provider'
    | 'settings'
    | 'mask'
    | 'save-preset'
    | 'presets'
    | 'draw-source'
    | 'asset-source'
    | 'asset-reference'
  >(null);
  const [presetName, setPresetName] = useState('');
  const [editingTools, setEditingTools] = useState(false);
  const [drawMode, setDrawMode] = useState(false);
  const [category, setCategory] = useState('All');
  const [query, setQuery] = useState('');
  const [historyFilter, setHistoryFilter] = useState('All');
  const [assetFilter, setAssetFilter] = useState('All');
  const [banner, setBanner] = useState(true);
  const [mobileControls, setMobileControls] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const uploadRole = useRef<'source' | 'reference' | 'library'>('source');
  const promptInput = useRef<HTMLTextAreaElement>(null);
  const modelAnchor = useRef<HTMLButtonElement>(null);
  const sourceAnchor = useRef<HTMLDivElement>(null);
  const effect = catalog.effects.find((e) => e.id === draft.effect_id);
  const model = catalog.models.find((m) => m.id === draft.model_id);
  const provider = catalog.providers.find((p) => p.id === draft.provider);
  const hostedCloud =
    draft.provider === 'comfy-cloud' &&
    /^https:\/\/cloud\.comfy\.org\/?$/.test(settings.comfy_cloud_url || 'https://cloud.comfy.org');
  const cloudRemoval =
    hostedCloud && draft.model_id === 'ltx-2.3' && draft.effect_id === 'remove-object';
  const strengthControl = effect ? model?.strength_controls?.[effect.task] : undefined;
  const source =
    assets.find((a) => a.id === draft.source_asset_id) || assetCache[draft.source_asset_id || ''];
  const mask =
    assets.find((a) => a.id === draft.mask_asset_id) || assetCache[draft.mask_asset_id || ''];
  const reference =
    assets.find((a) => a.id === draft.reference_asset_id) ||
    assetCache[draft.reference_asset_id || ''];
  const supportsReference =
    !!model?.supports_reference &&
    !!effect &&
    effect.task !== 'image-to-video' &&
    (!model.reference_tasks || model.reference_tasks.includes(effect.task));
  const currentJob = jobs.find((j) => j.id === selectedJob);
  const activeJobs = jobs.filter((j) => ['queued', 'running'].includes(j.status));
  const update = useCallback(
    (value: Partial<JobRequest>) => setDraft((d) => ({ ...d, ...value })),
    [],
  );
  useEffect(() => {
    if (model && effect && !supportsReference && draft.reference_asset_id)
      update({ reference_asset_id: undefined });
  }, [model, effect, supportsReference, draft.reference_asset_id, update]);
  useEffect(() => {
    const ids = [
      draft.source_asset_id,
      draft.mask_asset_id,
      draft.reference_asset_id,
      currentJob?.request.source_asset_id,
    ].filter((id): id is string => !!id && !assetCache[id] && !assets.some((a) => a.id === id));
    if (!ids.length) return;
    let cancelled = false;
    Promise.all([...new Set(ids)].map((id) => api<Asset>(`/assets/${id}`)))
      .then((found) => {
        if (!cancelled)
          setAssetCache((cache) => ({
            ...cache,
            ...Object.fromEntries(found.map((a) => [a.id, a])),
          }));
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [
    assets,
    assetCache,
    draft.source_asset_id,
    draft.mask_asset_id,
    draft.reference_asset_id,
    currentJob?.request.source_asset_id,
  ]);
  const notify = (text: string) => {
    setNotice(text);
  };
  const navigate = (next: string, nextPanel?: string) => {
    setView(next);
    if (nextPanel) setPanel(nextPanel);
    const params = new URLSearchParams({ view: next, panel: nextPanel || panel });
    history.pushState({}, '', `?${params}`);
  };
  const refresh = useCallback(async () => {
    const sequence = ++refreshSequence.current;
    try {
      const [c, s, a, j, p] = await Promise.all([
        api<Catalog>('/catalog'),
        api<Settings>('/settings'),
        listPage<Asset>('/assets', assetLimit),
        listPage<Job>('/jobs', jobLimit),
        api<{ items: Preset[] }>('/presets'),
      ]);
      if (sequence !== refreshSequence.current) return;
      setJobTotal(j.total);
      setAssetTotal(a.total);
      setCatalog(c);
      setSettings(s);
      setAssets(a.items);
      setJobs(j.items);
      setPresets(p.items);
      setOffline(false);
      setDraft((d) => ({
        ...d,
        provider: d.provider || s.default_provider || 'modal',
        model_id: c.models.some((m) => m.id === d.model_id)
          ? d.model_id
          : c.models[0]?.id || d.model_id,
        effect_id: c.effects.some((e) => e.id === d.effect_id)
          ? d.effect_id
          : c.effects[0]?.id || d.effect_id,
      }));
    } catch (e) {
      setOffline(true);
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [jobLimit, assetLimit]);
  useEffect(() => {
    refresh();
  }, [refresh]);
  useEffect(() => {
    let cancelled = false;
    const timer = setInterval(
      async () => {
        try {
          const result = await listPage<Job>('/jobs', jobLimit);
          if (cancelled) return;
          setJobs(result.items);
          setJobTotal(result.total);
          setOffline(false);
          if (
            result.items.some(
              (j) =>
                j.status === 'succeeded' &&
                j.outputs.some((o) => !assets.some((a) => a.id === o.id)),
            )
          ) {
            const a = await listPage<Asset>('/assets', assetLimit);
            if (cancelled) return;
            setAssets(a.items);
            setAssetTotal(a.total);
          }
        } catch {
          setOffline(true);
        }
      },
      activeJobs.length ? 2000 : 10000,
    );
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeJobs.length, assets, jobLimit, assetLimit]);
  useEffect(() => {
    const serialized = JSON.stringify(draft);
    const persist = () => {
      if (localStorage.getItem('openframe-draft') !== serialized) {
        localStorage.setItem('openframe-draft', serialized);
      }
    };
    const timer = setTimeout(persist, 500);
    addEventListener('pagehide', persist);
    addEventListener('beforeunload', persist);
    return () => {
      clearTimeout(timer);
      removeEventListener('pagehide', persist);
      removeEventListener('beforeunload', persist);
    };
  }, [draft]);
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(''), 4500);
    return () => clearTimeout(t);
  }, [notice]);
  useEffect(() => {
    const handler = () => {
      const p = new URLSearchParams(location.search);
      setView(p.get('view') || 'studio');
      setPanel(p.get('panel') || 'effects');
    };
    addEventListener('popstate', handler);
    return () => removeEventListener('popstate', handler);
  }, []);
  function chooseModel(id: string) {
    const m = catalog.models.find((x) => x.id === id);
    if (!m) return;
    const grid = Number(m.dimension_multiple || 32);
    update({
      ...alignDimensions(draft.width, draft.height, grid),
      model_id: id,
      reference_asset_id: m.supports_reference ? draft.reference_asset_id : undefined,
      steps: Number(m.default_steps || 8),
      guidance: Number(m.default_guidance || 1),
      fps: Number(m.default_fps || 24),
      frames:
        source?.kind === 'video'
          ? fitFrames(
              Number(m.default_frames || 97),
              Number(m.default_fps || 24),
              Number(m.frame_multiple || 8),
              Math.max(0, (source.duration || 0) - draft.trim_start),
            )
          : Number(m.default_frames || 97),
    });
  }
  function chooseEffect(e: Effect) {
    const m =
      catalog.models.find((m) => m.id === draft.model_id && e.model_ids.includes(m.id)) ||
      catalog.models.find((m) => e.model_ids.includes(m.id));
    // Preset selection already resets defaults; provider changes and recipe reuse do not.
    const defaultFrames =
      hostedCloud && e.id === 'remove-object' && e.id !== draft.effect_id && m?.id === 'ltx-2.3'
        ? 49
        : Number(m?.default_frames || draft.frames);
    setDraft((d) => ({
      ...d,
      effect_id: e.id,
      source_asset_id:
        (e.requires_video && source?.kind === 'video') ||
        (e.requires_image && source?.kind === 'image')
          ? d.source_asset_id
          : undefined,
      mask_asset_id: e.requires_mask && source?.kind === 'video' ? d.mask_asset_id : undefined,
      ...effectDimensions(d.width, d.height, m, e, resolutionChosen.current),
      prompt: e.prompt,
      model_id: m?.id || d.model_id,
      reference_asset_id: m?.supports_reference ? d.reference_asset_id : undefined,
      steps: Number(m?.default_steps || d.steps),
      guidance: Number(m?.default_guidance || d.guidance),
      fps: Number(m?.default_fps || d.fps),
      frames:
        source?.kind === 'video' && e.requires_video
          ? fitFrames(
              defaultFrames,
              Number(m?.default_fps || d.fps),
              Number(m?.frame_multiple || 8),
              Math.max(0, (source.duration || 0) - d.trim_start),
            )
          : defaultFrames,
    }));
    setEditingTools(false);
    setDrawMode(false);
    setSelectedJob(null);
    navigate('studio', 'help');
    setMobileControls(true);
    notify(`${e.name} selected`);
  }
  function selectAsset(asset: Asset, role: 'source' | 'reference') {
    if (role === 'reference') {
      update({ reference_asset_id: asset.id });
      return;
    }
    let selectedEffect = effect;
    if (asset.kind === 'video' && !effect?.requires_video)
      selectedEffect = catalog.effects.find((e) => e.id === 'restyle');
    if (asset.kind === 'image' && (effect?.requires_video || effect?.id === 'text-to-video'))
      selectedEffect = catalog.effects.find((e) => e.id === 'image-to-video');
    const selectedModel = selectedEffect
      ? catalog.models.find(
          (m) =>
            m.id ===
            (selectedEffect.model_ids.includes(draft.model_id)
              ? draft.model_id
              : selectedEffect.model_ids[0]),
        )
      : model;
    setDraft((d) => ({
      ...d,
      ...effectDimensions(
        d.width,
        d.height,
        selectedModel,
        selectedEffect,
        resolutionChosen.current,
      ),
      source_asset_id: asset.id,
      mask_asset_id: undefined,
      trim_start: 0,
      ...(asset.kind === 'video'
        ? {
            frames: fitFrames(
              d.frames,
              d.fps,
              Number(model?.frame_multiple || 8),
              asset.duration || 0,
            ),
          }
        : {}),
      ...(selectedEffect && selectedEffect.id !== effect?.id
        ? {
            effect_id: selectedEffect.id,
            prompt: selectedEffect.prompt,
            model_id: selectedEffect.model_ids.includes(d.model_id)
              ? d.model_id
              : selectedEffect.model_ids[0],
          }
        : {}),
    }));
    setSelectedJob(null);
    if (drawMode && selectedEffect?.requires_mask && asset.kind === 'video') setModal('mask');
  }
  async function acceptFiles(files: FileList | null, role = uploadRole.current) {
    if (!files?.length) return;
    setError('');
    setBusy('upload');
    try {
      const added: Asset[] = [];
      for (const file of Array.from(files)) {
        if (!file.type.startsWith('image/') && !file.type.startsWith('video/'))
          throw new Error('Choose an image or video file.');
        added.push(await upload(file));
      }
      setAssets((a) => [...added, ...a.filter((x) => !added.some((n) => n.id === x.id))]);
      if (role !== 'library') selectAsset(added[0], role);
      notify(`${added.length === 1 ? added[0].name : `${added.length} files`} uploaded`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
      if (fileInput.current) fileInput.current.value = '';
    }
  }
  function browse(role: 'source' | 'reference' | 'library') {
    uploadRole.current = role;
    if (fileInput.current) {
      fileInput.current.accept = role === 'reference' ? 'image/*' : 'image/*,video/*';
      fileInput.current.multiple = role === 'library';
      fileInput.current.click();
    }
  }
  function drop(e: DragEvent, role: 'source' | 'reference' | 'library') {
    e.preventDefault();
    acceptFiles(e.dataTransfer.files, role);
  }
  function validation() {
    if (!draft.prompt.trim()) return 'Describe the scene you want to create.';
    if (!effect || !model) return 'The model catalogue is not available yet.';
    if (!effect.model_ids.includes(draft.model_id))
      return 'Select a model that supports this effect.';
    if (effect.requires_video && source?.kind !== 'video')
      return 'Upload a source video for this effect.';
    if (effect.requires_image && source?.kind !== 'image')
      return 'Upload a starting image for this effect.';
    if (effect.requires_mask && !mask) return 'Paint a mask around the area you want to change.';
    if (
      effect.requires_mask &&
      mask?.kind !== 'video' &&
      draft.mask_tracking &&
      provider?.supported_tracking_methods &&
      !provider.supported_tracking_methods.includes(draft.mask_tracking_method)
    )
      return 'This compute connection does not support the selected tracking method. Choose optical flow or a static mask in Advanced settings, or change compute.';
    if (
      source?.kind === 'video' &&
      effect.requires_video &&
      draft.frames / draft.fps > (source.duration || 0) - draft.trim_start + 0.001
    )
      return 'Shorten the render duration to fit your source clip.';
    return '';
  }
  async function generate() {
    const issue = validation();
    if (issue) {
      setError(issue);
      setMobileControls(true);
      return;
    }
    setBusy('generate');
    setError('');
    try {
      const job = await post<Job>('/jobs', draft);
      setJobs((j) => [job, ...j]);
      setSelectedJob(job.id);
      navigate('studio', 'history');
      setMobileControls(false);
      notify('Your render has been queued.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  }
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        if (!busy && !modal) void generate();
      }
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        setModal('model');
      }
    };
    addEventListener('keydown', handler);
    return () => removeEventListener('keydown', handler);
  });
  async function jobAction(job: Job, action: 'cancel' | 'retry' | 'favorite' | 'delete') {
    setError('');
    try {
      if (action === 'delete') {
        if (!confirm('Delete this render from your history?')) return;
        await api(`/jobs/${job.id}`, { method: 'DELETE' });
        setJobs((j) => j.filter((x) => x.id !== job.id));
        if (selectedJob === job.id) setSelectedJob(null);
      } else if (action === 'favorite') {
        const result = await api<Job>(`/jobs/${job.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ favorite: !job.favorite }),
        });
        setJobs((j) => j.map((x) => (x.id === job.id ? result : x)));
      } else {
        const result = await post<Job>(`/jobs/${job.id}/${action}`);
        setJobs((j) => [result, ...j.filter((x) => x.id !== result.id)]);
        if (action === 'retry') setSelectedJob(result.id);
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function reuse(job: Job) {
    preserveResolution();
    setDraft(job.request);
    setSelectedJob(null);
    navigate('studio', 'help');
    setMobileControls(true);
    notify('Render settings restored. Change the seed for a new variation.');
  }
  async function exportWorkflow(job?: Job, bundle = false, canvas = false) {
    setError('');
    try {
      if (job && bundle) {
        const link = document.createElement('a');
        link.href = `/api/jobs/${job.id}/bundle?include_media=true`;
        link.download = `openframe-${job.id}.zip`;
        link.click();
      } else if (job)
        await download(
          `/jobs/${job.id}/workflow${canvas ? '?format=ui' : ''}`,
          `openframe-${job.id}${canvas ? '-canvas' : '-api'}.json`,
        );
      else await download('/workflows/export', 'openframe-workflow.json', draft);
      notify(bundle ? 'Full project download started.' : 'ComfyUI workflow downloaded.');
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function savePreset() {
    if (!presetName.trim()) return;
    setBusy('preset');
    try {
      const preset = await post<Preset>('/presets', { name: presetName.trim(), request: draft });
      setPresets((p) => [preset, ...p]);
      setModal(null);
      setPresetName('');
      notify('Preset saved.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  }
  function setRatio(ratio: string) {
    if (ratio === 'custom') return;
    const [w, h] = ratio.split(':').map(Number);
    let long = Math.max(draft.width, draft.height);
    const mult = Number(model?.dimension_multiple || 32);
    let width = w >= h ? long : (long * w) / h,
      height = w >= h ? (long * h) / w : long;
    update(alignDimensions(width, height, mult));
  }
  const ratioLabel =
    Math.abs(draft.width / draft.height - 16 / 9) < 0.001
      ? '16:9'
      : Math.abs(draft.width / draft.height - 9 / 16) < 0.001
        ? '9:16'
        : draft.width === draft.height
          ? '1:1'
          : Math.abs(draft.width / draft.height - 4 / 3) < 0.001
            ? '4:3'
            : 'custom';
  function setQuality(long: number) {
    preserveResolution();
    const ratio = ratioLabel === 'custom' ? `${draft.width}:${draft.height}` : ratioLabel;
    const [w, h] = ratio.split(':').map(Number);
    const mult = Number(model?.dimension_multiple || 32);
    update({
      width: Math.max(256, Math.round((w >= h ? long : (long * w) / h) / mult) * mult),
      height: Math.max(256, Math.round((w >= h ? (long * h) / w : long) / mult) * mult),
    });
  }
  const filteredEffects = catalog.effects.filter(
    (e) =>
      (category === 'All' || e.category === category) &&
      (e.name + ' ' + e.description).toLowerCase().includes(query.toLowerCase()),
  );
  const filteredJobs = jobs.filter(
    (j) =>
      historyFilter === 'All' ||
      (historyFilter === 'Favorites' && j.favorite) ||
      (historyFilter === 'Active' && ['queued', 'running'].includes(j.status)) ||
      (historyFilter === 'Completed' && j.status === 'succeeded') ||
      (historyFilter === 'Failed' && j.status === 'failed'),
  );
  const libraryProps = {
    assetTotal,
    onLoadMoreAssets: () => setAssetLimit((n) => Math.min(assetTotal, n + 100)),
    loadingAssets: assets.length < Math.min(assetLimit, assetTotal),
    assets,
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
  };
  return (
    <>
      <input ref={fileInput} type="file" hidden onChange={(e) => acceptFiles(e.target.files)} />
      {banner && (
        <div className="announcement">
          <Icon name="code" size={15} />
          <span>Create original videos and VFX with workflows you own</span>
          <button onClick={() => exportWorkflow()}>
            Open in ComfyUI
            <Icon name="external" size={12} />
          </button>
          <button
            className="announcement-close"
            onClick={() => setBanner(false)}
            aria-label="Dismiss announcement"
          >
            <Icon name="close" size={16} />
          </button>
        </div>
      )}
      <header className="topbar">
        <button
          className="brand"
          onClick={() => navigate('studio', 'effects')}
          aria-label="OpenFrame home"
        >
          <svg width="25" height="25" viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <path
              d="M6 12V5h12M26 20v7H14M6 21 26 7M6 29 26 15"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
            />
          </svg>
          <strong>OpenFrame</strong>
        </button>
        <nav aria-label="Main navigation">
          <button
            className={view === 'studio' && panel === 'effects' ? 'active' : ''}
            onClick={() => {
              setSelectedJob(null);
              navigate('studio', 'effects');
            }}
          >
            Explore
          </button>
          <button
            className={view === 'studio' && panel !== 'effects' ? 'active' : ''}
            onClick={() => {
              navigate('studio', 'help');
              setMobileControls(false);
            }}
          >
            Video
          </button>
          <button
            onClick={() => {
              const e = catalog.effects.find((e) => e.id === 'remove-object');
              if (e) chooseEffect(e);
            }}
          >
            VFX<span className="nav-badge">OPEN</span>
          </button>
          <button
            className={view === 'library' ? 'active' : ''}
            onClick={() => navigate('library')}
          >
            Library
          </button>
        </nav>
        <div className="topbar-right">
          <a
            className="cloud-link"
            href="https://comfy.org/platform/"
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="cloud" size={15} />
            <span>Comfy Cloud</span>
            <Icon name="external" size={12} />
          </a>
          <button
            className="icon-button"
            onClick={() => setModal('settings')}
            aria-label="Open compute settings"
          >
            <Icon name="settings" size={18} />
          </button>
          <button
            className={`compute-status ${provider?.available === true ? 'connected' : ''}`}
            title={`${provider?.name || 'Compute'} · ${provider?.available === true ? 'Connection verified' : provider?.available === false ? 'Connection unavailable' : 'Connection not checked'}`}
            onClick={() => setModal('provider')}
          >
            <span className={provider?.available ? 'status-dot online' : 'status-dot'} />
            <span className="compute-name">{provider?.name || 'Choose compute'}</span>
            <Icon name="down" size={12} />
          </button>
        </div>
      </header>
      {offline && (
        <div className="offline-banner">
          <Icon name="info" size={16} />
          <span>Server connection lost. Your draft is saved in this browser.</span>
          <button onClick={refresh}>Reconnect</button>
        </div>
      )}
      {error && (
        <div className="global-error">
          <ErrorBox message={error} onDismiss={() => setError('')} />
        </div>
      )}
      <main className={`app-shell ${view === 'library' ? 'library-shell' : ''}`}>
        {view === 'studio' && (
          <aside className={`controls-panel ${mobileControls ? 'mobile-open' : ''}`}>
            <div className="controls-tabs">
              <button
                className={!effect?.requires_video && !editingTools ? 'active' : ''}
                onClick={() => {
                  const e = catalog.effects.find((e) => e.id === 'text-to-video');
                  if (e) chooseEffect(e);
                }}
              >
                Create Video
              </button>
              <button
                className={effect?.requires_video || editingTools ? 'active' : ''}
                onClick={() => {
                  setEditingTools(true);
                  setSelectedJob(null);
                  setPanel('help');
                }}
              >
                Edit Video
              </button>
              <button onClick={() => setModal('advanced')}>Advanced</button>
              <button
                className="mobile-close icon-button"
                onClick={() => setMobileControls(false)}
                aria-label="Close controls"
              >
                <Icon name="close" />
              </button>
            </div>
            <div className="controls-scroll">
              <button
                className="preset-banner"
                aria-label="Change preset"
                onClick={() => {
                  setSelectedJob(null);
                  setPanel('effects');
                  setMobileControls(false);
                }}
              >
                <SceneArt id={draft.effect_id}>
                  <span className="change-preset">
                    <Icon name="brush" size={12} />
                    Change
                  </span>
                  <div className="preset-title">
                    <strong>
                      {editingTools
                        ? 'EDITING TOOLS'
                        : draft.effect_id === 'text-to-video'
                          ? 'GENERAL'
                          : effect?.name.toUpperCase()}
                    </strong>
                    <span>
                      {editingTools
                        ? 'Modify, restyle, change angles, transform'
                        : model?.name || 'Loading models…'}
                    </span>
                  </div>
                </SceneArt>
              </button>
              {editingTools ? (
                <div className="editing-tools-list">
                  {catalog.effects
                    .filter((e) => e.requires_video)
                    .map((e) => (
                      <button key={e.id} onClick={() => chooseEffect(e)}>
                        <Icon name={e.requires_mask ? 'mask' : 'sliders'} size={22} />
                        <span>
                          <strong>{e.name === 'Vanish' ? 'Remove Object' : e.name}</strong>
                          <small>{e.description}</small>
                        </span>
                        <Icon name="chevron" size={16} />
                      </button>
                    ))}
                </div>
              ) : (
                <>
                  <div className="input-mode">
                    <button
                      className={!drawMode ? 'active' : ''}
                      onClick={() => {
                        if (effect?.requires_video) {
                          setDrawMode(false);
                          promptInput.current?.focus();
                        } else setModal('asset-source');
                      }}
                    >
                      <Icon name={effect?.requires_video ? 'sliders' : 'image'} size={14} />
                      {effect?.requires_video ? 'Prompt' : 'References'}
                    </button>
                    <button
                      className={drawMode ? 'active' : ''}
                      onClick={() => {
                        if (effect?.requires_video) {
                          setDrawMode(true);
                          if (!effect.requires_mask) {
                            const masked = catalog.effects.find((e) => e.id === 'replace-object');
                            if (masked)
                              update({
                                effect_id: masked.id,
                                prompt: draft.prompt || masked.prompt,
                              });
                          }
                          setModal(source ? 'mask' : 'draw-source');
                        } else setModal('asset-source');
                      }}
                    >
                      <Icon name={effect?.requires_video ? 'brush' : 'folder'} size={14} />
                      {effect?.requires_video ? 'Draw' : 'My media'}
                      {mask && effect?.requires_video && <Icon name="check" size={12} />}
                    </button>
                  </div>
                  <div
                    ref={sourceAnchor}
                    className={`upload-zone ${source ? 'has-asset' : ''}`}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => drop(e, 'source')}
                  >
                    {source ? (
                      <>
                        <button className="source-preview" onClick={() => browse('source')}>
                          {source.kind === 'video' ? (
                            <video
                              src={mediaUrl(source)}
                              poster={source.thumbnail_url || undefined}
                              muted
                              preload="metadata"
                            />
                          ) : (
                            <img src={mediaUrl(source)} alt={source.name} />
                          )}
                          <span className="source-caption">{source.name}</span>
                        </button>
                        <button
                          className="remove-asset"
                          aria-label="Remove source"
                          onClick={() =>
                            update({ source_asset_id: undefined, mask_asset_id: undefined })
                          }
                        >
                          <Icon name="close" size={14} />
                        </button>
                        <span className="asset-badge">
                          {source.kind === 'video'
                            ? `${source.duration?.toFixed(1) || ''}s`
                            : 'IMAGE'}
                        </span>
                      </>
                    ) : (
                      <button
                        onClick={() => setModal('asset-source')}
                        className="upload-button"
                        aria-label="Add references"
                      >
                        <div className="upload-symbols">
                          <span className="upload-symbol">
                            <Icon name={effect?.requires_video ? 'video' : 'image'} size={16} />
                          </span>
                          {!effect?.requires_video && (
                            <span className="upload-symbol">
                              <Icon name="video" size={16} />
                            </span>
                          )}
                        </div>
                        <strong>
                          {effect?.requires_video
                            ? 'Add a video to edit'
                            : effect?.requires_image
                              ? 'Add a starting image'
                              : 'Add references'}
                        </strong>
                        <span>
                          {effect?.requires_video ? 'MP4, MOV or WebM' : 'Image or video'}
                        </span>
                      </button>
                    )}
                  </div>
                  {effect?.requires_mask && (
                    <div className="mask-control">
                      <button
                        className={`secondary ${mask ? 'selected' : ''}`}
                        disabled={!source}
                        onClick={() => setModal('mask')}
                      >
                        <Icon name="mask" />
                        {mask ? 'Edit selection mask' : 'Paint an edit mask'}
                        {mask && <Icon name="check" size={14} />}
                      </button>
                      {!source && <small>Add your video to select an area.</small>}
                    </div>
                  )}
                  {supportsReference && (
                    <div className="reference-row">
                      <button
                        className="reference-button"
                        onClick={() => setModal('asset-reference')}
                      >
                        <Icon name="image" size={15} />
                        <span>{reference ? reference.name : 'Add elements or references'}</span>
                        {!reference && <small>Reference image · optional</small>}
                        {!reference && <Icon name="plus" size={15} />}
                      </button>
                      {reference ? (
                        <button
                          className="icon-button"
                          aria-label="Remove reference"
                          onClick={() => update({ reference_asset_id: undefined })}
                        >
                          <Icon name="close" size={14} />
                        </button>
                      ) : null}
                    </div>
                  )}
                  <label className="prompt-box">
                    <span>Prompt</span>
                    <textarea
                      ref={promptInput}
                      value={draft.prompt}
                      onChange={(e) => update({ prompt: e.target.value })}
                      placeholder={
                        effect?.requires_video
                          ? 'Describe the scene you want to see after the edit…'
                          : 'Describe your shot: subject, movement, camera and light…'
                      }
                      rows={5}
                    />
                    <div className="prompt-footer">
                      <button
                        type="button"
                        onClick={() =>
                          setModal(supportsReference ? 'asset-reference' : 'asset-source')
                        }
                        title="Choose media from your library"
                      >
                        <Icon name="image" size={13} />
                        Elements
                      </button>
                      <button
                        type="button"
                        disabled={!model?.supports_audio && !effect?.requires_video}
                        onClick={() =>
                          model?.supports_audio
                            ? update({ generate_audio: !draft.generate_audio })
                            : update({ preserve_audio: !draft.preserve_audio })
                        }
                        title={
                          model?.supports_audio
                            ? 'Generate audio with this model'
                            : 'Preserve source audio'
                        }
                      >
                        <Icon name="sound" size={13} />
                        {(
                          model?.supports_audio
                            ? draft.generate_audio
                            : effect?.requires_video && draft.preserve_audio
                        )
                          ? 'On'
                          : 'Off'}
                      </button>
                      <button
                        className="reset-prompt"
                        type="button"
                        title="Restore preset prompt"
                        onClick={() => {
                          if (effect) update({ prompt: effect.prompt });
                        }}
                      >
                        <Icon name="refresh" size={13} />
                      </button>
                    </div>
                  </label>
                  <button
                    ref={modelAnchor}
                    className="model-control"
                    aria-label="Model"
                    aria-haspopup="dialog"
                    aria-expanded={modal === 'model'}
                    onClick={() => setModal('model')}
                  >
                    <span>
                      <small>Model</small>
                      <strong>
                        {model?.name || 'Select model'}
                        <span className="mini-wave">▥</span>
                      </strong>
                    </span>
                    <Icon name="chevron" size={15} />
                  </button>
                  <div className="control-grid">
                    <FieldSelect
                      label="Duration"
                      hint={
                        cloudRemoval
                          ? 'Start with 2s; longer/high-resolution jobs can exceed Cloud execution limits. Durations are never automatically shortened or retried.'
                          : undefined
                      }
                      value={duration(draft).toFixed(0)}
                      onChange={(v) => {
                        const n = Number(model?.frame_multiple || 8);
                        update({
                          frames: Math.min(
                            Number(model?.max_frames || 241),
                            Math.round((+v * draft.fps) / n) * n + 1,
                          ),
                        });
                      }}
                    >
                      {[2, 4, 6, 8]
                        .filter((n) => n * draft.fps < Number(model?.max_frames || 241))
                        .map((n) => (
                          <option key={n} value={n}>
                            {n}s
                          </option>
                        ))}
                      {![2, 4, 6, 8].includes(Math.round(duration(draft))) && (
                        <option value={duration(draft).toFixed(0)}>
                          {duration(draft).toFixed(1)}s
                        </option>
                      )}
                    </FieldSelect>
                    <FieldSelect label="Aspect Ratio" value={ratioLabel} onChange={setRatio}>
                      {(model?.aspect_ratios || ['16:9', '9:16', '1:1', '4:3']).map((r) => (
                        <option key={r}>{r}</option>
                      ))}
                      {ratioLabel === 'custom' && <option value="custom">Custom</option>}
                    </FieldSelect>
                    <FieldSelect
                      label="Quality"
                      value={Math.max(draft.width, draft.height)}
                      onChange={(v) => setQuality(+v)}
                    >
                      {(draft.model_id === 'wan-vace' ? [512, 768, 1024] : [512, 1024]).map((n) => (
                        <option key={n} value={n}>
                          {n === 512 ? 'Preview' : n === 768 ? 'Standard' : 'HD'} · {n}
                        </option>
                      ))}
                      {!(draft.model_id === 'wan-vace' ? [512, 768, 1024] : [512, 1024]).includes(
                        Math.max(draft.width, draft.height),
                      ) && (
                        <option value={Math.max(draft.width, draft.height)}>
                          Custom · {Math.max(draft.width, draft.height)}
                        </option>
                      )}
                    </FieldSelect>
                    <FieldSelect
                      label="Frame rate"
                      value={draft.fps}
                      onChange={(v) =>
                        update({
                          fps: +v,
                          ...(source?.kind === 'video'
                            ? {
                                frames: fitFrames(
                                  draft.frames,
                                  +v,
                                  Number(model?.frame_multiple || 8),
                                  Math.max(0, (source.duration || 0) - draft.trim_start),
                                ),
                              }
                            : {}),
                        })
                      }
                    >
                      {[12, 16, 24, 30].map((n) => (
                        <option value={n} key={n}>
                          {n} fps
                        </option>
                      ))}
                    </FieldSelect>
                  </div>
                  {source?.kind === 'video' && (source.duration || 0) > duration(draft) + 0.2 && (
                    <p className="clip-note">
                      Rendering {draft.trim_start.toFixed(1)}–
                      {(draft.trim_start + duration(draft)).toFixed(1)}s of your{' '}
                      {source.duration?.toFixed(1)}s clip.
                    </p>
                  )}
                </>
              )}
            </div>
            {!editingTools && (
              <div className="generate-footer">
                <button
                  className="generate-button"
                  disabled={!!busy || loading || offline}
                  onClick={generate}
                >
                  <Icon name={busy ? 'clock' : 'spark'} size={19} />
                  {busy === 'upload' ? 'Uploading…' : busy === 'generate' ? 'Queuing…' : 'Generate'}
                  <span>⌘ ↵</span>
                </button>
                <div className="footer-actions">
                  <button
                    onClick={() => {
                      setPresetName(effect?.name || 'My preset');
                      setModal('save-preset');
                    }}
                  >
                    <Icon name="save" size={13} />
                    Save preset
                  </button>
                  <button onClick={() => exportWorkflow()}>
                    <Icon name="code" size={13} />
                    Workflow
                  </button>
                </div>
              </div>
            )}
          </aside>
        )}
        <section className="stage-panel">
          {view === 'studio' && (
            <div className={`stage-tabs ${panel === 'effects' ? 'picker-open' : ''}`}>
              <div>
                <button
                  className={panel === 'history' ? 'active' : ''}
                  onClick={() => {
                    setSelectedJob(null);
                    setPanel('history');
                  }}
                >
                  <Icon name="clock" size={15} />
                  History
                  {activeJobs.length > 0 && <span className="count">{activeJobs.length}</span>}
                </button>
                <button
                  className={panel === 'help' ? 'active' : ''}
                  onClick={() => {
                    setSelectedJob(null);
                    setPanel('help');
                  }}
                >
                  <Icon name="book" size={15} />
                  How it works
                </button>
              </div>
              <button
                className="small-button"
                onClick={() => exportWorkflow()}
                title="Export your portable ComfyUI workflow"
              >
                <Icon name="code" size={15} />
                <span>ComfyUI workflow</span>
              </button>
            </div>
          )}
          {loading ? (
            <div className="loading-state">
              <div className="skeleton skeleton-title" />
              <div className="skeleton-grid">
                {[0, 1, 2, 3, 4, 5].map((i) => (
                  <div className="skeleton" key={i} />
                ))}
              </div>
              <p>Loading your studio…</p>
            </div>
          ) : view === 'library' ? (
            <MediaLibrary {...libraryProps} />
          ) : currentJob && panel === 'history' ? (
            <>
              <div className="back-row">
                <button className="text-button" onClick={() => setSelectedJob(null)}>
                  ← All creations
                </button>
                <span className="muted small">
                  {new Date(currentJob.created_at).toLocaleString()}
                </span>
              </div>
              {currentJob.warnings?.length ? (
                <div className="job-warnings">
                  {currentJob.warnings.map((w, i) => (
                    <p key={i}>
                      <Icon name="info" size={14} />
                      {w}
                    </p>
                  ))}
                </div>
              ) : null}
              {currentJob.status === 'succeeded' ? (
                <JobResult
                  job={currentJob}
                  source={
                    assets.find((a) => a.id === currentJob.request.source_asset_id) ||
                    assetCache[currentJob.request.source_asset_id || '']
                  }
                  onReuse={() => reuse(currentJob)}
                  onExport={(kind) =>
                    exportWorkflow(currentJob, kind === 'bundle', kind === 'canvas')
                  }
                  onFavorite={() => jobAction(currentJob, 'favorite')}
                  onError={setError}
                />
              ) : (
                <div className="render-state">
                  <div
                    className={`render-symbol ${currentJob.status === 'running' ? 'rendering' : ''}`}
                  >
                    <Icon
                      name={
                        currentJob.status === 'failed'
                          ? 'info'
                          : currentJob.status === 'cancelled'
                            ? 'stop'
                            : 'film'
                      }
                      size={42}
                    />
                  </div>
                  <span className="eyebrow">
                    {currentJob.request.model_id} · {currentJob.request.provider}
                  </span>
                  <h1>
                    {currentJob.status === 'queued'
                      ? 'YOUR SHOT IS IN THE QUEUE'
                      : currentJob.status === 'running'
                        ? 'MAKING YOUR NEXT SHOT'
                        : currentJob.status === 'failed'
                          ? 'THIS RENDER NEEDS ATTENTION'
                          : 'RENDER CANCELLED'}
                  </h1>
                  <p>{renderStage(currentJob.stage || currentJob.status)}</p>
                  {['running', 'queued'].includes(currentJob.status) && (
                    <>
                      <div className="render-progress">
                        <i style={{ width: `${Math.max(1, currentJob.progress * 100)}%` }} />
                      </div>
                      <strong>{Math.round(currentJob.progress * 100)}%</strong>
                      <p className="muted small">
                        You can keep exploring. Your render is saved in History.
                      </p>
                      <button className="secondary" onClick={() => jobAction(currentJob, 'cancel')}>
                        Cancel render
                      </button>
                    </>
                  )}
                  {currentJob.error && <ErrorBox message={currentJob.error} />}{' '}
                  {currentJob.request.provider === 'comfy-cloud' &&
                    currentJob.error?.includes('Job execution time exceeded maximum limit') && (
                      <p className="muted small">
                        The hosted service stopped this job. Choose fewer frames or a lower
                        resolution, or use Modal or local ComfyUI. The requested duration was not
                        changed and no automatic retry was made.
                      </p>
                    )}
                  {['failed', 'cancelled'].includes(currentJob.status) && (
                    <div className="button-row">
                      <button className="secondary" onClick={() => reuse(currentJob)}>
                        Edit settings
                      </button>
                      <button className="primary" onClick={() => jobAction(currentJob, 'retry')}>
                        <Icon name="refresh" />
                        Retry render
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          ) : panel === 'history' ? (
            <HistoryPanel
              jobTotal={jobTotal}
              onLoadMore={() => setJobLimit((n) => Math.min(jobTotal, n + 100))}
              loadingMore={jobs.length < Math.min(jobLimit, jobTotal)}
              {...{
                catalog,
                filteredJobs,
                historyFilter,
                setHistoryFilter,
                activeJobs,
                jobs,
                selectedJob,
                setSelectedJob,
                setPanel,
                refresh,
                jobAction,
                reuse,
                exportWorkflow,
              }}
            />
          ) : panel === 'help' ? (
            <HelpPanel
              editing={editingTools || !!effect?.requires_video}
              onSettings={() => setModal('settings')}
              onUpload={() => setModal('asset-source')}
              onPresets={() => setPanel('effects')}
            />
          ) : (
            <EffectsPanel
              {...{
                catalog,
                draft,
                category,
                setCategory,
                query,
                setQuery,
                filteredEffects,
                loading,
                chooseEffect,
                exportWorkflow,
              }}
              onPresets={() => setModal('presets')}
              onClose={() => setPanel('help')}
              onModelSelect={chooseModel}
            />
          )}
        </section>
      </main>
      <nav className="reference-mobile-nav" aria-label="Mobile navigation">
        <button
          onClick={() => {
            setSelectedJob(null);
            navigate('studio', 'help');
          }}
        >
          <Icon name="grid" />
          Home
        </button>
        <button onClick={() => navigate('studio', 'effects')}>
          <Icon name="film" />
          Presets
        </button>
        <button
          className="mobile-generate"
          aria-label="Generate"
          onClick={() => {
            if (view !== 'studio') navigate('studio', 'help');
            setMobileControls(true);
          }}
        >
          <Icon name="spark" />
        </button>
        <button onClick={() => navigate('library')}>
          <Icon name="folder" />
          Library
        </button>
        <button onClick={() => setModal('settings')}>
          <Icon name="settings" />
          Settings
        </button>
      </nav>
      {notice && (
        <div className="toast" role="status">
          <Icon name="check" size={17} />
          {notice}
        </div>
      )}
      {modal === 'model' && (
        <ModelPopover
          anchor={modelAnchor.current}
          selected={draft.model_id}
          onClose={() => setModal(null)}
          onSelect={chooseModel}
          options={catalog.models
            .filter((m) => effect?.model_ids.includes(m.id) ?? true)
            .map((m) => ({
              id: m.id,
              name: m.name,
              description: m.description,
              badge: String(m.badge || ''),
            }))}
        />
      )}
      {modal === 'advanced' && (
        <Modal title="Advanced controls" onClose={() => setModal(null)}>
          <div className="modal-content">
            <div className="advanced-controls">
              <div className="control-grid">
                <label className="input-label">
                  Seed
                  <input
                    type="number"
                    min="-1"
                    max="9007199254740991"
                    value={draft.seed}
                    onChange={(e) => update({ seed: +e.target.value })}
                  />
                </label>
                <label className="input-label">
                  Steps
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={draft.steps}
                    onChange={(e) => update({ steps: +e.target.value })}
                  />
                </label>
                <label className="input-label">
                  Guidance
                  <input
                    type="number"
                    min="0"
                    max="20"
                    step=".1"
                    value={draft.guidance}
                    onChange={(e) => update({ guidance: +e.target.value })}
                  />
                </label>
                <label className="input-label">
                  Frames
                  <input
                    type="number"
                    min="9"
                    max={Number(model?.max_frames || 241)}
                    step={Number(model?.frame_multiple || 8)}
                    value={draft.frames}
                    onChange={(e) => update({ frames: +e.target.value })}
                  />
                </label>
              </div>
              <p className="muted small">
                Seed −1 chooses a new seed. Output: {draft.width} × {draft.height}, {draft.frames}{' '}
                frames.
              </p>
              <label className="input-label">
                Negative prompt
                <textarea
                  rows={2}
                  value={draft.negative_prompt}
                  onChange={(e) => update({ negative_prompt: e.target.value })}
                  placeholder="What should stay out of the shot?"
                />
              </label>
              {effect?.requires_video && (
                <>
                  <label className="input-label">
                    Start time (seconds)
                    <input
                      type="number"
                      min="0"
                      max={Math.max(0, (source?.duration || 0) - 0.5)}
                      step=".1"
                      value={draft.trim_start}
                      onChange={(e) =>
                        update({
                          trim_start: +e.target.value,
                          mask_asset_id: undefined,
                          frames: source
                            ? fitFrames(
                                draft.frames,
                                draft.fps,
                                Number(model?.frame_multiple || 8),
                                Math.max(0, (source.duration || 0) - +e.target.value),
                              )
                            : draft.frames,
                        })
                      }
                    />
                  </label>
                  <label className="range-label">
                    {strengthControl?.label || 'Edit strength'}
                    <span>{draft.strength.toFixed(2)}</span>
                    <input
                      type="range"
                      min=".1"
                      max="1"
                      step=".05"
                      value={draft.strength}
                      onChange={(e) => update({ strength: +e.target.value })}
                    />
                  </label>
                  {strengthControl?.hint && <p className="muted small">{strengthControl.hint}</p>}
                  <Toggle
                    label="Keep source audio"
                    checked={draft.preserve_audio}
                    onChange={(v) => update({ preserve_audio: v })}
                  />
                </>
              )}
              {!!model?.supports_audio && (
                <Toggle
                  label="Generate audio"
                  checked={draft.generate_audio}
                  onChange={(v) => update({ generate_audio: v })}
                />
              )}{' '}
              {effect?.requires_mask && (
                <>
                  <Toggle
                    label="Preserve outside mask"
                    checked={draft.preserve_outside_mask}
                    onChange={(v) => update({ preserve_outside_mask: v })}
                  />
                  <FieldSelect
                    label="Selection tracking"
                    value={draft.mask_tracking_method}
                    onChange={(v) =>
                      update({ mask_tracking_method: v, mask_tracking: v !== 'static' })
                    }
                  >
                    <option value="sam2">SAM2 · object tracking</option>
                    <option value="flow">Optical flow · motion</option>
                    <option value="static">Static mask</option>
                  </FieldSelect>
                  <label className="range-label">
                    Edit margin
                    <span>{draft.mask_edit_margin ?? (draft.mask_tracking ? 12 : 0)}px</span>
                    <input
                      type="range"
                      min="0"
                      max="64"
                      value={draft.mask_edit_margin ?? (draft.mask_tracking ? 12 : 0)}
                      onChange={(e) => update({ mask_edit_margin: +e.target.value })}
                    />
                  </label>
                  <p className="muted small">
                    Includes this many output pixels around the tracked or painted mask, so blending
                    does not restore object edges. Nearby pixels may change.
                  </p>
                  <label className="range-label">
                    Generation margin<span>{draft.mask_dilation}px</span>
                    <input
                      type="range"
                      min="0"
                      max="64"
                      value={draft.mask_dilation}
                      onChange={(e) => update({ mask_dilation: +e.target.value })}
                    />
                  </label>
                  <label className="range-label">
                    Blend softness<span>{draft.mask_feather}px</span>
                    <input
                      type="range"
                      min="0"
                      max="32"
                      value={draft.mask_feather}
                      onChange={(e) => update({ mask_feather: +e.target.value })}
                    />
                  </label>
                </>
              )}
            </div>
            <div className="dialog-actions">
              <button className="secondary" onClick={() => setModal('presets')}>
                My presets
              </button>
              <button
                className="secondary"
                onClick={() => {
                  setPresetName(effect?.name || 'My preset');
                  setModal('save-preset');
                }}
              >
                <Icon name="save" />
                Save preset
              </button>
              <button className="secondary" onClick={() => exportWorkflow()}>
                <Icon name="code" />
                Export workflow
              </button>
            </div>
          </div>
        </Modal>
      )}
      {modal === 'provider' && (
        <Modal title="Where should this render run?" onClose={() => setModal(null)}>
          <div className="modal-content">
            <div className="choice-list">
              {catalog.providers.map((p) => (
                <button
                  className={`choice ${draft.provider === p.id ? 'selected' : ''}`}
                  key={p.id}
                  onClick={() => {
                    update({ provider: p.id });
                    setModal(null);
                  }}
                >
                  <span className="model-symbol">
                    <Icon name={p.id === 'local' ? 'monitor' : 'cloud'} />
                  </span>
                  <span>
                    <strong>{p.name}</strong>
                    <small>
                      {p.available
                        ? 'Connection verified'
                        : p.available === false
                          ? 'Connection unavailable · check settings'
                          : p.configured
                            ? 'Configured · verify connection'
                            : 'Connect in settings'}
                    </small>
                  </span>
                  {draft.provider === p.id && <Icon name="check" />}
                </button>
              ))}
            </div>
            <p className="muted small">
              Availability depends on your configured worker and installed model files.
            </p>
            <button className="secondary full-width" onClick={() => setModal('settings')}>
              <Icon name="settings" />
              Manage connections
            </button>
          </div>
        </Modal>
      )}
      {modal === 'settings' && (
        <SettingsPanel
          settings={settings}
          providers={catalog.providers}
          onSaved={(s) => {
            setSettings(s);
            if (s.default_provider) update({ provider: s.default_provider });
            void api<Catalog>('/catalog')
              .then(setCatalog)
              .catch(() => {});
          }}
          onClose={() => setModal(null)}
        />
      )}
      {modal === 'draw-source' && (
        <Modal title="Draw to Edit" wide onClose={() => setModal(null)}>
          <div className="draw-empty">
            <div className="draw-preview">
              <img
                src="/previews/ltx-fast-vase.jpg"
                alt="Original generated source example for drawing an edit mask"
              />
              <span className="draw-example-mask" />
            </div>
            <h2>DRAW TO EDIT</h2>
            <p>Sketch on the frame to remove, add, or replace.</p>
            <button className="primary" onClick={() => setModal('asset-source')}>
              <Icon name="upload" />
              Upload media
            </button>
          </div>
        </Modal>
      )}
      {modal === 'mask' && source && (
        <MaskEditor
          asset={source}
          existingMask={mask}
          startTime={draft.trim_start}
          onClose={() => setModal(null)}
          onSave={(a) => {
            setAssets((s) => [a, ...s]);
            update({ mask_asset_id: a.id });
            notify('Selection mask saved.');
          }}
        />
      )}
      {modal === 'save-preset' && (
        <Modal title="Save your creative setup" onClose={() => setModal(null)}>
          {error && <ErrorBox message={error} onDismiss={() => setError('')} />}
          <div className="modal-content">
            <p className="muted">
              Save the model, effect, prompt and render settings as a reusable preset.
            </p>
            <label className="input-label">
              Preset name
              <input
                autoFocus
                value={presetName}
                onChange={(e) => setPresetName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void savePreset();
                }}
                maxLength={100}
              />
            </label>
            <button
              className="primary full-width"
              disabled={!presetName.trim() || busy === 'preset'}
              onClick={savePreset}
            >
              <Icon name="save" />
              {busy === 'preset' ? 'Saving…' : 'Save preset'}
            </button>
          </div>
        </Modal>
      )}
      {modal === 'presets' && (
        <Modal title="Your presets" onClose={() => setModal(null)}>
          <div className="modal-content">
            {presets.length ? (
              <div className="preset-list">
                {presets.map((p) => (
                  <div key={p.id}>
                    <button
                      onClick={() => {
                        preserveResolution();
                        setDraft({ ...initial, ...p.request });
                        setModal(null);
                        setSelectedJob(null);
                        navigate('studio', 'effects');
                        notify(`${p.name} loaded`);
                      }}
                    >
                      <Icon name="save" />
                      <span>
                        <strong>{p.name}</strong>
                        <small>
                          {p.request.model_id} · {p.request.effect_id}
                        </small>
                      </span>
                      <Icon name="chevron" />
                    </button>
                    <button
                      className="icon-button"
                      aria-label={`Delete ${p.name}`}
                      onClick={async () => {
                        try {
                          await api(`/presets/${p.id}`, { method: 'DELETE' });
                          setPresets((ps) => ps.filter((x) => x.id !== p.id));
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }}
                    >
                      <Icon name="trash" size={16} />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon="save"
                title="Keep your favorite setups"
                description="Save a prompt and its render settings to reuse them in your next shot."
                action={
                  <button
                    className="primary"
                    onClick={() => {
                      setPresetName(effect?.name || 'My preset');
                      setModal('save-preset');
                    }}
                  >
                    Save current setup
                  </button>
                }
              />
            )}
          </div>
        </Modal>
      )}
      {(modal === 'asset-source' || modal === 'asset-reference') && (
        <AnchoredPopover
          anchor={sourceAnchor.current}
          onClose={() => setModal(null)}
          width={600}
          top={90}
          label="Media library"
          className="asset-popover"
        >
          <div className="asset-popover-tabs">
            <button
              className={assetFilter === 'All' ? 'active' : ''}
              onClick={() => setAssetFilter('All')}
            >
              Uploads
            </button>
            <button
              className={assetFilter === 'Image' ? 'active' : ''}
              onClick={() => setAssetFilter('Image')}
            >
              Images
            </button>
            {modal !== 'asset-reference' && (
              <button
                className={assetFilter === 'Video' ? 'active' : ''}
                onClick={() => setAssetFilter('Video')}
              >
                Videos
              </button>
            )}
            <button
              className="icon-button"
              aria-label="Close media library"
              onClick={() => setModal(null)}
            >
              <Icon name="close" size={16} />
            </button>
          </div>
          {error && <ErrorBox message={error} onDismiss={() => setError('')} />}
          <MediaLibrary
            {...libraryProps}
            picker={modal === 'asset-reference' ? 'reference' : 'source'}
          />
        </AnchoredPopover>
      )}
    </>
  );
}
