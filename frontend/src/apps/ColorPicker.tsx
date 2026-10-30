import { useEffect, useState } from 'react';
import type { PointerEvent } from 'react';
import { Icon } from '../Icon';
export function hsvToHex(h: number, s: number, v: number) {
  const f = (n: number) => {
    const k = (n + h / 60) % 6;
    return Math.round(255 * (v - v * s * Math.max(0, Math.min(k, 4 - k, 1))))
      .toString(16)
      .padStart(2, '0');
  };
  return ('#' + f(5) + f(3) + f(1)).toUpperCase();
}
export function hexToHsv(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const max = Math.max(r, g, b),
    min = Math.min(r, g, b),
    delta = max - min;
  let h =
    delta === 0
      ? 0
      : max === r
        ? 60 * (((g - b) / delta) % 6)
        : max === g
          ? 60 * ((b - r) / delta + 2)
          : 60 * ((r - g) / delta + 4);
  if (h < 0) h += 360;
  return { h, s: max === 0 ? 0 : delta / max, v: max };
}
export function ColorPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const [hex, setHex] = useState(value);
  const [hue, setHue] = useState(hexToHsv(value).h);
  const color = hexToHsv(value);
  useEffect(() => setHex(value), [value]);
  function select(event: PointerEvent<HTMLDivElement>) {
    const r = event.currentTarget.getBoundingClientRect();
    onChange(
      hsvToHex(
        hue,
        Math.max(0, Math.min(1, (event.clientX - r.left) / r.width)),
        1 - Math.max(0, Math.min(1, (event.clientY - r.top) / r.height)),
      ),
    );
  }
  return (
    <div className="cin-color-picker">
      <div
        className="cin-sv"
        style={{ backgroundColor: hsvToHex(hue, 1, 1) }}
        role="slider"
        aria-label="Color saturation and brightness"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(color.s * 100)}
        tabIndex={0}
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId);
          select(event);
        }}
        onPointerMove={(event) => {
          if (event.buttons === 1) select(event);
        }}
        onKeyDown={(event) => {
          const step = event.shiftKey ? 0.1 : 0.02;
          if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
            event.preventDefault();
            onChange(
              hsvToHex(
                hue,
                Math.max(
                  0,
                  Math.min(
                    1,
                    color.s +
                      (event.key === 'ArrowRight' ? step : event.key === 'ArrowLeft' ? -step : 0),
                  ),
                ),
                Math.max(
                  0,
                  Math.min(
                    1,
                    color.v +
                      (event.key === 'ArrowUp' ? step : event.key === 'ArrowDown' ? -step : 0),
                  ),
                ),
              ),
            );
          }
        }}
      >
        <i style={{ left: `${color.s * 100}%`, top: `${(1 - color.v) * 100}%` }} />
      </div>
      <input
        className="cin-hue"
        type="range"
        min={0}
        max={359}
        value={hue}
        aria-label="Hue"
        onChange={(event) => {
          const h = Number(event.target.value);
          setHue(h);
          onChange(hsvToHex(h, color.s, color.v));
        }}
      />
      <label>
        <Icon name="brush" size={16} />
        <input
          aria-label="Hex color"
          value={hex}
          maxLength={7}
          onChange={(event) => {
            setHex(event.target.value);
            if (/^#[\da-f]{6}$/i.test(event.target.value)) {
              onChange(event.target.value.toUpperCase());
              setHue(hexToHsv(event.target.value).h);
            }
          }}
          onBlur={() => setHex(value)}
        />
      </label>
    </div>
  );
}
