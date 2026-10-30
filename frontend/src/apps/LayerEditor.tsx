import { useEffect, useMemo, useRef, useState } from 'react';
import { mediaUrl } from '../api';
import type { Job } from '../types';
import './layer-editor.css';

type Layer = {
  id: string; name: string; visible: boolean; opacity: number; x: number; y: number;
  scale: number; rotation: number; brightness: number; saturation: number; hue: number;
};

export function LayerEditor({ job, onClose }: { job: Job; onClose: () => void }) {
  const outputs = useMemo(() => job.outputs.filter((asset) => /^layer-\d+$/.test(asset.role || ''))
    .sort((a, b) => Number(a.role!.split('-')[1]) - Number(b.role!.split('-')[1])), [job.outputs]);
  const defaults = useMemo(() => outputs.map((asset): Layer => ({ id: asset.id, name: asset.role || 'Layer', visible: true,
    opacity: 1, x: 0, y: 0, scale: 1, rotation: 0, brightness: 100, saturation: 100, hue: 0 })), [outputs]);
  const storageKey = `openframe:layer-edit:v1:${job.id}`;
  const [layers, setLayers] = useState<Layer[]>(() => {
    try {
      const saved: Layer[] = JSON.parse(localStorage.getItem(storageKey) || 'null');
      if (Array.isArray(saved) && saved.length === defaults.length && new Set(saved.map((layer) => layer.id)).size === defaults.length
        && saved.every((layer) => defaults.some((item) => item.id === layer.id) && typeof layer.name === 'string'
          && typeof layer.visible === 'boolean' && ['opacity', 'x', 'y', 'scale', 'rotation', 'brightness', 'saturation', 'hue']
            .every((key) => Number.isFinite(layer[key as keyof Layer])))) return saved;
    } catch { /* Missing or invalid local edits leave the immutable render untouched. */ }
    return defaults;
  });
  const latestLayers = useRef(layers);
  latestLayers.current = layers;
  const [selected, setSelected] = useState(defaults.at(-1)?.id || '');
  const [images, setImages] = useState<Map<string, HTMLImageElement>>(new Map());
  const [error, setError] = useState('');
  const canvas = useRef<HTMLCanvasElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const drag = useRef<{ id: string; clientX: number; clientY: number; x: number; y: number } | null>(null);
  const width = outputs[0]?.width || 640, height = outputs[0]?.height || 640;
  const chosen = layers.find((layer) => layer.id === selected);

  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    const flush = () => {
      try {
        const value = JSON.stringify(latestLayers.current);
        if (localStorage.getItem(storageKey) !== value) localStorage.setItem(storageKey, value);
      } catch { /* The mounted debounce reports storage failures; recipe export stays available. */ }
    };
    window.addEventListener('pagehide', flush);
    return () => { window.removeEventListener('pagehide', flush); flush(); };
  }, [storageKey]);
  useEffect(() => {
    let live = true;
    Promise.all(outputs.map((asset) => new Promise<[string, HTMLImageElement]>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve([asset.id, image]);
      image.onerror = () => reject(new Error(`Could not load ${asset.role}.`));
      image.src = mediaUrl(asset);
    }))).then((loaded) => { if (live) setImages(new Map(loaded)); })
      .catch((reason) => { if (live) setError((reason as Error).message); });
    return () => { live = false; };
  }, [outputs]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        const value = JSON.stringify(layers);
        if (localStorage.getItem(storageKey) !== value) localStorage.setItem(storageKey, value);
      } catch { setError('Edits cannot be saved in this browser. Download the edit recipe before closing.'); }
    }, 500);
    return () => window.clearTimeout(timer);
  }, [layers, storageKey]);
  useEffect(() => {
    const context = canvas.current?.getContext('2d');
    if (!context) return;
    context.clearRect(0, 0, width, height);
    for (const layer of layers) {
      const image = images.get(layer.id);
      if (!layer.visible || !image) continue;
      context.save();
      context.globalAlpha = Math.max(0, Math.min(1, layer.opacity));
      context.filter = `brightness(${layer.brightness}%) saturate(${layer.saturation}%) hue-rotate(${layer.hue}deg)`;
      context.translate(layer.x + width / 2, layer.y + height / 2);
      context.rotate(layer.rotation * Math.PI / 180);
      context.scale(layer.scale, layer.scale);
      context.drawImage(image, -width / 2, -height / 2, width, height);
      context.restore();
    }
  }, [layers, images, width, height]);

  function update(id: string, changes: Partial<Layer>) {
    setLayers((current) => current.map((layer) => layer.id === id ? { ...layer, ...changes } : layer));
  }
  function move(id: string, delta: number) {
    setLayers((current) => {
      const index = current.findIndex((layer) => layer.id === id), next = index + delta;
      if (next < 0 || next >= current.length) return current;
      const result = [...current];
      [result[index], result[next]] = [result[next], result[index]];
      return result;
    });
  }
  function download(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob), anchor = document.createElement('a');
    anchor.href = url; anchor.download = filename; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function exportPng() {
    try {
      canvas.current?.toBlob((blob) => {
        if (blob) download(blob, `openframe-layers-${job.id}.png`);
        else setError('The browser could not encode the composite.');
      }, 'image/png');
    } catch (reason) { setError((reason as Error).message); }
  }
  function close() {
    try { localStorage.setItem(storageKey, JSON.stringify(layers)); } catch { /* Explicit recipe export remains available. */ }
    onClose();
  }
  const controls: { key: keyof Pick<Layer, 'opacity' | 'scale' | 'rotation' | 'brightness' | 'saturation' | 'hue'>; label: string; min: number; max: number; step: number }[] = [
    { key: 'opacity', label: 'Opacity', min: 0, max: 1, step: .01 },
    { key: 'scale', label: 'Scale', min: .1, max: 3, step: .01 },
    { key: 'rotation', label: 'Rotation', min: -180, max: 180, step: 1 },
    { key: 'brightness', label: 'Brightness', min: 0, max: 200, step: 1 },
    { key: 'saturation', label: 'Saturation', min: 0, max: 200, step: 1 },
    { key: 'hue', label: 'Hue', min: -180, max: 180, step: 1 },
  ];
  return <dialog ref={dialog} className="layer-editor" onCancel={(event) => { event.preventDefault(); close(); }}>
    <header><div><h2>Edit layers</h2><small>{width} × {height} · RGBA</small></div>
      <button onClick={() => setLayers(defaults)}>Reset edits</button>
      <button onClick={() => download(new Blob([JSON.stringify({ schema: 'openframe-layer-edit/v1', source_job_id: job.id, width, height, stack_order: 'back-to-front', layers }, null, 2)], { type: 'application/json' }), `openframe-layers-${job.id}.json`)}>Download recipe</button>
      <button disabled={images.size !== outputs.length || !outputs.length} onClick={exportPng}>Download PNG</button>
      <button aria-label="Close layer editor" onClick={close}>×</button>
    </header>
    {error && <p role="alert">{error}</p>}
    <div className="layer-editor-body"><div className="layer-editor-preview">
      <canvas ref={canvas} width={width} height={height} aria-label="Layer composition preview"
        onPointerDown={(event) => {
          if (!chosen) return;
          drag.current = { id: chosen.id, clientX: event.clientX, clientY: event.clientY, x: chosen.x, y: chosen.y };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (!drag.current) return;
          const rect = event.currentTarget.getBoundingClientRect(), start = drag.current;
          update(start.id, { x: Math.round(start.x + (event.clientX - start.clientX) * width / rect.width), y: Math.round(start.y + (event.clientY - start.clientY) * height / rect.height) });
        }}
        onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} />
      <small>Drag the selected layer to reposition it. Original generated files stay available.</small>
    </div><aside>
      <h3>Layers <small>front → back</small></h3>
      {[...layers].reverse().map((layer) => <div key={layer.id} className={`layer-editor-row ${selected === layer.id ? 'selected' : ''}`}>
        <input type="checkbox" aria-label={`Show ${layer.name}`} checked={layer.visible} onChange={(event) => update(layer.id, { visible: event.target.checked })} />
        <button onClick={() => setSelected(layer.id)}>{layer.name}</button>
        <button aria-label={`Bring ${layer.name} forward`} disabled={layers.at(-1)?.id === layer.id} onClick={() => move(layer.id, 1)}>↑</button>
        <button aria-label={`Send ${layer.name} backward`} disabled={layers[0]?.id === layer.id} onClick={() => move(layer.id, -1)}>↓</button>
        <a href={mediaUrl(outputs.find((asset) => asset.id === layer.id)!)} download={`${layer.name}.png`} aria-label={`Download ${layer.name}`}>↓PNG</a>
      </div>)}
      {chosen && <section className="layer-editor-controls">
        <label>Name<input value={chosen.name} maxLength={80} onChange={(event) => update(chosen.id, { name: event.target.value })} /></label>
        {(['x', 'y'] as const).map((key) => <label key={key}>{key.toUpperCase()} position<input type="number" value={chosen[key]} min={-4096} max={4096} step={1}
          onChange={(event) => { const value = event.target.valueAsNumber; if (Number.isFinite(value)) update(chosen.id, { [key]: Math.max(-4096, Math.min(4096, value)) }); }} /></label>)}
        {controls.map(({ key, label, min, max, step }) => <label key={key}>{label}<span>{chosen[key]}</span>
          <input type="range" min={min} max={max} step={step} value={chosen[key]} onChange={(event) => update(chosen.id, { [key]: Number(event.target.value) })} />
        </label>)}
      </section>}
    </aside></div>
    <footer>Layers are generated interpretations, including inferred hidden content. They may differ from the original image. Edits are saved in this browser.</footer>
  </dialog>;
}
