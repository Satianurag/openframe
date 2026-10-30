import type { JobRequest, Model } from '../types';

export function modelSupportsReference(
  model: Model | undefined,
  task: string | undefined,
): boolean {
  return (
    !!model?.supports_reference &&
    !!task &&
    (!Array.isArray(model.reference_tasks) || model.reference_tasks.includes(task))
  );
}

export function modelProviderIssue(model: Model | undefined, provider: string, task?: string): string {
  if (!['local', 'comfy-cloud'].includes(provider)) return 'This saved connection is unavailable. Select Local ComfyUI or a supported Comfy Cloud operation explicitly; the saved provider has not been changed.';
  const supported = model?.supported_providers;
  const names: Record<string, string> = {
    local: 'Local ComfyUI',
    'comfy-cloud': 'Comfy Cloud',
  };
  if (model?.enabled_providers && !model.enabled_providers.includes(provider))
    return model.enabled_providers.length
      ? `${model.name} is available through ${model.enabled_providers.map((id) => names[id] || id).join(' or ')} in this configuration. Select an enabled provider; the saved provider has not been changed.`
      : `${model.name} is unavailable on the enabled connections in this configuration. Choose a supported model; the saved model has not been changed.`;
  const providerTasks = model?.provider_tasks?.[provider];
  if (task && providerTasks && !providerTasks.includes(task))
    return `${model.name} does not support this operation through ${names[provider] || provider}. Choose a supported model or connection; the saved settings have not been changed.`;
  if (!model || !Array.isArray(supported) || supported.includes(provider)) return '';
  return `${model.name} requires ${supported.map((id) => names[String(id)] || String(id)).join(' or ')}. Choose a compatible model or compute provider.`;
}

export function renderRequest(
  model: Model,
  values: Partial<JobRequest> & Pick<JobRequest, 'effect_id' | 'prompt' | 'provider'>,
): JobRequest {
  const task = ['remove-object', 'replace-object'].includes(values.effect_id) ? 'inpaint' : values.effect_id;
  const issue = modelProviderIssue(model, values.provider, task);
  if (issue) throw new Error(issue);
  return {
    model_id: model.id,
    negative_prompt: '',
    seed: -1,
    width: 1024,
    height: 576,
    frames: Number(model.default_frames || 97),
    fps: Number(model.fixed_fps || model.default_fps || 24),
    steps: Number(model.default_steps || 8),
    guidance: Number(model.default_guidance || 1),
    strength: 0.65,
    preserve_audio: true,
    preserve_outside_mask: true,
    mask_tracking: true,
    mask_tracking_method: 'sam2',
    trim_start: 0,
    mask_dilation: 8,
    mask_feather: 6,
    generate_audio: false,
    ...values,
    enhance_prompt:
      values.enhance_prompt ??
      (['remove-object', 'replace-object'].includes(values.effect_id) ? false : undefined),
  };
}
export function renderSize(model: Model, ratio: string, longest: number) {
  const [rw, rh] = ratio.split(':').map(Number);
  const multiple = Number(model.dimension_multiple || 32);
  const align = (value: number) => Math.max(multiple, Math.round(value / multiple) * multiple);
  return rw >= rh
    ? { width: align(longest), height: align((longest * rh) / rw) }
    : { width: align((longest * rw) / rh), height: align(longest) };
}
export function durationFrames(model: Model, seconds: number) {
  const fps = Number(model.fixed_fps || model.default_fps || 24),
    multiple = Number(model.frame_multiple || 8);
  return Math.max(1, Math.round((seconds * fps - 1) / multiple) * multiple + 1);
}
