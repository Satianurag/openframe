import { useEffect, useRef, useState } from 'react';

export type SphereSettings = { rotation: number; elevation: number; intensity: number };

export function RelightSphere({ value, onChange, onApply, applied, disabled }: {
  value: SphereSettings;
  onChange: (value: SphereSettings) => void;
  onApply: (file: File, value: SphereSettings) => Promise<void>;
  applied: boolean;
  disabled: boolean;
}) {
  const [preview, setPreview] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const latest = useRef(value);
  latest.current = value;
  useEffect(() => {
    let cancelled = false;
    setPreview('');
    const timer = setTimeout(() => {
      void import('./vendor/sphere-light/renderer.js').then(({ renderSphere }) => {
        if (cancelled) return;
        setPreview(renderSphere(value.rotation, value.elevation, value.intensity));
        setError('');
      }).catch((reason: unknown) => {
        if (!cancelled) setError(`Lighting preview failed: ${String(reason)}`);
      });
    }, 100);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [value.rotation, value.elevation, value.intensity]);

  async function apply() {
    setSaving(true);
    setError('');
    try {
      const snapshot = { ...latest.current };
      const { renderSphere } = await import('./vendor/sphere-light/renderer.js');
      const png = renderSphere(snapshot.rotation, snapshot.elevation, snapshot.intensity);
      const blob = await (await fetch(png)).blob();
      await onApply(new File([blob], 'relight-sphere.png', { type: 'image/png' }), snapshot);
    } catch (reason) {
      setError((reason as Error).message);
    } finally { setSaving(false); }
  }
  const directions = ['front', 'front-right', 'right', 'back-right', 'behind', 'back-left', 'left', 'front-left'];
  const direction = directions[Math.round(((value.rotation % 360 + 360) % 360) / 45) % 8];
  const altitude = value.elevation < 33 ? 'low' : value.elevation < 58 ? 'mid' : 'high';
  return <section className="relight-sphere-controls">
    <h3>Exterior lighting sphere</h3>
    {preview && <img className="relight-sphere-preview" src={preview} alt={`Lighting sphere: ${direction}, ${altitude} sun`} />}
    <div className="field-grid">
      <label className="input-label">Rotation · degrees<input type="number" min={-180} max={180} step={1} value={value.rotation} disabled={disabled || saving} onChange={(e) => onChange({ ...value, rotation: +e.target.value })} /></label>
      <label className="input-label">Elevation · degrees<input type="number" min={5} max={85} step={1} value={value.elevation} disabled={disabled || saving} onChange={(e) => onChange({ ...value, elevation: +e.target.value })} /></label>
      <label className="input-label">Intensity<input type="number" min={0.2} max={3} step={0.1} value={value.intensity} disabled={disabled || saving} onChange={(e) => onChange({ ...value, intensity: +e.target.value })} /></label>
    </div>
    <p className="muted small">Direction: {direction}; {altitude} sun. Begin the visible prompt with “relight the video to match the light-direction ball.” and describe the matching lighting. Exterior footage only. The source is fitted to the model’s fixed canvas; the sphere controls illumination and is not an object reference.</p>
    <button type="button" className="secondary-button" disabled={disabled || saving || applied || !preview || value.rotation < -180 || value.rotation > 180 || value.elevation < 5 || value.elevation > 85 || value.intensity < 0.2 || value.intensity > 3} onClick={() => void apply()}>{saving ? 'Saving lighting sphere…' : applied ? 'Lighting sphere applied' : 'Use this lighting sphere'}</button>
    <p className="muted small">{applied ? 'Prepared sphere is saved with this draft.' : 'Apply the sphere before generating. Changing its controls clears the previous prepared image.'} The generated relight still needs visual review.</p>
    {error && <p role="alert" className="error-text">{error}</p>}
  </section>;
}
