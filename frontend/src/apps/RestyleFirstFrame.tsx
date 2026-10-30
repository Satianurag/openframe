import { useState } from 'react';
import { download, post, upload } from '../api';
import type { Asset } from '../types';

/** Prepare an editable native-size still; never starts image or video inference. */
export function RestyleFirstFrame({ source, trimStart, prompt, appId, projectId, saveParent, onPrepared }: {
  source: Asset; trimStart: number; prompt: string; appId: string; projectId?: string;
  saveParent: () => Promise<{ id: string } | null>;
  onPrepared: (id: string) => Promise<unknown>;
}) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const path = `/assets/${source.id}/frame?time=${trimStart}`;
  async function prepare() {
    setBusy(true); setError('');
    try {
      const parent = await saveParent();
      if (!parent) throw new Error('Save the video project before preparing its starting frame.');
      const response = await fetch(`/api${path}`);
      if (!response.ok) throw new Error('The selected source frame could not be extracted.');
      const blob = await response.blob(), bitmap = await createImageBitmap(blob);
      const { width, height } = bitmap; bitmap.close();
      if (width !== source.width || height !== source.height)
        throw new Error('The extracted frame does not match the source dimensions. No edit draft was created.');
      const frame = await upload(new File([blob], `starting-frame-${source.id}-${trimStart}.png`, { type: 'image/png' }));
      const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('The editable full-frame mask could not be prepared.');
      ctx.fillStyle = 'white'; ctx.fillRect(0, 0, width, height);
      const maskBlob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('Mask encoding failed.')), 'image/png'));
      const mask = await upload(new File([maskBlob], `full-frame-${width}x${height}.png`, { type: 'image/png' }));
      const draft = await post<{ id: string }>('/apps/soul-image/documents', {
        title: 'Review edited starting frame', schema_version: 1, asset_ids: [frame.id, mask.id],
        state: {
          prompt: `Edit the complete supplied frame to this visual direction: ${prompt || 'the selected visual style'}. Keep the same people and objects, their identity, clothing, gestures, positions, camera framing and scene geometry. Change the visual style without replacing subjects.`,
          reference_asset_ids: [frame.id], mask_asset_id: mask.id, image_preservation: 'outside-mask',
          mask_feather: 0, mask_feather_explicit: true, image_prompt_mode: 'caption', image_reference_megapixels: 1,
          image_layout: [], model_id: 'flux3-klein', ratio: `${width}:${height}`, quality: Math.max(width, height),
          batch: 1, seed: -1, mode: 'image', style: '', scenes: [], character_adapter_id: '', character_strength: 1,
          preparation_source: { app_id: appId, document_id: parent.id, video_id: source.id, video_sha256: source.sha256,
            trim_start: trimStart, frame_sha256: frame.sha256, width, height },
        },
      });
      await onPrepared(draft.id);
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="ea-field">
    <small>Use a reviewed full {source.width} × {source.height} edit of the frame at {trimStart.toFixed(2)}s. Both native Canny passes condition on it; later identity and gestures still need review.</small>
    <button type="button" className="ea-outline" disabled={busy} onClick={() => void download(path, `starting-frame-${trimStart}.png`).catch((reason) => setError(reason.message))}>Download selected source frame</button>
    {projectId ? <a href={`/soul?document=${projectId}`} target="_blank" rel="noreferrer">Review image-edit draft</a>
      : <button type="button" className="ea-outline" disabled={busy} onClick={() => void prepare()}>{busy ? 'Preparing draft…' : 'Prepare starting-frame edit'}</button>}
    <small>Generate and review that still in Image Studio, then select its result here. Preparing a draft submits no model job.</small>
    {error && <p className="ea-error" role="alert">{error}</p>}
  </div>;
}
