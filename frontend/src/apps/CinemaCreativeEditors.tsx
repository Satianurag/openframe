import { useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import { Icon } from '../Icon';
import { upload, mediaUrl } from '../api';
import { ColorPicker, hexToHsv, hsvToHex } from './ColorPicker';
import './cinema-editors.css';
export type CinemaLight = {
  color: string;
  brightness: number;
  diffuse: number;
  position: string;
  x: number;
  y: number;
};
export type LightingPreset = { name: string; lights: CinemaLight[] };
export type ColorPalette = {
  name: string;
  colors: string[];
  image_asset_id?: string;
  image_url?: string;
};
export const defaultLights: CinemaLight[] = [
  { color: '#FFFFFF', brightness: 50, diffuse: 50, position: 'Front', x: 0, y: 0 },
];
const defaultColors = ['#4A90E2', '#4B4AE2', '#4AD7E2', '#924AE2', '#4AE2A6'];
export function LightingEditor({
  value,
  onApply,
  onSave,
}: {
  value: CinemaLight[];
  onApply: (lights: CinemaLight[]) => void;
  onSave: (preset: LightingPreset) => void;
}) {
  const [lights, setLights] = useState<CinemaLight[]>(value.length ? value : defaultLights);
  const [active, setActive] = useState(0);
  const [colorOpen, setColorOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState('');
  const light = lights[active];
  const update = (changes: Partial<CinemaLight>) =>
    setLights((items) =>
      items.map((item, index) => (index === active ? { ...item, ...changes } : item)),
    );
  function move(event: PointerEvent<SVGSVGElement>) {
    const r = event.currentTarget.getBoundingClientRect();
    const x = Math.max(-1, Math.min(1, ((event.clientX - r.left) / r.width - 0.5) * 2)),
      y = Math.max(-1, Math.min(1, ((event.clientY - r.top) / r.height - 0.5) * 2));
    update({
      x,
      y,
      position:
        Math.abs(y) > Math.abs(x)
          ? y < 0
            ? 'Top'
            : 'Bottom'
          : Math.abs(x) > 0.3
            ? x < 0
              ? 'Left'
              : 'Right'
            : 'Front',
    });
  }
  return (
    <div className="cin-light-editor">
      <div className="cin-light-tabs">
        {lights.map((_, index) => (
          <button
            key={index}
            className={index === active ? 'active' : ''}
            onClick={() => {
              setActive(index);
              setColorOpen(false);
            }}
          >
            Light {index + 1}
            {lights.length > 1 && (
              <span
                role="button"
                aria-label={`Remove light ${index + 1}`}
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    event.stopPropagation();
                    setLights((items) => items.filter((_, i) => i !== index));
                    setActive(0);
                  }
                }}
                onClick={(event) => {
                  event.stopPropagation();
                  setLights((items) => items.filter((_, i) => i !== index));
                  setActive(0);
                }}
              >
                <Icon name="close" size={10} />
              </span>
            )}
          </button>
        ))}
        <button
          disabled={lights.length >= 8}
          onClick={() => {
            setLights([...lights, { ...defaultLights[0] }]);
            setActive(lights.length);
          }}
        >
          ＋ Add Light
        </button>
      </div>
      <div className="cin-light-stage">
        <div className="cin-light-properties">
          <small>Light {active + 1}</small>
          <button className="cin-light-color" onClick={() => setColorOpen(!colorOpen)}>
            <span>Color</span>
            <i style={{ background: light.color }} />
            {light.color}
          </button>
          {colorOpen && <ColorPicker value={light.color} onChange={(color) => update({ color })} />}
          <label
            style={{
              background: `linear-gradient(90deg,#ffffff12 ${light.brightness}%,#ffffff05 ${light.brightness}%)`,
            }}
          >
            <span>Brightness</span>
            <input
              aria-label="Brightness"
              type="range"
              min={0}
              max={100}
              value={light.brightness}
              onChange={(event) => update({ brightness: Number(event.target.value) })}
            />
            <b>{light.brightness}%</b>
          </label>
          <label
            style={{
              background: `linear-gradient(90deg,#ffffff12 ${light.diffuse}%,#ffffff05 ${light.diffuse}%)`,
            }}
          >
            <span>Diffuse</span>
            <input
              aria-label="Diffuse"
              type="range"
              min={0}
              max={100}
              value={light.diffuse}
              onChange={(event) => update({ diffuse: Number(event.target.value) })}
            />
            <b>{light.diffuse}%</b>
          </label>
        </div>
        <svg
          className="cin-light-orbit"
          viewBox="0 0 280 280"
          role="slider"
          aria-label={`Light ${active + 1} position: ${light.position}`}
          aria-valuemin={-100}
          aria-valuemax={100}
          aria-valuenow={Math.round(light.x * 100)}
          tabIndex={0}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            move(event);
          }}
          onPointerMove={(event) => {
            if (event.buttons === 1) move(event);
          }}
          onKeyDown={(event) => {
            if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
              event.preventDefault();
              update({
                x: Math.max(
                  -1,
                  Math.min(
                    1,
                    light.x +
                      (event.key === 'ArrowRight' ? 0.1 : event.key === 'ArrowLeft' ? -0.1 : 0),
                  ),
                ),
                y: Math.max(
                  -1,
                  Math.min(
                    1,
                    light.y +
                      (event.key === 'ArrowDown' ? 0.1 : event.key === 'ArrowUp' ? -0.1 : 0),
                  ),
                ),
                position: 'Custom',
              });
            }
          }}
        >
          <defs>
            <radialGradient
              id="cin-light-face"
              cx={`${50 + light.x * 30}%`}
              cy={`${50 + light.y * 30}%`}
              r={`${30 + light.diffuse * 0.5}%`}
            >
              <stop stopColor={light.color} stopOpacity={light.brightness / 100} />
              <stop offset="1" stopColor="#414346" />
            </radialGradient>
            <filter id="cin-light-glow">
              <feGaussianBlur stdDeviation="3" />
            </filter>
          </defs>
          <g fill="none" stroke="#747a80" strokeOpacity=".12">
            <circle cx="140" cy="140" r="100" />
            {[20, 45, 70].map((width) => (
              <ellipse key={width} cx="140" cy="140" rx={width} ry="100" />
            ))}
            {[20, 55].map((height) => (
              <ellipse key={height} cx="140" cy="140" rx="100" ry={height} />
            ))}
            <path d="M40 140h200M140 40v200" />
          </g>
          <ellipse
            cx="140"
            cy="145"
            rx="100"
            ry="20"
            fill="none"
            stroke="#8b929a"
            strokeOpacity=".2"
            strokeWidth="4"
          />
          <path
            d="M92 100Q87 99 86 113L89 173Q89 181 99 182L182 188Q193 186 194 174L194 110Q194 101 184 100Z"
            fill="#42464b"
            stroke="#646a70"
            strokeOpacity=".25"
            strokeWidth="3"
          />
          <path
            d="M86 101Q80 101 80 113L83 171Q84 180 95 181L174 188Q184 187 185 175L185 112Q185 104 174 103Z"
            fill="url(#cin-light-face)"
            stroke="#b5bec7"
            strokeOpacity=".12"
            strokeWidth="2"
          />
          {lights.map((item, index) => (
            <g
              key={index}
              onPointerDown={(event) => {
                event.stopPropagation();
                setActive(index);
              }}
            >
              <circle
                cx={140 + item.x * 92}
                cy={145 + item.y * 92}
                r="10"
                fill={item.color}
                fillOpacity=".8"
              />
              <circle
                cx={140 + item.x * 92}
                cy={145 + item.y * 92}
                r="15"
                fill="none"
                stroke={index === active ? '#d1fe17' : '#ffffff60'}
                strokeWidth="2"
              />
            </g>
          ))}
        </svg>
        <div className="cin-light-quick">
          <small>Quick select</small>
          <div>
            {['Top', 'Front', 'Right', 'Left', 'Back', 'Bottom'].map((position) => (
              <button
                key={position}
                className={light.position === position ? 'selected' : ''}
                onClick={() =>
                  update({
                    position,
                    x: position === 'Right' ? 1 : position === 'Left' ? -1 : 0,
                    y: position === 'Top' ? -1 : position === 'Bottom' ? 1 : 0,
                  })
                }
              >
                {position}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="cin-light-actions">
        {saving ? (
          <>
            <input
              aria-label="Lighting preset name"
              placeholder="Preset name"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <button
              className="apply"
              disabled={!name.trim()}
              onClick={() => onSave({ name: name.trim(), lights })}
            >
              Save
            </button>
            <button onClick={() => setSaving(false)}>Cancel</button>
          </>
        ) : (
          <>
            <button className="apply" onClick={() => onApply(lights)}>
              Apply
            </button>
            <button className="save" onClick={() => setSaving(true)}>
              Save as preset
            </button>
          </>
        )}
      </div>
    </div>
  );
}
export function PaletteEditor({
  value,
  onSave,
  onError,
}: {
  value?: ColorPalette;
  onSave: (palette: ColorPalette) => void;
  onError: (error: string) => void;
}) {
  const [mode, setMode] = useState<'image' | 'wheel'>('image');
  const [colors, setColors] = useState(value?.colors.slice(0, 12) || defaultColors);
  const [name, setName] = useState(value?.name || '');
  const [expanded, setExpanded] = useState(false);
  const [harmony, setHarmony] = useState('Analogous');
  const [edit, setEdit] = useState<number | null>(null);
  const [image, setImage] = useState<{ id: string; url: string } | null>(
    value?.image_asset_id
      ? {
          id: value.image_asset_id,
          url: value.image_url || `/api/assets/${value.image_asset_id}/file`,
        }
      : null,
  );
  const input = useRef<HTMLInputElement>(null);
  const dragged = useRef<number | null>(null);
  const main = hexToHsv(colors[0]);
  const changeColor = (index: number, color: string) =>
    setColors((current) => current.map((entry, i) => (i === index ? color : entry)));
  function harmonyColors(h: number, s: number, v: number, type = harmony) {
    const offsets: Record<string, number[]> = {
      Analogous: [0, 30, -30, 60, -60],
      Complementary: [0, 180, 0, 180, 0],
      Triad: [0, 120, 240, 120, 240],
      Square: [0, 90, 180, 270, 0],
      'Split complementary': [0, 150, 210, 150, 210],
      Monochromatic: [0, 0, 0, 0, 0],
    };
    if (type === 'Custom') {
      changeColor(0, hsvToHex(h, s, v));
      return;
    }
    setColors(
      colors.map((_, index) =>
        hsvToHex(
          (h + (offsets[type] || offsets.Analogous)[index % 5] + 360) % 360,
          type === 'Monochromatic' ? Math.max(0.1, s - index * 0.1) : s,
          type === 'Monochromatic' ? Math.max(0.3, v - index * 0.08) : v,
        ),
      ),
    );
  }
  function wheel(event: PointerEvent<HTMLDivElement>) {
    const r = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - r.left - r.width / 2) / (r.width / 2),
      y = (event.clientY - r.top - r.height / 2) / (r.height / 2);
    const h = ((Math.atan2(x, -y) * 180) / Math.PI + 360) % 360;
    harmonyColors(h, Math.min(1, Math.hypot(x, y)), main.v);
  }
  async function fromImage(file?: File) {
    if (!file) return;
    try {
      const asset = await upload(file);
      const bitmap = await createImageBitmap(file);
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 96;
      const context = canvas.getContext('2d')!;
      context.drawImage(bitmap, 0, 0, 96, 96);
      bitmap.close();
      const pixels = context.getImageData(0, 0, 96, 96).data;
      const buckets = new Map<string, { count: number; r: number; g: number; b: number }>();
      for (let i = 0; i < pixels.length; i += 4) {
        if (pixels[i + 3] < 200) continue;
        const key = [pixels[i], pixels[i + 1], pixels[i + 2]]
          .map((v) => Math.floor(v / 32))
          .join(',');
        const entry = buckets.get(key) || { count: 0, r: 0, g: 0, b: 0 };
        entry.count++;
        entry.r += pixels[i];
        entry.g += pixels[i + 1];
        entry.b += pixels[i + 2];
        buckets.set(key, entry);
      }
      const palette = [...buckets.values()]
        .sort((a, b) => b.count - a.count)
        .slice(0, 5)
        .map(
          (entry) =>
            '#' +
            [entry.r, entry.g, entry.b]
              .map((v) =>
                Math.round(v / entry.count)
                  .toString(16)
                  .padStart(2, '0'),
              )
              .join('')
              .toUpperCase(),
        );
      if (palette.length) setColors(palette);
      setImage({ id: asset.id, url: mediaUrl(asset) });
    } catch (reason) {
      onError((reason as Error).message);
    }
  }
  function reorder(from: number, to: number) {
    if (from === to) return;
    const next = [...colors];
    const [color] = next.splice(from, 1);
    next.splice(to, 0, color);
    setColors(next);
    setEdit(null);
  }
  return (
    <div className={`cin-palette-editor ${expanded ? 'expanded' : ''}`}>
      <div className="cin-palette-source">
        <div className="cin-palette-tabs">
          <button className={mode === 'image' ? 'active' : ''} onClick={() => setMode('image')}>
            <Icon name="image" size={15} />
            From image
          </button>
          <button className={mode === 'wheel' ? 'active' : ''} onClick={() => setMode('wheel')}>
            <Icon name="spark" size={15} />
            Color wheel
          </button>
        </div>
        {mode === 'image' ? (
          <button className="cin-palette-image" onClick={() => input.current?.click()}>
            {image ? (
              <img src={image.url} alt="Palette source" />
            ) : (
              <>
                <Icon name="plus" size={28} />
                <span>Select image</span>
              </>
            )}
          </button>
        ) : (
          <div className="cin-wheel-area">
            <div
              className="cin-color-wheel"
              role="slider"
              aria-label="Main color position"
              aria-valuemin={0}
              aria-valuemax={359}
              aria-valuenow={Math.round(main.h)}
              tabIndex={0}
              onPointerDown={(event) => {
                event.currentTarget.setPointerCapture(event.pointerId);
                wheel(event);
              }}
              onPointerMove={(event) => {
                if (event.buttons === 1) wheel(event);
              }}
              onKeyDown={(event) => {
                if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
                  event.preventDefault();
                  harmonyColors(
                    (main.h + (event.key === 'ArrowRight' ? 2 : 358)) % 360,
                    main.s,
                    main.v,
                  );
                }
              }}
            >
              {colors.map((color, index) => {
                const hsv = hexToHsv(color);
                return (
                  <i
                    key={index}
                    style={{
                      left: `${50 + Math.sin((hsv.h * Math.PI) / 180) * hsv.s * 50}%`,
                      top: `${50 - Math.cos((hsv.h * Math.PI) / 180) * hsv.s * 50}%`,
                      background: color,
                    }}
                  />
                );
              })}
            </div>
            <div className="cin-harmonies">
              <p>
                Color harmonies: <strong>{harmony}</strong>
              </p>
              <div>
                {[
                  'Custom',
                  'Analogous',
                  'Complementary',
                  'Triad',
                  'Square',
                  'Split complementary',
                  'Monochromatic',
                ].map((type, index) => (
                  <button
                    key={type}
                    title={type}
                    aria-label={type}
                    aria-pressed={harmony === type}
                    className={harmony === type ? 'active' : ''}
                    onClick={() => {
                      setHarmony(type);
                      harmonyColors(main.h, main.s, main.v, type);
                    }}
                  >
                    <svg viewBox="0 0 32 32">
                      <circle
                        cx="16"
                        cy="16"
                        r="11"
                        fill="none"
                        stroke="currentColor"
                        opacity=".2"
                      />
                      {Array.from(
                        {
                          length:
                            index === 0
                              ? 3
                              : index === 1
                                ? 5
                                : index === 2
                                  ? 2
                                  : index === 3
                                    ? 3
                                    : index === 4
                                      ? 4
                                      : 3,
                        },
                        (_, i) => {
                          const total = index === 1 ? 5 : index === 2 ? 2 : index === 4 ? 4 : 3;
                          const a = (i / total) * Math.PI * 2;
                          return (
                            <g key={i}>
                              <path
                                d={`M16 16L${16 + Math.sin(a) * 11} ${16 - Math.cos(a) * 11}`}
                                stroke="currentColor"
                              />
                              <circle
                                cx={16 + Math.sin(a) * 11}
                                cy={16 - Math.cos(a) * 11}
                                r="2"
                                fill="currentColor"
                              />
                            </g>
                          );
                        },
                      )}
                    </svg>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
      <div className="cin-palette-colors">
        <header>
          <span>Palette</span>
          <div>
            <button
              onClick={() =>
                harmonyColors(
                  Math.random() * 360,
                  0.5 + Math.random() * 0.4,
                  0.7 + Math.random() * 0.25,
                )
              }
            >
              <Icon name="refresh" size={13} />
              Random
            </button>
            <button
              aria-label="Expand palette"
              aria-pressed={expanded}
              onClick={() => setExpanded(!expanded)}
            >
              <Icon name="fullscreen" size={14} />
            </button>
          </div>
        </header>
        <div className="cin-swatch-grid">
          {Array.from({ length: 12 }, (_, index) =>
            colors[index] ? (
              <div
                key={index}
                draggable
                onDragStart={() => {
                  dragged.current = index;
                }}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  if (dragged.current !== null) reorder(dragged.current, index);
                  dragged.current = null;
                }}
                className={`cin-swatch ${index === 0 ? 'main' : ''}`}
                style={{ background: colors[index] }}
              >
                <span>{index === 0 ? 'Main' : ''}</span>
                <div className="cin-swatch-tools">
                  <button
                    aria-label={`Edit color ${index + 1}`}
                    onClick={() => setEdit(edit === index ? null : index)}
                  >
                    <Icon name="sliders" size={13} />
                  </button>
                  <button
                    aria-label={`Move color ${index + 1} earlier`}
                    onClick={() => reorder(index, Math.max(0, index - 1))}
                  >
                    <Icon name="menu" size={13} />
                  </button>
                  <button
                    aria-label={`Remove color ${index + 1}`}
                    disabled={colors.length <= 1}
                    onClick={() => {
                      setColors(colors.filter((_, i) => i !== index));
                      setEdit(null);
                    }}
                  >
                    <Icon name="close" size={13} />
                  </button>
                </div>
                <footer>
                  <button onClick={() => setEdit(edit === index ? null : index)}>
                    {colors[index]}
                  </button>
                  <button
                    aria-label={`Copy ${colors[index]}`}
                    onClick={() =>
                      void navigator.clipboard
                        .writeText(colors[index])
                        .catch(() =>
                          onError(
                            'Clipboard access is unavailable. Select and copy the hex value.',
                          ),
                        )
                    }
                  >
                    <Icon name="copy" size={12} />
                  </button>
                </footer>
                {edit === index && (
                  <ColorPicker
                    value={colors[index]}
                    onChange={(color) => changeColor(index, color)}
                  />
                )}
              </div>
            ) : (
              <button
                key={index}
                className="cin-add-swatch"
                aria-label="Add color"
                onClick={() => setColors([...colors, hsvToHex(Math.random() * 360, 0.6, 0.85)])}
              >
                <Icon name="plus" size={22} />
              </button>
            ),
          )}
        </div>
        <footer>
          <input
            aria-label="Palette name"
            placeholder="Enter palette name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <button
            disabled={!name.trim()}
            onClick={() =>
              onSave({
                name: name.trim(),
                colors,
                ...(image ? { image_asset_id: image.id, image_url: image.url } : {}),
              })
            }
          >
            Save palette
          </button>
        </footer>
      </div>
      <input
        ref={input}
        hidden
        type="file"
        accept="image/*"
        onChange={(event) => void fromImage(event.target.files?.[0])}
      />
    </div>
  );
}
