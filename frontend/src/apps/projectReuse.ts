import { api } from '../api';
import type { Catalog, Job } from '../types';
import type { AppDocument, ApplicationId } from './registry';

export const projectReuseDescription =
  'Creates a new draft with the saved inputs and app controls. Exact sampler and seed settings remain in the workflow export.';
export const missingProjectSnapshot =
  'This historical render has no usable saved app project. Its inputs cannot be restored into this screen; download the workflow or full project to inspect the recorded request.';

export async function loadProjectSnapshot<T extends Record<string, unknown>>(
  job: Job,
  appId: ApplicationId,
  catalog: Catalog,
  assetIds: (state: T) => string[],
): Promise<AppDocument<T>> {
  let context: { document_snapshot?: AppDocument<T> };
  try {
    context = await api(`/jobs/${job.id}/app-context`);
  } catch (error) {
    if ((error as Error & { status?: number }).status === 404)
      throw new Error(missingProjectSnapshot);
    throw error;
  }
  const snapshot = context.document_snapshot;
  if (
    !snapshot ||
    snapshot.app_id !== appId ||
    snapshot.schema_version !== 1 ||
    !snapshot.state ||
    typeof snapshot.state !== 'object' ||
    Array.isArray(snapshot.state) ||
    typeof snapshot.state.prompt !== 'string'
  )
    throw new Error(missingProjectSnapshot);
  const restoredInputs = assetIds(snapshot.state);
  const recordedInputs = [
    job.request.source_asset_id,
    job.request.reference_asset_id,
    ...(job.request.reference_asset_ids || []),
    job.request.mask_asset_id,
    job.request.audio_asset_id,
  ].filter(Boolean);
  if (recordedInputs.some((id) => !restoredInputs.includes(id!)))
    throw new Error(missingProjectSnapshot);
  if (
    !catalog.models.some((model) => model.id === job.request.model_id) ||
    !catalog.effects
      .find((effect) => effect.id === job.request.effect_id)
      ?.model_ids.includes(job.request.model_id)
  )
    throw new Error(
      `The recorded model ${job.request.model_id} is unavailable for this operation. No replacement model was selected. Use the workflow export to inspect the original setup.`,
    );
  return snapshot;
}

export function showProjectDraft(documentId: string, pathname: string) {
  if (location.pathname !== pathname) return;
  const url = new URL(location.href);
  url.searchParams.set('document', documentId);
  history.replaceState(null, '', url);
}
