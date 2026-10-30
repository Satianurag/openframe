import { useEffect, useRef, useState } from 'react';
import { api, mediaUrl, post } from '../api';
import { Icon } from '../Icon';
import { Modal } from '../ui';
import type { Asset, Catalog, JobRequest, Settings } from '../types';
import type { AppDocument, ApplicationId } from './registry';
import { AssetPicker, useWorkspaceAssets } from './engine-apps-shared';
import { renderRequest } from './renderRequest';
import { plannerAvailable, plannerRunNote } from './plannerStatus';
import type { PlannerInfo } from './plannerStatus';
import './sequence-planner.css';

type Narration = { text: string; voice: string; language: 'English' | 'Chinese'; speed: number; start: number };
type CaptionCue = { start: number; end: number; text: string };
type Captions = { mode: 'none' | 'narration' | 'soundtrack' | 'manual'; language: 'English' | 'Chinese'; burn_in: boolean; cues: CaptionCue[] };
const emptyNarration = (): Narration => ({ text: '', voice: 'US_Emma', language: 'English', speed: 1, start: 0 });
const emptyCaptions = (): Captions => ({ mode: 'none', language: 'English', burn_in: false, cues: [] });

type Shot = {
  id: string;
  label: string;
  request: JobRequest;
  source_from_previous: boolean;
  existing_video_asset_id?: string | null;
  status?: string;
  job_status?: string;
  job_id?: string;
  progress?: number;
  stage?: string;
  error?: string;
  actual_duration?: number;
  output_asset_id?: string;
  narration?: Narration;
  narration_job_id?: string;
  narration_status?: string;
  narration_output?: Asset;
  narration_actual_duration?: number;
  narration_error?: string;
};
type Episode = {
  id?: string;
  title: string;
  target_duration: number;
  shots: Shot[];
  audio_asset_id: string | null;
  audio_start: number;
  pad_audio_silence?: boolean;
  audio_provider?: string | null;
  keep_shot_audio: boolean;
  transition?: 'cut' | 'fade' | 'dissolve' | 'wipeleft' | 'wiperight' | 'slideleft' | 'slideright';
  transition_frames?: number;
  encoding_quality?: 'standard' | 'high';
  background_audio_asset_id?: string | null;
  background_audio_start?: number;
  background_gain?: number;
  duck_background?: boolean;
  narration_gain?: number;
  shot_audio_gain?: number;
  captions?: Captions;
  planned_duration?: number;
  actual_duration?: number;
  output?: Asset | null;
  status?: string;
};
export type Sequence = {
  id: string;
  planner_id?: string | null;
  revision: number;
  app_id: string;
  document_id: string;
  document_revision: number;
  status: string;
  stage: string;
  progress: number;
  episodes: Episode[];
  error?: string;
  completed_shots: number;
  total_shots: number;
};
export function sequenceStatus(sequence: Sequence) {
  if (sequence.status === 'failed' && !sequence.error) {
    if (/^(Captions|Audio) changed;/.test(sequence.stage)) return 'Needs assembly';
    if (sequence.stage.startsWith('Narration changed;')) return 'Changes saved';
  }
  return sequence.status;
}
export type ShotProposal = {
  id: string;
  request?: { budget_seconds?: number };
  status: string;
  stage: string;
  progress: number;
  error?: string;
  proposal?: {
    reference_analysis?: { asset_id: string; observations: Record<string, string>; evidence: Record<string, unknown> }[];
    episodes: {
      title: string;
      target_duration: number;
      shots: { id: string; prompt: string; camera: string; voiceover: string; duration: number }[];
    }[];
    metadata: Record<string, unknown>;
  };
};
type SavedDocument = AppDocument<Record<string, unknown>>;
type Props = {
  appId: ApplicationId;
  document: SavedDocument;
  initialPrompt: string;
  initialStyle?: string;
  initialSequenceId?: string;
  targetDuration: number;
  episodeCount: number;
  catalog: Catalog;
  settings: Settings;
  initialRequest?: Partial<JobRequest>;
  initialExistingVideo?: Asset;
  initialAudioAssetId?: string;
  onClose: () => void;
  onPrepareDocument: (assetIds: string[]) => Promise<SavedDocument>;
  onCreated?: (sequence: Sequence) => void;
  onProposal?: (plan: ShotProposal) => void;
};

const active = (status?: string) => status === 'queued' || status === 'running';
const seconds = (value: number) => `${value.toFixed(2)}s`;

export function SequencePlanner(props: Props) {
  if (
    !props.catalog.models.some(
      (model) => model.tasks.includes('text-to-video') && model.tasks.includes('image-to-video'),
    )
  )
    return (
      <Modal title="Shot planner" onClose={props.onClose}>
        <p>A supported video model catalog must be loaded before creating a sequence.</p>
      </Modal>
    );
  return <SequenceEditor {...props} />;
}

export default SequencePlanner;

function SequenceEditor(props: Props) {
  const {
    appId,
    document: originalDocument,
    catalog,
    settings,
    onClose,
    onPrepareDocument,
    onCreated,
    onProposal,
  } = props;
  const dialog = useRef<HTMLDialogElement>(null);
  const notifiedPlan = useRef('');
  const createdCallback = useRef(onCreated);
  createdCallback.current = onCreated;
  const models = catalog.models.filter(
    (model) => model.tasks.includes('text-to-video') && model.tasks.includes('image-to-video'),
  );
  const initialModel =
    models.find((model) => model.id === props.initialRequest?.model_id) ||
    models.find((model) => model.id === 'ltx-2.5') || models[0];
  function freshShot(duration = 4): Shot {
    const model = initialModel;
    const request = renderRequest(model, {
      effect_id: 'text-to-video',
      prompt: '',
      provider: props.initialRequest?.provider || settings.default_provider || 'local',
      width: props.initialRequest?.width || 512,
      height: props.initialRequest?.height || 320,
      fps: props.initialRequest?.fps || Number(model.default_fps || 24),
    });
    const multiple = Number(model.frame_multiple || 8);
    request.frames = Math.max(
      multiple + 1,
      Math.min(
        Number(model.max_frames),
        Math.floor((duration * request.fps - 1) / multiple) * multiple + 1,
      ),
    );
    return {
      id: crypto.randomUUID().replaceAll('-', ''),
      label: 'Shot',
      request,
      source_from_previous: false,
    };
  }
  function openingShot(shot: Shot): Shot {
    return props.initialRequest?.source_asset_id &&
      props.initialRequest.effect_id === 'image-to-video'
      ? {
          ...shot,
          request: {
            ...shot.request,
            effect_id: 'image-to-video',
            source_asset_id: props.initialRequest.source_asset_id,
          },
        }
      : shot;
  }
  function existingShot(video: Asset): Shot {
    const model = catalog.models.find((item) => item.id === 'video-tools');
    if (!model || !video.frame_count || !video.width || !video.height || !video.fps)
      throw new Error('The selected video needs complete frame and geometry metadata before assembly.');
    return {
      id: crypto.randomUUID().replaceAll('-', ''), label: video.name,
      existing_video_asset_id: video.id, source_from_previous: false,
      request: renderRequest(model, { effect_id: 'trim-video', provider: 'local', prompt: '',
        source_asset_id: video.id, trim_start: 0, width: video.width, height: video.height,
        frames: video.frame_count, fps: video.fps, generate_audio: false, preserve_audio: !!video.has_audio }),
    };
  }
  const freshEpisodes = () =>
    Array.from(
      { length: Math.max(1, Math.min(4, props.episodeCount)) },
      (_, index) =>
        ({
          title: `Episode ${index + 1}`,
          target_duration: props.targetDuration,
          shots: [props.initialExistingVideo ? existingShot(props.initialExistingVideo) : openingShot(freshShot())],
          audio_asset_id: props.initialAudioAssetId || null,
          audio_provider: 'local',
          audio_start: 0,
          keep_shot_audio: false,
        }) satisfies Episode,
    );
  const [episodes, setEpisodes] = useState<Episode[]>(freshEpisodes);
  const [sequence, setSequence] = useState<Sequence | null>(null);
  const [history, setHistory] = useState<Sequence[]>([]);
  const [plan, setPlan] = useState<ShotProposal | null>(null);
  const [brief, setBrief] = useState(props.initialPrompt);
  const [style, setStyle] = useState(props.initialStyle || '');
  const [plannerProvider, setPlannerProvider] = useState('local');
  const [referenceIds, setReferenceIds] = useState<string[]>(() => Array.from(new Set([
    originalDocument.state.reference_asset_id,
    ...(Array.isArray(originalDocument.state.reference_asset_ids) ? originalDocument.state.reference_asset_ids : []),
    props.initialRequest?.source_asset_id,
  ].filter((value): value is string => typeof value === 'string' && !!value))).slice(0, 4));
  const [referenceNotes, setReferenceNotes] = useState('');
  const [plannerInfo, setPlannerInfo] = useState<PlannerInfo | null>(null);
  const [plannerModel, setPlannerModel] = useState<'qwen3.8-planner' | 'qwen-planner-7b'>('qwen3.8-planner');
  const plannerReady = plannerAvailable(plannerInfo, plannerProvider, plannerModel);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState('');
  const [closeBlocked, setCloseBlocked] = useState(false);
  const [picker, setPicker] = useState<{
    episode: number;
    shot?: number;
    kind: 'image' | 'audio';
    background?: boolean;
  } | null>(null);
  const [narrationEdits, setNarrationEdits] = useState<string[]>([]);
  const [captionEdits, setCaptionEdits] = useState<number[]>([]);
  const [audioEdits, setAudioEdits] = useState<number[]>([]);
  const [plannerId, setPlannerId] = useState<string | null>(null);
  const attached = episodes
    .flatMap((episode) => [
      episode.audio_asset_id || '',
      episode.background_audio_asset_id || '',
      ...episode.shots.flatMap((shot) => [
        shot.request.source_asset_id || '',
        shot.request.reference_asset_id || '',
        shot.request.audio_asset_id || '',
      ]),
    ])
    .filter(Boolean);
  const assets = useWorkspaceAssets([...originalDocument.asset_ids, ...attached, ...referenceIds]);
  const locked = !!sequence && sequence.status !== 'draft';
  const pending = active(sequence?.status) || active(plan?.status);
  const unsaved = dirty || narrationEdits.length > 0 || captionEdits.length > 0 || audioEdits.length > 0;
  const completeMedia = sequence?.episodes.every((episode) => episode.shots.every((shot) =>
    shot.status === 'succeeded' && (!shot.narration?.text.trim() || shot.narration_status === 'succeeded')));

  useEffect(() => {
    if (sequence) setHistory((items) => [sequence, ...items.filter((item) => item.id !== sequence.id)]);
  }, [sequence]);

  useEffect(() => {
    dialog.current?.showModal();
    let live = true;
    Promise.all([
      api<{ items: Sequence[] }>(
        `/apps/${appId}/sequences?document_id=${originalDocument.id}&limit=30`,
      ),
      api<{ items: ShotProposal[] }>(
        `/apps/${appId}/plans?document_id=${originalDocument.id}&limit=10`,
      ),
      api<PlannerInfo>('/planner'),
      props.initialSequenceId
        ? api<Sequence>(`/sequences/${props.initialSequenceId}`)
        : Promise.resolve(null),
    ])
      .then(([sequences, plans, info, selected]) => {
        if (!live) return;
        setHistory(sequences.items);
        setPlannerInfo(info);
        const current = selected || (props.initialExistingVideo
          ? sequences.items.find((item) => item.episodes.some((episode) => (!props.initialAudioAssetId || episode.audio_asset_id === props.initialAudioAssetId) && episode.shots.some((shot) => shot.existing_video_asset_id === props.initialExistingVideo!.id)))
          : sequences.items[0]);
        if (current) {
          setSequence(current);
          setEpisodes(current.episodes);
          setPlannerId(current.planner_id || null);
        }
        if (plans.items[0]) setPlan(plans.items[0]);
      })
      .catch((reason) => {
        if (live) setError(reason.message);
      });
    return () => {
      live = false;
    };
  }, [appId, originalDocument.id]);

  useEffect(() => {
    if (!pending) return;
    let live = true,
      polling = false;
    const poll = async () => {
      if (polling) return;
      polling = true;
      try {
        if (plan && active(plan.status)) {
          const current = await api<ShotProposal>(`/plans/${plan.id}`, {
            signal: AbortSignal.timeout(15000),
          });
          if (live) setPlan(current);
        }
        if (sequence && active(sequence.status)) {
          const current = await api<Sequence>(`/sequences/${sequence.id}`, {
            signal: AbortSignal.timeout(15000),
          });
          if (live) {
            setSequence(current);
            setEpisodes(current.episodes);
            if (!active(current.status)) createdCallback.current?.(current);
          }
        }
        if (live) setPollError('');
      } catch (reason) {
        if (live) setPollError((reason as Error).message);
      } finally {
        polling = false;
      }
    };
    const timer = setInterval(() => void poll(), 2000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [pending, plan?.id, plan?.status, sequence?.id, sequence?.status]);

  useEffect(() => {
    if (plan?.status === 'succeeded' && notifiedPlan.current !== plan.id) {
      notifiedPlan.current = plan.id;
      onProposal?.(plan);
    }
  }, [plan, onProposal]);

  function editEpisode(index: number, changes: Partial<Episode>) {
    setEpisodes((items) =>
      items.map((episode, at) => (at === index ? { ...episode, ...changes } : episode)),
    );
    if (!locked) setDirty(true);
  }
  function editAudio(index: number, changes: Partial<Episode>) {
    const episode = episodes[index];
    const soundtrackChanged =
      ('audio_asset_id' in changes && changes.audio_asset_id !== episode.audio_asset_id) ||
      ('audio_start' in changes && changes.audio_start !== episode.audio_start);
    if (soundtrackChanged && episode.captions?.mode === 'soundtrack') {
      changes = { ...changes, captions: { ...episode.captions, cues: [],
        ...('audio_asset_id' in changes && !changes.audio_asset_id ? { mode: 'manual' as const, burn_in: false } : {}),
      } };
      setCaptionEdits((items) => items.filter((at) => at !== index));
    }
    editEpisode(index, changes);
    if (locked) setAudioEdits((items) => [...new Set([...items, index])]);
  }
  function editShot(episode: number, shot: number, changes: Partial<Shot>) {
    setEpisodes((items) =>
      items.map((item, at) =>
        at === episode
          ? {
              ...item,
              shots: item.shots.map((value, index) =>
                index === shot ? { ...value, ...changes } : value,
              ),
            }
          : item,
      ),
    );
    if (!locked) setDirty(true);
  }
  function editNarration(episode: number, index: number, changes: Partial<Narration>) {
    const shot = episodes[episode].shots[index];
    editShot(episode, index, { narration: { ...emptyNarration(), ...shot.narration, ...changes } });
    if (locked) setNarrationEdits((items) => [...new Set([...items, shot.id])]);
  }
  function editCaptions(index: number, changes: Partial<Captions>) {
    editEpisode(index, { captions: { ...emptyCaptions(), ...episodes[index].captions, ...changes } });
    if (locked) setCaptionEdits((items) => [...new Set([...items, index])]);
  }
  function moveShot(episode: number, index: number, delta: number) {
    const items = [...episodes[episode].shots];
    [items[index], items[index + delta]] = [items[index + delta], items[index]];
    editEpisode(episode, { shots: items });
  }
  function changeModel(episode: number, index: number, id: string) {
    const model = models.find((item) => item.id === id)!;
    const current = episodes[episode].shots[index],
      request = current.request;
    const multiple = Number(model.frame_multiple || 8),
      grid = Number(model.dimension_multiple || 32);
    if (request.width % grid || request.height % grid) {
      setError(
        'This model needs different dimensions. Adjust the whole episode first so shots remain consistent.',
      );
      return;
    }
    editShot(episode, index, {
      request: {
        ...request,
        model_id: id,
        generate_audio: !!model.supports_audio && request.generate_audio,
        steps: Number(model.default_steps),
        guidance: Number(model.default_guidance),
        frames: Math.min(
          Number(model.max_frames),
          Math.max(multiple + 1, Math.floor((request.frames - 1) / multiple) * multiple + 1),
        ),
      },
    });
  }
  async function ensureDocument() {
    const ids = [...new Set([...originalDocument.asset_ids, ...attached, ...referenceIds])];
    const current = await onPrepareDocument(ids);
    if (!ids.every((id) => current.asset_ids.includes(id)))
      throw new Error('Save every selected input as a document attachment before continuing.');
    return current;
  }
  function payload(current: SavedDocument) {
    return {
      expected_revision: current.revision,
      planner_id: plannerId,
      episodes: episodes.map((episode) => ({
        title: episode.title,
        target_duration: episode.target_duration,
        audio_asset_id: episode.audio_asset_id,
        audio_start: episode.audio_start,
        pad_audio_silence: episode.pad_audio_silence || false,
        audio_provider: episode.audio_provider || 'local',
        keep_shot_audio: episode.keep_shot_audio,
        transition: episode.transition || 'cut',
        transition_frames: episode.transition_frames ?? 12,
        encoding_quality: episode.encoding_quality || 'high',
        background_audio_asset_id: episode.background_audio_asset_id || null,
        background_audio_start: episode.background_audio_start || 0,
        background_gain: episode.background_gain ?? .15,
        duck_background: episode.duck_background ?? true,
        narration_gain: episode.narration_gain ?? 1,
        shot_audio_gain: episode.shot_audio_gain ?? 1,
        captions: episode.captions || emptyCaptions(),
        shots: episode.shots.map((shot) => ({
          id: shot.id,
          label: shot.label,
          source_from_previous: shot.source_from_previous,
          existing_video_asset_id: shot.existing_video_asset_id || null,
          request: shot.request,
          narration: shot.narration || emptyNarration(),
        })),
      })),
    };
  }
  async function saveCorrections() {
    if (!sequence) return;
    let current = sequence;
    const document = audioEdits.length ? await ensureDocument() : null;
    for (const [episodeIndex, episode] of episodes.entries()) {
      let captionsSavedFirst = false;
      if (audioEdits.includes(episodeIndex) && !episode.audio_asset_id &&
          current.episodes[episodeIndex].captions?.mode === 'soundtrack') {
        // A removed recording can no longer supply automatic captions.
        current = await api<Sequence>(`/sequences/${current.id}/episodes/${episodeIndex}/captions`, {
          method: 'PATCH', body: JSON.stringify({ expected_revision: current.revision,
            cues: episode.captions?.cues || [], burn_in: episode.captions?.burn_in || false, reassemble: false }),
        });
        setSequence(current);
        setCaptionEdits((items) => items.filter((index) => index !== episodeIndex));
        captionsSavedFirst = true;
      }
      if (audioEdits.includes(episodeIndex)) {
        current = await api<Sequence>(`/sequences/${current.id}/episodes/${episodeIndex}/audio`, {
          method: 'PATCH', body: JSON.stringify({
            expected_revision: current.revision,
            expected_document_revision: document?.revision,
            audio_asset_id: episode.audio_asset_id || null,
            audio_start: episode.audio_start,
            pad_audio_silence: episode.pad_audio_silence || false,
            audio_provider: episode.audio_provider || 'local',
            keep_shot_audio: episode.keep_shot_audio,
            background_audio_asset_id: episode.background_audio_asset_id || null,
            background_audio_start: episode.background_audio_start || 0,
            background_gain: episode.background_gain ?? .15,
            duck_background: episode.duck_background ?? true,
            narration_gain: episode.narration_gain ?? 1,
            shot_audio_gain: episode.shot_audio_gain ?? 1,
            reassemble: false,
          }),
        });
        setSequence(current);
        setAudioEdits((items) => items.filter((index) => index !== episodeIndex));
      }
      for (const [shotIndex, shot] of episode.shots.entries()) {
        if (!narrationEdits.includes(shot.id)) continue;
        current = await api<Sequence>(`/sequences/${current.id}/episodes/${episodeIndex}/shots/${shotIndex}/narration`, {
          method: 'PATCH', body: JSON.stringify({ expected_revision: current.revision, narration: shot.narration || emptyNarration() }),
        });
        setSequence(current);
        setNarrationEdits((items) => items.filter((id) => id !== shot.id));
      }
      if (!captionsSavedFirst && captionEdits.includes(episodeIndex)) {
        current = await api<Sequence>(`/sequences/${current.id}/episodes/${episodeIndex}/captions`, {
          method: 'PATCH', body: JSON.stringify({ expected_revision: current.revision,
            cues: episode.captions?.cues || [], burn_in: episode.captions?.burn_in || false, reassemble: false }),
        });
        setSequence(current);
        setCaptionEdits((items) => items.filter((index) => index !== episodeIndex));
      }
    }
    setEpisodes(current.episodes);
    onCreated?.(current);
    return current;
  }
  async function reassembleAudio(index: number) {
    const current = await saveCorrections();
    if (!current) return;
    const result = await api<Sequence>(`/sequences/${current.id}/episodes/${index}/audio`, {
      method: 'PATCH',
      body: JSON.stringify({ expected_revision: current.revision, reassemble: true }),
    });
    setSequence(result);
    setEpisodes(result.episodes);
    onCreated?.(result);
  }
  async function reassembleCaptions(index: number) {
    const current = await saveCorrections();
    if (!current) return;
    const captions = current.episodes[index].captions || emptyCaptions();
    const result = await api<Sequence>(`/sequences/${current.id}/episodes/${index}/captions`, {
      method: 'PATCH', body: JSON.stringify({ expected_revision: current.revision,
        cues: captions.cues, burn_in: captions.burn_in, reassemble: true }),
    });
    setSequence(result);
    setEpisodes(result.episodes);
    onCreated?.(result);
  }
  async function saveDraft(): Promise<Sequence> {
    if (sequence && !dirty) return sequence;
    const current = await ensureDocument();
    const result =
      sequence?.status === 'draft'
        ? await api<Sequence>(`/sequences/${sequence.id}`, {
            method: 'PATCH',
            body: JSON.stringify({
              ...payload(current),
              expected_sequence_revision: sequence.revision,
            }),
          })
        : await post<Sequence>(
            `/apps/${appId}/documents/${current.id}/sequences`,
            payload(current),
          );
    setSequence(result);
    setEpisodes(result.episodes);
    setDirty(false);
    onCreated?.(result);
    return result;
  }
  async function perform(action: () => Promise<unknown>) {
    setBusy(true);
    setError('');
    setCloseBlocked(false);
    try {
      await action();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function start() {
    const saved = await saveDraft();
    const result = await post<Sequence>(`/sequences/${saved.id}/start`, {
      expected_revision: saved.revision,
    });
    setSequence(result);
    setEpisodes(result.episodes);
    onCreated?.(result);
  }
  async function sequenceAction(action: 'cancel' | 'resume' | 'retry') {
    if (!sequence) return;
    const result = await post<Sequence>(`/sequences/${sequence.id}/${action}`);
    setSequence(result);
    setEpisodes(result.episodes);
    onCreated?.(result);
  }
  async function generatePlan() {
    if (!plannerReady || !catalog.providers.some((item) => item.id === plannerProvider))
      throw new Error('Select an enabled planning connection. No alternate provider will be used.');
    const current = await ensureDocument();
    const result = await post<ShotProposal>(`/apps/${appId}/documents/${current.id}/plans`, {
      expected_revision: current.revision,
      prompt: brief,
      style,
      target_duration: props.targetDuration,
      episodes: props.episodeCount,
      seed: 42,
      provider: plannerProvider,
      model_id: plannerModel,
      reference_asset_ids: plannerModel === 'qwen3.8-planner' ? referenceIds : [],
      reference_notes: referenceNotes,
    });
    setPlan(result);
  }
  function useProposal() {
    if (!plan?.proposal) return;
    setEpisodes(
      plan.proposal.episodes.map((episode) => ({
        title: episode.title,
        target_duration: episode.target_duration,
        audio_asset_id: null,
        audio_provider: 'local' as const,
        audio_start: 0,
        keep_shot_audio: false,
        shots: episode.shots.map((proposal, index) => {
          const shot =
            index === 0 ? openingShot(freshShot(proposal.duration)) : freshShot(proposal.duration);
          shot.id = proposal.id;
          shot.label = proposal.camera.slice(0, 160);
          shot.request.prompt = `${proposal.prompt}\nCamera instruction: ${proposal.camera}`;
          shot.narration = { ...emptyNarration(), text: proposal.voiceover };
          return shot;
        }),
      })),
    );
    setPlannerId(plan.id);
    setSequence(null);
    setNarrationEdits([]);
    setCaptionEdits([]);
    setAudioEdits([]);
    setDirty(true);
  }
  async function close() {
    if (busy) return;
    if (!unsaved) {
      onClose();
      return;
    }
    setBusy(true);
    try {
      if (locked) await saveCorrections();
      else await saveDraft();
      onClose();
    } catch (reason) {
      setError(`Changes could not be saved: ${(reason as Error).message}`);
      setCloseBlocked(true);
    } finally {
      setBusy(false);
    }
  }
  const total = episodes.reduce((sum, episode) => sum + episode.shots.length, 0);

  return (
    <dialog
      ref={dialog}
      className="sequence-planner"
      aria-label="Shot plan and episode assembly"
      onCancel={(event) => {
        event.preventDefault();
        void close();
      }}
    >
      <header>
        <div>
          <span className="sequence-eyebrow">REVIEW BEFORE RENDERING</span>
          <h2>{props.initialExistingVideo ? 'Finish your video' : 'Build your sequence'}</h2>
        </div>
        <button aria-label="Close shot planner" disabled={busy} onClick={() => void close()}>
          <Icon name="close" />
        </button>
      </header>
      <div className="sequence-body">
        {!props.initialExistingVideo && <section className="sequence-proposal">
          <div>
            <h3>Start with an editable proposal</h3>
            <p>
              Cloud planning uses your brief and selected visual references to draft distinct shots.
              Review the prompts and narration here, then render the sequence.
            </p>
          </div>
          <label>
            Creative brief
            <textarea
              value={brief}
              maxLength={3000}
              onChange={(event) => setBrief(event.target.value)}
              rows={3}
            />
          </label>
          <div className="sequence-row">
            <label>
              Style notes
              <input
                value={style}
                maxLength={200}
                onChange={(event) => setStyle(event.target.value)}
                placeholder="Optional visual direction"
              />
            </label>
            <label>
              Planner compute
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
            <button
              className="sequence-secondary"
              disabled={
                busy ||
                active(plan?.status) ||
                !brief.trim() ||
                !plannerReady ||
                !catalog.providers.some((item) => item.id === plannerProvider)
              }
              onClick={() => void perform(generatePlan)}
            >
              Plan {props.episodeCount} × {props.targetDuration}s episodes
            </button>
          </div>
          <small>
            {plannerModel === 'qwen-planner-7b' ? 'Explicit legacy Qwen2.5 text planner' : plannerInfo?.name || 'Configured CUDA visual planner'} ·{' '}
            {plannerModel === 'qwen-planner-7b' ? plannerInfo?.legacy_text_detail : plannerInfo?.providers.find((item) => item.id === plannerProvider)?.detail}
          </small>
          <fieldset className="sequence-reference-analysis" disabled={plannerModel !== 'qwen3.8-planner' || active(plan?.status)}>
            <legend>Visual references · {referenceIds.length}/4</legend>
            {[...new Set([...originalDocument.asset_ids, ...referenceIds])].map((id) => {
              const asset = assets.get(id);
              return asset && (asset.kind === 'image' || asset.kind === 'video') ? (
                <label key={id}>
                  <input type="checkbox" checked={referenceIds.includes(id)}
                    disabled={!referenceIds.includes(id) && referenceIds.length >= 4}
                    onChange={(event) => setReferenceIds((current) => event.target.checked ? [...current, id] : current.filter((value) => value !== id))} />
                  {asset.name}
                </label>
              ) : null;
            })}
            <small>Analyzes images and up to 16 sampled frames per video. Audio is not analyzed. Videos must be five minutes or shorter.</small>
          </fieldset>
          {plannerModel === 'qwen-planner-7b' && referenceIds.length > 0 && <small>The local text planner does not analyze the selected references.</small>}
          {plan?.proposal?.reference_analysis?.map((analysis) => (
            <details key={analysis.asset_id}>
              <summary>Reference observations · {assets.get(analysis.asset_id)?.name || analysis.asset_id}</summary>
              {Object.entries(analysis.observations).map(([label, value]) => <p key={label}><strong>{label}:</strong> {value}</p>)}
              <small>{String(analysis.evidence.sampling || '')}</small>
            </details>
          ))}
          {(referenceIds.length > 0 || referenceNotes) && <label>
            Reference corrections for the next proposal
            <textarea value={referenceNotes} maxLength={3000} onChange={(event) => setReferenceNotes(event.target.value)}
              placeholder="Correct an observation or explain which reference details the new story should follow." />
          </label>}
          {plan && (
            <div className="sequence-plan-status">
              <span>{plan.status === 'succeeded' ? 'Editable proposal ready for review' : plan.stage}</span>
              {active(plan.status) && (
                <>
                  <progress value={plan.progress} max={1} />
                  <button
                    onClick={() =>
                      void perform(async () =>
                        setPlan(await post<ShotProposal>(`/plans/${plan.id}/cancel`)),
                      )
                    }
                  >
                    Cancel planning
                  </button>
                </>
              )}
              {plan.status === 'succeeded' && (
                <button
                  className="sequence-secondary"
                  disabled={busy || active(sequence?.status)}
                  onClick={useProposal}
                >
                  {unsaved ? 'Replace unsaved edits with proposal' : 'Review this proposal'}
                </button>
              )}
              {plannerRunNote(plan) && (
                <small className="sequence-planning-note">{plannerRunNote(plan)}</small>
              )}
              {plan.error && <p role="alert">{plan.error}</p>}
            </div>
          )}
        </section>}
        <div className="sequence-draft-tools">
          <h3>
            Ordered shots <span>{total}</span>
          </h3>
          <select
            aria-label="Saved sequence"
            value={sequence?.id || ''}
            disabled={unsaved || busy || pending}
            onChange={(event) => {
              const id = event.target.value;
              if (id) void perform(async () => {
                const value = await api<Sequence>(`/sequences/${id}`);
                setSequence(value);
                setEpisodes(value.episodes);
                setPlannerId(value.planner_id || null);
                setNarrationEdits([]);
                setCaptionEdits([]);
                setAudioEdits([]);
              });
            }}
          >
            <option value="">New manual plan</option>
            {history.map((item) => (
              <option key={item.id} value={item.id}>
                {item.episodes[0]?.title} · {sequenceStatus(item)}
              </option>
            ))}
          </select>
          <button
            disabled={busy || unsaved || active(sequence?.status)}
            onClick={() => {
              setSequence(null);
              setEpisodes(freshEpisodes());
              setPlannerId(null);
              setNarrationEdits([]);
              setCaptionEdits([]);
              setAudioEdits([]);
            }}
          >
            New manual plan
          </button>
        </div>
        {sequence && (
          <div className="sequence-status">
            <strong>{sequence.stage}</strong>
            <a href={`/api/sequences/${sequence.id}`} download={`sequence-${sequence.id}.json`}>
              Sequence manifest
            </a>
            <span>
              {sequence.completed_shots}/{sequence.total_shots} shots complete · {sequenceStatus(sequence)}
            </span>
            {active(sequence.status) && <progress value={sequence.progress} max={1} />}
            <small>
              Saved plan revision {sequence.revision}; originating document revision{' '}
              {sequence.document_revision}.
            </small>
            {sequence.error && <p role="alert">{sequence.error}</p>}
          </div>
        )}
        {episodes.map((episode, episodeIndex) => {
          const first = episode.shots[0]?.request;
          const captions = episode.captions || emptyCaptions();
          const hasNarration = episode.shots.some((shot) => !!shot.narration?.text.trim());
          const overlap = episode.transition && episode.transition !== 'cut' ? (episode.transition_frames ?? 12) / (first?.fps || 24) : 0;
          const planned = episode.shots.reduce(
              (sum, shot) => sum + shot.request.frames / shot.request.fps,
              0,
            ) - Math.max(0, episode.shots.length - 1) * overlap;
          const captionDuration = episode.actual_duration ?? planned;
          return (
            <section key={episodeIndex} className="sequence-episode">
              <header>
                <label>
                  Episode {episodeIndex + 1}
                  <input
                    value={episode.title}
                    maxLength={160}
                    disabled={locked}
                    onChange={(event) => editEpisode(episodeIndex, { title: event.target.value })}
                  />
                </label>
                <div className={planned > 300 ? 'sequence-over' : ''}>
                  <strong>{seconds(planned)} planned</strong>
                  <span>
                    {seconds(episode.target_duration)} editorial target
                    {episode.actual_duration != null
                      ? ` · ${seconds(episode.actual_duration)} assembled`
                      : ''}
                  </span>
                </div>
              </header>
              <div className="sequence-row sequence-geometry">
                {(['width', 'height', 'fps'] as const).map((key) => (
                  <label key={key}>
                    {key === 'fps' ? 'FPS' : key}
                    <input
                      type="number"
                      min={key === 'fps' ? 1 : 64}
                      max={key === 'fps' ? 120 : 1536}
                      value={first?.[key] || ''}
                      disabled={locked || episode.shots.some((shot) => !!shot.existing_video_asset_id)}
                      onChange={(event) => {
                        const value = Number(event.target.value);
                        editEpisode(episodeIndex, {
                          shots: episode.shots.map((shot) => ({
                            ...shot,
                            request: { ...shot.request, [key]: value },
                          })),
                        });
                      }}
                    />
                  </label>
                ))}
                <label>
                  Assembly audio
                  <select
                    value={
                      episode.audio_asset_id ? 'track' : episode.keep_shot_audio ? 'shots' : 'none'
                    }
                    disabled={busy || pending}
                    onChange={(event) => {
                      if (event.target.value === 'track')
                        setPicker({ episode: episodeIndex, kind: 'audio' });
                      else
                        editAudio(episodeIndex, {
                          audio_asset_id: null,
                          keep_shot_audio: event.target.value === 'shots',
                        });
                    }}
                  >
                    <option value="none">{hasNarration ? 'Narration only' : 'No shot audio'}</option>
                    <option value="shots">Keep each shot’s audio</option>
                    <option value="track" disabled={hasNarration}>Choose foreground soundtrack</option>
                  </select>
                </label>
              </div>
              <div className="sequence-row">
                <label>
                  Between shots
                  <select value={episode.transition || 'cut'} disabled={locked}
                    onChange={(event) => editEpisode(episodeIndex, { transition: event.target.value as Episode['transition'] })}>
                    <option value="cut">Cut</option>
                    <option value="fade">Crossfade</option>
                    <option value="dissolve">Dissolve</option>
                    <option value="wipeleft">Wipe left</option>
                    <option value="wiperight">Wipe right</option>
                    <option value="slideleft">Slide left</option>
                    <option value="slideright">Slide right</option>
                  </select>
                </label>
                {episode.transition && episode.transition !== 'cut' && <label>
                  Overlap frames
                  <input type="number" min={1} max={240} value={episode.transition_frames ?? 12} disabled={locked}
                    onChange={(event) => editEpisode(episodeIndex, { transition_frames: Math.max(1, Math.min(240, Number(event.target.value))) })} />
                  <small>{seconds(overlap)} per transition; shortens the assembled timeline.</small>
                </label>}
                <label>
                  Output bitrate
                  <select value={episode.encoding_quality || 'high'} disabled={locked}
                    onChange={(event) => editEpisode(episodeIndex, { encoding_quality: event.target.value as Episode['encoding_quality'] })}>
                    <option value="standard">Standard</option>
                    <option value="high">High</option>
                  </select>
                </label>
              </div>
              {episode.audio_asset_id && (
                <div className="sequence-soundtrack">
                  <audio controls src={`/api/assets/${episode.audio_asset_id}/file`} />
                  <label>
                    Recording start
                    <input
                      type="number"
                      min={0}
                      step={0.1}
                      value={episode.audio_start}
                      disabled={busy || pending}
                      onChange={(event) =>
                        editAudio(episodeIndex, { audio_start: Number(event.target.value) })
                      }
                    />
                  </label>
                  <label><input type="checkbox" checked={episode.pad_audio_silence || false} disabled={busy || pending}
                    onChange={(event) => editAudio(episodeIndex, { pad_audio_silence: event.target.checked })} />
                    Add silence after this recording if it ends before the video. Never loop it.
                  </label>
                  <button
                    disabled={busy || pending}
                    onClick={() => setPicker({ episode: episodeIndex, kind: 'audio' })}
                  >
                    Change soundtrack
                  </button>
                </div>
              )}
              <details className="sequence-mix">
                <summary>Music and audio mix</summary>
                <label>Speech and caption compute<select value={episode.audio_provider || 'local'} disabled={busy || pending}
                  onChange={(event) => editAudio(episodeIndex, { audio_provider: event.target.value })}>
                  {(episode.audio_provider || 'local') !== 'local' && <option value={episode.audio_provider || 'local'} disabled>Saved connection · disabled</option>}
                  {catalog.providers.filter((provider) => ['local'].includes(provider.id)).map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}
                </select></label>
                <small>Local requires the pinned Ming/Qwen CUDA runtimes on the configured ComfyUI host. Hosted Comfy Cloud does not support these speech nodes. Existing recordings and manual captions do not run a speech model.</small>
                <p>Narration requires an enabled speech provider. Use background audio for music underneath it; a foreground soundtrack replaces narration.</p>
                <div className="sequence-soundtrack">
                  <button disabled={busy || pending} onClick={() => setPicker({ episode: episodeIndex, kind: 'audio', background: true })}>
                    {episode.background_audio_asset_id ? 'Change background audio' : 'Choose background audio'}
                  </button>
                  {episode.background_audio_asset_id && <>
                    <audio controls src={`/api/assets/${episode.background_audio_asset_id}/file`} />
                    <button disabled={busy || pending} onClick={() => editAudio(episodeIndex, { background_audio_asset_id: null })}>Remove</button>
                  </>}
                </div>
                <div className="sequence-row">
                  {episode.background_audio_asset_id && <label>Background start (seconds)
                    <input type="number" min={0} step={.1} value={episode.background_audio_start || 0} disabled={busy || pending}
                      onChange={(event) => editAudio(episodeIndex, { background_audio_start: Number(event.target.value) })} />
                  </label>}
                  {(['background_gain', 'narration_gain', 'shot_audio_gain'] as const).map((field) => <label key={field}>
                    {{ background_gain: 'Background volume', narration_gain: 'Narration volume', shot_audio_gain: 'Shot audio volume' }[field]}
                    <input type="number" min={0} max={2} step={.05} disabled={busy || pending}
                      value={episode[field] ?? (field === 'background_gain' ? .15 : 1)}
                      onChange={(event) => editAudio(episodeIndex, { [field]: Number(event.target.value) })} />
                  </label>)}
                </div>
                <label className="sequence-audio-choice"><input type="checkbox" checked={episode.duck_background ?? true} disabled={busy || pending}
                  onChange={(event) => editAudio(episodeIndex, { duck_background: event.target.checked })} />Lower background music during foreground audio</label>
                {locked && <p>Audio changes retain completed shots and generated narration. Replacing the foreground soundtrack clears its automatic captions for retranscription. Removing it also clears those captions.</p>}
                {locked && completeMedia && <button disabled={busy || pending || narrationEdits.length > 0}
                  onClick={() => void perform(() => reassembleAudio(episodeIndex))}>Rebuild completed video with this audio</button>}
              </details>
              <details className="sequence-captions" open={captions.mode !== 'none'}>
                <summary>Captions</summary>
                <div className="sequence-row">
                  <label>Caption source
                    <select value={captions.mode} disabled={locked || busy} onChange={(event) => editCaptions(episodeIndex, { mode: event.target.value as Captions['mode'] })}>
                      <option value="none">No captions</option><option value="narration">Transcribe generated narration</option>
                      <option value="soundtrack">Transcribe soundtrack</option><option value="manual">Write timed captions</option>
                    </select>
                  </label>
                  <label>Language<select value={captions.language} disabled={locked || busy}
                    onChange={(event) => editCaptions(episodeIndex, { language: event.target.value as Captions['language'] })}>
                    <option value="English">English</option><option value="Chinese">Mandarin Chinese</option>
                  </select></label>
                  <label className="sequence-audio-choice"><input type="checkbox" checked={captions.burn_in} disabled={busy || pending}
                    onChange={(event) => editCaptions(episodeIndex, { burn_in: event.target.checked })} />Burn captions into video</label>
                </div>
                {(captions.mode === 'narration' || captions.mode === 'soundtrack') && <small>Qwen transcribes the actual audio and aligns words. Review the resulting times and text after rendering.</small>}
                {captions.cues.map((cue, index) => <div className="sequence-caption-cue" key={index}>
                  <label>Start<input type="number" min={0} step={.01} value={cue.start} disabled={busy || pending}
                    onChange={(event) => editCaptions(episodeIndex, { cues: captions.cues.map((item, at) => at === index ? { ...item, start: Number(event.target.value) } : item) })} /></label>
                  <label>End<input type="number" min={0} step={.01} value={cue.end} disabled={busy || pending}
                    onChange={(event) => editCaptions(episodeIndex, { cues: captions.cues.map((item, at) => at === index ? { ...item, end: Number(event.target.value) } : item) })} /></label>
                  <label>Caption<textarea rows={2} maxLength={300} value={cue.text} disabled={busy || pending}
                    onChange={(event) => editCaptions(episodeIndex, { cues: captions.cues.map((item, at) => at === index ? { ...item, text: event.target.value } : item) })} /></label>
                  <button aria-label={`Remove caption ${index + 1}`} disabled={busy || pending}
                    onClick={() => editCaptions(episodeIndex, { cues: captions.cues.filter((_, at) => at !== index) })}>×</button>
                </div>)}
                {(captions.mode === 'manual' || captions.cues.length > 0) && <button disabled={busy || pending || captions.cues.length >= 1000 || (captions.cues.at(-1)?.end || 0) >= captionDuration}
                  onClick={() => { const start = captions.cues.at(-1)?.end || 0;
                    editCaptions(episodeIndex, { cues: [...captions.cues, { start, end: Math.min(captionDuration, start + 2), text: '' }] }); }}>Add timed caption</button>}
                {sequence && captions.cues.length > 0 && !unsaved && <div className="sequence-caption-downloads">
                  <a href={`/api/sequences/${sequence.id}/episodes/${episodeIndex}/captions.srt`} download>Download SRT</a>
                  <a href={`/api/sequences/${sequence.id}/episodes/${episodeIndex}/captions.vtt`} download>Download VTT</a>
                </div>}
                {locked && completeMedia && <button disabled={busy || pending || narrationEdits.length > 0}
                  onClick={() => void perform(() => reassembleCaptions(episodeIndex))}>Apply captions to completed video</button>}
              </details>
              {episode.shots.map((shot, shotIndex) => {
                const model = models.find((item) => item.id === shot.request.model_id),
                  state = shot.job_status || shot.status;
                const renderLocked = locked || !!shot.existing_video_asset_id;
                const narration = shot.narration || emptyNarration();
                const sourceVideo = assets.get(shot.request.source_asset_id || '')?.kind === 'video';
                return (
                  <article key={shot.id} className="sequence-shot">
                    <div className="sequence-shot-number">
                      <span>{String(shotIndex + 1).padStart(2, '0')}</span>
                      <button
                        aria-label={`Move shot ${shotIndex + 1} earlier`}
                        disabled={locked || shotIndex === 0}
                        onClick={() => moveShot(episodeIndex, shotIndex, -1)}
                      >
                        ↑
                      </button>
                      <button
                        aria-label={`Move shot ${shotIndex + 1} later`}
                        disabled={locked || shotIndex === episode.shots.length - 1}
                        onClick={() => moveShot(episodeIndex, shotIndex, 1)}
                      >
                        ↓
                      </button>
                    </div>
                    <div className="sequence-shot-form">
                      {shot.existing_video_asset_id && <p>Uses the complete existing video at its native size and frame rate. No video generation is submitted; only selected audio, captions and final assembly run.</p>}
                      <label>
                        Shot description
                        <textarea
                          rows={3}
                          maxLength={16000}
                          value={shot.request.prompt}
                          disabled={renderLocked}
                          placeholder="Write a concrete shot. This will be rendered once, not repeated to fill time."
                          onChange={(event) =>
                            editShot(episodeIndex, shotIndex, {
                              request: { ...shot.request, prompt: event.target.value },
                            })
                          }
                        />
                      </label>
                      <div className="sequence-row">
                        <label>
                          Model
                          <select
                            value={shot.request.model_id}
                            disabled={renderLocked}
                            onChange={(event) =>
                              changeModel(episodeIndex, shotIndex, event.target.value)
                            }
                          >
                            {!model && <option value={shot.request.model_id} disabled>
                              {catalog.models.find((item) => item.id === shot.request.model_id)?.name || shot.request.model_id} · saved operation
                            </option>}
                            {models.map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Compute
                          <select
                            value={shot.request.provider}
                            disabled={renderLocked}
                            onChange={(event) =>
                              editShot(episodeIndex, shotIndex, {
                                request: { ...shot.request, provider: event.target.value },
                              })
                            }
                          >
                            {!catalog.providers.some((item) => item.id === shot.request.provider) && <option value={shot.request.provider} disabled>{shot.request.provider} · saved connection disabled</option>}
                            {catalog.providers.filter((item) => ['local', 'comfy-cloud'].includes(item.id)).map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Frames
                          <input
                            type="number"
                            min={Number(model?.frame_multiple || 8) + 1}
                            max={Number(model?.max_frames || 241)}
                            step={Number(model?.frame_multiple || 8)}
                            value={shot.request.frames}
                            disabled={renderLocked}
                            onChange={(event) =>
                              editShot(episodeIndex, shotIndex, {
                                request: { ...shot.request, frames: Number(event.target.value) },
                              })
                            }
                          />
                          <small>
                            {seconds(shot.request.frames / shot.request.fps)} at {shot.request.fps}
                            fps
                          </small>
                        </label>
                      </div>
                      <div className="sequence-shot-source">
                        <label>
                          <input
                            type="checkbox"
                            disabled={renderLocked || shotIndex === 0}
                            checked={shot.source_from_previous}
                            onChange={(event) =>
                              editShot(episodeIndex, shotIndex, {
                                source_from_previous: event.target.checked,
                                request: {
                                  ...shot.request,
                                  source_asset_id: undefined,
                                  effect_id: event.target.checked
                                    ? 'image-to-video'
                                    : 'text-to-video',
                                },
                              })
                            }
                          />
                          Continue from previous shot’s final frame
                        </label>
                        <button
                          disabled={renderLocked || shot.source_from_previous}
                          onClick={() =>
                            setPicker({ episode: episodeIndex, shot: shotIndex, kind: 'image' })
                          }
                        >
                          {shot.request.source_asset_id
                            ? sourceVideo ? 'Source video' : 'Change opening image'
                            : 'Choose opening image'}
                        </button>
                        {shot.request.source_asset_id && (
                          <button
                            disabled={renderLocked}
                            onClick={() =>
                              editShot(episodeIndex, shotIndex, {
                                request: {
                                  ...shot.request,
                                  source_asset_id: undefined,
                                  effect_id: 'text-to-video',
                                },
                              })
                            }
                          >
                            Remove {sourceVideo ? 'video' : 'image'}
                          </button>
                        )}
                      </div>
                      {shot.request.source_asset_id && (sourceVideo ? (
                        <video className="sequence-input-preview" controls preload="metadata"
                          src={`/api/assets/${shot.request.source_asset_id}/file`} aria-label={`Source video for shot ${shotIndex + 1}`} />
                      ) : (
                        <img
                          className="sequence-input-preview"
                          src={`/api/assets/${shot.request.source_asset_id}/file`}
                          alt={`Opening image for shot ${shotIndex + 1}`}
                        />
                      ))}
                      <label className="sequence-audio-choice">
                        <input
                          type="checkbox"
                          checked={shot.request.generate_audio}
                          disabled={renderLocked || !model?.supports_audio}
                          onChange={(event) =>
                            editShot(episodeIndex, shotIndex, {
                              request: { ...shot.request, generate_audio: event.target.checked },
                            })
                          }
                        />
                        Generate native shot audio when supported
                      </label>
                      <details className="sequence-narration" open={!!narration.text || !!shot.narration_error}>
                        <summary>Narration for this shot</summary>
                        <label>Voiceover script<textarea rows={2} maxLength={1200} value={narration.text}
                          disabled={busy || pending || !!episode.audio_asset_id}
                          placeholder="Leave empty for no narration. Speech is generated when this sequence renders."
                          onChange={(event) => editNarration(episodeIndex, shotIndex, { text: event.target.value })} /></label>
                        {episode.audio_asset_id && <small>Remove the foreground soundtrack before adding narration. Background music can be mixed separately.</small>}
                        {!!narration.text && <div className="sequence-row">
                          <label>Voice<select value={narration.voice} disabled={busy || pending}
                            onChange={(event) => editNarration(episodeIndex, shotIndex, { voice: event.target.value,
                              language: event.target.value.startsWith('US_') || event.target.value.startsWith('UK_') ? 'English' : 'Chinese' })}>
                            <option value="US_Emma">Emma · US English</option><option value="UK_George">George · UK English</option>
                            <option value="灵小柔">Ling Xiaorou · Mandarin</option><option value="灵楷">Ling Kai · Mandarin</option>
                          </select></label>
                          <label>Speech speed<input type="number" min={.75} max={1.5} step={.05} value={narration.speed} disabled={busy || pending}
                            onChange={(event) => editNarration(episodeIndex, shotIndex, { speed: Number(event.target.value) })} /></label>
                          <label>Start within shot (seconds)<input type="number" min={0} step={.1} value={narration.start} disabled={busy || pending}
                            onChange={(event) => editNarration(episodeIndex, shotIndex, { start: Number(event.target.value) })} /></label>
                        </div>}
                        {!!narration.text && <small>Speech must fit the shot. If it runs too long, shorten the script and resume; completed video shots are retained.</small>}
                        {shot.narration_status && <p>{shot.narration_status}{shot.narration_actual_duration != null ? ` · ${seconds(shot.narration_actual_duration)}` : ''}</p>}
                        {shot.narration_output && <audio controls src={mediaUrl(shot.narration_output)} />}
                        {shot.narration_job_id && <a href={`/api/jobs/${shot.narration_job_id}/workflow`} download>Speech workflow</a>}
                        {shot.narration_error && <p role="alert">{shot.narration_error}</p>}
                      </details>
                      {state && (
                        <p className="sequence-shot-state">
                          {state}
                          {shot.stage ? ` · ${shot.stage}` : ''}
                          {shot.job_id && (
                            <>
                              {' '}
                              ·{' '}
                              <a href={`/api/jobs/${shot.job_id}/workflow`} download>
                                Workflow
                              </a>{' '}
                              ·{' '}
                              <a
                                href={`/api/jobs/${shot.job_id}/bundle?include_media=true`}
                                download
                              >
                                Project
                              </a>
                            </>
                          )}
                        </p>
                      )}
                      {shot.error && <p role="alert">{shot.error}</p>}
                    </div>
                    <button
                      className="sequence-remove"
                      aria-label={`Remove shot ${shotIndex + 1}`}
                      disabled={locked || episode.shots.length === 1}
                      onClick={() =>
                        editEpisode(episodeIndex, {
                          shots: episode.shots.filter((_, index) => index !== shotIndex),
                        })
                      }
                    >
                      <Icon name="close" size={15} />
                    </button>
                  </article>
                );
              })}
              {!locked && !props.initialExistingVideo && (
                <button
                  className="sequence-add"
                  disabled={episode.shots.length >= 64}
                  onClick={() => {
                    const shot = freshShot();
                    if (first)
                      shot.request = {
                        ...shot.request,
                        width: first.width,
                        height: first.height,
                        fps: first.fps,
                      };
                    editEpisode(episodeIndex, { shots: [...episode.shots, shot] });
                  }}
                >
                  + Add a new, blank shot
                </button>
              )}
              {episode.output && (
                <div className="sequence-output">
                  <video controls playsInline src={mediaUrl(episode.output)} />
                  <a href={mediaUrl(episode.output)} download={episode.output.name}>
                    <Icon name="download" size={16} />
                    Download assembled episode
                  </a>
                </div>
              )}
            </section>
          );
        })}
        <p className="sequence-policy">
          The target is editorial. Frame-aligned shots determine actual duration; no looping,
          stretching or hidden trimming fills the difference. Assembly uses only completed shots in
          order. A failed shot leaves the sequence incomplete; resume retains completed shots. No
          music or narration is added unless selected above.
        </p>
        {pollError && (
          <p className="sequence-error" role="status">
            Status refresh interrupted; the saved job may still be running. Retrying status only.{' '}
            {pollError}
          </p>
        )}
        {error && (
          <p className="sequence-error" role="alert">
            {error}
          </p>
        )}
      </div>
      <footer>
        <span>
          {unsaved ? 'Unsaved edits' : sequence ? 'Saved plan' : 'Manual plan'} · up to 4
          episodes / 300s each
        </span>
        <div>
          {closeBlocked && <button onClick={onClose}>Discard unsaved edits and close</button>}
          {locked && (narrationEdits.length > 0 || captionEdits.length > 0 || audioEdits.length > 0) && <button disabled={busy || pending}
            onClick={() => void perform(saveCorrections)}>{captionEdits.length ? 'Save audio and caption corrections' : 'Save audio changes'}</button>}
          {!locked && (
            <>
              <button disabled={busy} onClick={() => void perform(saveDraft)}>
                Save draft
              </button>
              <button
                className="sequence-primary"
                disabled={busy || !total}
                onClick={() => void perform(start)}
              >
                {busy ? 'Working…' : `Render ${total} reviewed shots`}
              </button>
            </>
          )}
          {active(sequence?.status) && (
            <button disabled={busy} onClick={() => void perform(() => sequenceAction('cancel'))}>
              Cancel sequence
            </button>
          )}
          {(sequence?.status === 'failed' || sequence?.status === 'cancelled') && (
            <button
              className="sequence-primary"
              disabled={busy || unsaved}
              onClick={() =>
                void perform(() =>
                  sequenceAction(sequence.status === 'failed' ? 'retry' : 'resume'),
                )
              }
            >
              Resume incomplete work
            </button>
          )}
        </div>
      </footer>
      {picker && (
        <AssetPicker
          title={
            picker.kind === 'audio'
              ? picker.background ? 'Choose background audio' : 'Choose an explicit episode soundtrack'
              : 'Choose a shot opening image'
          }
          kind={picker.kind}
          assets={assets.assets}
          onAdded={assets.add}
          onClose={() => setPicker(null)}
          onSelect={(selected) => {
            if (picker.kind === 'audio') {
              if (picker.background) editAudio(picker.episode, { background_audio_asset_id: selected.id, background_audio_start: 0 });
              else editAudio(picker.episode, {
                  audio_asset_id: selected.id,
                  audio_start: 0,
                  keep_shot_audio: false,
                });
            }
            else if (picker.shot != null) {
              const shot = episodes[picker.episode].shots[picker.shot];
              editShot(picker.episode, picker.shot, {
                source_from_previous: false,
                request: {
                  ...shot.request,
                  source_asset_id: selected.id,
                  effect_id: 'image-to-video',
                },
              });
            }
          }}
        />
      )}
    </dialog>
  );
}
