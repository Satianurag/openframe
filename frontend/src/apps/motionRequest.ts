import type { Asset, Catalog } from '../types';
import { boundedVideoFrames } from './engine-apps-shared';
import { modelSupportsReference, renderRequest, renderSize } from './renderRequest';
import { recastReferenceCleanupIssue } from './recastSupport';
import { motionDefaults } from './MotionControls';
import type { MotionConditioning } from './MotionControls';

export type MotionOptions = {
  operation: 'motion-transfer' | 'character-replacement' | 'replace-object';
  modelId: string;
  provider: string;
  source?: Asset;
  reference?: Asset;
  maskAssetId?: string;
  recastCompositeTracking?: 'native' | 'official' | 'official-union';
  recastReferenceCleanup?: boolean;
  vaceReferenceMode?: 'appearance' | 'first-frame';
  inpaintReferenceMode?: 'edited-first-frame' | null;
  styleName?: string;
  stylePrompt?: string;
  styleAssetId?: string;
  styleModelId?: string;
  preparedCharacterId?: string;
  prompt?: string;
  promptEnabled: boolean;
  enhancePrompt?: boolean;
  duration: number;
  fps?: number;
  seed?: number;
  trimStart: number;
  longestSide: number;
  conditioning?: MotionConditioning;
};

/** A custom style image prepares an editable still; the caller must review it before motion. */
export function buildMotionRequest(catalog: Catalog, value: MotionOptions) {
  const model = catalog.models.find((item) => item.id === value.modelId);
  const effect = catalog.effects.find((item) => item.id === value.operation);
  if (!model || !effect?.model_ids.includes(model.id))
    throw new Error('Choose a compatible model for this operation.');
  if (!value.source || value.source.kind !== 'video')
    throw new Error('Choose a source motion video.');
  const vaceFirstFrame = value.vaceReferenceMode === 'first-frame';
  const inpaintFirstFrame = value.inpaintReferenceMode === 'edited-first-frame';
  const firstFrameControl = vaceFirstFrame || inpaintFirstFrame;
  if (vaceFirstFrame && (!Array.isArray(model.reference_modes) || !model.reference_modes.includes('first-frame')))
    throw new Error('This model does not support edited-first-frame VACE control.');
  if (inpaintFirstFrame && (value.operation !== 'replace-object' || !model.inpaint_reference_modes?.includes('edited-first-frame')))
    throw new Error('This model does not support edited-first-frame inpainting.');
  if (value.reference && value.operation === 'replace-object' && model.inpaint_reference_modes?.length && !inpaintFirstFrame)
    throw new Error('Explicitly select Edited full first frame for this reference, or clear it for text-only replacement.');
  if ((model.requires_reference || firstFrameControl) && !value.reference)
    throw new Error(
      model.reference_must_match_source_dimensions || firstFrameControl
        ? 'Choose the edited full starting frame for this video interval.'
        : 'Choose a character reference image.',
    );
  if (
    (model.reference_must_match_source_dimensions || firstFrameControl) &&
    value.reference &&
    (value.reference.width !== value.source.width || value.reference.height !== value.source.height)
  )
    throw new Error(
      'The edited starting frame must have the same canvas dimensions as the source video.',
    );
  if (value.reference && value.reference.kind !== 'image')
    throw new Error('Choose an image for the appearance reference.');
  if (value.operation !== 'replace-object' && !value.reference)
    throw new Error('Choose a character reference image.');
  if (value.reference && !modelSupportsReference(model, effect.task))
    throw new Error(
      'This model uses text for replacement. Remove the image reference or choose Wan VACE.',
    );
  if (
    value.operation === 'replace-object' &&
    !value.reference &&
    !(value.promptEnabled && value.prompt?.trim())
  )
    throw new Error('Add an appearance reference or describe the replacement.');
  if (value.operation !== 'motion-transfer' && !model.mask_optional && !value.maskAssetId)
    throw new Error('Paint the subject to replace first.');
  const cleanupIssue = model.id === 'scail-2' ? recastReferenceCleanupIssue(catalog, value.provider, value.recastReferenceCleanup) : '';
  if (cleanupIssue) throw new Error(cleanupIssue);
  const fps = Number(model.fixed_fps ?? value.fps ?? model.default_fps ?? 16);
  if (!Number.isFinite(fps) || fps < 1 || fps > 120)
    throw new Error('Choose a frame rate between 1 and 120 fps.');
  if (model.fixed_fps && value.fps !== undefined && value.fps !== Number(model.fixed_fps))
    throw new Error(`This model requires ${model.fixed_fps} fps.`);
  const frames = boundedVideoFrames(model, value.duration, value.source, value.trimStart, fps);
  if (frames < 9) throw new Error('Choose a longer source interval.');
  const preparingStyle =
    value.operation === 'motion-transfer' &&
    value.styleName === 'Custom' &&
    !!value.styleAssetId &&
    !value.preparedCharacterId;
  const conditioning = { ...motionDefaults, ...value.conditioning };
  if (
    model.supports_motion_controls &&
    conditioning.pose_start_percent >= conditioning.pose_end_percent
  )
    throw new Error('Motion conditioning start must be lower than its end.');
  const operation = preparingStyle ? 'edit-image' : value.operation;
  if (value.provider === 'comfy-cloud' && operation !== 'replace-object')
    throw new Error('Choose Local ComfyUI for this character workflow.');
  const renderModel = preparingStyle
    ? catalog.models.find((item) => item.id === (value.styleModelId || 'flux-klein-4b'))
    : model;
  if (
    !renderModel ||
    !catalog.effects.find((item) => item.id === operation)?.model_ids.includes(renderModel.id)
  )
    throw new Error('Choose a compatible model for image preparation.');
  const direction =
    value.promptEnabled && value.prompt?.trim()
      ? value.prompt
      : value.operation === 'replace-object'
        ? 'Replace the painted subject using the reference appearance. Match the source lighting and perspective, coherent motion and detailed edges.'
        : value.operation === 'character-replacement' && model.native_mask_tracking
          ? 'The reference character replaces the performer in the original scene. Follow the source hand grips, body movements and action timing. Retain the original held objects, their appearance and interactions, source camera and background. Natural coherent anatomy and scene lighting.'
          : 'The reference character performs the source video movements naturally. Preserve the character appearance, coherent body proportions, clothing and facial motion.';
  const style =
    value.operation === 'motion-transfer'
      ? value.styleName === 'Custom'
        ? value.stylePrompt
        : value.styleName
      : '';
  const prompt = preparingStyle
    ? `Render the character from the first image in the visual style of the second image. Keep the first character's identity, pose, clothes and proportions; borrow only materials, texture, palette and rendering style from the second image, not its subject. ${value.stylePrompt || ''}`
    : [direction, style && `Visual style direction: ${style}.`].filter(Boolean).join('\n');
  const ratio =
    value.source.width && value.source.height
      ? `${value.source.width}:${value.source.height}`
      : '3:4';
  return {
    operation,
    preparingStyle,
    request: renderRequest(renderModel, {
      effect_id: operation,
      prompt,
      seed: value.seed ?? -1,
      enhance_prompt: value.enhancePrompt,
      provider: value.provider,
      ...renderSize(renderModel, ratio, value.longestSide),
      frames: preparingStyle ? 1 : frames,
      fps: preparingStyle ? 1 : fps,
      source_asset_id: preparingStyle ? value.reference!.id : value.source.id,
      ...(!preparingStyle && model.reference_modes ? { vace_reference_mode: value.vaceReferenceMode || 'appearance' } : {}),
      ...(!preparingStyle && inpaintFirstFrame ? { inpaint_reference_mode: 'edited-first-frame' } : {}),
      reference_asset_id: preparingStyle
        ? value.styleAssetId
        : value.operation === 'motion-transfer'
          ? value.preparedCharacterId || value.reference?.id
          : value.reference?.id,
      mask_asset_id:
        !preparingStyle && value.operation !== 'motion-transfer' ? value.maskAssetId : undefined,
      trim_start: preparingStyle ? 0 : value.trimStart,
      ...(!preparingStyle && model.id === 'scail-2' ? { recast_composite_tracking: value.maskAssetId ? 'native' : value.recastCompositeTracking || 'native', recast_reference_cleanup: value.recastReferenceCleanup ?? false } : {}),
      ...(!preparingStyle && model.supports_motion_controls ? conditioning : {}),
      ...(!preparingStyle && model.native_mask_tracking ? { mask_dilation: 0 } : {}),
    }),
  };
}
