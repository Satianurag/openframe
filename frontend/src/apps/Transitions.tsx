import { useRef, useState } from 'react';
import { api, mediaUrl, post, upload } from '../api';
import { Icon } from '../Icon';
import type { Asset, Job, JobRequest } from '../types';
import type { AppDocument } from './registry';
import { useAppDocument } from './useAppDocument';
import { renderRequest, renderSize } from './renderRequest';
import {
  AssetPicker,
  ReferenceMedia,
  ResultDialog,
  SourceSlot,
  useReferenceLibrary,
  useWorkspaceAssets,
  WorkspaceDialog,
  WorkspaceHistory,
} from './engine-apps-shared';
import type { EngineAppProps, ReferenceItem } from './engine-apps-shared';
import './transitions.css';

const directions: Record<string, string> = {
  'Raven Transition':
    'A flock of dark birds crosses the camera, briefly filling the frame before revealing the destination scene.',
  Morph:
    'Transform the shapes and materials of the first scene smoothly into the second scene, maintaining continuous visual movement.',
  'Air Bending':
    'A swirling current of air and light dust carries the first scene into the destination scene.',
  'Shadow Smoke':
    'Dark curling smoke sweeps across the frame and dissipates to reveal the second scene.',
  'Water Bending':
    'A flowing ribbon of water wraps across the image, refracting the scene and revealing the destination.',
  Firelava:
    'A wave of glowing molten textures and sparks transforms the first scene into the second.',
  'Flying Cam Transition':
    'The camera flies forward through the first scene and arrives smoothly inside the destination scene.',
  'Melt Transition':
    'The first scene flows into liquid-like shapes that resolve into the destination scene.',
  'Splash Transition':
    'A vivid liquid splash fills the lens, then falls away to reveal the second scene.',
  'Flame Transition':
    'A bright flame sweeps across the image and clears into the destination scene.',
  'Smoke Transition':
    'Soft atmospheric smoke fills the frame and clears to reveal the second scene.',
  'Logo Transform':
    'Transform the central shape of the first image into the central shape of the destination, with clean coordinated movement.',
  'Hand Transition':
    'A hand moves toward the lens and covers the frame, then withdraws to reveal the destination scene.',
  'Column Wipe':
    'Vertical architectural columns pass across the camera, revealing the destination between them.',
  'Hole Transition':
    'A portal opens within the first scene and the camera moves through it into the destination.',
  'Display Transition':
    'Move the camera into a screen within the first scene, then expand its image to reveal the destination scene.',
  'Jump Transition':
    'Use an energetic upward camera movement to connect the first scene to the destination with a coherent landing.',
  'Seamless Transition':
    'Connect the composition and motion of the first scene to the second with a smooth, natural camera movement.',
  Trucksition:
    'A truck crosses close to the camera, covering the frame and revealing the destination as it passes.',
  'Gorilla Transfer':
    'A large gorilla passes close to the lens, covering the scene before revealing the destination.',
  Intermission:
    'Transition through a brief abstract cinematic light-and-color interlude into the destination scene.',
  'Stranger Transition':
    'A dark swirling portal with red atmospheric light opens into the destination scene.',
  'Earth Wave':
    'A wave of earth and dust rises across the image and settles to reveal the destination scene.',
};
type State = {
  kind: 'transition-video';
  model_id: string;
  source_asset_id: string;
  end_asset_id: string;
  reference_asset_id: string;
  enhance_prompt: boolean;
  effect: string;
  prompt: string;
  frames: number;
  ratio: string;
  resolution: number;
  seed: number;
  transition_include_inputs: boolean;
  preserve_audio: boolean;
  generate_audio?: boolean;
  reframe_fit: 'crop' | 'pad';
  anchor_x: number;
  anchor_y: number;
  encoding_quality: 'legacy' | 'standard' | 'high';
  replay_settings?: Partial<
    Pick<
      JobRequest,
      'steps' | 'guidance' | 'strength' | 'negative_prompt' | 'video_refinement' | 'generate_audio'
    >
  >;
};
const initial: State = {
  kind: 'transition-video',
  model_id: '',
  source_asset_id: '',
  end_asset_id: '',
  reference_asset_id: '',
  enhance_prompt: true,
  effect: 'Raven Transition',
  prompt: directions['Raven Transition'],
  frames: 121,
  ratio: 'Auto',
  resolution: 1024,
  seed: -1,
  transition_include_inputs: false,
  preserve_audio: true,
  reframe_fit: 'crop',
  anchor_x: 0.5,
  anchor_y: 0.5,
  encoding_quality: 'high',
};
const ids = (state: State) =>
  [state.source_asset_id, state.end_asset_id, state.reference_asset_id].filter(Boolean);

export function Transitions({ catalog, settings, onSettings }: EngineAppProps) {
  const session = useAppDocument('mini-apps', initial, ids, 'transition-video', 'Transitions');
  const state = { ...initial, ...session.state };
  const assets = useWorkspaceAssets(ids(state));
  const library = useReferenceLibrary('transitions');
  const [picker, setPicker] = useState<{
    slot: 'source' | 'end' | 'guide';
    kind: 'image' | 'video';
  } | null>(null);
  const [uploadSlot, setUploadSlot] = useState<'source' | 'end'>('source');
  const [effectsOpen, setEffectsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [advanced, setAdvanced] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<Job | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const source = assets.get(state.source_asset_id),
    end = assets.get(state.end_asset_id),
    guide = assets.get(state.reference_asset_id);
  const definition = catalog.effects.find((item) => item.id === 'transition-video');
  const models = catalog.models.filter((item) => definition?.model_ids.includes(item.id));
  const model = state.model_id ? models.find((item) => item.id === state.model_id) : models[0];
  const supportsGuide =
    !!model &&
    Array.isArray(model.reference_tasks) &&
    model.reference_tasks.includes('transition-video');
  const supportsEnhancement =
    !!model &&
    Array.isArray(model.prompt_enhancement_tasks) &&
    model.prompt_enhancement_tasks.includes('transition-video');
  const fixedFraming = model?.fixed_framing === 'center-crop';
  const provider = settings.default_provider || 'local';
  const effects = library.effects || [];
  const current = effects.find((item) => item.title === state.effect) || effects[0];
  const filtered = effects.filter((item) =>
    item.title.toLowerCase().includes(search.toLowerCase()),
  );
  const ratio =
    state.ratio === 'Auto' && source?.width && source?.height
      ? `${source.width}:${source.height}`
      : state.ratio === 'Auto'
        ? '16:9'
        : state.ratio;
  const dimensions = model
    ? renderSize(model, ratio, state.resolution)
    : { width: 1024, height: 576 };
  const duration = state.frames / 24;
  const assembledDuration =
    duration +
    (state.transition_include_inputs
      ? (source?.kind === 'video' ? source.duration || 0 : 0) +
        (end?.kind === 'video' ? end.duration || 0 : 0)
      : 0);
  const jobs = session.jobs.filter((job) => job.request.effect_id === 'transition-video');
  function choose(asset: Asset, slot: 'source' | 'end' | 'guide') {
    if (slot === 'guide') {
      if (asset.kind !== 'image') {
        setError('Choose a still image for the midpoint guide.');
        return;
      }
      assets.add(asset);
      session.update({ reference_asset_id: asset.id });
      setError('');
      return;
    }
    if (!['image', 'video'].includes(asset.kind)) {
      setError('Choose an image or video.');
      return;
    }
    if (asset.kind === 'video' && ((asset.duration || 0) > 5.001 || (asset.fps || 0) > 120)) {
      setError(
        'Each input video must be no longer than 5 seconds and at most 120 fps. Trim or convert it first.',
      );
      return;
    }
    assets.add(asset);
    session.update(slot === 'source' ? { source_asset_id: asset.id } : { end_asset_id: asset.id });
    setError('');
  }
  async function addFile(value?: File, slot = uploadSlot) {
    if (!value) return;
    setBusy(true);
    setError('');
    try {
      choose(await upload(value), slot);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
      if (file.current) file.current.value = '';
    }
  }
  function chooseEffect(item: ReferenceItem) {
    const smokeDefault =
      item.title === 'Smoke Transition' && !state.model_id
        ? models.find((candidate) => candidate.id === 'ltx-2.3-transition')
        : undefined;
    session.update({
      effect: item.title,
      prompt:
        directions[item.title] || `Create a smooth cinematic transition inspired by ${item.title}.`,
      ...(smokeDefault
        ? {
            model_id: smokeDefault.id,
            enhance_prompt: false,
            reframe_fit: 'crop' as const,
            anchor_x: 0.5,
            anchor_y: 0.5,
            replay_settings: undefined,
          }
        : {}),
    });
    setEffectsOpen(false);
  }
  async function generate() {
    if (!model || !source || !end) return;
    setBusy(true);
    setError('');
    try {
      if (
        !session.application?.operations.find((item) => item.id === 'transition-video')?.available
      )
        throw new Error('The native transition operation is unavailable on this backend.');
      if (!['local'].includes(provider))
        throw new Error('Choose a supported local ComfyUI connection for this native transition.');
      if (!state.prompt.trim()) throw new Error('Describe the transition motion.');
      if (
        [source, end].some(
          (asset) =>
            asset.kind === 'video' && ((asset.duration || 0) > 5.001 || (asset.fps || 0) > 120),
        )
      )
        throw new Error('Each input video must be at most 5 seconds and 120 fps.');
      if (![121, 241].includes(state.frames))
        throw new Error('Choose the native 5-second or 10-second duration.');
      const limits = model.default_task_limits as
        { max_long_side?: number; max_pixels?: number } | undefined;
      if (
        dimensions.width > Number(model.max_width || 1920) ||
        dimensions.height > Number(model.max_height || 1920) ||
        Math.max(dimensions.width, dimensions.height) > Number(limits?.max_long_side || 1920) ||
        dimensions.width * dimensions.height > Number(limits?.max_pixels || 2088960)
      )
        throw new Error('Choose a smaller output canvas within this model’s limits.');
      if (
        fixedFraming &&
        (state.reframe_fit !== 'crop' || state.anchor_x !== 0.5 || state.anchor_y !== 0.5)
      )
        throw new Error(
          'This matched template uses centered cropping. Select its model again to apply that framing, or choose LTX 2.5 for custom anchors.',
        );
      if (state.reference_asset_id && (!guide || guide.kind !== 'image'))
        throw new Error('The midpoint image is unavailable. Choose another image or clear it.');
      if (guide && !supportsGuide)
        throw new Error(
          'This model does not support a midpoint guide. Clear it or choose a compatible model.',
        );
      const document = await session.save(true);
      if (!document) throw new Error('Save the draft before generating.');
      const request = renderRequest(model, {
        ...state.replay_settings,
        effect_id: 'transition-video',
        provider,
        prompt: state.prompt,
        source_asset_id: source.id,
        end_asset_id: end.id,
        reference_asset_id: guide?.id,
        enhance_prompt: supportsEnhancement && state.enhance_prompt,
        strength: state.replay_settings?.strength ?? Number(model.default_strength ?? 0.65),
        negative_prompt:
          state.replay_settings?.negative_prompt ?? String(model.default_negative_prompt ?? ''),
        generate_audio:
          state.generate_audio ??
          state.replay_settings?.generate_audio ??
          Boolean(model.default_generate_audio),
        frames: state.frames,
        fps: 24,
        ...dimensions,
        seed: state.seed,
        transition_include_inputs: state.transition_include_inputs,
        preserve_audio: state.preserve_audio,
        reframe_fit: state.reframe_fit,
        anchor_x: state.anchor_x,
        anchor_y: state.anchor_y,
        encoding_quality: state.encoding_quality,
      });
      const job = await post<Job>(`/apps/mini-apps/documents/${document.id}/jobs`, {
        expected_revision: document.revision,
        operation: 'transition-video',
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
      const context = await api<{ document_snapshot: AppDocument<State> }>(
        `/jobs/${job.id}/app-context`,
      );
      await session.newDocument({
        ...initial,
        ...context.document_snapshot.state,
        model_id: job.request.model_id,
        seed: job.request.seed,
        reference_asset_id: job.request.reference_asset_id || '',
        enhance_prompt: job.request.enhance_prompt ?? true,
        encoding_quality: job.request.encoding_quality || 'legacy',
        generate_audio: job.request.generate_audio,
        replay_settings: {
          steps: job.request.steps,
          guidance: job.request.guidance,
          strength: job.request.strength,
          negative_prompt: job.request.negative_prompt,
          video_refinement: job.request.video_refinement,
          generate_audio: job.request.generate_audio,
        },
      });
      setShowHistory(false);
    } catch (reason) {
      setError((reason as Error).message);
    }
  }
  function input(slot: 'source' | 'end', asset?: Asset) {
    const frameTime =
      slot === 'source' && asset?.kind === 'video'
        ? Math.max(0, (asset.duration || 0) - 1 / (asset.fps || 24))
        : 0;
    return (
      <div
        className="transition-input"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          void addFile(event.dataTransfer.files[0], slot);
        }}
      >
        <button
          className="transition-upload"
          disabled={busy}
          onClick={() => {
            setUploadSlot(slot);
            file.current?.click();
          }}
        >
          {asset ? (
            <img
              src={
                asset.kind === 'image'
                  ? mediaUrl(asset)
                  : `/api/assets/${asset.id}/frame?time=${frameTime.toFixed(4)}`
              }
              alt={slot === 'source' ? 'Last source frame' : 'First destination frame'}
            />
          ) : (
            <Icon name="image" size={24} />
          )}
          <strong>{slot === 'source' ? 'Start Frame' : 'End Frame'}</strong>
          <span>{asset ? asset.name : 'Add image or video.'}</span>
          <small>
            {asset?.kind === 'video' ? `${asset.duration?.toFixed(2)}s` : '(5s max for video)'}
          </small>
        </button>
        {asset && (
          <button
            className="transition-remove"
            aria-label={`Remove ${slot} input`}
            onClick={() =>
              session.update(slot === 'source' ? { source_asset_id: '' } : { end_asset_id: '' })
            }
          >
            <Icon name="close" size={13} />
          </button>
        )}
        <div className="transition-library">
          <button onClick={() => setPicker({ slot, kind: 'image' })}>Images</button>
          <button onClick={() => setPicker({ slot, kind: 'video' })}>Videos</button>
        </div>
      </div>
    );
  }
  return (
    <main className="transitions-app">
      <nav className="transition-breadcrumb">
        <a href="/apps">Apps</a>
        <span>/</span>
        <strong>Transitions</strong>
        <div />
        <button onClick={() => setShowHistory((value) => !value)}>My generations</button>
        <button onClick={() => void session.newDocument()}>New transition</button>
        <button onClick={onSettings}>{provider === 'local' ? 'Local ComfyUI' : 'Saved connection unavailable'}</button>
      </nav>
      {showHistory ? (
        <section className="transition-history">
          <h1>Your transitions</h1>
          <WorkspaceHistory
            jobs={jobs}
            total={jobs.length + (session.jobs.length < session.jobTotal ? 1 : 0)}
            onSelect={setSelected}
            onMore={session.loadMoreJobs}
          />
        </section>
      ) : (
        <>
          <section className="transition-hero">
            <div className="transition-composer">
              <h1>SMOOTH TRANSITIONS</h1>
              <p>
                Connect two images, videos, or a mix of both. Choose a visual direction and create a
                continuous bridge between them.
              </p>
              <div className="transition-inputs">
                {input('source', source)}
                <button className="transition-effect-card" onClick={() => setEffectsOpen(true)}>
                  <ReferenceMedia item={current} />
                  <Icon name="spark" size={17} />
                  <strong>{state.effect}</strong>
                </button>
                {input('end', end)}
              </div>
              <div className="transition-duration">
                <button
                  className={state.frames === 121 ? 'active' : ''}
                  onClick={() => session.update({ frames: 121 })}
                >
                  5s
                </button>
                <button
                  className={state.frames === 241 ? 'active' : ''}
                  onClick={() => session.update({ frames: 241 })}
                >
                  10s
                </button>
              </div>
              <p className="transition-actual">
                {state.frames} frames · {duration.toFixed(3)}s at 24 fps
              </p>
              <button
                className="transition-generate"
                disabled={busy || !source || !end || !model || !session.ready}
                onClick={() => void generate()}
              >
                {busy ? 'Preparing…' : 'Generate Video'}
                <Icon name="spark" size={16} />
              </button>
              <button
                className="transition-options-button"
                onClick={() => setAdvanced((value) => !value)}
              >
                <Icon name="sliders" size={14} />
                Directions and output settings
                <Icon name="down" size={12} />
              </button>
              {advanced && (
                <div className="transition-options">
                  <label>
                    Transition model
                    <select
                      value={model?.id || ''}
                      onChange={(event) => {
                        const next = models.find((item) => item.id === event.target.value);
                        session.update({
                          model_id: event.target.value,
                          replay_settings: undefined,
                          ...(next?.fixed_framing === 'center-crop'
                            ? {
                                reframe_fit: 'crop',
                                anchor_x: 0.5,
                                anchor_y: 0.5,
                                enhance_prompt: false,
                              }
                            : {}),
                        });
                      }}
                    >
                      {!model && <option value="">Choose a compatible model</option>}
                      {models.map((item) => (
                        <option value={item.id} key={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  {state.replay_settings && (
                    <section>
                      <small>
                        Recorded rendering settings are retained for this reused result.
                      </small>
                      <button
                        className="transition-options-button"
                        onClick={() => session.update({ replay_settings: undefined })}
                      >
                        Use current model defaults
                      </button>
                    </section>
                  )}
                  {fixedFraming && (
                    <small>
                      First/last-frame trained adapter, eight-step single-pass recipe and centered
                      endpoint framing. The recorded model prompt includes its required trigger.
                      Smoke motion is generative and must be reviewed; no midpoint image or overlay
                      is used.
                    </small>
                  )}
                  {(supportsGuide || state.reference_asset_id) && (
                    <section>
                      <SourceSlot
                        title="Midpoint image guide"
                        detail="Optional still image"
                        optional
                        compact
                        asset={guide}
                        onChoose={() => setPicker({ slot: 'guide', kind: 'image' })}
                        onClear={() => session.update({ reference_asset_id: '' })}
                      />
                      <small>
                        Guides the generated bridge around frame{' '}
                        {Math.floor((state.frames - 1) / 2)} (
                        {(Math.floor((state.frames - 1) / 2) / 24).toFixed(2)}s). It is fitted to
                        the output canvas and used during generation, not pasted over the video. The
                        exact result is not guaranteed.
                      </small>
                    </section>
                  )}
                  <label>
                    Transition direction
                    <textarea
                      value={state.prompt}
                      onChange={(event) => session.update({ prompt: event.target.value })}
                    />
                  </label>
                  <small>
                    Editable OpenFrame directions guide the native model. Gallery media is a public
                    reference, not proof of matching proprietary effects.
                  </small>
                  <div>
                    <label>
                      Aspect
                      <select
                        value={state.ratio}
                        onChange={(event) => session.update({ ratio: event.target.value })}
                      >
                        <option>Auto</option>
                        {(model?.aspect_ratios || ['16:9', '9:16', '1:1']).map((value) => (
                          <option key={value}>{value}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Longest side
                      <select
                        value={state.resolution}
                        onChange={(event) =>
                          session.update({ resolution: Number(event.target.value) })
                        }
                      >
                        {[512, 768, 1024, 1280, 1536, 1920].map((value) => (
                          <option
                            value={value}
                            key={value}
                            disabled={value > Number(model?.max_width || 1920)}
                          >
                            {value}px
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div>
                    <label>
                      Fit inputs
                      <select
                        value={state.reframe_fit}
                        disabled={fixedFraming}
                        onChange={(event) =>
                          session.update({
                            reframe_fit: event.target.value as State['reframe_fit'],
                          })
                        }
                      >
                        <option value="crop">Crop to fill</option>
                        <option value="pad">Fit with black padding</option>
                      </select>
                    </label>
                    <label>
                      Seed
                      <input
                        type="number"
                        min={-1}
                        max={2147483647}
                        value={state.seed}
                        onChange={(event) => session.update({ seed: Number(event.target.value) })}
                      />
                    </label>
                  </div>
                  <label>
                    Horizontal position · {Math.round(state.anchor_x * 100)}%
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.01}
                      value={state.anchor_x}
                      disabled={fixedFraming}
                      onChange={(event) => session.update({ anchor_x: Number(event.target.value) })}
                    />
                  </label>
                  <label>
                    Vertical position · {Math.round(state.anchor_y * 100)}%
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.01}
                      value={state.anchor_y}
                      disabled={fixedFraming}
                      onChange={(event) => session.update({ anchor_y: Number(event.target.value) })}
                    />
                  </label>
                  {supportsEnhancement && (
                    <label className="transition-checkbox">
                      <input
                        type="checkbox"
                        checked={state.enhance_prompt}
                        onChange={(event) =>
                          session.update({ enhance_prompt: event.target.checked })
                        }
                      />
                      Enhance the transition direction
                    </label>
                  )}
                  {!!model?.supports_audio && (
                    <label className="transition-checkbox">
                      <input
                        type="checkbox"
                        checked={
                          state.generate_audio ??
                          state.replay_settings?.generate_audio ??
                          Boolean(model.default_generate_audio)
                        }
                        onChange={(event) =>
                          session.update({ generate_audio: event.target.checked })
                        }
                      />
                      Generate audio for the bridge
                    </label>
                  )}
                  <label className="transition-checkbox">
                    <input
                      type="checkbox"
                      checked={state.transition_include_inputs}
                      onChange={(event) =>
                        session.update({ transition_include_inputs: event.target.checked })
                      }
                    />
                    Include original video clips before and after the bridge
                  </label>
                  {state.transition_include_inputs && (
                    <label className="transition-checkbox">
                      <input
                        type="checkbox"
                        checked={state.preserve_audio}
                        onChange={(event) =>
                          session.update({ preserve_audio: event.target.checked })
                        }
                      />
                      Keep the original clips' audio
                    </label>
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
                      <option value="high">High</option>
                      <option value="standard">Standard</option>
                    </select>
                  </label>
                  <small>
                    {dimensions.width} × {dimensions.height} ·{' '}
                    {state.transition_include_inputs
                      ? `approximately ${assembledDuration.toFixed(3)}s with original clips; final duration comes from the encoded output`
                      : 'Generated bridge only'}
                    . Auto aspect follows the first input.
                  </small>
                </div>
              )}
              {(error || session.error || assets.error) && (
                <p className="ea-error" role="alert">
                  {error || session.error || assets.error}
                </p>
              )}
            </div>
            <div className="transition-preview">
              {current?.video ? (
                <video
                  key={current.video}
                  src={current.video}
                  poster={current.poster}
                  muted
                  loop
                  playsInline
                  autoPlay={!matchMedia('(prefers-reduced-motion: reduce)').matches}
                  controls
                  preload="metadata"
                />
              ) : (
                <ReferenceMedia item={current} />
              )}
              <span>Public reference preview</span>
            </div>
          </section>
          <section className="transition-features">
            <small>How the workflow works</small>
            <h2>CONNECT YOUR SCENES</h2>
            <p>
              Each transition is an actual video generation with both endpoints in its ComfyUI
              workflow.
            </p>
            <div>
              <article>
                <Icon name="image" />
                <h3>Images and short clips</h3>
                <p>
                  Use two images, two clips, or one of each. Clips can be up to five seconds long.
                </p>
              </article>
              <article>
                <Icon name="spark" />
                <h3>Editable visual direction</h3>
                <p>Choose a reference effect and adjust its OpenFrame prompt before generating.</p>
              </article>
              <article>
                <Icon name="square" />
                <h3>Consistent framing</h3>
                <p>
                  Auto follows the first input. Choose crop or padding for differently sized
                  endpoints.
                </p>
              </article>
              <article>
                <Icon name="download" />
                <h3>Portable workflow</h3>
                <p>
                  Download the actual result, its ComfyUI graph and a project with the original
                  media.
                </p>
              </article>
            </div>
          </section>
        </>
      )}
      <input
        ref={file}
        type="file"
        hidden
        accept="image/*,video/*"
        onChange={(event) => void addFile(event.target.files?.[0])}
      />
      {effectsOpen && (
        <WorkspaceDialog
          title="All Transitions"
          onClose={() => setEffectsOpen(false)}
          className="transition-effect-dialog"
        >
          <label className="transition-effect-search">
            <Icon name="search" size={17} />
            <input
              placeholder="Search"
              aria-label="Search transitions"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="transition-effect-grid">
            {filtered.map((item) => (
              <button
                key={item.id || item.title}
                onClick={() => chooseEffect(item)}
                className={item.title === state.effect ? 'active' : ''}
              >
                <ReferenceMedia item={item} />
                <h3>{item.title}</h3>
              </button>
            ))}
          </div>
          {!filtered.length && <p>No transition references match this search.</p>}
          <p className="ea-muted">
            Public reference previews. OpenFrame's editable directions use the available native
            transition model.
          </p>
        </WorkspaceDialog>
      )}
      {picker && (
        <AssetPicker
          title={
            picker.slot === 'guide'
              ? 'Choose midpoint image guide'
              : `Choose ${picker.slot === 'source' ? 'start' : 'end'} ${picker.kind}`
          }
          kind={picker.kind}
          assets={assets.assets}
          onAdded={assets.add}
          jobs={session.jobs}
          onSelect={(asset) => choose(asset, picker.slot)}
          onClose={() => setPicker(null)}
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
