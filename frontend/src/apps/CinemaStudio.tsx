import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, KeyboardEvent as ReactKeyboardEvent } from 'react';
import { api, mediaUrl, post, upload } from '../api';
import { Icon } from '../Icon';
import type { Asset, Catalog, Job, Settings } from '../types';
import { AppSwitcher } from './AppSwitcher';
import { useAppDocument } from './useAppDocument';
import { durationFrames, renderRequest, renderSize, resolveProvider } from './renderRequest';
import { loadProjectSnapshot, showProjectDraft } from './projectReuse';
import { AnchoredPopover } from '../Popovers';
import './cinema-studio.css';
import cinemaReferenceFallback from './cinema-reference.json';
import { LightingEditor, PaletteEditor, defaultLights } from './CinemaCreativeEditors';
import type { CinemaLight, ColorPalette, LightingPreset } from './CinemaCreativeEditors';
import { compileCinemaPrompt, compileReferenceSheetLegend, describeCameraMovement } from './cinemaPrompt';
import type { CinemaReferenceRole } from './cinemaPrompt';

type CinemaReferenceEntry = {
  asset_id: string;
  name: string;
  role: CinemaReferenceRole;
};
type CinemaState = {
  prompt: string;
  mode: 'image' | 'video';
  model_id: string;
  provider: string;
  aspect_ratio: string;
  quality: number;
  duration: number;
  variants: number;
  generate_audio: boolean;
  /** Legacy per-shot list; kept in sync so old drafts, reuse and sequences keep working. */
  reference_asset_ids: string[];
  /** Project reference library (up to 50 images). */
  references: CinemaReferenceEntry[];
  /** Ordered per-shot selection sent as source/reference_asset_ids. */
  active_reference_ids: string[];
  attachment_asset_ids: string[];
  film: { genre: string; era: string; tempo: string };
  camera: { body: string; lens: string; aperture: string; movements: string[] };
  palette: string;
  lighting: string;
  palette_colors: string[];
  custom_lights: CinemaLight[];
  palette_presets: ColorPalette[];
  lighting_presets: LightingPreset[];
  pinned_presets: string[];
};
type Preview = { title: string; poster?: string; video?: string; colors?: string[] };
type CinemaReference = Record<string, Preview[]>;
const LIBRARY_LIMIT = 50;
const REFERENCE_EFFECT_ID = 'reference-to-video';
const initial: CinemaState = {
  prompt: '',
  mode: 'video',
  model_id: 'ltx-2.5',
  provider: '',
  aspect_ratio: '16:9',
  quality: 1024,
  duration: 5,
  variants: 1,
  generate_audio: true,
  reference_asset_ids: [],
  references: [],
  active_reference_ids: [],
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
};
const referenceRoles: CinemaReferenceRole[] = ['character', 'location', 'prop'];
const uniqueIds = (values: string[]) => [...new Set(values.filter(Boolean))];
const referenceLibrary = (state: CinemaState): CinemaReferenceEntry[] =>
  Array.isArray(state.references) ? state.references : [];
const activeReferenceIds = (state: CinemaState): string[] =>
  uniqueIds(
    Array.isArray(state.active_reference_ids)
      ? state.active_reference_ids
      : Array.isArray(state.reference_asset_ids)
        ? state.reference_asset_ids
        : [],
  );
const assetIds = (state: CinemaState) => [
  ...new Set([
    ...referenceLibrary(state).map((entry) => entry.asset_id),
    ...activeReferenceIds(state),
    ...(Array.isArray(state.reference_asset_ids) ? state.reference_asset_ids : []),
    ...(state.attachment_asset_ids || []),
    ...(state.palette_presets || [])
      .map((preset) => preset.image_asset_id)
      .filter((id): id is string => !!id),
  ]),
];
const cinemaEffectId = (mode: 'image' | 'video', count: number, referenceAvailable: boolean) =>
  mode === 'image'
    ? count
      ? 'edit-image'
      : 'create-image'
    : count === 0
      ? 'text-to-video'
      : referenceAvailable || count > 1
        ? REFERENCE_EFFECT_ID
        : 'image-to-video';
function referenceLimitFromCatalog(
  effect: Catalog['effects'][number] | undefined,
  model: Catalog['models'][number] | undefined,
  fallback: number,
) {
  const effectRecord = (effect || {}) as Record<string, unknown>;
  const modelRecord = (model || {}) as Record<string, unknown>;
  let maximum: number | undefined;
  for (const value of [
    effectRecord.max_references,
    effectRecord.max_reference_images,
    effectRecord.reference_limit,
    effectRecord.reference_image_limit,
  ]) {
    const limit = Number(value);
    if (Number.isFinite(limit) && limit > 0) {
      maximum = limit;
      break;
    }
  }
  // LTX 2.5 declares its ordered-reference ceiling per task rather than in
  // the flat max_references field (which is 1 for its other reference tasks).
  const task = typeof effectRecord.task === 'string' ? effectRecord.task : '';
  const taskLimits = modelRecord.reference_limits_by_task as
    | Record<string, unknown>
    | undefined;
  const taskLimit = Number(taskLimits?.[task]);
  if (Number.isFinite(taskLimit) && taskLimit > 0)
    maximum = maximum === undefined ? taskLimit : Math.min(maximum, taskLimit);
  if (maximum !== undefined) return Math.max(1, maximum);
  const modelLimit = Number(modelRecord.max_references);
  // An older model entry still says max_references: 1. Only trust a model
  // value that actually declares multi-reference support for this effect.
  if (Number.isFinite(modelLimit) && modelLimit > 1) return modelLimit;
  return fallback;
}
function normalizeCinemaState(raw: Partial<CinemaState> | undefined): CinemaState {
  const value = (raw || {}) as Partial<CinemaState>;
  const legacy = Array.isArray(value.reference_asset_ids)
    ? uniqueIds(value.reference_asset_ids.filter((id): id is string => typeof id === 'string'))
    : [];
  const active = Array.isArray(value.active_reference_ids)
    ? uniqueIds(
        value.active_reference_ids.filter((id): id is string => typeof id === 'string'),
      )
    : legacy;
  const entries = (Array.isArray(value.references) ? value.references : [])
    .filter(
      (entry): entry is CinemaReferenceEntry =>
        !!entry && typeof entry.asset_id === 'string' && typeof entry.name === 'string',
    )
    .map((entry) => ({
      asset_id: entry.asset_id,
      name: entry.name,
      role: referenceRoles.includes(entry.role) ? entry.role : ('prop' as CinemaReferenceRole),
    }));
  const known = new Set(entries.map((entry) => entry.asset_id));
  for (const id of active)
    if (!known.has(id)) {
      entries.push({ asset_id: id, name: '', role: 'prop' });
      known.add(id);
    }
  return {
    ...initial,
    ...value,
    film: { ...initial.film, ...(value.film || {}) },
    camera: {
      ...initial.camera,
      ...(value.camera || {}),
      movements: Array.isArray(value.camera?.movements) ? value.camera.movements : [],
    },
    references: entries,
    active_reference_ids: active,
    reference_asset_ids: active,
    attachment_asset_ids: Array.isArray(value.attachment_asset_ids)
      ? value.attachment_asset_ids
      : [],
    palette_colors: Array.isArray(value.palette_colors) ? value.palette_colors : [],
    custom_lights: Array.isArray(value.custom_lights) ? value.custom_lights : [],
    palette_presets: Array.isArray(value.palette_presets) ? value.palette_presets : [],
    lighting_presets: Array.isArray(value.lighting_presets) ? value.lighting_presets : [],
    pinned_presets: Array.isArray(value.pinned_presets) ? value.pinned_presets : [],
  };
}
const filmOptions = {
  genre: ['Drama', 'Noir', 'Comedy', 'Horror', 'Action', 'General', 'Epic'],
  era: ['1960s', '1980s', '1990s', '2000s', '2020s', 'Auto'],
  tempo: ['Dynamic', 'Calm', 'Single shot', 'Auto', 'Chaotic'],
};
const cameraOptions = {
  body: ['Auto', 'Modern', '35mm Film', '8mm Film', 'DV Camcorder'],
  lens: [
    'Auto',
    'Clean Sharp',
    'Anamorphic',
    'Vintage Anamorphic',
    'Warm Vintage',
    'Halation Vintage',
  ],
  aperture: ['Auto', 'f/1.4 Wide Open', 'f/4 Moderate', 'f/11 Deep Focus'],
};
function PreviewMedia({ item }: { item?: Preview }) {
  if (!item) return null;
  return item.video ? (
    <video
      src={item.video}
      poster={item.poster}
      muted
      playsInline
      loop
      preload="none"
      onMouseEnter={(event) => void event.currentTarget.play().catch(() => {})}
      onMouseLeave={(event) => event.currentTarget.pause()}
    />
  ) : item.poster ? (
    <img src={item.poster} alt={item.title} />
  ) : null;
}
export function CinemaStudio({
  catalog,
  settings,
  onSettings,
}: {
  catalog: Catalog;
  settings: Settings;
  onSettings: () => void;
}) {
  const session = useAppDocument('cinema-studio', initial, assetIds);
  const { state, update } = session;
  const [mention, setMention] = useState<{ start: number; query: string } | null>(null);
  const [mentionIndex, setMentionIndex] = useState(0);
  const [view, setView] = useState('Home');
  const [showLearn, setShowLearn] = useState(true);
  const [panel, setPanel] = useState<string | null>(null);
  const [filmTab, setFilmTab] = useState<keyof typeof filmOptions>('genre');
  const [cameraTab, setCameraTab] = useState<'setup' | 'movement'>('setup');
  const [reference, setReference] = useState<CinemaReference>(cinemaReferenceFallback);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [presetSearch, setPresetSearch] = useState('');
  const [presetSort, setPresetSort] = useState(false);
  const [presetActions, setPresetActions] = useState<string | null>(null);
  const [editorReset, setEditorReset] = useState(0);
  const [editPalette, setEditPalette] = useState<ColorPalette | undefined>();
  const [editLights, setEditLights] = useState<CinemaLight[]>(defaultLights);
  const [movementSearch, setMovementSearch] = useState('');
  const [movementSort, setMovementSort] = useState(false);
  const [menu, setMenu] = useState<{ name: string; anchor: HTMLElement } | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [selectedJobSnapshot, setSelectedJob] = useState<Job | null>(null);
  const selectedJob =
    session.jobs.find((job) => job.id === selectedJobSnapshot?.id) || selectedJobSnapshot;
  const dialog = useRef<HTMLDialogElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const promptInput = useRef<HTMLTextAreaElement>(null);
  const mentionMenu = useRef<HTMLDivElement>(null);
  const migratedDocument = useRef('');
  const activeIds = activeReferenceIds(state);
  const library = [...referenceLibrary(state)];
  for (const id of activeIds)
    if (!library.some((entry) => entry.asset_id === id))
      library.push({ asset_id: id, name: '', role: 'prop' });
  const assetFor = (id: string) => assets.find((asset) => asset.id === id);
  const referenceName = (entry: CinemaReferenceEntry, index: number) =>
    entry.name.trim() || assetFor(entry.asset_id)?.name || `Reference ${index + 1}`;
  const activeReferences = activeIds.map((id, index) => {
    const entry = library.find((item) => item.asset_id === id);
    const asset = assetFor(id);
    return {
      id,
      asset,
      role: entry?.role || ('prop' as CinemaReferenceRole),
      name: entry ? referenceName(entry, index) : asset?.name || `Reference ${index + 1}`,
    };
  });
  const referenceEffect = catalog.effects.find((item) => item.id === REFERENCE_EFFECT_ID);
  const referenceEffectInCatalog =
    !!referenceEffect &&
    referenceEffect.model_ids.some((id) => catalog.models.some((item) => item.id === id));
  const referenceOperation = session.application?.operations.find(
    (item) => item.id === REFERENCE_EFFECT_ID,
  );
  const referenceOperationAvailable = !session.application || !!referenceOperation?.available;
  const referenceEffectAvailable = referenceEffectInCatalog && referenceOperationAvailable;
  const effectId = cinemaEffectId(state.mode, activeIds.length, referenceEffectAvailable);
  const effect = catalog.effects.find((item) => item.id === effectId);
  const models = catalog.models.filter((item) => effect?.model_ids.includes(item.id));
  const model =
    models.find((item) => item.id === state.model_id) ||
    (!state.model_id
      ? models.find((item) => item.id === (state.mode === 'image' ? 'flux3-klein' : 'ltx-2.5')) || models[0]
      : undefined);
  const referenceModel =
    catalog.models.find(
      (item) => item.id === state.model_id && referenceEffect?.model_ids.includes(item.id),
    ) || catalog.models.find((item) => referenceEffect?.model_ids.includes(item.id));
  const imageReferenceLimit = Number(model?.max_references || 4);
  const referenceLimit = referenceLimitFromCatalog(referenceEffect, referenceModel, 9);
  const provider = resolveProvider(state.provider, settings.default_provider);
  const maxReferences =
    state.mode === 'image' ? imageReferenceLimit : referenceEffectAvailable ? referenceLimit : 1;
  const effectLabel =
    state.mode === 'image'
      ? activeIds.length
        ? 'Edit image'
        : 'Create image'
      : activeIds.length === 0
        ? 'Text to video'
        : referenceEffectAvailable
          ? 'Reference to video'
          : activeIds.length === 1
            ? 'Image to video'
            : 'Reference to video (unavailable)';
  const referenceSummary =
    state.mode === 'image'
      ? `${imageReferenceLimit} active image${imageReferenceLimit === 1 ? '' : 's'} allowed by ${model?.name || 'the selected image model'}. The first is the edit source; any remaining images are references.`
      : referenceEffectAvailable
        ? `1–${referenceLimit} active references use reference-to-video${referenceModel ? ` (${referenceModel.name})` : ''}; they are sent in this order and composed into a reference sheet. No reference is used as the opening frame.`
        : referenceEffectInCatalog && !referenceOperationAvailable
          ? 'The catalog lists reference-to-video, but this app build does not expose an available render operation. Only image-to-video (1 active reference) can be submitted.'
          : 'This catalog offers only image-to-video for video: 1 active reference. reference-to-video is unavailable on this backend, so extra references cannot be submitted.';
  const referenceBlockReason =
    state.mode === 'video' && activeIds.length >= 2 && !referenceEffectInCatalog
      ? 'Reference-to-video is not offered by this catalog. Remove references to use image-to-video, or update the backend.'
      : state.mode === 'video' && activeIds.length >= 2 && !referenceOperationAvailable
        ? 'Reference-to-video is not available in this app build. Remove references to use image-to-video, or update the backend.'
        : state.mode === 'video' && activeIds.length >= 1 && referenceEffectAvailable && !!referenceEffect && !model
          ? `Reference-to-video requires ${referenceEffect.model_ids.join(' or ')}. Choose a supported model in the model menu.`
          : activeIds.length > maxReferences
            ? `${effectLabel} accepts ${maxReferences} active reference${maxReferences === 1 ? '' : 's'}. Remove ${activeIds.length - maxReferences}.`
            : '';
  const activeNote =
    referenceBlockReason || `${effectLabel} · ${activeIds.length}/${maxReferences} active reference${maxReferences === 1 ? '' : 's'}`;
  const currentFilm = filmOptions[filmTab];
  const selectedFilm = state.film[filmTab];
  const filmIndex = Math.max(0, currentFilm.indexOf(selectedFilm));
  const mentionMatches = mention
    ? library.filter((entry, index) =>
        referenceName(entry, index).toLowerCase().includes(mention.query.toLowerCase()),
      )
    : [];
  useEffect(() => {
    fetch('/reference-media/components.json')
      .then((response) => (response.ok ? response.json() : null))
      .then((value) => setReference(value?.['cinema-studio'] || cinemaReferenceFallback))
      .catch(() => {});
    api<{ items: Asset[] }>('/assets?limit=100')
      .then((value) => setAssets(value.items))
      .catch((reason) => setError(reason.message));
  }, []);
  const libraryKey = library.map((entry) => entry.asset_id).join(',');
  useEffect(() => {
    for (const id of uniqueIds([...activeIds, ...library.map((entry) => entry.asset_id)]))
      if (!assets.some((asset) => asset.id === id))
        void api<Asset>(`/assets/${id}`)
          .then((asset) =>
            setAssets((items) =>
              items.some((item) => item.id === id) ? items : [...items, asset],
            ),
          )
          .catch(() => {});
  }, [activeIds.join(','), libraryKey, assets.length]);
  useEffect(() => {
    const doc = session.document;
    if (!session.ready || !doc || migratedDocument.current === doc.id) return;
    migratedDocument.current = doc.id;
    const raw = doc.state as Partial<CinemaState>;
    if (
      Array.isArray(raw.references) &&
      Array.isArray(raw.active_reference_ids) &&
      Array.isArray(raw.reference_asset_ids)
    )
      return;
    const normalized = normalizeCinemaState(raw);
    update({
      references: normalized.references,
      active_reference_ids: normalized.active_reference_ids,
      reference_asset_ids: normalized.reference_asset_ids,
    });
  }, [session.ready, session.document?.id]);
  useEffect(() => {
    if (!mention) return;
    const outside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (mentionMenu.current?.contains(target) || promptInput.current?.contains(target)) return;
      setMention(null);
    };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [mention]);
  useEffect(() => {
    const element = dialog.current;
    if (panel || preview || selectedJob) element?.showModal();
    return () => element?.close();
  }, [panel, preview, selectedJob?.id]);
  const close = () => {
    setPanel(null);
    setPreview(null);
    setSelectedJob(null);
  };
  const open = (name: string) => {
    setMenu(null);
    setPanel(name);
  };
  const popover = (name: string, anchor: HTMLElement) =>
    setMenu(menu?.name === name ? null : { name, anchor });
  const chooseFilm = (name: string) => update({ film: { ...state.film, [filmTab]: name } });
  const chooseCamera = (key: keyof typeof cameraOptions, name: string) =>
    update({ camera: { ...state.camera, [key]: name } });
  function changeMode(mode: 'image' | 'video') {
    const preferred = mode === 'image' ? 'flux3-klein' : 'ltx-2.5';
    const fallback = mode === 'image' ? 'flux-klein-4b' : 'ltx-2.3';
    update({ mode, model_id: catalog.models.some((item) => item.id === preferred) ? preferred : fallback });
  }
  function commitReferences(nextLibrary: CinemaReferenceEntry[], nextActive: string[]) {
    const ids = new Set(nextLibrary.map((entry) => entry.asset_id));
    const active = uniqueIds(nextActive).filter((id) => ids.has(id));
    update({
      references: nextLibrary,
      active_reference_ids: active,
      reference_asset_ids: active,
    });
  }
  function referenceLimitError() {
    if (referenceBlockReason) return referenceBlockReason;
    return `${effectLabel} accepts ${maxReferences} active reference${maxReferences === 1 ? '' : 's'}${model ? ` on ${model.name}` : ''}. Remove one first.`;
  }
  function addActiveReference(id: string) {
    if (activeIds.includes(id)) return true;
    if (activeIds.length >= maxReferences) {
      setError(referenceLimitError());
      return false;
    }
    commitReferences(library, [...activeIds, id]);
    setError('');
    return true;
  }
  function toggleActiveReference(id: string) {
    if (activeIds.includes(id)) commitReferences(library, activeIds.filter((item) => item !== id));
    else addActiveReference(id);
  }
  function addReferenceAsset(asset: Asset, activate = true) {
    if (library.some((entry) => entry.asset_id === asset.id)) {
      if (activate) toggleActiveReference(asset.id);
      return;
    }
    if (library.length >= LIBRARY_LIMIT) {
      setError(`The project reference library is full (${LIBRARY_LIMIT}). Remove an image first.`);
      return;
    }
    const nextLibrary = [...library, { asset_id: asset.id, name: asset.name || '', role: 'prop' as CinemaReferenceRole }];
    commitReferences(
      nextLibrary,
      activate && activeIds.length < maxReferences ? [...activeIds, asset.id] : activeIds,
    );
  }
  function removeReferenceFromLibrary(id: string) {
    commitReferences(
      library.filter((entry) => entry.asset_id !== id),
      activeIds.filter((item) => item !== id),
    );
  }
  function updateReferenceEntry(
    id: string,
    changes: Partial<Pick<CinemaReferenceEntry, 'name' | 'role'>>,
  ) {
    commitReferences(
      library.map((entry) => (entry.asset_id === id ? { ...entry, ...changes } : entry)),
      activeIds,
    );
  }
  function clearActiveReferences() {
    commitReferences(library, []);
  }
  async function uploadReferences(files: FileList | null) {
    if (!files?.length) return;
    if (files.length + library.length > LIBRARY_LIMIT) {
      setError(
        `Choose up to ${LIBRARY_LIMIT - library.length} more image${LIBRARY_LIMIT - library.length === 1 ? '' : 's'}; the project library holds ${LIBRARY_LIMIT}.`,
      );
      return;
    }
    setUploading(true);
    try {
      const added: Asset[] = [];
      for (const file of Array.from(files)) added.push(await upload(file));
      setAssets((items) => [...added, ...items]);
      const entries: CinemaReferenceEntry[] = added.map((asset) => ({
        asset_id: asset.id,
        name: asset.name || '',
        role: 'prop',
      }));
      const openSlots = Math.max(0, maxReferences - activeIds.length);
      commitReferences(
        [...library, ...entries],
        [...activeIds, ...entries.slice(0, openSlots).map((entry) => entry.asset_id)],
      );
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  }
  function detectMention(value: string, caret: number) {
    const match = /(^|[\s(])@([^\s@\n]{0,40})$/.exec(value.slice(0, caret));
    if (!match) {
      setMention(null);
      return;
    }
    setMention({ start: caret - match[2].length - 1, query: match[2] });
    setMentionIndex(0);
  }
  function changePrompt(event: ChangeEvent<HTMLTextAreaElement>) {
    const value = event.target.value;
    update({ prompt: value });
    detectMention(value, event.target.selectionStart ?? value.length);
  }
  function insertMention(entry: CinemaReferenceEntry) {
    if (!mention) return;
    const index = library.findIndex((item) => item.asset_id === entry.asset_id);
    const name = referenceName(entry, index);
    const start = mention.start;
    const textarea = promptInput.current;
    const caret = textarea?.selectionStart ?? state.prompt.length;
    if (!activeIds.includes(entry.asset_id) && activeIds.length >= maxReferences) {
      setError(referenceLimitError());
      setMention(null);
      return;
    }
    const nextActive = activeIds.includes(entry.asset_id)
      ? activeIds
      : [...activeIds, entry.asset_id];
    update({
      prompt: `${state.prompt.slice(0, start)}@${name} ${state.prompt.slice(caret)}`,
      references: library,
      active_reference_ids: nextActive,
      reference_asset_ids: nextActive,
    });
    setMention(null);
    setError('');
    requestAnimationFrame(() => {
      const field = promptInput.current;
      if (!field) return;
      field.focus();
      const position = start + name.length + 2;
      field.setSelectionRange(position, position);
    });
  }
  function promptKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (!mention) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      setMention(null);
      return;
    }
    if (!mentionMatches.length) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setMentionIndex(
        (index) =>
          (index + (event.key === 'ArrowDown' ? 1 : -1) + mentionMatches.length) %
          mentionMatches.length,
      );
    } else if (event.key === 'Enter' || event.key === 'Tab') {
      event.preventDefault();
      insertMention(mentionMatches[Math.min(mentionIndex, mentionMatches.length - 1)]);
    }
  }
  async function generate() {
    if (submitting) return;
    setError('');
    setSubmitting(true);
    try {
      if (!state.prompt.trim()) throw new Error('Describe your shot before generating.');
      if (referenceBlockReason) throw new Error(referenceBlockReason);
      if (activeIds.length > maxReferences)
        throw new Error(`${effectLabel} accepts ${maxReferences} active references. Remove the extra references first.`);
      if (!effect) throw new Error('This generation operation is not in the catalog.');
      if (!model)
        throw new Error(
          `Choose a model that supports ${effect.name}. The saved model does not support this operation.`,
        );
      const operation = session.application?.operations.find((item) => item.id === effectId);
      if (!operation?.available)
        throw new Error(operation?.reason || 'This operation is not available.');
      const doc = await session.save();
      if (!doc) throw new Error('Save this project before generating.');
      const legend =
        state.mode === 'video' && activeReferences.length
          ? compileReferenceSheetLegend(
              activeReferences.map((reference) => ({
                name: reference.name,
                role: reference.role,
              })),
            )
          : '';
      const direction = compileCinemaPrompt(state);
      const usesReferenceVideo = state.mode === 'video' && effectId === REFERENCE_EFFECT_ID;
      const sourceAssetId =
        state.mode === 'image'
          ? activeIds[0]
          : !usesReferenceVideo && activeIds.length === 1
            ? activeIds[0]
            : undefined;
      const referenceAssetIds =
        state.mode === 'image'
          ? activeIds.slice(1)
          : usesReferenceVideo
            ? activeIds
            : undefined;
      const request = renderRequest(model, {
        effect_id: effectId,
        prompt: [state.prompt.trim(), legend, direction].filter(Boolean).join('\n\n'),
        provider,
        ...renderSize(model, state.aspect_ratio, state.quality),
        frames: state.mode === 'image' ? 1 : durationFrames(model, state.duration),
        fps: state.mode === 'image' ? 1 : Number(model.default_fps || 24),
        source_asset_id: sourceAssetId,
        reference_asset_ids: referenceAssetIds,
        batch_size: state.mode === 'image' ? state.variants : 1,
        generate_audio: state.mode === 'video' && state.generate_audio && !!model.supports_audio,
      });
      const group = crypto.randomUUID();
      const count = state.mode === 'image' ? 1 : state.variants;
      for (let index = 0; index < count; index++)
        await post<Job>(`/apps/cinema-studio/documents/${doc.id}/jobs`, {
          expected_revision: doc.revision,
          operation: effectId,
          request,
          group_id: group,
          step_id: `variant-${index + 1}`,
        });
      await session.refreshJobs();
      setView('My projects');
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  async function reuse(job: Job) {
    try {
      const snapshot = await loadProjectSnapshot<CinemaState>(job, 'cinema-studio', catalog, assetIds);
      if (!await session.newDocument(normalizeCinemaState(snapshot.state))) return;
      const draft = await session.save(true);
      if (!draft) throw new Error('The reused project could not be saved.');
      showProjectDraft(draft.id, '/generate');
      close();
      setView('Home');
    } catch (reason) {
      setError((reason as Error).message);
    }
  }
  const visibleJobs =
    view === 'My favorites'
      ? session.jobs.filter((job) => job.favorite)
      : view === 'My projects' && session.document
        ? session.jobs.filter((job) => job.app_context?.document_id === session.document?.id)
        : session.jobs;
  const presetKind = panel === 'Lighting' ? 'lighting' : 'palette';
  const customPresets: Preview[] =
    presetKind === 'lighting'
      ? (state.lighting_presets || []).map((item) => ({ title: item.name }))
      : (state.palette_presets || []).map((item) => ({
          title: item.name,
          colors: item.colors,
          poster: item.image_url,
        }));
  const presetItems = [...customPresets, ...(reference[presetKind] || [])]
    .filter((item) => item.title.toLowerCase().includes(presetSearch.toLowerCase()))
    .sort(
      (a, b) =>
        Number((state.pinned_presets || []).includes(b.title)) -
          Number((state.pinned_presets || []).includes(a.title)) ||
        (presetSort ? a.title.localeCompare(b.title) : 0),
    );
  function resetCreative() {
    if (panel === 'Film setup') update({ film: initial.film });
    else if (panel === 'Camera') update({ camera: initial.camera });
    else if (panel === 'Color palette') update({ palette: 'Auto', palette_colors: [] });
    else if (panel === 'Lighting') update({ lighting: 'Auto', custom_lights: [] });
    else {
      setEditPalette(undefined);
      setEditLights(defaultLights);
      setEditorReset((n) => n + 1);
    }
  }
  function selectPreset(item: Preview) {
    if (presetKind === 'palette')
      update({ palette: item.title, palette_colors: item.colors || [] });
    else
      update({
        lighting: item.title,
        custom_lights:
          state.lighting_presets?.find((entry) => entry.name === item.title)?.lights || [],
      });
  }
  function newCreativePreset() {
    setEditPalette(undefined);
    setEditLights(defaultLights);
    setEditorReset((n) => n + 1);
    setPanel(presetKind === 'lighting' ? 'New lighting preset' : 'New palette');
  }
  const movements = (reference['camera-movement'] || []).filter((item) =>
    item.title.toLowerCase().includes(movementSearch.toLowerCase()),
  );
  if (movementSort) movements.sort((a, b) => a.title.localeCompare(b.title));
  const icon = (index: number) => reference['control-icons']?.[index]?.poster;
  return (
    <main className="cinema-studio">
      <aside className="cin-rail">
        <AppSwitcher name="Cinema Studio" />
        <nav>
          {[
            ['Home', 'home'],
            ['My generations', 'spark'],
            ['My elements', 'grid'],
            ['My favorites', 'heart'],
            ['Community', 'globe'],
          ].map(([label, name]) => (
            <button
              key={label}
              className={view === label ? 'active' : ''}
              onClick={() => setView(label)}
            >
              <span>
                <Icon name={name} size={16} />
              </span>
              {label}
            </button>
          ))}
        </nav>
        <div className="cin-project-label">
          <span>Projects</span>
          <button aria-label="Search projects" onClick={() => open('Projects')}>
            <Icon name="search" size={14} />
          </button>
          <button aria-label="Project order" onClick={() => open('Projects')}>
            <Icon name="sliders" size={14} />
          </button>
        </div>
        <button
          className="cin-new-project"
          onClick={() => {
            void session.newDocument();
            setView('Home');
          }}
        >
          <Icon name="plus" size={16} />
          New project
        </button>
        <div className="cin-projects">
          {session.documents.map((doc) => (
            <button
              key={doc.id}
              onClick={() => {
                void session.openDocument(doc);
                setView('My projects');
              }}
            >
              {doc.title}
            </button>
          ))}
        </div>
        <div className="cin-rail-bottom">
          {showLearn && (
            <div className="cin-learn">
              <button aria-label="Dismiss learning card" onClick={() => setShowLearn(false)}>
                <Icon name="close" size={14} />
              </button>
              <small>Learn Cinema Studio</small>
              <p>
                Build a cinematic scene
                <br />
                one shot at a time
              </p>
              <a href="https://academy.higgsfield.ai/" target="_blank" rel="noreferrer">
                Learn now
                <Icon name="external" size={13} />
              </a>
            </div>
          )}
          <button className="cin-settings" onClick={onSettings}>
            <Icon name="settings" size={16} />
            Compute settings
            <Icon name="chevron" size={14} />
          </button>
        </div>
      </aside>
      <section className="cin-main">
        <div className="cin-top-actions">
          <button onClick={onSettings}>
            {catalog.providers.find((item) => item.id === provider)?.name || provider}
            <Icon name="chevron" size={12} />
          </button>
        </div>
        {view === 'Home' && (
          <>
            <div className="cin-hero-strip">
              {reference.hero?.map((item, index) => (
                <button
                  key={index}
                  className={`cin-hero-card cin-hero-${index}`}
                  onClick={() => setPreview(item)}
                >
                  <PreviewMedia item={item} />
                  <span>{item.title}</span>
                </button>
              ))}
            </div>
            <h1>BRING YOUR STORIES TO LIFE</h1>
          </>
        )}
        {view !== 'Home' && (
          <div className="cin-page-heading">
            <h1>{view}</h1>
            <p>
              {view === 'Community'
                ? 'Public reference projects. Your generations stay in this workspace.'
                : view === 'My elements'
                  ? 'Uploaded reference images in this workspace.'
                  : `${session.jobs.length} of ${session.jobTotal} generations loaded`}
            </p>
          </div>
        )}
        {view === 'My elements' && (
          <div className="cin-elements">
            {assets
              .filter((asset) => asset.kind === 'image')
              .map((asset) => (
                <button
                  key={asset.id}
                  onClick={() => {
                    addReferenceAsset(asset);
                    setView('Home');
                  }}
                >
                  <img src={asset.thumbnail_url || mediaUrl(asset)} alt={asset.name} />
                  <span>{asset.name}</span>
                </button>
              ))}
          </div>
        )}
        {view === 'Community' && (
          <div className="cin-community">
            {reference.hero?.map((item, index) => (
              <button key={index} onClick={() => setPreview(item)}>
                <PreviewMedia item={item} />
                <span>{item.title}</span>
              </button>
            ))}
          </div>
        )}
        {(view === 'My projects' || view === 'My favorites' || view === 'My generations') && (
          <div className="cin-job-grid">
            {visibleJobs.map((job) => {
              const output = job.outputs.find((asset) => asset.role === 'result') || job.outputs[0];
              return (
                <button key={job.id} onClick={() => setSelectedJob(job)} className="cin-job">
                  <div>
                    {output?.kind === 'video' ? (
                      <video
                        src={mediaUrl(output)}
                        poster={output.thumbnail_url || undefined}
                        muted
                        preload="metadata"
                      />
                    ) : output?.kind === 'image' ? (
                      <img src={mediaUrl(output)} alt="Generated result" />
                    ) : (
                      <Icon name="film" size={32} />
                    )}
                  </div>
                  <strong>{job.request.prompt}</strong>
                  <span>
                    {job.status === 'running'
                      ? `Rendering · ${Math.round(job.progress * 100)}%`
                      : job.status}
                  </span>
                </button>
              );
            })}
            {!visibleJobs.length && <p>No generations here yet.</p>}
            {session.jobs.length < session.jobTotal && (
              <button onClick={session.loadMoreJobs}>Load more</button>
            )}
          </div>
        )}
        <div className={`cin-compose-area ${view !== 'Home' ? 'cin-compose-bottom' : ''}`}>
          <div className="cin-mode-tabs">
            <button
              className={state.mode === 'image' ? 'active' : ''}
              onClick={() => changeMode('image')}
            >
              <Icon name="image" size={22} />
              <span>Image</span>
            </button>
            <button
              className={state.mode === 'video' ? 'active' : ''}
              onClick={() => changeMode('video')}
            >
              <Icon name="video" size={22} />
              <span>Video</span>
            </button>
          </div>
          <div className="cin-composer-wrap">
            <div className="cin-creative-controls">
              <button
                className="cin-reference-control"
                onClick={() => open('References')}
                title={`${library.length} of ${LIBRARY_LIMIT} images in the project library · ${activeIds.length}/${maxReferences} active for this shot`}
              >
                <Icon name="image" size={20} />
                <span>
                  References
                  <small>
                    {library.length}/{LIBRARY_LIMIT}
                  </small>
                </span>
              </button>
              {[
                ['Film setup', 0, state.film.genre === 'General' ? 'Auto' : state.film.genre],
                ['Camera', 1, state.camera.body],
                ['Color palette', 2, state.palette],
                ['Lighting', 3, state.lighting],
              ].map(([label, index, value]) => (
                <button key={label} onClick={() => open(String(label))}>
                  {icon(Number(index)) && <img src={icon(Number(index))} alt="" />}
                  <span>
                    {label}
                    <small>{value}</small>
                  </span>
                </button>
              ))}
            </div>
            {(activeIds.length > 0 || referenceBlockReason) && (
              <p className={`cin-reference-note ${referenceBlockReason ? 'warning' : ''}`}>
                {activeNote}
              </p>
            )}
            <div className="cin-prompt-box">
              <div className="cin-prompt-content">
                {activeReferences.length > 0 && (
                  <div className="cin-selected-refs">
                    {activeReferences.map((reference, index) => (
                      <button
                        key={reference.id}
                        title={`${reference.name} — ${reference.role}. Position ${index + 1} in the reference sheet. Remove from this shot.`}
                        aria-label={`Remove ${reference.name} from this shot`}
                        onClick={() => toggleActiveReference(reference.id)}
                      >
                        <b className="cin-ref-order">{index + 1}</b>
                        {reference.asset ? (
                          <img
                            src={reference.asset.thumbnail_url || mediaUrl(reference.asset)}
                            alt={reference.name}
                          />
                        ) : (
                          <span className="cin-ref-placeholder">
                            <Icon name="image" size={14} />
                          </span>
                        )}
                        <span className="cin-ref-name">{reference.name}</span>
                        <Icon name="close" size={12} />
                      </button>
                    ))}
                  </div>
                )}
                <textarea
                  ref={promptInput}
                  value={state.prompt}
                  onChange={changePrompt}
                  onKeyDown={promptKeyDown}
                  onClick={(event) =>
                    detectMention(
                      event.currentTarget.value,
                      event.currentTarget.selectionStart ?? event.currentTarget.value.length,
                    )
                  }
                  placeholder="Describe your shot. Type @ to mention a reference, or select camera movements"
                  aria-label="Describe your shot"
                />
                {mention && (
                  <div
                    ref={mentionMenu}
                    className="cin-mention-menu"
                    role="listbox"
                    aria-label="Project references"
                  >
                    <h3>Insert project reference</h3>
                    {mentionMatches.length ? (
                      mentionMatches.map((entry, index) => {
                        const itemIndex = library.findIndex(
                          (item) => item.asset_id === entry.asset_id,
                        );
                        const name = referenceName(entry, itemIndex);
                        const asset = assetFor(entry.asset_id);
                        return (
                          <button
                            key={entry.asset_id}
                            type="button"
                            role="option"
                            aria-selected={index === Math.min(mentionIndex, mentionMatches.length - 1)}
                            className={
                              index === Math.min(mentionIndex, mentionMatches.length - 1)
                                ? 'active'
                                : ''
                            }
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={() => insertMention(entry)}
                          >
                            {asset ? (
                              <img src={asset.thumbnail_url || mediaUrl(asset)} alt="" />
                            ) : (
                              <span className="cin-ref-placeholder">
                                <Icon name="image" size={14} />
                              </span>
                            )}
                            <span>
                              <strong>{name}</strong>
                              <small>{entry.role}</small>
                            </span>
                            {activeIds.includes(entry.asset_id) && (
                              <em>{activeIds.indexOf(entry.asset_id) + 1}</em>
                            )}
                          </button>
                        );
                      })
                    ) : (
                      <p>
                        {library.length
                          ? 'No project references match that name.'
                          : 'No project references yet. Add images in the References panel.'}
                      </p>
                    )}
                    <small className="cin-mention-hint">
                      ↑↓ choose · Enter insert · Esc close. Choosing a reference adds it to this shot.
                    </small>
                  </div>
                )}
                <div className="cin-config-row">
                  <span className="cin-variants">
                    <button
                      aria-label="Fewer variants"
                      disabled={state.variants <= 1}
                      onClick={() => update({ variants: state.variants - 1 })}
                    >
                      −
                    </button>
                    <b>{state.variants}/4</b>
                    <button
                      aria-label="More variants"
                      disabled={state.variants >= 4}
                      onClick={() => update({ variants: state.variants + 1 })}
                    >
                      +
                    </button>
                  </span>
                  <button
                    className="cin-model-choice"
                    onClick={(event) => popover('Model', event.currentTarget)}
                  >
                    <Icon name="film" size={14} />
                    {model?.name || 'Choose model'}
                    <Icon name="chevron" size={11} />
                  </button>
                  <button onClick={(event) => popover('Quality', event.currentTarget)}>
                    {state.quality}px
                    <Icon name="chevron" size={11} />
                  </button>
                  <button onClick={(event) => popover('Aspect ratio', event.currentTarget)}>
                    <Icon name="square" size={11} />
                    {state.aspect_ratio}
                    <Icon name="chevron" size={11} />
                  </button>
                  {state.mode === 'video' && (
                    <>
                      <button onClick={(event) => popover('Duration', event.currentTarget)}>
                        {state.duration}s<Icon name="chevron" size={11} />
                      </button>
                      <button
                        className={state.generate_audio ? 'enabled' : ''}
                        disabled={!model?.supports_audio}
                        title={
                          model?.supports_audio
                            ? 'Generate native audio'
                            : 'This model does not generate native audio'
                        }
                        onClick={() => update({ generate_audio: !state.generate_audio })}
                      >
                        <Icon name="sound" size={14} />
                        <span className="cin-switch" />
                      </button>
                    </>
                  )}
                </div>
              </div>
              <button
                className="cin-generate"
                disabled={!session.ready || !state.prompt.trim() || submitting}
                onClick={() => void generate()}
              >
                <Icon name="spark" size={18} />
                <strong>{submitting ? 'Queueing…' : 'Generate'}</strong>
                <span>
                  {state.mode === 'image'
                    ? `${state.variants} image${state.variants > 1 ? 's' : ''}`
                    : `${state.variants} video${state.variants > 1 ? 's' : ''}`}
                </span>
              </button>
            </div>
            {(error || session.error) && (
              <p className="cin-error" role="alert">
                {error || session.error}
              </p>
            )}
            <span className="cin-save-status">
              {session.saving ? 'Saving…' : session.document ? 'Project saved' : ''}
            </span>
          </div>
        </div>
      </section>
      {menu && (
        <AnchoredPopover
          anchor={menu.anchor}
          onClose={() => setMenu(null)}
          width={menu.name === 'Model' ? 260 : 180}
          label={menu.name}
          placement="bottom-end"
          className="cin-options"
        >
          <h3>{menu.name}</h3>
          {menu.name === 'Model' ? (
            models.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  update({ model_id: item.id });
                  setMenu(null);
                }}
              >
                {item.name}
                {item.id === model?.id && <Icon name="check" size={14} />}
              </button>
            ))
          ) : menu.name === 'Quality' ? (
            [512, 768, 1024].map((value) => (
              <button
                key={value}
                onClick={() => {
                  update({ quality: value });
                  setMenu(null);
                }}
              >
                {value}px{value === state.quality && <Icon name="check" size={14} />}
              </button>
            ))
          ) : menu.name === 'Aspect ratio' ? (
            (model?.aspect_ratios || ['16:9', '9:16', '1:1']).map((value) => (
              <button
                key={value}
                onClick={() => {
                  update({ aspect_ratio: value });
                  setMenu(null);
                }}
              >
                {value}
                {value === state.aspect_ratio && <Icon name="check" size={14} />}
              </button>
            ))
          ) : (
            <>
              <label>
                {state.duration}s
                <input
                  type="range"
                  min="1"
                  max={
                    model
                      ? Math.floor(
                          Number(model.max_frames || 241) / Number(model.default_fps || 24),
                        )
                      : 10
                  }
                  step="1"
                  value={state.duration}
                  onChange={(event) => update({ duration: Number(event.target.value) })}
                />
              </label>
              <small>
                {model &&
                  `${durationFrames(model, state.duration)} frames · ${(durationFrames(model, state.duration) / Number(model.default_fps || 24)).toFixed(2)}s actual`}
              </small>
            </>
          )}
        </AnchoredPopover>
      )}
      <dialog
        ref={dialog}
        className={`cin-dialog ${['Film setup', 'Camera', 'Color palette', 'Lighting', 'New palette', 'New lighting preset'].includes(panel || '') ? 'cin-creative-dialog' : ''}`}
        onCancel={close}
        onClick={(event) => {
          if (event.target === event.currentTarget) close();
        }}
      >
        <header>
          <h2>
            {(panel === 'New palette' || panel === 'New lighting preset') && (
              <button
                aria-label="Back"
                onClick={() => setPanel(panel === 'New palette' ? 'Color palette' : 'Lighting')}
              >
                <Icon name="chevron" size={16} />
              </button>
            )}
            {panel || preview?.title || 'Generation'}
          </h2>
          <div>
            {[
              'Film setup',
              'Camera',
              'Color palette',
              'Lighting',
              'New palette',
              'New lighting preset',
            ].includes(panel || '') && <button onClick={resetCreative}>Reset all</button>}
            <button aria-label="Close dialog" onClick={close}>
              <Icon name="close" size={16} />
            </button>
          </div>
        </header>
        {panel === 'Film setup' && (
          <div className="cin-dialog-layout">
            <nav>
              {(['genre', 'era', 'tempo'] as const).map((tab) => (
                <button
                  className={filmTab === tab ? 'active' : ''}
                  key={tab}
                  onClick={() => setFilmTab(tab)}
                >
                  <Icon
                    name={tab === 'genre' ? 'film' : tab === 'era' ? 'clock' : 'bolt'}
                    size={16}
                  />
                  {tab[0].toUpperCase() + tab.slice(1)}
                  <span>{state.film[tab]}</span>
                </button>
              ))}
            </nav>
            <div className="cin-film-picker">
              <h3>
                {filmTab === 'genre'
                  ? 'Pick a genre'
                  : filmTab === 'era'
                    ? 'Set the era'
                    : 'Set the tempo'}
              </h3>
              <p>
                {filmTab === 'genre'
                  ? 'The feeling that holds your story together.'
                  : 'Added to your shot prompt as creative direction.'}
              </p>
              <div className="cin-film-carousel">
                {[-2, -1, 0, 1, 2].map((offset) => {
                  const name =
                    currentFilm[(filmIndex + offset + currentFilm.length) % currentFilm.length];
                  const item = reference[`film-${filmTab}`]?.find((entry) => entry.title === name);
                  return (
                    <button
                      key={offset}
                      className={`cin-film-option position-${offset + 2}`}
                      onClick={() => chooseFilm(name)}
                      aria-label={name}
                    >
                      <PreviewMedia item={item} />
                      {!item && <span>{name}</span>}
                    </button>
                  );
                })}
              </div>
              <div className="cin-carousel-footer">
                <button
                  aria-label={`Previous ${filmTab}`}
                  onClick={() =>
                    chooseFilm(
                      currentFilm[(filmIndex - 1 + currentFilm.length) % currentFilm.length],
                    )
                  }
                >
                  <Icon name="chevron" size={16} />
                </button>
                <strong>{selectedFilm}</strong>
                <button
                  aria-label={`Next ${filmTab}`}
                  onClick={() => chooseFilm(currentFilm[(filmIndex + 1) % currentFilm.length])}
                >
                  <Icon name="chevron" size={16} />
                </button>
              </div>
            </div>
          </div>
        )}
        {panel === 'Camera' && (
          <div className="cin-dialog-layout">
            <nav>
              <button
                className={cameraTab === 'setup' ? 'active' : ''}
                onClick={() => setCameraTab('setup')}
              >
                <Icon name="sliders" size={16} />
                Setup<span>{state.camera.body}</span>
              </button>
              <button
                className={cameraTab === 'movement' ? 'active' : ''}
                onClick={() => setCameraTab('movement')}
              >
                <Icon name="video" size={16} />
                Movement<span>{state.camera.movements.length || 'Auto'}</span>
              </button>
            </nav>
            {cameraTab === 'setup' ? (
              <div className="cin-camera-wheels">
                {(Object.keys(cameraOptions) as (keyof typeof cameraOptions)[]).map((key) => (
                  <div key={key}>
                    <h3>{key === 'body' ? 'Camera' : key[0].toUpperCase() + key.slice(1)}</h3>
                    <div className="cin-camera-wheel">
                      {cameraOptions[key].map((name) => (
                        <button
                          key={name}
                          className={state.camera[key] === name ? 'selected' : ''}
                          onClick={() => chooseCamera(key, name)}
                        >
                          <PreviewMedia
                            item={reference['camera-setup']?.find((item) => item.title === name)}
                          />
                          <span>{name}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="cin-movement-panel">
                <div>
                  <h3>Direct a camera move</h3>
                  <p>
                    Adds to the prompt box, or type # there.
                    <br />
                    Several per shot; order matters. The render prompt expands each move with a
                    short description.
                  </p>
                  <div className="cin-movement-tools">
                    <button
                      aria-label="Sort movements"
                      onClick={() => setMovementSort(!movementSort)}
                    >
                      <Icon name="sliders" size={16} />
                    </button>
                    <label>
                      <Icon name="search" size={16} />
                      <input
                        aria-label="Search movements"
                        placeholder="Search"
                        value={movementSearch}
                        onChange={(event) => setMovementSearch(event.target.value)}
                      />
                    </label>
                  </div>
                </div>
                <div className="cin-movement-grid">
                  {movements.map((item) => (
                    <button
                      key={item.title}
                      className={state.camera.movements.includes(item.title) ? 'selected' : ''}
                      title={describeCameraMovement(item.title)}
                      aria-label={`${item.title}: ${describeCameraMovement(item.title)}`}
                      onClick={() =>
                        update({
                          prompt: state.camera.movements.includes(item.title)
                            ? state.prompt
                                .split('#' + item.title)
                                .join('')
                                .trim()
                            : `${state.prompt.trim()} #${item.title}`.trim(),
                          camera: {
                            ...state.camera,
                            movements: state.camera.movements.includes(item.title)
                              ? state.camera.movements.filter((name) => name !== item.title)
                              : [...state.camera.movements, item.title],
                          },
                        })
                      }
                    >
                      <div>
                        <PreviewMedia item={item} />
                        <span>Put on prompt</span>
                      </div>
                      <strong>{item.title}</strong>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {panel === 'References' && (
          <div className="cin-reference-picker cin-references-panel">
            <header className="cin-reference-header">
              <button
                className="cin-upload"
                onClick={() => fileInput.current?.click()}
                disabled={uploading || library.length >= LIBRARY_LIMIT}
              >
                <Icon name="upload" />
                {uploading ? 'Uploading…' : 'Upload images'}
              </button>
              <span className="cin-library-counter">
                {library.length}/{LIBRARY_LIMIT} project references
              </span>
            </header>
            <p className="cin-reference-summary">{referenceSummary}</p>
            <section
              className={`cin-reference-active-summary ${referenceBlockReason ? 'warning' : ''}`}
            >
              <div>
                <strong>
                  {activeIds.length}/{maxReferences} active for this shot
                </strong>
                <span>
                  {effectLabel}
                  {model ? ` · ${model.name}` : ''}
                </span>
              </div>
              <div>
                <span>{library.length}/{LIBRARY_LIMIT} in library</span>
                {activeIds.length > 0 && (
                  <button onClick={clearActiveReferences}>Clear active</button>
                )}
              </div>
              {referenceBlockReason && <p role="alert">{referenceBlockReason}</p>}
            </section>
            <section className="cin-reference-library-section">
              <header>
                <h3>Project library</h3>
                <span>Active order is the reference-sheet order (1 → {maxReferences}).</span>
              </header>
              {library.length ? (
                <div className="cin-reference-library">
                  {library.map((entry, index) => {
                    const asset = assetFor(entry.asset_id);
                    const active = activeIds.includes(entry.asset_id);
                    const name = referenceName(entry, index);
                    return (
                      <article
                        key={entry.asset_id}
                        className={`cin-reference-card ${active ? 'active' : ''}`}
                      >
                        <button
                          className="cin-reference-thumb"
                          aria-pressed={active}
                          aria-label={`${active ? 'Deactivate' : 'Activate'} ${name} for this shot`}
                          onClick={() => toggleActiveReference(entry.asset_id)}
                        >
                          {asset ? (
                            <img
                              src={asset.thumbnail_url || mediaUrl(asset)}
                              alt={name}
                            />
                          ) : (
                            <span className="cin-ref-placeholder">
                              <Icon name="image" size={20} />
                            </span>
                          )}
                          <span className="cin-reference-check">
                            {active ? (
                              <b>{activeIds.indexOf(entry.asset_id) + 1}</b>
                            ) : (
                              <Icon name="plus" size={13} />
                            )}
                          </span>
                        </button>
                        <div className="cin-reference-meta">
                          <input
                            aria-label={`Name for reference ${index + 1}`}
                            placeholder={asset?.name || `Reference ${index + 1}`}
                            value={entry.name}
                            onChange={(event) =>
                              updateReferenceEntry(entry.asset_id, {
                                name: event.target.value,
                              })
                            }
                          />
                          <select
                            aria-label={`Role for ${name}`}
                            value={entry.role}
                            onChange={(event) =>
                              updateReferenceEntry(entry.asset_id, {
                                role: event.target.value as CinemaReferenceRole,
                              })
                            }
                          >
                            {referenceRoles.map((role) => (
                              <option key={role} value={role}>
                                {role[0].toUpperCase() + role.slice(1)}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="cin-reference-actions">
                          <button onClick={() => toggleActiveReference(entry.asset_id)}>
                            {active ? 'Deactivate' : 'Activate'}
                          </button>
                          <button
                            className="cin-reference-remove"
                            aria-label={`Remove ${name} from the project library`}
                            title="Remove from project library"
                            onClick={() => removeReferenceFromLibrary(entry.asset_id)}
                          >
                            <Icon name="trash" size={14} />
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              ) : (
                <p>
                  No project references yet. Upload images or add a workspace image below; the
                  library holds {LIBRARY_LIMIT}.
                </p>
              )}
            </section>
            <section className="cin-reference-workspace">
              <header>
                <h3>Workspace images</h3>
                <span>Adding an image puts it in this project; it is not deleted from the workspace.</span>
              </header>
              <div className="cin-reference-assets">
                {assets
                  .filter(
                    (asset) =>
                      asset.kind === 'image' &&
                      !library.some((entry) => entry.asset_id === asset.id),
                  )
                  .map((asset) => (
                    <button
                      key={asset.id}
                      disabled={library.length >= LIBRARY_LIMIT}
                      onClick={() => addReferenceAsset(asset)}
                      title={`Add ${asset.name} to the project reference library`}
                    >
                      <img src={asset.thumbnail_url || mediaUrl(asset)} alt={asset.name} />
                      <span>
                        <Icon name="plus" size={12} />
                        Add
                      </span>
                    </button>
                  ))}
              </div>
              {!assets.some(
                (asset) =>
                  asset.kind === 'image' &&
                  !library.some((entry) => entry.asset_id === asset.id),
              ) && <p>No unadded workspace images. Upload a new image above.</p>}
            </section>
          </div>
        )}
        {panel === 'Projects' && (
          <div className="cin-document-picker">
            {session.documents.map((doc) => (
              <button
                key={doc.id}
                onClick={() => {
                  void session.openDocument(doc);
                  setView('My projects');
                  close();
                }}
              >
                {doc.title}
              </button>
            ))}
          </div>
        )}
        {(panel === 'Color palette' || panel === 'Lighting') && (
          <div className="cin-preset-panel">
            <div className="cin-preset-heading">
              <h3>{presetKind === 'lighting' ? 'Set up lighting' : 'Set up color palette'}</h3>
              <p>
                {presetKind === 'lighting'
                  ? 'Pick a scheme or place your own lights'
                  : 'Palette the color grade should follow'}
              </p>
              <div>
                <button onClick={() => setPresetSort(!presetSort)}>
                  <Icon name="sliders" size={14} />
                  {presetSort ? 'Name' : 'Sort by'}
                </button>
                <label>
                  <Icon name="search" size={15} />
                  <input
                    aria-label="Search presets"
                    placeholder="Search"
                    value={presetSearch}
                    onChange={(event) => setPresetSearch(event.target.value)}
                  />
                </label>
              </div>
            </div>
            <div className={`cin-preset-grid ${presetKind}`}>
              <div className="cin-preset-card cin-new-preset">
                <button onClick={newCreativePreset}>
                  <span className="cin-preset-image">
                    <Icon name="plus" size={28} />
                  </span>
                  <strong>
                    {presetKind === 'lighting' ? 'New lighting preset' : 'New palette'}
                  </strong>
                </button>
              </div>
              {presetItems.map((item, index) => (
                <div
                  className={`cin-preset-card ${(presetKind === 'lighting' ? state.lighting : state.palette) === item.title ? 'selected' : ''}`}
                  key={item.title + index}
                >
                  <button onClick={() => selectPreset(item)}>
                    <span className="cin-preset-image">
                      <PreviewMedia item={item} />
                      {item.colors && (
                        <span className="cin-preset-colors">
                          {item.colors.map((color, i) => (
                            <i key={i} style={{ background: color }} />
                          ))}
                        </span>
                      )}
                    </span>
                    <strong>{item.title}</strong>
                  </button>
                  <div className="cin-preset-card-tools">
                    <button
                      className={(state.pinned_presets || []).includes(item.title) ? 'pinned' : ''}
                      aria-label={`Pin ${item.title}`}
                      onClick={() =>
                        update({
                          pinned_presets: (state.pinned_presets || []).includes(item.title)
                            ? state.pinned_presets.filter((name) => name !== item.title)
                            : [...(state.pinned_presets || []), item.title],
                        })
                      }
                    >
                      <Icon name="pin" size={13} />
                    </button>
                    <button
                      aria-label={`${item.title} actions`}
                      onClick={() =>
                        setPresetActions(presetActions === item.title ? null : item.title)
                      }
                    >
                      <Icon name="more" size={13} />
                    </button>
                  </div>
                  {presetActions === item.title && (
                    <div className="cin-preset-actions">
                      <button
                        onClick={() => {
                          setPresetActions(null);
                          if (presetKind === 'palette') {
                            setEditPalette({
                              name: item.title + ' copy',
                              colors: item.colors || [],
                            });
                            setPanel('New palette');
                          } else {
                            setEditLights(
                              state.lighting_presets?.find((entry) => entry.name === item.title)
                                ?.lights || defaultLights,
                            );
                            setPanel('New lighting preset');
                          }
                          setEditorReset((n) => n + 1);
                        }}
                      >
                        Edit a copy
                      </button>
                      {customPresets.some((entry) => entry.title === item.title) && (
                        <button
                          onClick={() => {
                            if (presetKind === 'palette')
                              update({
                                palette_presets: state.palette_presets.filter(
                                  (entry) => entry.name !== item.title,
                                ),
                              });
                            else
                              update({
                                lighting_presets: state.lighting_presets.filter(
                                  (entry) => entry.name !== item.title,
                                ),
                              });
                            setPresetActions(null);
                          }}
                        >
                          Delete preset
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
        {panel === 'New lighting preset' && (
          <LightingEditor
            key={editorReset}
            value={editLights}
            onApply={(lights) => {
              update({ lighting: 'Custom', custom_lights: lights });
              setPanel('Lighting');
            }}
            onSave={(preset) => {
              update({
                lighting: preset.name,
                custom_lights: preset.lights,
                lighting_presets: [
                  ...(state.lighting_presets || []).filter((item) => item.name !== preset.name),
                  preset,
                ],
              });
              setPanel('Lighting');
            }}
          />
        )}
        {panel === 'New palette' && (
          <PaletteEditor
            key={editorReset}
            value={editPalette}
            onError={setError}
            onSave={(preset) => {
              update({
                palette: preset.name,
                palette_colors: preset.colors,
                palette_presets: [
                  ...(state.palette_presets || []).filter((item) => item.name !== preset.name),
                  preset,
                ],
                attachment_asset_ids: [
                  ...new Set([
                    ...(state.attachment_asset_ids || []),
                    ...(preset.image_asset_id ? [preset.image_asset_id] : []),
                  ]),
                ],
              });
              setPanel('Color palette');
            }}
          />
        )}
        {preview && (
          <div className="cin-preview">
            <video src={preview.video} poster={preview.poster} controls playsInline />
            <p>
              Public reference project from Higgsfield. This is not a generation from your
              workspace.
            </p>
          </div>
        )}
        {selectedJob && (
          <div className="cin-result">
            <p>{selectedJob.request.prompt}</p>
            {selectedJob.outputs
              .filter((asset) => asset.role !== 'mask')
              .map((asset) => (
                <div key={asset.id}>
                  {asset.kind === 'video' ? (
                    <video src={mediaUrl(asset)} controls playsInline />
                  ) : (
                    <img src={mediaUrl(asset)} alt="Generated result" />
                  )}
                  <a href={mediaUrl(asset)} download={asset.name}>
                    Download result
                  </a>
                </div>
              ))}
            {selectedJob.error && <p role="alert">{selectedJob.error}</p>}
            <div className="cin-result-actions">
              <button onClick={() => void reuse(selectedJob)}>Reuse project</button>
              <a href={`/api/jobs/${selectedJob.id}/workflow`} download>
                Workflow API
              </a>
              <a href={`/api/jobs/${selectedJob.id}/bundle?include_media=true`} download>
                Full project
              </a>
              <button
                onClick={() => {
                  void api<Job>(`/jobs/${selectedJob.id}`, {
                    method: 'PATCH',
                    body: JSON.stringify({ favorite: !selectedJob.favorite }),
                  })
                    .then((job) => {
                      setSelectedJob(job);
                      void session.refreshJobs();
                    })
                    .catch((reason) => setError(reason.message));
                }}
              >
                {selectedJob.favorite ? 'Unfavorite' : 'Favorite'}
              </button>
            </div>
          </div>
        )}
      </dialog>
      <input
        ref={fileInput}
        type="file"
        hidden
        accept="image/*"
        multiple
        onChange={(event) => void uploadReferences(event.target.files)}
      />
    </main>
  );
}
