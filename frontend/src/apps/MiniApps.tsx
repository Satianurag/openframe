import { useEffect, useState } from 'react';
import { api, mediaUrl, post, upload } from '../api';
import { Icon } from '../Icon';
import { previewSources, previewVideos } from '../previews';
import { nativeVideoCards } from './NativeVideoTools';
import { MaskEditor } from '../MaskEditor';
import { ImageRelightControls, defaultImageLighting, imageLightingPrompt } from './ImageRelightControls';
import type { ImageLighting } from './ImageRelightControls';
import { portraitLightingPrompt, portraitRelightSize } from './portraitRelight';
import { imageRelightSize, lightingMapFile, lightingMapKey, lightingMapVersion, qwenLightDirection, qwenLightingPrompt } from './imageLightingMap';
import { BillboardStages, defaultBillboardVideo, useBillboardSequence } from './BillboardStages';
import type { BillboardVideo } from './BillboardStages';
import { officialRecastAvailable, preferredRecastSupport, recastSupportIssue, recastReferenceCleanupAvailable, recastReferenceCleanupIssue } from './recastSupport';
import type { Job, JobRequest } from '../types';
import { useAppDocument } from './useAppDocument';
import {
  modelProviderIssue,
  modelSupportsReference,
  providerReadinessIssue,
  renderRequest,
  renderSize,
  resolveProvider,
} from './renderRequest';
import {
  AssetPicker,
  ReferenceMedia,
  ResultDialog,
  SourceSlot,
  useWorkspaceAssets,
  useReferenceLibrary,
  WorkspaceHistory,
} from './engine-apps-shared';
import type { EngineAppProps } from './engine-apps-shared';
import './engine-apps.css';
import './mini-apps.css';

type Preset = {
  id: string;
  name: string;
  category: string;
  effect: string;
  model: string;
  description: string;
  prompt: string;
  note: string;
  poster: string;
  video?: string;
  own?: boolean;
  illustration?: boolean;
  reference?: string;
  referenceLabel?: string;
  source_url?: string;
};
const presets: Preset[] = [
  {
    id: 'portrait',
    reference: 'ai-headshot-generator',
    name: 'Headshot Generator',
    category: 'Portrait & Style',
    effect: 'edit-image',
    model: 'flux3-klein',
    description: 'Create a polished portrait from your photo.',
    prompt:
      'Create a professional studio headshot of the person in the source image. Preserve their recognizable facial appearance. Soft directional light, natural skin texture, a simple neutral background, refined realistic photography.',
    note: 'Reference-guided portrait editing; identity is not trained or guaranteed.',
    poster:
      '/reference-media/40fe81a8ed2e0453aca1.webp',
    source_url: 'https://higgsfield.ai/apps/ai-headshot-generator',
  },
  {
    id: 'relight',
    reference: 'relight',
    name: 'Relight',
    category: 'Portrait & Style',
    effect: 'edit-image',
    model: 'qwen-portrait-relight',
    description: 'Adjust light direction, softness, brightness and color.',
    prompt:
      'Relight the source image while preserving the scene composition, subject appearance, pose and materials. Render coherent illumination and natural shadows.',
    note: 'Portrait Relight restores the original background around one person. Facial detail and edge lighting can change. Lighting-map and FLUX alternatives remain available for other subjects.',
    poster:
      '/reference-media/55cea2e45b33dde14d8c.webp',
    source_url: 'https://higgsfield.ai/apps/relight',
  },
  {
    id: 'outfit',
    reference: 'outfit-swap',
    name: 'Outfit Swap',
    category: 'Portrait & Style',
    effect: 'edit-image',
    model: 'flux3-klein',
    referenceLabel: 'Outfit reference',
    description: 'Use a clothing image to restyle your portrait.',
    prompt:
      "Dress the person in the first image in the outfit shown in the second reference image. Preserve the person's recognizable face, pose and the original background. Render natural garment folds and coherent lighting.",
    note: 'Klein uses both images as visual references. Fit and identity consistency need review.',
    poster:
      '/reference-media/afc709090beda2439a15.webp',
    source_url: 'https://higgsfield.ai/apps/outfit-swap',
  },
  {
    id: 'paint',
    reference: 'paint-app',
    name: 'Paint App',
    category: 'Portrait & Style',
    effect: 'edit-image',
    model: 'flux3-klein',
    description: 'Frame your photo inside a retro paint interface on a CRT monitor.',
    prompt:
      'Place the supplied photo as the recognizable canvas inside a classic 1990s desktop paint application displayed on a vintage CRT monitor. Include a gray window frame, small paint-tool icons and a color palette around the photo, with a curved glass screen, subtle scanlines and a restrained lo-fi vaporwave atmosphere. Keep the person and composition recognizable inside the canvas; show the monitor as a coherent physical object. Do not add unrelated people or advertising slogans.',
    note: 'An editable retro-screen composition using Klein. Optional region painting is a separate localized edit; interface lettering and source details need review.',
    poster:
      '/reference-media/3f59f3f673c30f5be024.webp',
    source_url: 'https://higgsfield.ai/apps/paint-app',
  },
  {
    id: 'background',
    reference: 'image-background-remover',
    name: 'Background Remover',
    category: 'Products & Images',
    effect: 'remove-background',
    model: 'birefnet',
    description: 'Extract your foreground as a transparent PNG.',
    prompt: 'Extract the foreground with a clean soft alpha boundary.',
    note: 'Dedicated BiRefNet segmentation. The output retains the source image dimensions.',
    poster:
      '/reference-media/da552ac353c5755cb4b2.webp',
    source_url: 'https://higgsfield.ai/apps/image-background-remover',
  },
  {
    id: 'billboard',
    reference: 'billboard',
    name: 'Billboard Ad',
    category: 'Products & Images',
    effect: 'edit-image',
    model: 'flux3-klein',
    description: 'Turn your image into a city billboard timelapse.',
    prompt:
      'Use the supplied image as the artwork on a large, realistic urban billboard. Show the billboard within an architecturally coherent street scene with natural perspective, daylight and realistic materials. Do not add invented brand slogans.',
    note: 'A durable image-composition stage followed by image-to-video animation. Review display readability, product details and temporal stability.',
    poster:
      '/reference-media/361e4d6fbff6cffb40c1.webp',
    source_url: 'https://higgsfield.ai/apps/billboard',
  },
  {
    id: 'product',
    reference: 'bullet-time-scene',
    name: 'Product Reveal',
    category: 'Products & Images',
    effect: 'product-reveal',
    model: 'ltx-2.5',
    description: 'Animate an opening product photograph.',
    prompt:
      'A premium product reveal, slow camera orbit, controlled studio highlights and an elegant backdrop. Keep the product recognizable with coherent shape and materials.',
    note: 'Prompt-directed image animation, not a reconstructed 3D product or guaranteed 360\u00b0 scan.',
    poster:
      '/reference-media/9b6704fb3a329f859813.webp',
    source_url: 'https://higgsfield.ai/apps/bullet-time-scene',
  },
  {
    id: 'talking-portrait',
    name: 'Talking Portrait',
    category: 'Motion & Characters',
    effect: 'speak',
    model: 'longcat-avatar-1.5',
    description: 'Animate a portrait with your recorded speech.',
    prompt:
      'A person speaking naturally to the camera, clear facial expression, subtle head movement, stable framing and consistent lighting.',
    note: 'The selected portrait-animation model conditions video on your image and uploaded recording. The original selected audio is retained. The preview is a portrait reference only, not a lip-sync result; review the generated mouth motion.',
    poster:
      '/reference-media/40fe81a8ed2e0453aca1.webp',
    source_url: 'https://higgsfield.ai/apps/ai-headshot-generator',
  },
  {
    id: 'character-image',
    reference: 'character-swap',
    name: 'Character Swap',
    category: 'Motion & Characters',
    effect: 'edit-image',
    model: 'flux3-klein',
    referenceLabel: 'Character reference',
    description: 'Reimagine an image with a different character.',
    prompt:
      "Replace the main character in the first scene image with the person or character in the second reference. Follow the first scene's pose, framing and lighting while keeping the second reference recognizable.",
    note: 'A generated multi-reference image edit; it is not a face-swap or identity-lock model.',
    poster:
      '/reference-media/da5c72aa06a93c89e2b0.webp',
    source_url: 'https://higgsfield.ai/apps/character-swap',
  },
  {
    id: 'motion',
    reference: 'recast',
    name: 'Motion Transfer',
    category: 'Motion & Characters',
    effect: 'motion-transfer',
    model: 'wan-animate',
    referenceLabel: 'Character image',
    description: 'Drive a character using an actual performance.',
    prompt:
      "The character in the reference image follows the source performer's body motion and facial movement. Maintain coherent anatomy, stable appearance and natural expression.",
    note: 'The selected motion model follows the driving performance and character reference. A clear human performer works best; inspect hands, expression and identity in the result.',
    poster:
      '/reference-media/ce4398ea4df0b2c695b2.webp',
    source_url: 'https://higgsfield.ai/apps/recast',
  },
  {
    id: 'recast',
    reference: 'recast',
    name: 'Recast',
    category: 'Motion & Characters',
    effect: 'character-replacement',
    model: 'scail-2',
    referenceLabel: 'Replacement character',
    description: 'Replace a performer using full-video motion conditioning.',
    prompt:
      "The reference character performs the source person's movements in the original scene. Preserve the surrounding background and use natural, consistent lighting.",
    note: 'SCAIL-2 follows the full driving footage with automatic single-person segmentation. A painted first-frame mask overrides source selection. Inspect the raw clip, tracked edges, hands and held objects; exact performance fidelity is not guaranteed.',
    poster:
      '/reference-media/ce4398ea4df0b2c695b2.webp',
    source_url: 'https://higgsfield.ai/apps/recast',
  },
  {
    id: 'vanish',
    name: 'Vanish',
    category: 'Video VFX',
    effect: 'remove-object',
    model: 'ltx-2.5',
    description: 'Remove a painted object from your footage.',
    prompt:
      'A clean uninterrupted background, natural scene details, consistent lighting and camera movement. Remove the painted object and reconstruct the background.',
    note: 'Matched LTX IC-LoRA masked video editing, with explicit plate preservation.',
    poster: previewSources['remove-object'],
    video: previewVideos['remove-object'],
    source_url: 'https://higgsfield.ai/ai/video/edit',
  },
  {
    id: 'replace',
    name: 'Replace',
    category: 'Video VFX',
    effect: 'replace-object',
    model: 'ltx-2.5',
    description: 'Describe what should replace a painted object.',
    prompt:
      'Replace the painted object with a matte black sculptural chess knight. Keep it grounded in the scene with coherent perspective, material and natural shadow.',
    note: 'Masked generation preserves the plate outside the edit region; mask coverage affects boundaries.',
    poster: previewSources['replace-object'],
    video: previewVideos['replace-object'],
    source_url: 'https://higgsfield.ai/ai/video/edit',
  },
  {
    id: 'restyle',
    name: 'Restyle',
    category: 'Video VFX',
    effect: 'restyle',
    model: 'wan-vace',
    description: 'Repaint the look of an existing video.',
    prompt:
      'Reimagine the source clip as a delicate watercolor painting with visible paper grain, soft pigment edges and coherent movement. Preserve its main composition.',
    note: 'Video-conditioned style generation. Lower Wan source guidance allows larger changes.',
    poster: previewSources['restyle'],
    video: previewVideos['restyle'],
    source_url: 'https://higgsfield.ai/ai/video/edit',
  },
  {
    id: 'weather',
    name: 'Change Weather',
    category: 'Video VFX',
    effect: 'weather',
    model: 'ltx-2.5',
    description: 'Reimagine a clip with new atmosphere.',
    prompt:
      'Gentle rain falls through the scene. Wet reflective surfaces, overcast cinematic light, coherent motion and a natural atmosphere.',
    note: 'Prompt-directed video transformation; the card shows a public Higgsfield atmosphere reference.',
    poster: previewSources['weather'],
    video: previewVideos['weather'],
    source_url: 'https://higgsfield.ai/ai/video/edit',
  },
];
const videoUtilities: {
  id: string;
  name: string;
  description: string;
  icon: string;
  video?: string;
  badge: string;
  category?: string;
  poster?: string;
}[] = [
  ...nativeVideoCards,
  {
    id: 'expand-image',
    name: 'Expand Image',
    description: 'Generate outside the original picture while preserving its pixels.',
    icon: 'image',
    badge: 'Reference preview',
    video: '/reference-media/91be9c967520232980f7.mp4',
    poster:
      '/reference-media/0a96ffd21fc2a028da87.webp',
    category: 'Image Utilities',
  },
  {
    id: 'image-layers',
    name: 'Layers',
    description: 'Separate an image into editable transparent layers.',
    icon: 'layers',
    badge: 'Reference preview',
    video: '/reference-media/81cf406c9031751cc529.mp4',
    poster: '/reference-media/e25e5ec986709f52d5df.webp',
    category: 'Image Utilities',
  },
  {
    id: 'trim-video',
    name: 'Trim Video',
    description: 'Keep a precise frame interval with source audio.',
    icon: 'video',
    badge: 'CPU video tool',
  },
  {
    id: 'video-reframe',
    name: 'Reframe',
    description: 'Crop or pad your video to a new canvas.',
    icon: 'square',
    badge: 'CPU video tool',
  },
  {
    id: 'transitions',
    name: 'Transitions',
    description: 'Generate a bridge between two images or short videos.',
    icon: 'spark',
    badge: 'Reference preview',
    video: '/reference-media/28b632c79343452bf1a9.mp4',
  },
  {
    id: 'fps-boost',
    name: 'FPS Boost',
    description: 'Generate intermediate frames at a higher frame rate.',
    icon: 'film',
    badge: 'Reference preview',
    video: '/reference-media/cdfed63e476a374ee627.mp4',
    poster: '/reference-media/abfb3ba53fe03704e84e.webp',
  },
  {
    id: 'video-depth',
    name: 'Depth Map',
    description: 'Estimate temporal depth and export lossless depth data.',
    icon: 'layers',
    badge: 'Reference preview',
    video: '/reference-media/d86242bce10cc3d73821.mp4',
    poster: '/reference-media/a84840ea719371dc4dfa.webp',
  },
];
const categories = [
  'All',
  ...new Set(presets.map((item) => item.category)),
  'Image Utilities',
  'Video Utilities',
];
type Draft = {
  billboard_video?: BillboardVideo | null;
  image_lighting?: ImageLighting | null;
  image_light_map_key?: string;
  image_light_map_renderer?: string;
  image_brightness?: number;
  replay_settings?: Partial<JobRequest>;
  enhance_prompt?: boolean;
  preset_id: string;
  prompt: string;
  model_id: string;
  provider: string;
  source_asset_id: string;
  reference_asset_id: string;
  mask_asset_id: string;
  image_preservation: 'none' | 'outside-mask' | 'inside-mask';
  image_edit_focus?: 'full' | 'masked-region';
  audio_asset_id: string;
  audio_start: number;
  audio_conditioning_strength: number;
  ratio: string;
  size: number;
  frames: number;
  trim_start: number;
  strength: number;
  restyle_method?: 'latent' | 'canny' | 'water';
  seed: number;
  batch_size: number;
  tracking: string;
  preserve_audio: boolean;
  generate_audio: boolean;
  mask_dilation: number;
  mask_feather: number;
  mask_edit_margin?: number;
  recast_composite_tracking?: 'native' | 'official' | 'official-union';
  recast_reference_cleanup?: boolean;
};
const initial: Draft = {
  recast_reference_cleanup: true,
  preset_id: '',
  prompt: '',
  model_id: '',
  provider: '',
  source_asset_id: '',
  reference_asset_id: '',
  mask_asset_id: '',
  image_preservation: 'none',
  image_edit_focus: 'full',
  image_brightness: 0,
  audio_asset_id: '',
  audio_start: 0,
  audio_conditioning_strength: 1,
  ratio: '16:9',
  size: 768,
  frames: 49,
  trim_start: 0,
  strength: 0.65,
  seed: -1,
  batch_size: 1,
  tracking: 'sam2',
  preserve_audio: true,
  generate_audio: false,
  mask_dilation: 8,
  mask_feather: 6,
};
const inputs = (state: Draft) =>
  [
    state.source_asset_id,
    state.reference_asset_id,
    state.mask_asset_id,
    state.audio_asset_id,
  ].filter(Boolean);

const presetTitle = (state: Draft) =>
  presets.find((item) => item.id === state.preset_id)?.name || 'Mini-app project';

export function MiniApps({ catalog, settings, onSettings }: EngineAppProps) {
  const session = useAppDocument('mini-apps', initial, inputs, undefined, presetTitle);
  const state = { ...initial, ...session.state };
  // Loaded recipes without this new field retain their original behavior.
  const recastReferenceCleanup = session.state.recast_reference_cleanup ?? false;
  const { update } = session;
  const assets = useWorkspaceAssets(inputs(state));
  const library = useReferenceLibrary('mini-apps');
  function mediaFor(item: Preset, detail = false) {
    const imported =
      detail && item.id === 'background'
        ? library.hero?.find((value) => value.id === item.id)
        : library.presets?.find((value) => value.id === item.id);
    if (imported) return imported;
    return {
      title: item.name,
      poster:
        detail && item.id === 'background'
          ? '/reference-media/cd4cf26ee7d14d72720f.webp'
          : item.poster,
      video:
        detail && item.id === 'background'
          ? '/reference-media/15b84cec684fb13f9cd0.mp4'
          : item.video,
    };
  }
  const [query, setQuery] = useState(() => new URLSearchParams(location.search).get('q') || '');
  const [category, setCategory] = useState(
    () => new URLSearchParams(location.search).get('category') || 'All',
  );
  const [tab, setTab] = useState<'explore' | 'generations'>('explore');
  const [detailHistory, setDetailHistory] = useState(false);
  const [detailJobs, setDetailJobs] = useState<Job[]>([]);
  const [detailTotal, setDetailTotal] = useState(0);
  const [detailLimit, setDetailLimit] = useState(100);
  const [historyError, setHistoryError] = useState('');
  const [historyLoading, setHistoryLoading] = useState(false);
  const [routeRevision, setRouteRevision] = useState(0);
  const [launch, setLaunch] = useState(false),
    [picker, setPicker] = useState<'source' | 'reference' | 'audio' | null>(null),
    [painting, setPainting] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [selected, setSelected] = useState<Job | null>(null);
  const preset = presets.find((item) => item.id === state.preset_id);
  const billboardWorkflow = useBillboardSequence(session.document?.id, preset?.id === 'billboard');
  const billboardVideo = preset?.id === 'billboard' ? state.billboard_video : null;
  const billboardModel = catalog.models.find((item) => item.id === billboardVideo?.model_id && catalog.effects.find((entry) => entry.id === 'image-to-video')?.model_ids.includes(item.id));
  const directionalRelight = preset?.id === 'relight' && state.model_id === 'qwen-image-relight';
  const portraitRelight = preset?.id === 'relight' && state.model_id === 'qwen-portrait-relight';
  const nativeImageRelight = directionalRelight || portraitRelight;
  const lightingPrompt = portraitRelight ? portraitLightingPrompt : directionalRelight ? qwenLightingPrompt : imageLightingPrompt;
  const effect = catalog.effects.find((item) => item.id === (nativeImageRelight ? 'relight-image' : preset?.effect));
  const compatible = catalog.models.filter((item) => preset?.id === 'relight' ? ['qwen-image-relight', 'qwen-portrait-relight'].includes(item.id) || catalog.effects.find((entry) => entry.id === 'edit-image')?.model_ids.includes(item.id) : effect?.model_ids.includes(item.id));
  const model =
    compatible.find((item) => item.id === state.model_id) ||
    compatible.find((item) => item.id === preset?.model) ||
    compatible[0];
  const operation = session.application?.operations.find((item) => item.id === effect?.id);
  const source = assets.get(state.source_asset_id),
    reference = assets.get(state.reference_asset_id),
    mask = assets.get(state.mask_asset_id);
  const audio = assets.get(state.audio_asset_id);
  const needsAudio = effect?.requires_audio === true;
  const unavailableModel =
    (needsAudio || preset?.id === 'billboard' || preset?.id === 'relight') && !!state.model_id && !compatible.some((item) => item.id === state.model_id);
  const imageOutput = effect?.output_kind === 'image';
  const restyleMethods = effect?.task === 'restyle' ? (model?.restyle_methods || []).filter((method) => !method.effect_ids || method.effect_ids.includes(effect.id)) : [];
  const restyleMethod = state.restyle_method || 'latent';
  const waterRestyle = restyleMethod === 'water';
  const cannyRestyle = restyleMethod === 'canny' && restyleMethods.some((item) => item.id === 'canny');
  const weatherFirstFrame = preset?.id === 'weather' && cannyRestyle && !!model?.restyle_first_frame_effects?.includes(preset.effect);
  const paintRegion = preset?.id === 'paint' && effect?.task === 'image-edit';
  const imageRegion = paintRegion && !!state.mask_asset_id && state.image_preservation !== 'none';
  const referenceLabel =
    (directionalRelight ? 'Lighting map' : undefined) ||
    (weatherFirstFrame ? 'Edited first frame (optional)' : undefined) ||
    preset?.referenceLabel ||
    (effect && model?.reference_tasks?.includes(effect.task)
      ? 'Optional visual reference'
      : preset?.id === 'weather' && state.reference_asset_id ? 'Saved first-frame reference' : undefined);
  const supportsEnhancement =
    !!model &&
    !!effect &&
    Array.isArray(model.prompt_enhancement_tasks) &&
    model.prompt_enhancement_tasks.includes(effect.task);
  const provider = resolveProvider(state.provider, settings.default_provider);
  const selectedProvider = catalog.providers.find((item) => item.id === provider);
  const cleanupAvailable = recastReferenceCleanupAvailable(catalog, provider);
  const cleanupIssue = model?.id === 'scail-2' ? recastReferenceCleanupIssue(catalog, provider, recastReferenceCleanup) : '';
  const officialSupportAvailable = officialRecastAvailable(catalog, provider);
  const unionSupportAvailable = officialRecastAvailable(catalog, provider, 'official-union');
  const supportIssue = model?.id === 'scail-2' && !state.mask_asset_id
    ? recastSupportIssue(catalog, provider, state.recast_composite_tracking) : '';
  const modelProviderError = modelProviderIssue(model, provider, effect?.task);
  const providerIssue = providerReadinessIssue(selectedProvider);
  const cloudUnsupported =
    !!providerIssue ||
    !!modelProviderError ||
    (provider === 'comfy-cloud' &&
      !!effect &&
      [
        'text-to-image',
        'image-edit',
        'background-removal',
        'motion-transfer',
        'character-replacement',
        'audio-to-video',
      ].includes(effect.task));
  const filtered = presets.filter(
    (item) =>
      (category === 'All' || item.category === category) &&
      `${item.name} ${item.description} ${item.category}`
        .toLowerCase()
        .includes(query.toLowerCase().trim()),
  );
  const filteredUtilities = videoUtilities.filter(
    (item) =>
      (category === 'All' || category === (item.category || 'Video Utilities')) &&
      `${item.name} ${item.description}`.toLowerCase().includes(query.toLowerCase().trim()),
  );
  const fps = Number(state.replay_settings?.fps || model?.fixed_fps || model?.default_fps || 24),
    multiple = Number(model?.frame_multiple || 8),
    duration = state.frames / fps;
  const currentJob =
    selected &&
    ((detailHistory ? detailJobs : session.jobs).find((item) => item.id === selected.id) ||
      selected);
  useEffect(() => {
    const url = new URL(location.href);
    query ? url.searchParams.set('q', query) : url.searchParams.delete('q');
    category !== 'All'
      ? url.searchParams.set('category', category)
      : url.searchParams.delete('category');
    history.replaceState(null, '', url);
  }, [query, category]);
  useEffect(() => {
    const changed = () => {
      const params = new URLSearchParams(location.search);
      setQuery(params.get('q') || '');
      setCategory(params.get('category') || 'All');
      setRouteRevision((value) => value + 1);
    };
    window.addEventListener('popstate', changed);
    return () => window.removeEventListener('popstate', changed);
  }, []);
  useEffect(() => {
    if (!session.ready) return;
    const slug =
      location.pathname.split('/')[2] || new URLSearchParams(location.search).get('effect');
    const chosen =
      presets.find((item) => item.id === slug) || presets.find((item) => item.reference === slug);
    if (chosen) choose(chosen, false);
    else setLaunch(false);
  }, [session.ready, routeRevision]);
  function closeLaunch() {
    setDetailHistory(false);
    setLaunch(false);
    const url = new URL(location.href);
    url.pathname = '/apps';
    url.searchParams.delete('effect');
    history.pushState(null, '', url);
  }
  function choose(item: Preset, navigate = true) {
    const definition = catalog.effects.find((value) => value.id === item.effect);
    const selectedModel = catalog.models.find((value) => value.id === item.model);
    const requiredKind = definition?.requires_video ? 'video' : 'image';
    const same = state.preset_id === item.id;
    if (!same)
      update({
        preset_id: item.id,
        recast_reference_cleanup: item.id === 'recast',
        recast_composite_tracking: item.model === 'scail-2' && !(definition?.requires_mask && source?.kind === requiredKind && state.mask_asset_id) ? preferredRecastSupport(catalog, provider) : 'native',
        replay_settings: undefined,
        prompt: item.prompt,
        image_lighting: item.id === 'relight' ? { ...defaultImageLighting } : undefined,
        image_light_map_key: undefined,
        image_light_map_renderer: undefined,
        image_brightness: 0,
        billboard_video: item.id === 'billboard' ? { ...defaultBillboardVideo } : undefined,
        model_id: item.model,
        source_asset_id: source?.kind === requiredKind ? source.id : '',
        reference_asset_id: item.referenceLabel ? state.reference_asset_id : '',
        mask_asset_id:
          definition?.requires_mask && source?.kind === requiredKind ? state.mask_asset_id : '',
        trim_start: 0,
        image_preservation: 'none',
        image_edit_focus: 'full',
        audio_asset_id: definition?.requires_audio ? state.audio_asset_id : '',
        audio_start: definition?.requires_audio ? state.audio_start : 0,
        ...(definition?.requires_audio ? { ratio: '9:16' } : {}),
        frames: Number(selectedModel?.default_frames || 49),
        generate_audio: false,
        strength: item.effect === 'restyle' ? 0.4 : 0.65,
        restyle_method: 'latent',
      });
    setLaunch(true);
    if (navigate) {
      const url = new URL(location.href);
      const aliasIsAnotherId = presets.some(
        (value) => value.id !== item.id && value.id === item.reference,
      );
      url.pathname = `/apps/${aliasIsAnotherId ? item.id : item.reference || item.id}`;
      url.searchParams.delete('effect');
      history.pushState(null, '', url);
    }
    setError('');
  }
  useEffect(() => {
    if (!detailHistory || !preset) return;
    let active = true;
    let loading = false;
    const load = async () => {
      if (loading) return;
      loading = true;
      if (active) setHistoryLoading(true);
      try {
        const query = new URLSearchParams({ preset_id: preset.id });
        if (!['billboard', 'relight'].includes(preset.id)) query.set('operation', preset.effect);
        const pages = await Promise.all(
          Array.from({ length: Math.ceil(detailLimit / 500) }, (_, index) =>
            api<{ items: Job[]; total: number }>(
              `/apps/mini-apps/jobs?${query}&limit=${Math.min(500, detailLimit - index * 500)}&offset=${index * 500}`,
            ),
          ),
        );
        if (active) {
          setDetailJobs(pages.flatMap((page) => page.items));
          setDetailTotal(pages[0]?.total || 0);
          setHistoryError('');
        }
      } catch (reason) {
        if (active) setHistoryError((reason as Error).message);
      } finally {
        loading = false;
        if (active) setHistoryLoading(false);
      }
    };
    void load();
    const timer = setInterval(() => void load(), 2500);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [detailHistory, preset?.id, detailLimit]);

  async function reuse(job: Job) {
    setBusy(true);
    setError('');
    try {
      const context = job.app_context
        ? await api<{ document_snapshot: { state: Partial<Draft> } }>(`/jobs/${job.id}/app-context`)
        : null;
      const snapshot = context?.document_snapshot.state || {};
      const billboardVideoReuse = snapshot.preset_id === 'billboard' && job.request.effect_id === 'image-to-video';
      const item =
        (job.request.effect_id === 'relight-image' ? presets.find((value) => value.id === 'relight') : undefined) ||
        (billboardVideoReuse ? presets.find((value) => value.id === 'billboard') : undefined) ||
        presets.find(
          (value) => value.id === snapshot.preset_id && value.effect === job.request.effect_id,
        ) ||
        presets.find(
          (value) =>
            value.id === job.app_context?.step_id && value.effect === job.request.effect_id,
        ) ||
        presets.find((value) => value.effect === job.request.effect_id);
      if (!item)
        throw new Error(
          'This recorded operation has a separate utility page. Open it from Apps to reuse the result.',
        );
      const r = job.request;
      const preserved: (keyof JobRequest)[] = [
        'fps',
        'steps',
        'guidance',
        'negative_prompt',
        'encoding_quality',
        'mask_edit_margin',
        'preserve_outside_mask',
        'export_mask',
        'video_refinement',
        'motion_prompt',
        'pose_strength',
        'reference_strength',
        'pose_start_percent',
        'pose_end_percent',
        'image_prompt_mode',
        'image_layout',
        'image_preservation',
        'image_reference_megapixels',
        'character_adapter_id',
        'character_strength',
      ];
      let a = r.width,
        b = r.height;
      while (b) [a, b] = [b, a % b];
      const next: Draft = {
        ...initial,
        ...snapshot,
        preset_id: item.id,
        model_id: r.model_id,
        provider: r.provider,
        prompt: item.id === 'relight' && snapshot.image_lighting && (r.model_id === 'qwen-portrait-relight' ? portraitLightingPrompt : r.model_id === 'qwen-image-relight' ? qwenLightingPrompt : imageLightingPrompt)(snapshot.prompt || '', snapshot.image_lighting) === r.prompt ? snapshot.prompt || '' : r.prompt,
        image_lighting: item.id === 'relight' && snapshot.image_lighting && (r.model_id === 'qwen-portrait-relight' ? portraitLightingPrompt : r.model_id === 'qwen-image-relight' ? qwenLightingPrompt : imageLightingPrompt)(snapshot.prompt || '', snapshot.image_lighting) === r.prompt ? snapshot.image_lighting : null,
        source_asset_id: r.source_asset_id || '',
        reference_asset_id: r.reference_asset_id || r.reference_asset_ids?.[0] || '',
        mask_asset_id: r.mask_asset_id || '',
        recast_composite_tracking: r.recast_composite_tracking || 'native',
        recast_reference_cleanup: r.recast_reference_cleanup ?? false,
        image_preservation: r.image_preservation || 'none',
        image_edit_focus: r.image_edit_focus || 'full',
        image_brightness: r.image_brightness ?? 0,
        audio_asset_id: r.audio_asset_id || '',
        audio_start: r.audio_start || 0,
        audio_conditioning_strength: r.audio_conditioning_strength ?? 1,
        ratio: `${r.width / a}:${r.height / a}`,
        size: Math.max(r.width, r.height),
        frames: r.frames,
        trim_start: r.trim_start || 0,
        strength: r.strength,
        restyle_method: r.restyle_method || 'latent',
        seed: r.seed,
        batch_size: r.batch_size || 1,
        tracking: r.mask_tracking === false ? 'static' : r.mask_tracking_method || 'sam2',
        preserve_audio: r.preserve_audio,
        generate_audio: r.generate_audio,
        mask_dilation: r.mask_dilation,
        mask_feather: r.mask_feather,
        mask_edit_margin: r.mask_edit_margin ?? undefined,
        enhance_prompt: r.enhance_prompt,
        replay_settings: Object.fromEntries(
          preserved.filter((key) => r[key] !== undefined).map((key) => [key, r[key]]),
        ),
      };
      if (billboardVideoReuse) {
        if (!snapshot.source_asset_id || !snapshot.model_id || !snapshot.billboard_video)
          throw new Error('This historical video has no complete billboard project snapshot to restore. Its recorded video workflow remains exportable.');
        Object.assign(next, snapshot, {
          provider: r.provider,
          replay_settings: snapshot.replay_settings,
          billboard_video: { ...snapshot.billboard_video, model_id: r.model_id, prompt: r.prompt, frames: r.frames, fps: r.fps, seed: r.seed, generate_audio: r.generate_audio, enhance_prompt: r.enhance_prompt ?? true },
        });
      }
      if (!(await session.newDocument(next))) return;
      const document = await session.updateAndSave(next);
      if (!document) throw new Error('The reused settings could not be saved.');
      const aliasIsAnotherId = presets.some(
        (value) => value.id !== item.id && value.id === item.reference,
      );
      const url = new URL(location.href);
      url.pathname = `/apps/${aliasIsAnotherId ? item.id : item.reference || item.id}`;
      url.searchParams.set('document', document.id);
      url.searchParams.delete('job');
      history.pushState(null, '', url);
      setLaunch(true);
      setDetailHistory(false);
      setSelected(null);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function changeModel(id: string) {
    const next = compatible.find((item) => item.id === id);
    if (!next) return;
    if (state.image_brightness && !next.supports_image_brightness) {
      setError('Reset Post-render brightness to 0 before choosing a model without that operation.');
      return;
    }
    if (imageRegion && !next.supports_image_preservation) {
      setError('Remove the painted region before choosing a model without region preservation.');
      return;
    }
    if (state.image_edit_focus === 'masked-region' && !next.supports_region_focus) {
      setError('Turn off region focus before choosing a model without this capability.');
      return;
    }
    setError((current) => current.startsWith('Reset Post-render brightness to 0') ? '' : current);
    const frameMultiple = Number(next.frame_multiple || 8);
    update({
      replay_settings: undefined,
      model_id: id,
      restyle_method: next.restyle_methods?.some((method) => method.id === restyleMethod && (!method.effect_ids || method.effect_ids.includes(preset?.effect || ''))) ? restyleMethod : 'latent',
      reference_asset_id: preset?.id === 'relight' && id !== state.model_id ? '' : modelSupportsReference(next, effect?.task) ? state.reference_asset_id : '',
      ...(preset?.id === 'relight' ? { image_light_map_key: undefined, batch_size: 1, image_lighting: state.image_lighting || { ...defaultImageLighting } } : {}),
      frames: Math.min(
        Number(next.max_frames),
        Math.max(
          Number(next.min_frames || 9),
          Math.round(
            (duration * Number(next.fixed_fps || next.default_fps || 24) - 1) / frameMultiple,
          ) *
            frameMultiple +
            1,
        ),
      ),
      generate_audio: !!next.supports_audio && state.generate_audio,
    });
  }
  async function applyLightingMap() {
    if (!state.image_lighting) return;
    setBusy(true); setError('');
    try {
      const asset = await upload(await lightingMapFile(state.image_lighting));
      assets.add(asset);
      const saved = await session.updateAndSave({ reference_asset_id: asset.id, image_light_map_key: lightingMapKey(state.image_lighting), image_light_map_renderer: lightingMapVersion });
      if (!saved) throw new Error('The lighting map uploaded, but its project could not be saved.');
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }
  async function generate() {
    setBusy(true);
    setError('');
    try {
      if (!preset || !model || !effect || !operation?.available)
        throw new Error(operation?.reason || 'The selected workflow is not loaded.');
      if (cloudUnsupported)
        throw new Error(providerIssue || modelProviderError || 'Use Local ComfyUI for this workflow.');
      if (supportIssue || cleanupIssue) throw new Error(supportIssue || cleanupIssue);
      if (restyleMethod !== 'latent' && !restyleMethods.some((method) => method.id === restyleMethod))
        throw new Error('The saved transformation method is unavailable for this model and operation. Explicitly choose a supported method.');
      if (waterRestyle) {
        if (preset.id !== 'weather' || state.reference_asset_id || state.mask_asset_id) throw new Error('Water Simulation needs only the source video. Clear the saved reference or mask.');
        if (fps !== 24 || state.frames > 185) throw new Error('Water Simulation uses 24 FPS and at most 185 frames; shorten the interval explicitly.');
        if (!state.prompt.includes('ADD WATER') || !/Reference shows/i.test(state.prompt) || !/Edited shows/i.test(state.prompt)) throw new Error('Water Simulation needs ADD WATER, Reference shows… and Edited shows… in the visible prompt. Describe the dry source and the desired water effect.');
        const size = renderSize(model, state.ratio, state.size);
        if (Math.max(size.width, size.height) > 1920 || Math.min(size.width, size.height) > 1088) throw new Error('Water Simulation supports a canvas up to 1920 pixels on the long side and 1088 on the short side.');
      }
      if (unavailableModel)
        throw new Error(
          'The saved model no longer supports this operation. Explicitly choose a supported model in Generation settings.',
        );
      if (
        !imageOutput &&
        (!Number.isInteger(state.frames) ||
          state.frames < Number(model.min_frames || 9) ||
          state.frames > Number(model.max_frames) ||
          (state.frames - 1) % multiple)
      )
        throw new Error(
          `Choose ${model.min_frames || 9}–${model.max_frames} frames, in steps of ${multiple}.`,
        );
      if (model.fixed_fps && fps !== Number(model.fixed_fps))
        throw new Error(
          `This model now requires ${model.fixed_fps} FPS. Explicitly use its current defaults before generating.`,
        );
      if (needsAudio) {
        if (audio?.kind !== 'audio') throw new Error('Upload a speech recording first.');
        if (!Number.isFinite(state.audio_start) || state.audio_start < 0)
          throw new Error('Choose a valid audio start time.');
        if (duration + state.audio_start > (audio.duration || 0) + 0.001)
          throw new Error(
            'The selected video interval exceeds the recording. Reduce frames or choose an earlier audio start; audio is never silently extended.',
          );
      }
      if (!source || source.kind !== (effect.requires_video ? 'video' : 'image'))
        throw new Error(`Choose the required ${effect.requires_video ? 'video' : 'image'} first.`);
      if (preset.id === 'weather' && state.reference_asset_id) {
        if (!weatherFirstFrame && !modelSupportsReference(model, effect.task))
          throw new Error('This edited first-frame guide requires the Canny method. Select it or clear the saved guide.');
        if (weatherFirstFrame && (reference?.kind !== 'image' || reference.width !== source.width || reference.height !== source.height))
          throw new Error(`The edited starting frame must match the original video: ${source.width} × ${source.height}.`);
      }
      if (directionalRelight && (reference?.kind !== 'image' || (state.image_lighting && state.image_light_map_key !== lightingMapKey(state.image_lighting)))) throw new Error('Apply the current lighting map before generating. The selected map is explicit conditioning, not an output preview.');
      if (state.image_brightness && !model.supports_image_brightness) throw new Error('This model does not support the saved Post-render brightness adjustment. Select its supported Relight profile before generating.');
      if (preset.referenceLabel && reference?.kind !== 'image')
        throw new Error('Choose the required reference image.');
      if (effect.requires_mask && !model.mask_optional && !mask) throw new Error('Paint the region to edit first.');
      if (imageRegion && (!model.supports_image_preservation || !mask || mask.kind !== 'image' || mask.width !== source.width || mask.height !== source.height))
        throw new Error('Region painting requires a compatible model and a mask matching the original image dimensions.');
      if (state.image_edit_focus === 'masked-region' && (!paintRegion || !imageRegion || !model.supports_region_focus
          || state.image_preservation !== 'outside-mask' || state.reference_asset_id || state.replay_settings?.image_layout?.length))
        throw new Error('Region focus needs one source and an outside-mask edit, without extra references or layout boxes.');
      if (!state.prompt.trim() && !(preset.id === 'relight' && state.image_lighting)) throw new Error('Describe the requested result.');
      if (billboardVideo) {
        if (!billboardModel) throw new Error('Choose an available image-to-video model for the billboard video stage.');
        const issue = modelProviderIssue(billboardModel, provider, 'image-to-video');
        if (issue) throw new Error(issue);
        if (!billboardVideo.prompt.trim()) throw new Error('Describe the billboard timelapse movement.');
        if (!Number.isInteger(billboardVideo.frames) || billboardVideo.frames < Number(billboardModel.min_frames || 9) || billboardVideo.frames > Number(billboardModel.max_frames) || (billboardVideo.frames - 1) % Number(billboardModel.frame_multiple || 8))
          throw new Error('Choose a supported frame count for the billboard video model.');
        if (billboardModel.fixed_fps && billboardVideo.fps !== Number(billboardModel.fixed_fps)) throw new Error('The saved video FPS differs from the selected model. Explicitly reselect its current defaults.');
        if (state.batch_size !== 1) throw new Error('The billboard video sequence requires one composition. Select one variation explicitly.');
      }
      if (source.kind === 'video' && duration > (source.duration || 0) - state.trim_start + 0.001)
        throw new Error(
          'The selected duration exceeds the source interval. Reduce frames or explicitly fit the available interval.',
        );
      if (
        effect.requires_mask &&
        !model.native_mask_tracking &&
        selectedProvider?.supported_tracking_methods &&
        !selectedProvider.supported_tracking_methods.includes(state.tracking)
      )
        throw new Error(
          'The selected provider does not support this mask-tracking method. Choose another method or compute provider.',
        );
      const document = await session.save(true);
      if (!document) throw new Error('Save the draft before generating.');
      const request = renderRequest(model, {
        ...state.replay_settings,
        effect_id: effect.id,
        prompt: preset.id === 'relight' ? lightingPrompt(state.prompt, state.image_lighting) : state.prompt,
        enhance_prompt: waterRestyle ? false : state.enhance_prompt,
        provider,
        ...renderSize(model, state.ratio, state.size),
        ...(billboardVideo && billboardModel ? renderSize(billboardModel, state.ratio, state.size) : {}),
        ...(directionalRelight ? { ...imageRelightSize(Number(source.width), Number(source.height)), steps: 8, guidance: 1, negative_prompt: '', image_prompt_mode: 'expand' as const } : {}),
        ...(portraitRelight ? { ...portraitRelightSize(Number(source.width), Number(source.height)), steps: 4, guidance: 1, negative_prompt: '', image_prompt_mode: 'expand' as const } : {}),
        ...(imageRegion ? {
          width: Math.ceil(Number(source.width) / 16) * 16,
          height: Math.ceil(Number(source.height) / 16) * 16,
        } : {}),
        image_preservation: paintRegion
          ? imageRegion ? state.image_preservation || 'outside-mask' : 'none'
          : state.replay_settings?.image_preservation,
        image_edit_focus: paintRegion ? state.image_edit_focus || 'full' : state.replay_settings?.image_edit_focus,
        image_brightness: model.supports_image_brightness ? state.image_brightness ?? 0 : undefined,
        source_asset_id: source.id,
        audio_asset_id: needsAudio ? state.audio_asset_id : undefined,
        audio_start: needsAudio ? state.audio_start : 0,
        ...(model.supports_audio_conditioning_controls
          ? { audio_conditioning_strength: state.audio_conditioning_strength ?? 1 }
          : {}),
        reference_asset_ids:
          !directionalRelight && imageOutput && referenceLabel && state.reference_asset_id
            ? [state.reference_asset_id]
            : [],
        reference_asset_id:
          directionalRelight ? state.reference_asset_id : !imageOutput && referenceLabel ? state.reference_asset_id || undefined : undefined,
        mask_asset_id: effect.requires_mask || imageRegion ? state.mask_asset_id : undefined,
        ...(model.id === 'scail-2' ? { recast_composite_tracking: state.mask_asset_id ? 'native' : state.recast_composite_tracking || 'native', recast_reference_cleanup: recastReferenceCleanup } : {}),
        frames: imageOutput ? 1 : state.frames,
        fps: imageOutput ? 1 : fps,
        trim_start: source.kind === 'video' ? state.trim_start : 0,
        strength: nativeImageRelight || cannyRestyle || waterRestyle ? 1 : state.strength,
        restyle_method: waterRestyle ? 'water' : cannyRestyle ? 'canny' : 'latent',
        ...(cannyRestyle ? { steps: 8, guidance: 1, video_refinement: 'two-stage' } : {}),
        ...(waterRestyle ? { steps: 8, guidance: 1, video_refinement: 'single', negative_prompt: '', audio_mode: state.preserve_audio ? 'source' : 'silent' } : {}),
        seed: state.seed,
        batch_size: !nativeImageRelight && imageOutput && preset.effect === 'edit-image' ? state.batch_size : 1,
        mask_tracking: state.tracking !== 'static',
        mask_tracking_method: state.tracking,
        mask_dilation: state.mask_dilation,
        mask_feather: state.mask_feather,
        ...(model.native_mask_tracking ? { mask_edit_margin: state.mask_edit_margin ?? 12, mask_dilation: 0 } : {}),
        preserve_audio: needsAudio ? true : state.preserve_audio,
        generate_audio:
          !waterRestyle && !needsAudio && !imageOutput && !!model.supports_audio && state.generate_audio,
      });
      if (billboardVideo && billboardModel) {
        const video = renderRequest(billboardModel, {
          effect_id: 'image-to-video', prompt: billboardVideo.prompt, provider,
          width: request.width, height: request.height, frames: billboardVideo.frames,
          fps: billboardVideo.fps, seed: billboardVideo.seed,
          generate_audio: billboardVideo.generate_audio, preserve_audio: false,
          enhance_prompt: billboardVideo.enhance_prompt,
        });
        await billboardWorkflow.start(document, request, video);
        return;
      }
      const job = await post<Job>(`/apps/mini-apps/documents/${document.id}/jobs`, {
        expected_revision: document.revision,
        operation: effect.id,
        request,
        step_id: preset.id,
      });
      setSelected(job);
      await session.refreshJobs();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function fitInterval() {
    const input = needsAudio ? audio : source;
    const start = needsAudio ? state.audio_start : state.trim_start;
    if (!input?.duration || !model) return;
    const frames =
      Math.floor(
        (Math.min(input.duration - start, (waterRestyle ? 185 : Number(model.max_frames)) / fps) * fps - 1 + 0.00001) /
          multiple,
      ) *
        multiple +
      1;
    if (frames < Number(model.min_frames || 9))
      setError(
        'This interval is too short for the model. Choose a longer recording or an earlier start.',
      );
    else update({ frames });
  }
  const failure = error || session.error || assets.error;
  return (
    <main className={`mini-apps ${launch ? 'mini-detail-page' : ''}`}>
      {!launch && (
        <>
          <header className="mini-heading">
            <div>
              <Icon name="grid" size={26} />
              <h1>
                Welcome to <span>OpenFrame apps</span>
              </h1>
              <p>
                Image edits, motion and video effects — ready to run with real open-source
                workflows.
              </p>
            </div>
            <div className="mini-heading-actions">
              <button
                className={tab === 'explore' ? 'active' : ''}
                onClick={() => setTab('explore')}
              >
                Explore
              </button>
              <button
                className={tab === 'generations' ? 'active' : ''}
                onClick={() => setTab('generations')}
              >
                My generations
              </button>
              <button aria-label="Compute settings" onClick={onSettings}>
                <Icon name="settings" />
              </button>
            </div>
          </header>
          <div className="mini-toolbar">
            <div className="mini-categories" aria-label="Effect categories">
              {categories.map((value) => (
                <button
                  key={value}
                  className={category === value ? 'active' : ''}
                  onClick={() => {
                    setCategory(value);
                    setTab('explore');
                  }}
                >
                  {value}
                </button>
              ))}
            </div>
            <label className="mini-search">
              <Icon name="search" size={17} />
              <input
                aria-label="Search effects"
                placeholder="Search apps"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              {query && (
                <button aria-label="Clear search" onClick={() => setQuery('')}>
                  <Icon name="close" size={14} />
                </button>
              )}
            </label>
          </div>
          {failure && !launch && (
            <p className="mini-error" role="alert">
              {failure}
            </p>
          )}
          {tab === 'generations' ? (
            <section className="mini-generations">
              <h2>My generations</h2>
              <WorkspaceHistory
                jobs={session.jobs}
                total={session.jobTotal}
                onSelect={setSelected}
                onMore={session.loadMoreJobs}
              />
            </section>
          ) : (
            <>
              {preset && (
                <button className="mini-resume" onClick={() => choose(preset)}>
                  <Icon name="clock" size={16} />
                  <span>Continue your {preset.name} draft</span>
                  <Icon name="arrow" size={16} />
                </button>
              )}
              {categories
                .slice(1)
                .filter((value) => category === 'All' || value === category)
                .map((group) => {
                  const items = filtered.filter((item) => item.category === group);
                  return (
                    items.length > 0 && (
                      <section className="mini-category-section" key={group}>
                        <header>
                          <div>
                            <h2>{group}</h2>
                            <p>
                              {group === 'Portrait & Style'
                                ? 'Reimagine your photographs with image-conditioned edits'
                                : group === 'Products & Images'
                                  ? 'Prepare product images and turn them into moving shots'
                                  : group === 'Motion & Characters'
                                    ? 'Use actual source images, poses and performance footage'
                                    : 'Transform your footage with controlled video workflows'}
                            </p>
                          </div>
                          {category === 'All' && (
                            <button onClick={() => setCategory(group)}>
                              See all
                              <Icon name="arrow" size={15} />
                            </button>
                          )}
                        </header>
                        <div className="mini-card-grid">
                          {items.map((item) => (
                            <button
                              className="mini-card"
                              key={item.id}
                              onClick={() => choose(item)}
                            >
                              <div className="mini-card-media">
                                <ReferenceMedia
                                  item={{
                                    title: item.name,
                                    poster: item.poster,
                                    video: item.video,
                                  }}
                                />
                                <span className="mini-media-credit">
                                  {item.effect === 'speak'
                                    ? 'Portrait reference only'
                                    : item.own
                                      ? 'OpenFrame render'
                                      : item.illustration
                                        ? 'Illustrative render'
                                        : 'Reference example'}
                                </span>
                                <span className="mini-card-run">
                                  <Icon name="play" size={14} />
                                  Run
                                </span>
                              </div>
                              <strong>{item.name}</strong>
                              <p>{item.description}</p>
                              <span className="mini-card-try">
                                Try now
                                <Icon name="arrow" size={14} />
                              </span>
                            </button>
                          ))}
                        </div>
                      </section>
                    )
                  );
                })}
              {filteredUtilities.length > 0 && (
                <section className="mini-category-section">
                  <header>
                    <div>
                      <h2>{category === 'All' ? 'Image & Video Tools' : category}</h2>
                      <p>Dedicated canvas, timing and scene-to-scene operations</p>
                    </div>
                  </header>
                  <div className="mini-card-grid">
                    {filteredUtilities.map((item) => (
                      <a
                        className="mini-card mini-utility-card"
                        href={`/apps/${item.id}`}
                        key={item.id}
                      >
                        <div className="mini-card-media">
                          <Icon name={item.icon} size={48} />
                          {item.video && (
                            <ReferenceMedia
                              item={{ title: item.name, video: item.video, poster: item.poster }}
                            />
                          )}
                          <span className="mini-media-credit">{item.badge}</span>
                        </div>
                        <strong>{item.name}</strong>
                        <p>{item.description}</p>
                        <span className="mini-card-try">
                          Open tool
                          <Icon name="arrow" size={14} />
                        </span>
                      </a>
                    ))}
                  </div>
                </section>
              )}
              {!filtered.length && !filteredUtilities.length && (
                <div className="mini-empty">
                  <Icon name="search" size={30} />
                  <h2>No effects match “{query}”</h2>
                  <button
                    onClick={() => {
                      setQuery('');
                      setCategory('All');
                    }}
                  >
                    Clear filters
                  </button>
                </div>
              )}
              <p className="mini-gallery-note">
                A curated set of implemented workflows. Public reference examples show the visual
                idea, not results from these open-source models. Prompt presets are not separately
                trained effect models.
              </p>
            </>
          )}
        </>
      )}
      {launch && preset && (
        <section className={`mini-launch mini-detail-${preset.id}`}>
          <nav className="mini-breadcrumb" aria-label="Breadcrumb">
            <button onClick={closeLaunch}>Apps</button>
            <span>/</span>
            <span>{preset.name}</span>
            <button
              onClick={() => {
                setDetailHistory(!detailHistory);
                setDetailLimit(100);
              }}
            >
              {detailHistory ? 'Reference example' : 'My generations'}
            </button>
            <button className="mini-detail-compute" onClick={onSettings}>
              Compute settings
            </button>
          </nav>
          <div className="mini-launch-grid">
            {detailHistory ? (
              <aside className="mini-detail-history">
                <h3>{preset.name} generations</h3>
                <p>Only this tool’s runs, across your saved projects.</p>
                {historyError && (
                  <p className="mini-error" role="alert">
                    {historyError}
                  </p>
                )}
                {historyLoading && !detailJobs.length ? (
                  <p role="status">Loading generations…</p>
                ) : (
                  <WorkspaceHistory
                    jobs={detailJobs}
                    total={detailTotal}
                    onSelect={setSelected}
                    onMore={() => setDetailLimit((value) => value + 100)}
                  />
                )}
              </aside>
            ) : (
              <aside>
                <ReferenceMedia item={mediaFor(preset, true)} />
                <h3>{preset.description}</h3>
                <p>{preset.note}</p>
                <small>
                  {preset.own
                    ? 'Actual OpenFrame output.'
                    : preset.illustration
                      ? 'Illustrative generated scene.'
                      : 'Public Higgsfield reference example; not an OpenFrame output.'}
                </small>
                {preset.source_url && (
                  <a href={preset.source_url} target="_blank" rel="noreferrer">
                    View reference
                    <Icon name="external" size={13} />
                  </a>
                )}
              </aside>
            )}
            <div
              className="mini-form"
              role="form"
              aria-label={`${preset.name} generation settings`}
            >
              <div className="mini-form-heading">
                <h1>{preset.name}</h1>
                <p>{preset.description}</p>
              </div>
              <div className="mini-source-grid">
                <SourceSlot
                  asset={source}
                  title={
                    needsAudio
                      ? 'Upload Portrait'
                      : effect?.requires_video
                        ? 'Upload Video'
                        : 'Upload Image'
                  }
                  detail={
                    effect?.requires_video
                      ? 'MP4, MOV or from your workspace'
                      : 'PNG, JPG, WebP or from your workspace'
                  }
                  onChoose={() => setPicker('source')}
                  onClear={() => update({ source_asset_id: '', mask_asset_id: '', image_preservation: 'none', image_edit_focus: 'full', trim_start: 0 })}
                />
                {needsAudio && (
                  <section className="mini-audio-input" aria-label="Speech recording">
                    <button type="button" onClick={() => setPicker('audio')}>
                      <Icon name="sound" size={22} />
                      <strong>{audio ? 'Change recording' : 'Upload speech recording'}</strong>
                      <span>WAV, MP3 or another supported audio file</span>
                    </button>
                    {audio && (
                      <>
                        <strong className="mini-audio-name">{audio.name}</strong>
                        <audio controls src={mediaUrl(audio)} />
                        <div>
                          <span>{audio.duration?.toFixed(2)}s recording</span>
                          <button
                            type="button"
                            onClick={() => update({ audio_asset_id: '', audio_start: 0 })}
                          >
                            Remove
                          </button>
                        </div>
                      </>
                    )}
                    <label>
                      Audio start (seconds)
                      <input
                        type="number"
                        min={0}
                        step={0.1}
                        max={audio?.duration}
                        value={state.audio_start}
                        onChange={(event) => update({ audio_start: Number(event.target.value) })}
                      />
                    </label>
                    <small>
                      {duration.toFixed(2)}s of the original recording will accompany the generated
                      video.
                    </small>
                    {model?.supports_audio_conditioning_controls ? (
                      <label>
                        Audio conditioning · {(state.audio_conditioning_strength ?? 1).toFixed(2)}
                        <input
                          type="range"
                          min={0}
                          max={2}
                          step={0.05}
                          value={state.audio_conditioning_strength ?? 1}
                          onChange={(event) =>
                            update({ audio_conditioning_strength: Number(event.target.value) })
                          }
                        />
                      </label>
                    ) : null}
                    {audio && (
                      <button type="button" onClick={fitInterval}>
                        Fit recording within model limit
                      </button>
                    )}
                  </section>
                )}
                {referenceLabel && (
                  <SourceSlot
                    asset={reference}
                    title={referenceLabel}
                    optional={!directionalRelight && !preset.referenceLabel}
                    detail={directionalRelight ? "Required opaque PNG conditioning map. Apply the lighting controls below to create it." : weatherFirstFrame ? `A reviewed full ${source?.width || 'native-width'} × ${source?.height || 'native-height'} edit at the selected source start. Both native passes condition on it; later identity is not guaranteed.` : "A separate image used by the model"}
                    onChoose={() => setPicker('reference')}
                    onClear={() => update({ reference_asset_id: '' })}
                  />
                )}
              </div>
              {(effect?.requires_mask || (paintRegion && !!model?.supports_image_preservation)) && (
                <div className="mini-mask-row">
                  <button type="button" disabled={!source} onClick={() => setPainting(true)}>
                    <Icon name="brush" size={16} />
                    {mask ? 'Edit painted mask' : model?.mask_optional ? 'Override automatic performer selection' : paintRegion ? 'Paint an optional region' : 'Paint region to change'}
                  </button>
                  {mask && (
                    <>
                      <img src={mask.url} alt="Selected edit mask" />
                      <button type="button" onClick={() => update({ mask_asset_id: '', image_preservation: 'none', image_edit_focus: 'full' })}>
                        Remove mask
                      </button>
                    </>
                  )}
                </div>
              )}
              {model?.id === 'scail-2' && <label className="mini-restored-settings">
                <input type="checkbox" aria-label="Clean reference edges" checked={recastReferenceCleanup}
                  disabled={!cleanupAvailable && !recastReferenceCleanup}
                  onChange={event => update({ recast_reference_cleanup: event.target.checked })} /> Clean reference edges<br/>
                <small>Removes background color from the character reference edge before generation. Adds CPU matting; hands and fine details can still change.</small>
                {cleanupIssue && <small role="alert">{cleanupIssue}</small>}
              </label>}
              {model?.id === 'scail-2' && (
                <label className="mini-restored-settings">Final composite tracking
                  <select value={mask ? 'native' : state.recast_composite_tracking || 'native'}
                    disabled={!!mask} onChange={e => update({ recast_composite_tracking: e.target.value as 'native' | 'official' | 'official-union' })}>
                    <option value="official-union" disabled={!unionSupportAvailable}>Source + generated performer support</option>
                    <option value="official" disabled={!officialSupportAvailable}>Official source performer support · legacy</option>
                    <option value="native">Native SAM3.1 · original / manual mask</option>
                  </select>
                  <small>{mask ? 'The painted override uses native tracking for both conditioning and final support.' : 'Source + generated support combines both performer silhouettes for final compositing. Native SCAIL conditioning and generated detail stay unchanged; halos already present in the generated video may remain. The exported mask shows the actual support.'}</small>
                  {supportIssue && <small role="alert">{supportIssue}</small>}
                  {!mask && !officialSupportAvailable && !supportIssue && <small>Official support needs the isolated Linux CUDA runtime and a successful Local connection check in Settings.</small>}
                </label>
              )}
              {paintRegion && (
                <p className="mini-restored-settings">
                  {imageRegion
                    ? state.image_preservation === 'inside-mask'
                      ? `This saved recipe protects the painted region. Original ${source?.width} × ${source?.height} canvas retained.`
                      : `Only the painted region changes; original pixels outside it stay unchanged. Original ${source?.width} × ${source?.height} canvas retained.`
                    : 'Without a mask, the instructions apply to the whole image.'}
                </p>
              )}
              {paintRegion && imageRegion && (
                <label className="mini-restored-settings">
                  <input
                    type="checkbox"
                    checked={state.image_edit_focus === 'masked-region'}
                    disabled={state.image_edit_focus !== 'masked-region' && (!model?.supports_region_focus || state.image_preservation !== 'outside-mask' || !!state.reference_asset_id || !!state.replay_settings?.image_layout?.length)}
                    onChange={(event) => update({ image_edit_focus: event.target.checked ? 'masked-region' : 'full' })}
                  />{' '}Focus on painted region
                  <small>Uses a 1024 × 1024 crop for small-area detail, then fits it back into the original canvas. Protected pixels stay unchanged. Requires one source without layout boxes.</small>
                </label>
              )}
              {!!model?.native_mask_tracking && (
                <p className="mini-restored-settings">
                  Native SAM3.1 tracks one performer and identifies the person in the character image.
                  The painted override selects the performer at the start of the chosen interval.
                  The result preserves the surrounding plate; the separate silent preview shows raw generation.
                  Describe the final scene and held objects in the caption below.
                </p>
              )}
              {directionalRelight && <section className="mini-restored-settings"><strong>Released Qwen lighting-map workflow</strong><p>One output at approximately 1 MP, retaining the source aspect with the native VAE’s small edge crop. No exact original-pixel preservation.</p>{source?.width && source.height && <small>Output: {imageRelightSize(source.width, source.height).width} × {imageRelightSize(source.width, source.height).height}</small>}{reference && <img src={mediaUrl(reference)} alt="Actual lighting-map conditioning image, not a relit preview" style={{ width: 120, display: 'block' }} />}{state.image_lighting && <><p>Adapter direction: {qwenLightDirection(state.image_lighting)}. {state.image_light_map_key === lightingMapKey(state.image_lighting) ? 'Current map saved.' : 'Apply the changed controls to save a new map.'}</p><button type="button" disabled={busy} onClick={() => void applyLightingMap()}>Apply lighting map</button></>}</section>}
              {portraitRelight && <section className="mini-restored-settings"><strong>Portrait relighting · restored background</strong><p>Use one person’s photo. The original background is restored around the relit person; fine facial and hair detail may change. Post-render brightness also adjusts the restored background.</p>{source?.width && source.height && <small>Native canvas: {portraitRelightSize(source.width, source.height).width} × {portraitRelightSize(source.width, source.height).height} · one image · raw render also saved.</small>}</section>}
              {preset.id === 'relight' && <ImageRelightControls mapConditioned={directionalRelight} portraitConditioned={portraitRelight} value={state.image_lighting} onChange={(image_lighting) => update({ image_lighting })} postBrightness={state.image_brightness ?? 0} onPostBrightness={model?.supports_image_brightness ? (image_brightness) => { update({ image_brightness }); if (image_brightness === 0) setError((current) => current.startsWith('Reset Post-render brightness to 0') ? '' : current); } : undefined} />}
              {preset.effect !== 'remove-background' && (
                <>
                  <label>
                    {preset.id === 'relight' && state.image_lighting ? 'Additional instructions (optional)' : billboardVideo ? '1 · Billboard composition instructions' : 'Instructions'}
                    <textarea
                      rows={4}
                      value={state.prompt}
                      maxLength={preset.id === 'relight' && state.image_lighting ? 15000 : 16000}
                      onChange={(event) => update({ prompt: event.target.value })}
                    />
                  </label>
                  {preset.id === 'relight' && state.image_lighting && <details><summary>Exact lighting instructions sent with the image</summary><p style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{lightingPrompt(state.prompt, state.image_lighting)}</p></details>}
                </>
              )}
              {preset.id === 'billboard' && <BillboardStages value={state.billboard_video} onChange={(billboard_video) => update({ billboard_video })} catalog={catalog} provider={provider} workflow={billboardWorkflow} onJob={setSelected} />}
              {billboardVideo && billboardModel && <small>Both stages use {renderSize(billboardModel, state.ratio, state.size).width} × {renderSize(billboardModel, state.ratio, state.size).height}; the composition is the video’s opening image.</small>}
              <div className="mini-launch-footer">
                <span>
                  {session.saving
                    ? 'Saving draft…'
                    : session.document
                      ? 'Draft saved locally'
                      : 'New local draft'}
                </span>
                <button
                  className="mini-generate"
                  disabled={
                    busy ||
                    !operation?.available ||
                    !!cleanupIssue ||
                    (directionalRelight && (!source || !reference || !!state.image_lighting && state.image_light_map_key !== lightingMapKey(state.image_lighting))) ||
                    cloudUnsupported ||
                    !session.ready ||
                    (billboardVideo && (!billboardWorkflow.ready || billboardWorkflow.busy || billboardWorkflow.active || !billboardModel || !!modelProviderIssue(billboardModel, provider, 'image-to-video'))) ||
                    (needsAudio && (!source || !audio || unavailableModel))
                  }
                  type="button"
                  onClick={() => void generate()}
                >
                  {busy ? 'Submitting…' : billboardVideo ? billboardWorkflow.items.some((item) => item.status === 'succeeded') ? 'Generate new composition + video' : 'Generate billboard video' : `Generate ${imageOutput ? 'image' : 'video'}`}
                  <Icon name="arrow" size={16} />
                </button>
              </div>
              {providerIssue && (
                <p className="muted small" role="status">
                  {providerIssue}
                </p>
              )}
              {!providerIssue && cloudUnsupported && (
                <p className="mini-error">
                  {modelProviderError ||
                    'This workflow requires Local ComfyUI. Choose a compatible provider in Generation settings below.'}
                </p>
              )}
              {failure && (
                <p className="mini-error" role="alert">
                  {failure}
                </p>
              )}
              {unavailableModel && (
                <p className="mini-error">
                  The saved model is unsupported. Choose a compatible model below;
                  saved settings are not silently substituted.
                </p>
              )}
              {state.replay_settings && (
                <p className="mini-restored-settings">
                  Recorded model settings restored.
                  <button onClick={() => update({ replay_settings: undefined })}>
                    Use current model defaults
                  </button>
                </p>
              )}
              <details className="mini-advanced" open={needsAudio}>
                <summary>
                  Generation settings · {model?.name || 'Loading model'}
                  {!imageOutput ? ` · ${duration.toFixed(2)}s` : ''}
                </summary>
                <div className="mini-fields">
                  <label>
                    Model
                    <select
                      value={unavailableModel ? '' : model?.id || ''}
                      onChange={(event) => changeModel(event.target.value)}
                    >
                      {unavailableModel && (
                        <option value="" disabled>
                          Choose a supported model
                        </option>
                      )}
                      {compatible.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
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
                </div>
                {preset.effect !== 'remove-background' && !nativeImageRelight && (
                  <div className="mini-fields">
                    <label>
                      Aspect ratio
                      <select
                        value={state.ratio}
                        disabled={imageRegion}
                        onChange={(event) => update({ ratio: event.target.value })}
                      >
                        {!['16:9', '9:16', '1:1', '4:3', '3:4'].includes(state.ratio) && (
                          <option value={state.ratio}>{state.ratio} · recorded</option>
                        )}
                        {['16:9', '9:16', '1:1', '4:3', '3:4'].map((value) => (
                          <option key={value}>{value}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Longest side
                      <select
                        value={state.size}
                        disabled={imageRegion}
                        onChange={(event) => update({ size: Number(event.target.value) })}
                      >
                        {![512, 768, 1024].includes(state.size) && (
                          <option value={state.size}>{state.size}px · recorded</option>
                        )}
                        {[512, 768, 1024].map((value) => (
                          <option key={value} value={value}>
                            {value}px
                          </option>
                        ))}
                      </select>
                    </label>
                    {imageOutput && (
                      <label>
                        Variations
                        <select
                          value={state.batch_size}
                          onChange={(event) => update({ batch_size: Number(event.target.value) })}
                        >
                          {(billboardVideo ? [...new Set([1, state.batch_size])] : [1, 2, 3, 4]).map((value) => (
                            <option key={value}>{value}</option>
                          ))}
                        </select>
                      </label>
                    )}
                  </div>
                )}
                {!imageOutput && (
                  <div className="mini-fields">
                    <label>
                      Frames
                      <input
                        type="number"
                        min={Number(model?.min_frames || 9)}
                        max={waterRestyle ? 185 : Number(model?.max_frames || 241)}
                        step={multiple}
                        value={state.frames}
                        onChange={(event) => update({ frames: Number(event.target.value) })}
                      />
                      <small>
                        {duration.toFixed(2)} seconds at {fps}fps
                        {model?.fixed_fps ? ' (model fixed)' : ''}
                      </small>
                    </label>
                    {effect?.requires_video && (
                      <label>
                        Source start
                        <input
                          type="number"
                          min={0}
                          step={0.1}
                          value={state.trim_start}
                          onChange={(event) =>
                            update({ trim_start: Number(event.target.value), mask_asset_id: '' })
                          }
                        />
                        <small>Changing start clears the painted mask.</small>
                      </label>
                    )}
                  </div>
                )}
                {source?.kind === 'video' && (
                  <div className="mini-interval">
                    <span>
                      Source: {(source.duration || 0).toFixed(2)}s total. Selected: {state.trim_start.toFixed(2)}–{(state.trim_start + duration).toFixed(2)}s ({duration.toFixed(2)}s).
                      {' '}Fit uses at most {((waterRestyle ? 185 : Number(model?.max_frames || 241)) / fps).toFixed(2)}s after the start and rounds down to supported frames; it does not process a longer source in full.
                    </span>
                    <button type="button" onClick={fitInterval}>
                      Fit within available / model limit
                    </button>
                  </div>
                )}
                {imageRegion && (
                  <label>
                    Region edge feather · pixels
                    <input type="number" min={0} max={32} value={state.mask_feather}
                      onChange={(event) => update({ mask_feather: Number(event.target.value) })} />
                  </label>
                )}
                {effect?.requires_mask && !model?.native_mask_tracking && (
                  <div className="mini-fields">
                    <label>
                      Track mask
                      <select
                        value={state.tracking}
                        onChange={(event) => update({ tracking: event.target.value })}
                      >
                        <option value="sam2">SAM2</option>
                        <option value="flow">Optical flow</option>
                        <option value="static">Static</option>
                      </select>
                    </label>
                    <label>
                      Generation margin
                      <input
                        type="number"
                        min={0}
                        max={64}
                        value={state.mask_dilation}
                        onChange={(event) => update({ mask_dilation: Number(event.target.value) })}
                      />
                    </label>
                    <label>
                      Edge feather
                      <input
                        type="number"
                        min={0}
                        max={32}
                        value={state.mask_feather}
                        onChange={(event) => update({ mask_feather: Number(event.target.value) })}
                      />
                    </label>
                  </div>
                )}
                {!!model?.native_mask_tracking && (
                  <div className="mini-fields">
                    <label>
                      Final edit margin · pixels
                      <input type="number" min={0} max={64} value={state.mask_edit_margin ?? 12}
                        onChange={(event) => update({ mask_edit_margin: Number(event.target.value) })} />
                    </label>
                    <label>
                      Final edge feather · pixels
                      <input type="number" min={0} max={32} value={state.mask_feather}
                        onChange={(event) => update({ mask_feather: Number(event.target.value) })} />
                    </label>
                  </div>
                )}
                {!!restyleMethods.length && (
                  <label>
                    Transformation method
                    <select value={restyleMethod} onChange={(event) => update({ restyle_method: event.target.value as 'latent' | 'canny' | 'water', ...(event.target.value === 'water' ? { fps: 24, strength: 1, enhance_prompt: false, generate_audio: false, reference_asset_id: '', mask_asset_id: '', replay_settings: undefined } : {}) })}>
                      {restyleMethods.map((method) => <option key={method.id} value={method.id}>{method.label}</option>)}
                    </select>
                    <small>{restyleMethods.find((method) => method.id === restyleMethod)?.hint}</small>
                    {waterRestyle && <small>Official single-stage Water recipe: 8 steps, CFG/source guidance 1, 24 FPS, up to 185 frames. No mask, reference image or prompt enhancement. Requires authorized access and the installed Water-Simulation adapter. A 49-frame private comparison retained the overall McLaren silhouette and arm motion with visible rain and wet surfaces; small-detail and parking-line drift remained. Exact preservation is not guaranteed. In the prompt, include ADD WATER, Reference shows… and Edited shows…; your text is sent unchanged. Keep source audio below, or turn it off for silence.</small>}
                    {cannyRestyle && <small>Uses every source frame to guide structure, with full regeneration and two-stage refinement. Review the weather and geometry in the result.</small>}
                  </label>
                )}
                {!cannyRestyle && !waterRestyle && (effect?.task === 'restyle' || effect?.task === 'inpaint') && (
                  <label>
                    {model?.family === 'Wan'
                      ? 'Source guidance'
                      : effect.task === 'restyle'
                        ? 'Transformation strength'
                        : 'Source guidance'}
                    <input
                      type="range"
                      min={0.05}
                      max={1}
                      step={0.05}
                      value={state.strength}
                      onChange={(event) => update({ strength: Number(event.target.value) })}
                    />
                    <small>
                      {state.strength.toFixed(2)} ·{' '}
                      {model?.family === 'Wan'
                        ? 'Higher values preserve more of the source.'
                        : 'Changes how strongly the model follows or transforms the source.'}
                    </small>
                  </label>
                )}
                <div className="mini-fields">
                  <label>
                    Seed
                    <input
                      type="number"
                      min={-1}
                      max={4294967295}
                      value={state.seed}
                      onChange={(event) => update({ seed: Number(event.target.value) })}
                    />
                    <small>−1 selects and records a random seed.</small>
                  </label>
                  {!imageOutput && (
                    <div className="mini-checks">
                      {supportsEnhancement && !waterRestyle && (
                        <label>
                          <input
                            type="checkbox"
                            checked={state.enhance_prompt ?? effect?.task !== 'inpaint'}
                            onChange={(event) => update({ enhance_prompt: event.target.checked })}
                          />
                          Enhance prompt
                        </label>
                      )}
                      {source?.kind === 'video' && (
                        <label>
                          <input
                            type="checkbox"
                            checked={state.preserve_audio}
                            onChange={(event) => update({ preserve_audio: event.target.checked })}
                          />
                          Keep source audio
                        </label>
                      )}
                      {!!model?.supports_audio && !waterRestyle && !effect?.requires_video && !needsAudio && (
                        <label>
                          <input
                            type="checkbox"
                            checked={state.generate_audio}
                            onChange={(event) => update({ generate_audio: event.target.checked })}
                          />
                          Generate native audio
                        </label>
                      )}
                    </div>
                  )}
                </div>
              </details>
              {!operation?.available && (
                <p className="mini-error">
                  {operation?.reason || 'Waiting for the implemented workflow catalog.'}
                </p>
              )}
            </div>
          </div>
        </section>
      )}
      {picker && (
        <AssetPicker
          title={
            picker === 'audio'
              ? 'Choose speech recording'
              : picker === 'reference'
                ? referenceLabel || 'Reference image'
                : effect?.requires_video
                  ? 'Choose source video'
                  : 'Choose source image'
          }
          kind={
            picker === 'audio'
              ? 'audio'
              : picker === 'source' && effect?.requires_video
                ? 'video'
                : 'image'
          }
          assets={assets.assets}
          onAdded={assets.add}
          onClose={() => setPicker(null)}
          onSelect={(asset) =>
            picker === 'audio'
              ? update({ audio_asset_id: asset.id, audio_start: 0 })
              : picker === 'source'
                ? update({ source_asset_id: asset.id, mask_asset_id: '', image_preservation: 'none', image_edit_focus: 'full', trim_start: 0 })
                : update({ reference_asset_id: asset.id })
          }
        />
      )}
      {painting && source && (
        <MaskEditor
          asset={source}
          existingMask={mask}
          startTime={state.trim_start}
          onSave={(asset) => {
            assets.add(asset);
            update({ mask_asset_id: asset.id, recast_composite_tracking: 'native', ...(paintRegion ? { image_preservation: state.image_preservation === 'inside-mask' ? 'inside-mask' : 'outside-mask' } : {}) });
            setPainting(false);
          }}
          onClose={() => setPainting(false)}
        />
      )}
      {currentJob && (
        <ResultDialog
          job={currentJob}
          reuseLabel={preset?.id === 'billboard' ? 'Reuse billboard project' : 'Reuse settings'}
          onClose={() => setSelected(null)}
          onRefresh={() => void session.refreshJobs()}
          onReuse={
            (currentJob.request.effect_id === 'relight-image' || presets.some((item) => item.effect === currentJob.request.effect_id) || (preset?.id === 'billboard' && currentJob.request.effect_id === 'image-to-video'))
              ? () => void reuse(currentJob)
              : undefined
          }
        />
      )}
    </main>
  );
}
