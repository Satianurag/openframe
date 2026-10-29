import { useCallback, useEffect, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import type { Asset } from './types';
import { Icon } from './Icon';
import { Modal, ErrorBox } from './ui';
import { upload } from './api';
type Stroke = {
  points: { x: number; y: number }[];
  size: number;
  erase: boolean;
  rect: boolean;
};
export function MaskEditor({
  asset,
  existingMask,
  startTime = 0,
  onSave,
  onClose,
}: {
  asset: Asset;
  existingMask?: Asset;
  startTime?: number;
  onSave: (mask: Asset) => void;
  onClose: () => void;
}) {
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [tool, setTool] = useState<'brush' | 'erase' | 'rectangle'>('brush');
  const [brush, setBrush] = useState(35);
  const [opacity, setOpacity] = useState(0.55);
  const [time, setTime] = useState(startTime);
  const [dimensions, setDimensions] = useState({ w: 768, h: 512 });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [keepExisting, setKeepExisting] = useState(true);
  const canvas = useRef<HTMLCanvasElement>(null);
  const base = useRef<HTMLImageElement | null>(null);
  const current = useRef<Stroke | null>(null);
  const image = useRef<HTMLImageElement>(null);
  const frame = `/api/assets/${asset.id}/frame?time=${time.toFixed(2)}`;
  const paint = useCallback(() => {
    const c = canvas.current;
    if (!c) return;
    const ctx = c.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, c.width, c.height);
    if (base.current && keepExisting) ctx.drawImage(base.current, 0, 0, c.width, c.height);
    for (const s of [...strokes, ...(current.current ? [current.current] : [])]) {
      ctx.globalCompositeOperation = s.erase ? 'destination-out' : 'source-over';
      ctx.fillStyle = 'white';
      ctx.strokeStyle = 'white';
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.lineWidth = (s.size * c.width) / 768;
      if (s.rect) {
        const a = s.points[0],
          b = s.points.at(-1)!;
        ctx.fillRect(a.x * c.width, a.y * c.height, (b.x - a.x) * c.width, (b.y - a.y) * c.height);
      } else {
        ctx.beginPath();
        s.points.forEach((p, i) =>
          i ? ctx.lineTo(p.x * c.width, p.y * c.height) : ctx.moveTo(p.x * c.width, p.y * c.height),
        );
        ctx.stroke();
        if (s.points.length === 1) {
          ctx.beginPath();
          ctx.arc(
            s.points[0].x * c.width,
            s.points[0].y * c.height,
            ctx.lineWidth / 2,
            0,
            Math.PI * 2,
          );
          ctx.fill();
        }
      }
    }
    ctx.globalCompositeOperation = 'source-over';
  }, [strokes, keepExisting]);
  useEffect(() => {
    if (!existingMask) return;
    const img = new Image();
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = img.width;
      c.height = img.height;
      const ctx = c.getContext('2d')!;
      ctx.drawImage(img, 0, 0);
      const data = ctx.getImageData(0, 0, c.width, c.height);
      for (let i = 0; i < data.data.length; i += 4) {
        data.data[i + 3] = data.data[i] > 127 ? 255 : 0;
        data.data[i] = data.data[i + 1] = data.data[i + 2] = 255;
      }
      ctx.putImageData(data, 0, 0);
      const transparent = new Image();
      transparent.onload = () => {
        base.current = transparent;
        paint();
      };
      transparent.src = c.toDataURL();
    };
    img.src = existingMask.url;
  }, [existingMask]);
  useEffect(() => {
    paint();
  }, [paint, dimensions]);
  const point = (e: PointerEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)),
      y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)),
    };
  };
  const start = (e: PointerEvent<HTMLCanvasElement>) => {
    if (!loaded) return;
    if (Math.abs(time - startTime) > 0.01) {
      setError('Return to the first frame of your selected clip to paint its tracking mask.');
      return;
    }
    setError('');
    e.currentTarget.setPointerCapture(e.pointerId);
    current.current = {
      points: [point(e)],
      size: brush,
      erase: tool === 'erase',
      rect: tool === 'rectangle',
    };
    paint();
  };
  const move = (e: PointerEvent<HTMLCanvasElement>) => {
    if (!current.current) return;
    current.current.points.push(point(e));
    paint();
  };
  const end = () => {
    if (current.current) {
      const next = current.current;
      current.current = null;
      setStrokes((s) => [...s, next]);
    }
  };
  async function save() {
    const c = canvas.current;
    if (!c) return;
    if (!strokes.length && !(existingMask && keepExisting)) {
      setError('Paint the area you want to edit before saving.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const out = document.createElement('canvas');
      out.width = c.width;
      out.height = c.height;
      const ctx = out.getContext('2d')!;
      ctx.fillStyle = 'black';
      ctx.fillRect(0, 0, c.width, c.height);
      ctx.drawImage(c, 0, 0);
      const pixels = ctx.getImageData(0, 0, c.width, c.height).data;
      if (!pixels.some((value, index) => index % 4 === 0 && value > 127)) {
        throw new Error('The mask is empty. Paint an area before saving.');
      }
      const blob = await new Promise<Blob>((resolve, reject) =>
        out.toBlob(
          (b) => (b ? resolve(b) : reject(new Error('Could not create mask.'))),
          'image/png',
        ),
      );
      const saved = await upload(new File([blob], `mask-${asset.id}.png`, { type: 'image/png' }));
      onSave(saved);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <Modal title="Draw to Edit" wide onClose={onClose}>
      <div className="mask-workspace">
        <div className="mask-stage">
          <div className="canvas-wrap" style={{ aspectRatio: `${dimensions.w}/${dimensions.h}` }}>
            <img
              ref={image}
              src={frame}
              alt="Source frame for mask painting"
              onLoad={() => {
                setDimensions({
                  w: image.current!.naturalWidth,
                  h: image.current!.naturalHeight,
                });
                setLoaded(true);
              }}
              onError={() =>
                setError('The source frame could not be loaded. Try uploading the video again.')
              }
            />
            <canvas
              ref={canvas}
              width={dimensions.w}
              height={dimensions.h}
              style={{ opacity }}
              onPointerDown={start}
              onPointerMove={move}
              onPointerUp={end}
              onPointerCancel={end}
              aria-label="Paint the edit mask on your source frame"
            />
          </div>
          {asset.kind === 'video' && (
            <label className="frame-seek">
              Preview frame{' '}
              <input
                type="range"
                min={startTime}
                max={Math.max(startTime, (asset.duration || 1) - 0.1)}
                step="0.1"
                value={time}
                onChange={(e) => setTime(+e.target.value)}
              />
              <span>{time.toFixed(1)}s</span>
            </label>
          )}
          {Math.abs(time - startTime) > 0.01 && (
            <button className="secondary" onClick={() => setTime(startTime)}>
              Return to mask seed ({startTime.toFixed(1)}s)
            </button>
          )}
          <p className="muted small">
            White selects the area the model can change. Black protects the surrounding scene.
          </p>
        </div>
        <aside className="mask-tools">
          <div className="segmented">
            {(['brush', 'erase', 'rectangle'] as const).map((t) => (
              <button
                key={t}
                aria-label={t}
                title={t}
                className={tool === t ? 'active' : ''}
                onClick={() => setTool(t)}
              >
                <Icon name={t === 'rectangle' ? 'square' : t} />
              </button>
            ))}
          </div>
          <label className="range-label">
            Brush size <span>{brush}px</span>
            <input
              type="range"
              min={4}
              max={180}
              value={brush}
              onChange={(e) => setBrush(+e.target.value)}
            />
          </label>
          <label className="range-label">
            Overlay <span>{Math.round(opacity * 100)}%</span>
            <input
              type="range"
              min=".1"
              max=".9"
              step=".05"
              value={opacity}
              onChange={(e) => setOpacity(+e.target.value)}
            />
          </label>
          <button
            className="secondary"
            disabled={!strokes.length}
            onClick={() => setStrokes((s) => s.slice(0, -1))}
          >
            <Icon name="undo" />
            Undo stroke
          </button>
          <button
            className="secondary"
            onClick={() => {
              setStrokes([]);
              setKeepExisting(false);
            }}
          >
            <Icon name="trash" />
            Clear mask
          </button>
          <div className="mask-help">
            <Icon name="info" />
            <p>
              Paint the whole object, its soft edges, its cast shadow, and a small margin. Preserve
              unmasked area keeps pixels outside the painted/tracked mask unchanged. Generation
              margin adds model context; it does not enlarge the final edit area.
            </p>
            <p>
              If you inspect another frame, return to {startTime.toFixed(1)}s to paint the tracking
              seed.
            </p>
          </div>
          {error && <ErrorBox message={error} />}
          <button className="primary" onClick={save} disabled={saving || !loaded}>
            {saving ? 'Saving mask…' : 'Use this mask'}
            <Icon name="check" />
          </button>
        </aside>
      </div>
    </Modal>
  );
}
