import type { JobRequest } from '../types';

export type MotionConditioning = Pick<
  JobRequest,
  | 'motion_prompt'
  | 'pose_strength'
  | 'reference_strength'
  | 'pose_start_percent'
  | 'pose_end_percent'
>;
export const motionDefaults: Required<MotionConditioning> = {
  motion_prompt: '',
  pose_strength: 1,
  reference_strength: 1,
  pose_start_percent: 0,
  pose_end_percent: 1,
};
export function MotionControls({
  value,
  onChange,
}: {
  value: MotionConditioning;
  onChange: (value: Partial<MotionConditioning>) => void;
}) {
  const state = { ...motionDefaults, ...value };
  return (
    <details className="motion-conditioning">
      <summary>Motion conditioning</summary>
      <label>
        Driving-motion caption
        <textarea
          value={state.motion_prompt}
          placeholder="Optional description of the source movement; put appearance and background in the main prompt."
          onChange={(event) => onChange({ motion_prompt: event.target.value })}
        />
      </label>
      {(
        [
          { key: 'pose_strength', label: 'Driving motion strength', max: 2 },
          { key: 'reference_strength', label: 'Appearance reference strength', max: 2 },
          { key: 'pose_start_percent', label: 'Conditioning starts', max: 1 },
          { key: 'pose_end_percent', label: 'Conditioning ends', max: 1 },
        ] as const
      ).map(({ key, label, max }) => (
        <label key={key}>
          {label} · {state[key].toFixed(2)}
          <input
            type="range"
            min={0}
            max={max}
            step={0.05}
            value={state[key]}
            onChange={(event) => onChange({ [key]: Number(event.target.value) })}
          />
        </label>
      ))}
      <small>
        Start/end specify the denoising interval, not the source-video trim. Start must be lower
        than end.
      </small>
    </details>
  );
}
