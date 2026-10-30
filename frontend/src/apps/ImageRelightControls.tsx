import { useId, useState } from 'react';
import type { PointerEvent } from 'react';
import { ColorPicker } from './ColorPicker';
import './image-relight.css';

export type ImageLighting = {
  azimuth: number;
  elevation: number;
  softness: number;
  brightness: number;
  color: string;
};
export const defaultImageLighting: ImageLighting = {
  azimuth: 0,
  elevation: 0,
  softness: 50,
  brightness: 50,
  color: '#FFFFFF',
};
export function imageLightingPrompt(prompt: string, light?: ImageLighting | null) {
  if (!light) return prompt;
  const horizontal =
    light.azimuth === 0
      ? 'front, beside the camera'
      : Math.abs(light.azimuth) === 180
        ? 'behind the subject'
        : `${Math.abs(light.azimuth).toFixed(0)} degrees from the camera toward camera-${light.azimuth < 0 ? 'left' : 'right'} (the ${light.azimuth < 0 ? 'left' : 'right'} edge of the image, not the subject’s anatomical side)`;
  const side = light.azimuth < 0 ? 'left' : 'right';
  const opposite = light.azimuth < 0 ? 'right' : 'left';
  const sideInstruction = light.azimuth !== 0 && Math.abs(light.azimuth) < 180
    ? ` The key light enters from image-${side}; light-facing surfaces on image-${side} should be brighter, with cast shadows extending toward image-${opposite}.`
    : '';
  const vertical =
    light.elevation === 0
      ? 'at subject height'
      : `${Math.abs(light.elevation).toFixed(0)} degrees ${light.elevation > 0 ? 'above' : 'below'} the subject`;
  const softness =
    light.softness < 25
      ? 'hard, focused light with crisp shadows'
      : light.softness > 75
        ? 'broad soft light with diffuse shadows'
        : 'moderately soft light with gently defined shadows';
  return `${prompt.trim()}\n\nLighting direction: ${horizontal}, ${vertical}.${sideInstruction} Use ${softness} (softness ${light.softness}/100), relative brightness ${light.brightness}/100, and light color ${light.color}. Change illumination and corresponding shadows while retaining the subject’s recognizable appearance, pose, scene geometry and framing. These are lighting directions for the image edit, not instructions to add lamps or light-source objects.`;
}
export function ImageRelightControls({
  value,
  onChange,
  mapConditioned = false,
  portraitConditioned = false,
  postBrightness = 0,
  onPostBrightness,
}: {
  value?: ImageLighting | null;
  mapConditioned?: boolean;
  portraitConditioned?: boolean;
  onChange: (value: ImageLighting | null) => void;
  postBrightness?: number;
  onPostBrightness?: (value: number) => void;
}) {
  const [colorOpen, setColorOpen] = useState(false);
  const gradient = useId();
  const light = value || defaultImageLighting;
  const set = (patch: Partial<ImageLighting>) => onChange({ ...light, ...patch });
  function move(event: PointerEvent<SVGSVGElement>) {
    const r = event.currentTarget.getBoundingClientRect();
    set({
      azimuth: Math.round(
        Math.max(-180, Math.min(180, ((event.clientX - r.left) / r.width) * 360 - 180)),
      ),
      elevation: Math.round(
        Math.max(-90, Math.min(90, 90 - ((event.clientY - r.top) / r.height) * 180)),
      ),
    });
  }
  return (
    <section className="mini-image-lighting">
      <label className="mini-light-enable">
        <input
          type="checkbox"
          checked={!!value}
          onChange={(event) => onChange(event.target.checked ? { ...defaultImageLighting } : null)}
        />{' '}
        Use lighting controls
      </label>
      {!value ? (
        <small>Saved prompt-only editing is retained until you enable the controls.</small>
      ) : (
        <>
          <span>Quick select</span>
          <div className="mini-light-directions">
            {(
              [
                ['Top', 0, 90],
                ['Front', 0, 0],
                ['Right', 90, 0],
                ['Left', -90, 0],
                ['Back', 180, 0],
                ['Bottom', 0, -90],
              ] as const
            ).map(([name, azimuth, elevation]) => (
              <button
                type="button"
                key={name}
                aria-pressed={light.azimuth === azimuth && light.elevation === elevation}
                onClick={() => set({ azimuth, elevation })}
              >
                {name}
              </button>
            ))}
          </div>
          <svg
            viewBox="0 0 280 170"
            role="slider"
            aria-label="Lighting direction"
            aria-valuetext={`${light.azimuth} degrees horizontal, ${light.elevation} degrees vertical`}
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
                set({
                  azimuth: Math.max(
                    -180,
                    Math.min(
                      180,
                      light.azimuth +
                        (event.key === 'ArrowLeft' ? -5 : event.key === 'ArrowRight' ? 5 : 0),
                    ),
                  ),
                  elevation: Math.max(
                    -90,
                    Math.min(
                      90,
                      light.elevation +
                        (event.key === 'ArrowUp' ? 5 : event.key === 'ArrowDown' ? -5 : 0),
                    ),
                  ),
                });
              }
            }}
          >
            <defs>
              <radialGradient
                id={gradient}
                cx={`${50 + Math.sin((light.azimuth * Math.PI) / 180) * 35}%`}
                cy={`${50 - light.elevation / 3}%`}
                r={`${35 + light.softness / 3}%`}
              >
                <stop stopColor={light.color} stopOpacity={0.2 + light.brightness / 125} />
                <stop offset="1" stopColor="#202329" />
              </radialGradient>
            </defs>
            <ellipse cx="140" cy="100" rx="112" ry="34" fill="none" stroke="#555" />
            <circle cx="140" cy="85" r="57" fill={`url(#${gradient})`} stroke="#666" />
            <circle
              cx={20 + ((light.azimuth + 180) / 360) * 240}
              cy={15 + ((90 - light.elevation) / 180) * 140}
              r="7"
              fill={light.color}
              stroke="#d1fe17"
              strokeWidth="2"
            />
          </svg>
          <small>
            Drag to set direction; arrow keys adjust by5°. This guide is illustrative, not a preview
            of the result.
          </small>
          <div className="mini-fields">
            <label>
              Horizontal direction
              <input
                type="number"
                min={-180}
                max={180}
                value={light.azimuth}
                onChange={(event) =>
                  set({ azimuth: Math.max(-180, Math.min(180, Number(event.target.value))) })
                }
              />
            </label>
            <label>
              Elevation
              <input
                type="number"
                min={-90}
                max={90}
                value={light.elevation}
                onChange={(event) =>
                  set({ elevation: Math.max(-90, Math.min(90, Number(event.target.value))) })
                }
              />
            </label>
          </div>
          <label>
            Softness · {light.softness}%
            <input
              type="range"
              min={0}
              max={100}
              value={light.softness}
              onChange={(event) => set({ softness: Number(event.target.value) })}
            />
            <span className="mini-light-range-labels">
              <span>Hard</span>
              <span>Soft</span>
            </span>
          </label>
          {!portraitConditioned && <label>
            {mapConditioned ? 'Lighting-map brightness' : 'Brightness instruction'} · {light.brightness}%
            <input
              type="range"
              min={0}
              max={100}
              value={light.brightness}
              onChange={(event) => set({ brightness: Number(event.target.value) })}
            />
          </label>}
          <button
            type="button"
            className="mini-light-color"
            onClick={() => setColorOpen(!colorOpen)}
          >
            Color <i style={{ background: light.color }} />
            {light.color}
          </button>
          {colorOpen && <ColorPicker value={light.color} onChange={(color) => set({ color })} />}
          <small>
            {portraitConditioned ? 'Direction, color and softness guide portrait relighting; they are not calibrated physical settings. Background is restored, but facial detail and edge lighting can change.' : mapConditioned ? 'These controls shape the explicit lighting-map image. Direction is also mapped to the adapter’s nearest trained direction; softness changes the map falloff. They are not calibrated physical lighting. Subject detail and directional accuracy still require output review.' : 'These controls become explicit instructions for FLUX image editing. Direction, shadow accuracy and subject preservation require reviewing the output; they are not physical constraints.'}
          </small>
        </>
      )}
      {onPostBrightness && <>
        <label>Post-render brightness · {postBrightness > 0 ? '+' : ''}{postBrightness}%
          <input type="range" min={-100} max={100} step={1} value={postBrightness}
            onChange={(event) => onPostBrightness(Number(event.target.value))} />
        </label>
        <button type="button" disabled={postBrightness === 0} onClick={() => onPostBrightness(0)}>Reset brightness adjustment</button>
        <small>Adjusts the finished image’s brightness without changing shadows. High values may clip highlights.</small>
      </>}
    </section>
  );
}
