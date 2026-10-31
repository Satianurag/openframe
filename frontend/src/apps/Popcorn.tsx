import { useEffect, useRef, useState } from 'react';
import { api, mediaUrl, post } from '../api';
import { Icon } from '../Icon';
import { AnchoredPopover } from '../Popovers';
import { useAppDocument } from './useAppDocument';
import { providerReadinessIssue, renderRequest, renderSize, resolveProvider } from './renderRequest';
import type { Job } from '../types';
import type { AppDocument } from './registry';
import type { ShotProposal } from './SequencePlanner';
import { plannerAvailable, plannerRunNote } from './plannerStatus';
import { showProjectDraft } from './projectReuse';
import type { PlannerInfo } from './plannerStatus';
import {
  AssetPicker,
  ReferenceMedia,
  ResultDialog,
  WorkspaceDialog,
  WorkspaceHistory,
  useReferenceLibrary,
  useWorkspaceAssets,
} from './engine-apps-shared';
import type { EngineAppProps, ReferenceItem } from './engine-apps-shared';
import './engine-apps.css';
import './popcorn.css';

type Scene = { id: string; prompt: string };
type PopcornState = Record<string, unknown> & {
  prompt: string;
  mode: 'auto' | 'manual';
  scenes: Scene[];
  reference_asset_ids: string[];
  result_count: number;
  aspect_ratio: string;
  model_id: string;
  quality: number;
  seed: number;
  provider: string;
  planner_id: string;
  pack_name: string;
  pending_storyboard?: { id: string; signature: string } | null;
  last_storyboard_id?: string;
};
const emptyScene = (): Scene => ({ id: crypto.randomUUID(), prompt: '' });
const initial: PopcornState = {
  prompt: '',
  mode: 'auto',
  scenes: Array.from({ length: 4 }, emptyScene),
  reference_asset_ids: [],
  result_count: 4,
  aspect_ratio: '3:4',
  model_id: 'flux3-klein',
  quality: 1024,
  seed: -1,
  provider: '',
  planner_id: '',
  pack_name: '',
};
const assetIds = (state: PopcornState) => state.reference_asset_ids;
const ratios = ['3:4', '2:3', '3:2', '9:16', '1:1', '4:3', '16:9', 'Auto'];

export function Popcorn({ catalog, settings, onSettings }: EngineAppProps) {
  const session = useAppDocument('popcorn', initial, assetIds),
    { state, update } = session;
  const assets = useWorkspaceAssets(state.reference_asset_ids),
    library = useReferenceLibrary('popcorn');
  const [view, setView] = useState<'Create' | 'History'>('Create'),
    [hidden, setHidden] = useState(false),
    [picker, setPicker] = useState(false),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState<{ name: string; anchor: HTMLElement } | null>(null),
    [heroIndex, setHeroIndex] = useState(0),
    [plan, setPlan] = useState<ShotProposal | null>(null),
    [selectedId, setSelectedId] = useState<string | null>(null);
  const [packStep, setPackStep] = useState<number | null>(null),
    [pack, setPack] = useState<ReferenceItem | null>(null),
    [packName, setPackName] = useState(''),
    [showHelp, setShowHelp] = useState(false);
  const [packSearch, setPackSearch] = useState('');
  const [pollError, setPollError] = useState('');
  const [plannerProvider, setPlannerProvider] = useState<string>('local');
  const [plannerInfo, setPlannerInfo] = useState<PlannerInfo | null>(null);
  const [plannerModel, setPlannerModel] = useState<'qwen3.8-planner' | 'qwen-planner-7b'>('qwen3.8-planner');
  const plannerReady = plannerAvailable(plannerInfo, plannerProvider, plannerModel);
  const [board, setBoard] = useState<{ id: string; items: Job[] } | null>(null);
  useEffect(() => {
    if (!state.last_storyboard_id || !session.document) { setBoard(null); return; }
    let live = true, loading = false;
    const read = async () => {
      if (loading) return;
      loading = true;
      try {
        const value = await api<{ id: string; items: Job[] }>(`/apps/popcorn/documents/${session.document!.id}/storyboards/${state.last_storyboard_id}`, { signal: AbortSignal.timeout(15000) });
        if (live) setBoard(value);
        if (value.items.every((job) => !['queued', 'running'].includes(job.status))) clearInterval(timer);
      } catch (reason) { if (live) setError((reason as Error).message); }
      finally { loading = false; }
    };
    const timer = setInterval(() => void read(), 3000);
    void read();
    return () => { live = false; clearInterval(timer); };
  }, [state.last_storyboard_id, session.document?.id,
    session.jobs.filter((job) => job.app_context?.group_id === state.last_storyboard_id).map((job) => `${job.id}:${job.status}`).join(',')]);
  useEffect(() => {
    let live = true;
    void api<PlannerInfo>('/planner')
      .then((value) => {
        if (live) setPlannerInfo(value);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);
  const composer = useRef<HTMLElement>(null);
  const model = catalog.models.find((item) => item.id === state.model_id);
  const operation = state.reference_asset_ids.length ? 'edit-image' : 'create-image';
  const models = catalog.models.filter((item) =>
    catalog.effects.find((effect) => effect.id === operation)?.model_ids.includes(item.id),
  );
  const provider = resolveProvider(state.provider, settings.default_provider);
  const providerIssue = providerReadinessIssue(
    catalog.providers.find((item) => item.id === provider),
  );
  const selected = session.jobs.find((job) => job.id === selectedId) || board?.items.find((job) => job.id === selectedId);
  const activePlan = plan?.status === 'queued' || plan?.status === 'running';
  const references = state.reference_asset_ids.map((id) => assets.get(id)).filter(Boolean);
  const heroItems = library.hero || [];
  const hero = heroItems[heroIndex] || heroItems[0];
  const reducedMotion =
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const packs =
    (library as typeof library & { packs?: ReferenceItem[] }).packs || library.presets || [];
  const displayRatio =
    state.aspect_ratio === 'Auto' && references[0]?.width && references[0]?.height
      ? `${references[0].width}:${references[0].height}`
      : state.aspect_ratio === 'Auto'
        ? '3:4'
        : state.aspect_ratio;

  useEffect(() => {
    if (!state.planner_id && !session.document) {
      setPlan(null);
      return;
    }
    let live = true;
    const fetchPlan = state.planner_id
      ? api<ShotProposal>(`/plans/${state.planner_id}`)
      : api<{ items: ShotProposal[] }>(
          `/apps/popcorn/plans?document_id=${session.document!.id}&limit=1`,
        ).then((value) => value.items[0] || null);
    void fetchPlan
      .then((value) => {
        if (live) setPlan(value);
      })
      .catch((reason) => {
        if (live) setError(reason.message);
      });
    return () => {
      live = false;
    };
  }, [state.planner_id, session.document?.id]);
  useEffect(() => {
    if (!activePlan || !plan) return;
    let live = true,
      loading = false;
    const timer = setInterval(async () => {
      if (loading) return;
      loading = true;
      try {
        const result = await api<ShotProposal>(`/plans/${plan.id}`, {
          signal: AbortSignal.timeout(15000),
        });
        if (live) {
          setPlan(result);
          setPollError('');
        }
      } catch (reason) {
        if (live) setPollError((reason as Error).message);
      } finally {
        loading = false;
      }
    }, 2000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [plan?.id, activePlan]);

  function setCount(count: number) {
    update({
      result_count: count,
      ...(state.mode === 'manual'
        ? {
            scenes: Array.from(
              { length: count },
              (_, index) => state.scenes[index] || emptyScene(),
            ),
          }
        : {}),
    });
  }
  function editScene(id: string, prompt: string) {
    update({
      scenes: state.scenes.map((scene) => (scene.id === id ? { ...scene, prompt } : scene)),
    });
  }
  function removeScene(id: string) {
    const scenes = state.scenes.filter((scene) => scene.id !== id);
    update({ scenes, result_count: scenes.length });
  }
  function addScene() {
    if (state.scenes.length >= 8) return;
    const scenes = [...state.scenes, emptyScene()];
    update({ scenes, result_count: scenes.length });
  }
  function moveScene(index: number, delta: number) {
    const scenes = [...state.scenes];
    [scenes[index], scenes[index + delta]] = [scenes[index + delta], scenes[index]];
    update({ scenes });
  }
  function usePlan() {
    if (!plan?.proposal) return;
    const shots = plan.proposal.episodes[0]?.shots || [];
    if (!shots.length) {
      setError('The planner returned no scenes.');
      return;
    }
    update({
      mode: 'manual',
      scenes: shots.map((shot) => ({
        id: shot.id,
        prompt: [shot.prompt, shot.camera && `Camera: ${shot.camera}`].filter(Boolean).join('\n'),
      })),
      result_count: shots.length,
    });
  }
  async function planScenes() {
    if (!state.prompt.trim()) return;
    if (state.result_count === 1) {
      update({ mode: 'manual', scenes: [{ id: crypto.randomUUID(), prompt: state.prompt }] });
      return;
    }
    setBusy(true);
    setError('');
    try {
      if (!plannerReady || !catalog.providers.some((item) => item.id === plannerProvider))
        throw new Error('Select an enabled planning connection. No alternate provider will be used.');
      const doc = await session.save(true);
      if (!doc) throw new Error('Save the storyboard brief first.');
      const value = await post<ShotProposal>(`/apps/popcorn/documents/${doc.id}/plans`, {
        expected_revision: doc.revision,
        prompt: `Create ${state.result_count} distinct storyboard still frames for this visual story. Each frame must have a clear composition, action and continuity.\n${state.prompt}`,
        style:
          plannerModel === 'qwen3.8-planner' ? 'Cinematic storyboard stills. Use the observed reference content for coherent scene proposals; do not invent unseen actions.' : 'Cinematic storyboard stills. References are used only during image generation; do not claim to have viewed them.',
        target_duration: state.result_count * 10,
        episodes: 1,
        seed: state.seed < 0 ? 42 : state.seed,
        provider: plannerProvider,
        model_id: plannerModel,
        reference_asset_ids: plannerModel === 'qwen3.8-planner' ? state.reference_asset_ids : [],
      });
      setPlan(value);
      await session.updateAndSave({ planner_id: value.id });
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function generate() {
    if (state.mode === 'auto') {
      await planScenes();
      return;
    }
    if (!model || busy) return;
    setBusy(true);
    setError('');
    try {
      if (providerIssue) throw new Error(providerIssue);
      if (state.scenes.some((scene) => scene.prompt.length > 15900))
        throw new Error('Keep each scene description below15,900 characters.');
      if (state.scenes.some((scene) => !scene.prompt.trim()))
        throw new Error('Write each scene before generating, or remove unused scenes.');
      if (state.reference_asset_ids.length > 4)
        throw new Error('Use at most four reference images.');
      const capability = session.application?.operations.find((item) => item.id === operation);
      if (!capability?.available)
        throw new Error(capability?.reason || 'Image generation is unavailable.');
      const shots = state.scenes.map((scene, index) => {
        const request = renderRequest(model, {
          effect_id: operation,
          provider,
          prompt: `Create one storyboard still frame. ${scene.prompt}`,
          frames: 1,
          fps: 1,
          ...renderSize(model, displayRatio, state.quality),
          seed: state.seed < 0 ? -1 : state.seed + index,
          source_asset_id: state.reference_asset_ids[0],
          reference_asset_ids: state.reference_asset_ids.slice(1),
          batch_size: 1,
        });
        return { request, step_id: scene.id };
      });
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(shots)));
      const signature = Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, '0')).join('');
      if (state.pending_storyboard && state.pending_storyboard.signature !== signature)
        throw new Error('Resolve the earlier submission before submitting changed scenes. No extra jobs were queued.');
      const pending = state.pending_storyboard || { id: crypto.randomUUID().replaceAll('-', ''), signature };
      const doc = await session.updateAndSave({ pending_storyboard: pending });
      if (!doc) throw new Error('Save the storyboard before generating.');
      await post<{ id: string; items: Job[] }>(`/apps/popcorn/documents/${doc.id}/storyboards`, {
        expected_revision: doc.revision, submission_id: pending.id, shots,
      });
      await session.updateAndSave({ pending_storyboard: null, last_storyboard_id: pending.id });
      await session.refreshJobs();
      setView('History');
      setHidden(true);
    } catch (reason) {
      setError((reason as Error).message);
      await session.refreshJobs().catch(() => {});
    } finally {
      setBusy(false);
    }
  }
  async function recoverSubmission() {
    if (!state.pending_storyboard || !session.document) return;
    setBusy(true); setError('');
    try {
      await api(`/apps/popcorn/documents/${session.document.id}/storyboards/${state.pending_storyboard.id}`);
      await session.updateAndSave({ last_storyboard_id: state.pending_storyboard.id, pending_storyboard: null });
      await session.refreshJobs();
      setView('History'); setHidden(true);
    } catch (reason) {
      if ((reason as Error & { status?: number }).status === 404) {
        await session.updateAndSave({ pending_storyboard: null });
        setError('The earlier submission was not stored. You can submit the reviewed scenes now.');
      } else setError((reason as Error).message);
    } finally { setBusy(false); }
  }
  function applyPack() {
    const name = pack?.title || packName.trim() || 'Custom photo series';
    const framing = [
      'An establishing view of the environment',
      'A candid medium shot with a natural pose',
      'A close-up detail with expressive lighting',
      'A wider finishing shot with a different angle',
    ];
    update({
      mode: 'manual',
      pack_name: name,
      reference_asset_ids: state.reference_asset_ids.slice(0, 1),
      result_count: 4,
      scenes: framing.map((description) => ({
        id: crypto.randomUUID(),
        prompt: `${name}. ${description}. Preserve the appearance of the person or subject in the uploaded reference. ${pack?.prompt || ''}`,
      })),
    });
    setPackStep(null);
    setView('Create');
    setHidden(false);
  }
  async function reuse(job: Job) {
    try {
      const context = await api<{ document_snapshot: { state: PopcornState } }>(
        `/jobs/${job.id}/app-context`,
      );
      if (await session.newDocument({ ...context.document_snapshot.state, pending_storyboard: null, last_storyboard_id: undefined })) {
        const draft = await session.save(true);
        if (!draft) throw new Error('The reused storyboard could not be saved.');
        showProjectDraft(draft.id, '/popcorn');
        setSelectedId(null);
        setView('Create');
        setHidden(false);
      }
    } catch (reason) {
      setError((reason as Error).message);
    }
  }
  const enabled =
    state.mode === 'auto'
      ? !!state.prompt.trim()
      : state.scenes.length > 0 && state.scenes.every((scene) => scene.prompt.trim());
  return (
    <main
      className={`pop-app ${state.mode === 'manual' ? 'manual' : ''} ${hidden ? 'composer-hidden' : ''}`}
    >
      {state.pending_storyboard && <button disabled={busy} onClick={() => void recoverSubmission()}>
        Resolve earlier storyboard submission
      </button>}
      {error && view === 'History' && (
        <p role="alert" className="pop-global-error ea-error">
          {error}
        </p>
      )}
      <div className="pop-view-switch">
        <button className={view === 'Create' ? 'active' : ''} onClick={() => setView('Create')}>
          Create
        </button>
        <button
          className={view === 'History' ? 'active' : ''}
          onClick={() => {
            setView('History');
            setHidden(true);
          }}
        >
          My storyboards
        </button>
        <button onClick={onSettings}>
          <Icon name="settings" size={14} />
          Compute
        </button>
      </div>
      {view === 'History' ? (
        <section className="pop-history">
          <h1>Your storyboards</h1>
          {board && <section aria-label="Ordered storyboard">
            <h2>{board.items.every((job) => job.status === 'succeeded') ? 'Completed storyboard' : 'Storyboard in progress or incomplete'}</h2>
            <p>{board.items.filter((job) => job.status === 'succeeded').length}/{board.items.length} scenes completed. Failed or cancelled scenes stay visible; retry them individually.</p>
            <ol className="pop-board-results">{board.items.map((job, index) => {
              const result = job.outputs.find((asset) => asset.kind === 'image' && asset.role === 'result');
              return <li key={job.id}><button onClick={() => setSelectedId(job.id)}>
                {result && <img src={mediaUrl(result)} alt={`Storyboard scene ${index + 1}`} />}
                Scene {index + 1} · {job.status}
              </button></li>;
            })}</ol>
          </section>}
          <WorkspaceHistory
            jobs={session.jobs}
            total={session.jobTotal}
            onMore={session.loadMoreJobs}
            onSelect={(job) => setSelectedId(job.id)}
          />
        </section>
      ) : (
        <section className="pop-intro">
          <div className="pop-hero">
            {hero?.video ? (
              <video
                src={hero.video}
                poster={hero.poster}
                muted
                playsInline
                loop
                autoPlay={!reducedMotion}
                preload="auto"
                onLoadedData={(event) => {
                  if (event.currentTarget.currentTime < 0.5)
                    event.currentTarget.currentTime = Math.min(
                      1.5,
                      event.currentTarget.duration / 2,
                    );
                }}
              />
            ) : (
              <ReferenceMedia item={hero} />
            )}
            {!hero && <span className="pop-hero-badge">Storyboard Mode</span>}
            {heroItems.length > 1 && (
              <div className="pop-hero-thumbs">
                {heroItems.map((item, index) => (
                  <button
                    key={item.id || index}
                    className={heroIndex === index ? 'active' : ''}
                    onClick={() => setHeroIndex(index)}
                    aria-label={`Preview scene ${index + 1}`}
                  >
                    <ReferenceMedia item={item} />
                  </button>
                ))}
              </div>
            )}
          </div>
          <h1>
            Create visual stories
            <br />
            with <span>OpenFrame Popcorn</span>
          </h1>
          <p>
            Create a storyboard that lets you plan and visualize your idea before video generation.
          </p>
          <button className="pop-learn" onClick={() => setShowHelp(true)}>
            Explore more about Popcorn
          </button>
        </section>
      )}
      <section
        ref={composer}
        className={`pop-composer ${hidden ? 'collapsed' : ''}`}
        aria-label="Storyboard composer"
      >
        <nav>
          <div>
            {(['auto', 'manual'] as const).map((mode) => (
              <button
                className={state.mode === mode ? 'active' : ''}
                key={mode}
                onClick={() => {
                  update({ mode });
                  setView('Create');
                  setHidden(false);
                }}
              >
                {mode === 'auto' ? 'Auto' : 'Manual'}
                {mode === 'manual' && <span>{state.scenes.length}</span>}
              </button>
            ))}
            <button
              onClick={() => {
                setPackStep(0);
                setPack(null);
              }}
            >
              Instadump
            </button>
          </div>
          <button onClick={() => setHidden(!hidden)}>
            {hidden ? 'Show' : 'Hide'}
            <Icon name="down" size={13} />
          </button>
        </nav>
        {!hidden && (
          <>
            <div className="pop-references">
              {references.map(
                (asset) =>
                  asset && (
                    <div key={asset.id}>
                      <img src={mediaUrl(asset)} alt={asset.name} />
                      <button
                        aria-label={`Remove ${asset.name}`}
                        onClick={() =>
                          update({
                            reference_asset_ids: state.reference_asset_ids.filter(
                              (id) => id !== asset.id,
                            ),
                          })
                        }
                      >
                        <Icon name="close" size={10} />
                      </button>
                    </div>
                  ),
              )}
              {state.reference_asset_ids.length < 4 && (
                <button onClick={() => setPicker(true)}>
                  <i>
                    <Icon name="plus" size={16} />
                  </i>
                  {!references.length && (
                    <span>Upload up to 4 images to guide or extend your storyboard</span>
                  )}
                </button>
              )}
            </div>
            {state.mode === 'auto' ? (
              <div className="pop-auto-prompt">
                <i>
                  <Icon name="brush" size={16} />
                </i>
                <textarea
                  value={state.prompt}
                  onChange={(event) => update({ prompt: event.target.value })}
                  maxLength={2600}
                  aria-label="Storyboard brief"
                  placeholder="Describe the mood or action to create your scenes"
                />
              </div>
            ) : (
              <div className="pop-scenes">
                {state.scenes.map((scene, index) => (
                  <div className="pop-scene" key={scene.id}>
                    <span>{index + 1}</span>
                    <textarea
                      value={scene.prompt}
                      onChange={(event) => editScene(scene.id, event.target.value)}
                      placeholder={`Write what happens in Scene ${index + 1}`}
                      aria-label={`Scene ${index + 1}`}
                      maxLength={16000}
                    />
                    <div className="pop-scene-tools">
                      {index > 0 && (
                        <button
                          onClick={() => moveScene(index, -1)}
                          aria-label={`Move scene ${index + 1} earlier`}
                        >
                          <Icon name="arrow" size={12} />
                        </button>
                      )}
                      {index < state.scenes.length - 1 && (
                        <button
                          onClick={() => moveScene(index, 1)}
                          aria-label={`Move scene ${index + 1} later`}
                        >
                          <Icon name="arrow" size={12} />
                        </button>
                      )}
                      {state.scenes.length > 1 && (
                        <button
                          onClick={() => removeScene(scene.id)}
                          aria-label={`Remove scene ${index + 1}`}
                        >
                          <Icon name="trash" size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {state.scenes.length < 8 && (
                  <button className="pop-add-scene" onClick={addScene}>
                    <Icon name="plus" size={14} />
                    Add scene
                  </button>
                )}
              </div>
            )}
            {plan && state.mode === 'auto' && (
              <div className="pop-plan-status">
                {activePlan ? (
                  <>
                    <progress value={plan.progress} max="1" />
                    <span>{plan.stage || 'Planning scenes…'}</span>
                    <button
                      onClick={() =>
                        void post(`/plans/${plan.id}/cancel`)
                          .then((value) => setPlan(value as ShotProposal))
                          .catch((reason) => setError(reason.message))
                      }
                    >
                      Cancel
                    </button>
                  </>
                ) : plan.status === 'succeeded' ? (
                  <>
                    <Icon name="check" size={15} />
                    <span>{plan.proposal?.episodes[0]?.shots.length || 0} scenes planned</span>
                    <button onClick={usePlan}>Review scenes</button>
                  </>
                ) : (
                  <span role="alert">{plan.error || plan.status}</span>
                )}
                {plannerRunNote(plan) && (
                  <small className="pop-planning-note">{plannerRunNote(plan)}</small>
                )}
              </div>
            )}
            {pollError && (
              <p className="ea-error" role="status">
                Status refresh interrupted; the saved proposal may still be running. Retrying status
                only. {pollError}
              </p>
            )}
            {(error || session.error || assets.error) && (
              <p className="ea-error" role="alert">
                {error || session.error || assets.error}
              </p>
            )}
            {providerIssue && (
              <p className="muted small" role="status">
                {providerIssue}
              </p>
            )}
            <footer>
              <div>
                <button
                  onClick={(event) => setMenu({ name: 'count', anchor: event.currentTarget })}
                >
                  {state.mode === 'manual' ? state.scenes.length : state.result_count} results
                  <Icon name="down" size={12} />
                </button>
                <button
                  onClick={(event) => setMenu({ name: 'ratio', anchor: event.currentTarget })}
                >
                  <Icon name="square" size={14} />
                  {state.aspect_ratio}
                </button>
                <button
                  className="pop-model-control"
                  onClick={(event) => setMenu({ name: 'model', anchor: event.currentTarget })}
                  aria-label="Generation settings"
                >
                  <Icon name="settings" size={14} />
                  <span>{model?.name || 'Model'}</span>
                </button>
              </div>
              <button
                className="pop-generate"
                disabled={
                  !enabled ||
                  busy ||
                  activePlan ||
                  !session.ready ||
                  !!providerIssue ||
                  (state.mode === 'auto' &&
                    state.result_count > 1 &&
                    (!plannerReady || !catalog.providers.some((item) => item.id === plannerProvider)))
                }
                onClick={() => void generate()}
              >
                {busy ? 'Submitting…' : state.mode === 'auto' ? 'Plan scenes' : 'Generate'}
              </button>
            </footer>
          </>
        )}
      </section>
      {menu && (
        <AnchoredPopover
          anchor={menu.anchor}
          label={
            menu.name === 'count'
              ? 'Output images amount'
              : menu.name === 'ratio'
                ? 'Aspect ratio'
                : 'Generation settings'
          }
          width={menu.name === 'model' ? 300 : 240}
          className="pop-menu"
          onClose={() => setMenu(null)}
        >
          {menu.name === 'count' ? (
            <>
              <h3>Output images amount</h3>
              <p>Each scene is a separate image generation.</p>
              {Array.from({ length: 8 }, (_, index) => index + 1).map((value) => (
                <button
                  key={value}
                  className={value === state.result_count ? 'active' : ''}
                  onClick={() => {
                    setCount(value);
                    setMenu(null);
                  }}
                >
                  {value} {value === 1 ? 'Result' : 'Results'}
                  {value === state.result_count && <Icon name="check" size={14} />}
                </button>
              ))}
            </>
          ) : menu.name === 'ratio' ? (
            <>
              <h3>Aspect ratio</h3>
              {ratios.map((ratio) => (
                <button
                  className={ratio === state.aspect_ratio ? 'active' : ''}
                  key={ratio}
                  onClick={() => {
                    update({ aspect_ratio: ratio });
                    setMenu(null);
                  }}
                >
                  <Icon name="square" size={14} />
                  {ratio}
                  {ratio === state.aspect_ratio && <Icon name="check" size={14} />}
                </button>
              ))}
            </>
          ) : (
            <>
              <label>
                Image model
                <select
                  value={state.model_id}
                  onChange={(event) => update({ model_id: event.target.value })}
                >
                  {models.map((item) => (
                    <option value={item.id} key={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Resolution
                <select
                  value={state.quality}
                  onChange={(event) => update({ quality: Number(event.target.value) })}
                >
                  {[512, 768, 1024].map((value) => (
                    <option key={value} value={value}>
                      {value}px longest side
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Compute
                <select
                  value={provider}
                  onChange={(event) => update({ provider: event.target.value })}
                >
                  {catalog.providers.filter((item) => ['local', 'comfy-cloud'].includes(item.id)).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Seed
                <input
                  type="number"
                  min="-1"
                  max={Number.MAX_SAFE_INTEGER - 8}
                  value={state.seed}
                  onChange={(event) => update({ seed: Number(event.target.value) })}
                />
              </label>
              <label>
                Planning provider
                <select
                  value={plannerProvider}
                  onChange={(event) => { setPlannerProvider(event.target.value); setPlannerModel('qwen3.8-planner'); }}
                >
                  {plannerInfo?.providers.filter((item) => item.id === 'local' && catalog.providers.some((connection) => connection.id === item.id)).map((item) => (
                    <option key={item.id} value={item.id}>{item.name || item.id}</option>
                  ))}
                </select>
              </label>
              {plannerProvider === 'local' && <label>Planning model<select value={plannerModel} onChange={(event) => setPlannerModel(event.target.value as typeof plannerModel)}>
                <option value="qwen3.8-planner">Qwen3.8 27B · CUDA visual planner</option>
                <option value="qwen-planner-7b">Legacy Qwen2.5 7B · CPU text only</option>
              </select></label>}
              <small>
                Auto uses {plannerModel === 'qwen-planner-7b' ? 'the explicit legacy CPU text planner' : 'the configured Qwen3.8 CUDA visual planner'} for editable scenes.
                {plannerModel === 'qwen3.8-planner' ? 'Uploaded images are analyzed before proposing scenes and also condition the image renders.' : 'The legacy text planner does not inspect uploaded images.'}
              </small>
              <small>
                {plannerModel === 'qwen-planner-7b' ? plannerInfo?.legacy_text_detail : plannerInfo?.providers.find((item) => item.id === plannerProvider)?.detail}
              </small>
              <button
                onClick={() => {
                  setMenu(null);
                  onSettings();
                }}
              >
                Connection settings
              </button>
            </>
          )}
        </AnchoredPopover>
      )}
      {picker && (
        <AssetPicker
          title={packStep === 1 ? 'Choose your photo' : 'Add storyboard reference'}
          kind="image"
          assets={assets.assets}
          onAdded={assets.add}
          onClose={() => setPicker(false)}
          onSelect={(asset) =>
            update({
              reference_asset_ids:
                packStep === 1
                  ? [asset.id]
                  : [...new Set([...state.reference_asset_ids, asset.id])].slice(0, 4),
            })
          }
        />
      )}
      {packStep !== null && (
        <WorkspaceDialog
          title={
            packStep === 0 ? 'Instadump' : packStep === 1 ? 'Add your photo' : 'Review your scenes'
          }
          className="pop-pack-dialog"
          onClose={() => setPackStep(null)}
        >
          <nav>
            {['Choose a Pack', 'Add Photo', 'Get Instadump'].map((label, index) => (
              <button
                disabled={index > packStep}
                className={index === packStep ? 'active' : ''}
                key={label}
                onClick={() => setPackStep(index)}
              >
                <span>{index + 1}</span>
                {label}
              </button>
            ))}
          </nav>
          <div className="pop-pack-body">
            {packStep === 0 ? (
              <>
                <section className="pop-pack-hero">
                  <div>
                    <span>
                      <Icon name="image" size={16} />
                      Instadump
                    </span>
                    <h2>Generate your Instadump</h2>
                    <p>
                      Upload a photo and build an editable pack of scenes guided by your reference.
                    </p>
                  </div>
                  <ReferenceMedia
                    item={
                      (library as typeof library & { instadump_hero?: ReferenceItem[] })
                        .instadump_hero?.[0]
                    }
                  />
                </section>
                <div className="pop-pack-toolbar">
                  <label>
                    <Icon name="search" size={14} />
                    <input
                      value={packSearch}
                      onChange={(event) => setPackSearch(event.target.value)}
                      placeholder="Search"
                    />
                  </label>
                  <button
                    onClick={() => {
                      setPack(null);
                      setPackName('');
                      setPackStep(1);
                    }}
                  >
                    <Icon name="plus" size={16} />
                    Create pack
                  </button>
                </div>
                <div className="pop-pack-grid">
                  {packs
                    .filter((item) => item.title.toLowerCase().includes(packSearch.toLowerCase()))
                    .map((item) => (
                      <button
                        className={
                          pack?.id === item.id && pack?.title === item.title ? 'selected' : ''
                        }
                        key={item.id || item.title}
                        onClick={() => setPack(item)}
                      >
                        {(item as ReferenceItem & { images?: string[] }).images?.length ? (
                          <div className="pop-pack-images">
                            {(item as ReferenceItem & { images: string[] }).images
                              .slice(0, 3)
                              .map((url, index) => (
                                <img key={url + index} src={url} alt="" />
                              ))}
                          </div>
                        ) : (
                          <ReferenceMedia item={item} />
                        )}
                        <strong>{item.title}</strong>
                      </button>
                    ))}
                </div>
                <footer>
                  <small>Editable prompt directions; original pack recipes are not exposed.</small>
                  <button disabled={!pack} className="pop-pack-next" onClick={() => setPackStep(1)}>
                    Select pack
                  </button>
                </footer>
              </>
            ) : packStep === 1 ? (
              <>
                <p className="pop-pack-subtitle">
                  Upload a photo to guide the appearance of your scenes.
                </p>
                {!pack && (
                  <label className="pop-custom-direction">
                    Pack direction
                    <input
                      value={packName}
                      onChange={(event) => setPackName(event.target.value)}
                      placeholder="For example, a candid weekend at the coast"
                    />
                  </label>
                )}
                <button className="pop-photo-drop" onClick={() => setPicker(true)}>
                  {references[0] ? (
                    <img src={mediaUrl(references[0])} alt="Your reference" />
                  ) : (
                    <i>
                      <Icon name="image" size={30} />
                      <span>+</span>
                    </i>
                  )}
                  <strong>{references.length ? 'Change your photo' : 'Upload your photo'}</strong>
                  <span>Use a clear, well-lit photo for best results.</span>
                  <small>PNG, JPG or another supported image.</small>
                </button>
                <footer>
                  <select
                    className="pop-pack-ratio"
                    aria-label="Pack aspect ratio"
                    value={state.aspect_ratio}
                    onChange={(event) => update({ aspect_ratio: event.target.value })}
                  >
                    {ratios.map((ratio) => (
                      <option value={ratio} key={ratio}>
                        {ratio}
                      </option>
                    ))}
                  </select>
                  <span />
                  <button onClick={() => setPackStep(0)}>Back</button>
                  <button
                    className="pop-pack-next"
                    disabled={!references.length || (!pack && !packName.trim())}
                    onClick={() => setPackStep(2)}
                  >
                    Review scenes
                  </button>
                </footer>
              </>
            ) : (
              <div className="pop-pack-review">
                <h2>Four scenes, ready to make yours</h2>
                <p>
                  Review and edit the establishing shot, candid portrait, close-up and wider
                  finishing shot before generation.
                </p>
                <strong>{pack?.title || packName}</strong>
                <button className="pop-pack-next" onClick={applyPack}>
                  Edit scenes
                </button>
              </div>
            )}
          </div>
        </WorkspaceDialog>
      )}
      {showHelp && (
        <WorkspaceDialog title="Create a visual storyboard" onClose={() => setShowHelp(false)}>
          <p>
            Auto uses a real CPU language model to propose scenes. Review its result in Manual, edit
            every scene and select up to four image references. Generate then creates one real image
            job for each scene.
          </p>
          <p>
            Instadump starts an editable four-scene photo series. The reference images guide
            appearance without training an identity model. Every result includes its actual ComfyUI
            workflow.
          </p>
          <p>
            To animate a finished frame, open it from My storyboards and use it in Cinema Studio.
          </p>
        </WorkspaceDialog>
      )}
      {selected && (
        <ResultDialog
          job={selected}
          onClose={() => setSelectedId(null)}
          onRefresh={() => void session.refreshJobs()}
          onReuse={() => void reuse(selected)}
          useKind="image"
          useLabel="Animate in Cinema Studio"
          onUse={(asset) => {
            void (async () => {
              try {
                const doc = await post<AppDocument<Record<string, unknown>>>(
                  '/apps/cinema-studio/documents',
                  {
                    title: 'Animate storyboard frame',
                    state: {
                      prompt: `Animate this storyboard frame with coherent natural movement, preserving its characters and setting. ${selected.request.prompt.replace(/^Create one storyboard still frame\.\s*/, '')}`,
                      mode: 'video',
                      model_id: catalog.models.some((item) => item.id === 'ltx-2.5') ? 'ltx-2.5' : 'ltx-2.3',
                      provider: '',
                      aspect_ratio: state.aspect_ratio === 'Auto' ? '3:4' : state.aspect_ratio,
                      quality: 1024,
                      duration: 4,
                      variants: 1,
                      generate_audio: true,
                      reference_asset_ids: [asset.id],
                      attachment_asset_ids: [],
                      film: { genre: 'General', era: 'Auto', tempo: 'Auto' },
                      camera: { body: 'Auto', lens: 'Auto', aperture: 'Auto', movements: [] },
                      palette: 'Auto',
                      lighting: 'Auto',
                      palette_colors: [],
                      custom_lights: [],
                      palette_presets: [],
                      lighting_presets: [],
                      pinned_presets: [],
                    },
                    asset_ids: [asset.id],
                  },
                );
                location.assign(`/generate?document=${doc.id}`);
              } catch (reason) {
                setError((reason as Error).message);
              }
            })();
          }}
        />
      )}
    </main>
  );
}
