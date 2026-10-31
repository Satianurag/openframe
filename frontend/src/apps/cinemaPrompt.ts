import type { CinemaLight } from './CinemaCreativeEditors';

/**
 * Prompt-side compiler for Cinema Studio's creative controls.
 *
 * These controls are direction, not physical scene parameters: the only way
 * they can influence an LTX render is through deterministic prompt guidance.
 * Keep every phrase here stable so the same project produces the same prompt.
 */
export type CinemaPromptControls = {
  film: { genre: string; era: string; tempo: string };
  camera: { body: string; lens: string; aperture: string; movements: string[] };
  palette: string;
  palette_colors?: string[];
  lighting: string;
  custom_lights?: CinemaLight[];
};

export type CinemaReferenceRole = 'character' | 'location' | 'prop';

export type CinemaReferenceLegendEntry = {
  name: string;
  role: CinemaReferenceRole;
};

const genreNotes: Record<string, string> = {
  Drama: 'grounded human drama, restrained performances, emotionally motivated framing',
  Noir: 'shadowy film-noir atmosphere, hard key lighting, deep blacks, venetian-blind shadows and moral ambiguity',
  Comedy: 'comedic timing, bright readable staging and expressive performances',
  Horror: 'dread-building horror atmosphere, negative space, unsettling shadows and a mounting sense of threat',
  Action: 'kinetic action staging, clear spatial geography and weighty, impactful movement',
  Epic: 'large-scale epic scope, sweeping vistas and monumental composition',
};

const eraNotes: Record<string, string> = {
  '1960s': '1960s period detail, analog film stock, muted warm dyes, period-accurate wardrobe and props',
  '1980s': '1980s period detail, saturated neon accents, zoom-heavy camerawork and analog video texture',
  '1990s': '1990s period detail, grunge and early-digital textures, naturalistic color',
  '2000s': '2000s period detail, early digital cinematography and cool color casts',
  '2020s': 'present-day 2020s setting, contemporary technology and styling',
};

const tempoNotes: Record<string, string> = {
  Dynamic: 'brisk, energetic pacing with continuous motion and a driving rhythm',
  Calm: 'calm deliberate pacing, longer holds and unhurried movement',
  'Single shot': 'one continuous single take with no cuts; camera and action flow uninterrupted',
  Chaotic: 'chaotic frenetic pacing, overlapping action and a restless camera',
};

const bodyNotes: Record<string, string> = {
  Modern: 'modern digital cinema camera, clean highlight roll-off and precise detail',
  '35mm Film': '35mm film camera with organic grain, halation and a soft analog roll-off',
  '8mm Film': '8mm home-movie camera with coarse grain, soft edges and gentle gate weave',
  'DV Camcorder': 'early DV camcorder with interlaced video texture and limited dynamic range',
};

const lensNotes: Record<string, string> = {
  'Clean Sharp': 'clean modern prime lens, high micro-contrast, minimal aberration and crisp detail',
  Anamorphic: 'anamorphic optics with oval bokeh, horizontal flares and widescreen perspective compression',
  'Vintage Anamorphic': 'vintage anamorphic optics with oval bokeh, warm flares, soft edges and gentle distortion',
  'Warm Vintage': 'warm vintage lens with lower contrast, amber color bias and soft halation',
  'Halation Vintage': 'vintage lens with pronounced halation, blooming highlights and a dreamy analog falloff',
};

const apertureNotes: Record<string, string> = {
  'f/1.4 Wide Open': 'very shallow depth of field, creamy focus falloff and strong subject separation',
  'f/4 Moderate': 'moderate depth of field, balanced subject separation and environmental context',
  'f/11 Deep Focus': 'deep focus with the foreground through background held sharp',
};

/** Brief, model-readable definitions for every movement offered by the UI. */
export const cameraMovementDescriptions: Record<string, string> = {
  Snorricam:
    "camera rigidly mounted to the performer's body, so the subject stays fixed in frame while the world swings and distorts around them",
  'Robot arm':
    'precise motorized robotic-arm move with repeatable, accelerated arcs, sweeps or spins',
  'Tilt up': 'the camera pivots upward from a fixed position, revealing height',
  'Rack focus': 'focus pulls between foreground and background planes within a single shot',
  'Tilt down': 'the camera pivots downward from a fixed position, revealing the ground or a detail',
  POV: "first-person perspective from a character's eyes, with their movement driving the frame",
  'Pan left': 'the camera rotates horizontally to the left from a fixed position',
  'Crane up': 'the camera rises vertically on a crane, lifting to reveal the wider scene',
  'Pan right': 'the camera rotates horizontally to the right from a fixed position',
  'Crane down': 'the camera descends vertically on a crane, settling toward the subject',
  'Side tracking': 'the camera tracks sideways alongside the subject, keeping them parallel in frame',
  'Pedestal up': 'the camera body rises vertically without tilting or panning',
  'Pedestal down': 'the camera body lowers vertically without tilting or panning',
  Handheld: 'loose human-held camera with subtle shake, breathing and imperfect framing',
  Tracking: 'the camera follows the subject through the space, matching their path and pace',
  'Drone orbit': 'an aerial drone circles the subject in a smooth orbit, revealing the surrounding scale',
  'Dolly zoom': 'the camera moves toward or away while zooming to hold subject size, shifting background perspective (Vertigo effect)',
  'Aerial pullback': 'a high aerial camera retreats and rises to reveal the scale of the location',
  'Static shot': 'locked-off camera with no movement; action happens within a fixed frame',
  'Bullet time': 'time slows while the camera sweeps around frozen or near-frozen action',
  'Whip pan': 'a very fast horizontal pan with heavy motion blur that lands on a new subject',
  'Slow zoom in': 'a gradual zoom toward the subject, increasing emphasis and intimacy',
  'Arc left': 'the camera arcs around the subject to the left, changing the background perspective',
  'Slow zoom out': 'a gradual zoom away from the subject, revealing more of the surroundings',
  'Arc right': 'the camera arcs around the subject to the right, changing the background perspective',
  'Truck right': 'the camera translates laterally to the right, keeping its facing direction',
  'Dolly in': 'the camera physically moves toward the subject, increasing intimacy and emphasis',
  'Truck left': 'the camera translates laterally to the left, keeping its facing direction',
  'Dolly out': 'the camera physically retreats from the subject, revealing context',
  'Slider right': 'a smooth short lateral slider move to the right with steady framing',
  'Crush zoom': 'a fast, aggressive zoom toward the subject with compressed perspective',
  'Slider left': 'a smooth short lateral slider move to the left with steady framing',
  'Helicopter shot': 'a moving aerial helicopter-style shot, banking and travelling over the scene',
};

export function describeCameraMovement(name: string): string {
  return cameraMovementDescriptions[name] || `a deliberate ${name.toLowerCase()} camera move`;
}

function lightPosition(light: CinemaLight): string {
  const horizontal =
    light.x < -0.2 ? 'camera-left of the subject' : light.x > 0.2 ? 'camera-right of the subject' : 'centered on the subject';
  const vertical =
    light.y < -0.2 ? 'above subject height' : light.y > 0.2 ? 'below subject height' : 'at subject height';
  const depth =
    light.position === 'Back'
      ? 'behind the subject'
      : light.position === 'Top'
        ? 'overhead'
        : light.position === 'Bottom'
          ? 'low, below the subject'
          : 'in front of the subject';
  return `${depth}, ${horizontal}, ${vertical}`;
}

export function compileCinemaPrompt(controls: CinemaPromptControls): string {
  const lines: string[] = [];
  const { genre, era, tempo } = controls.film;
  const { body, lens, aperture } = controls.camera;
  const movements = (controls.camera.movements || []).filter(Boolean);

  if (genre && genre !== 'General' && genre !== 'Auto')
    lines.push(`- Genre: ${genre} — ${genreNotes[genre] || `${genre} genre conventions and mood`}.`);
  if (era && era !== 'Auto')
    lines.push(`- Period: ${era} — ${eraNotes[era] || `${era} period detail, wardrobe and production design`}.`);
  if (tempo && tempo !== 'Auto')
    lines.push(`- Pacing: ${tempo} — ${tempoNotes[tempo] || `${tempo} pacing`}.`);
  if (body && body !== 'Auto')
    lines.push(`- Camera body: ${body} — ${bodyNotes[body] || `${body} camera character`}.`);
  if (lens && lens !== 'Auto')
    lines.push(`- Lens: ${lens} — ${lensNotes[lens] || `${lens} optical character`}.`);
  if (aperture && aperture !== 'Auto')
    lines.push(`- Aperture: ${aperture} — ${apertureNotes[aperture] || `${aperture} depth of field`}.`);
  if (movements.length)
    lines.push(
      `- Camera movement sequence (in order): ${movements
        .map((name, index) => `${index + 1}) ${name} — ${describeCameraMovement(name)}`)
        .join('; ')}.`,
    );

  const colors = (controls.palette_colors || []).filter((color) => /^#[0-9a-f]{6}$/i.test(color));
  const paletteName =
    controls.palette && controls.palette !== 'Auto'
      ? controls.palette
      : colors.length
        ? 'Custom palette'
        : '';
  if (paletteName)
    lines.push(
      colors.length
        ? `- Color palette: ${paletteName}. Grade toward these exact hex values: ${colors.join(', ')}.`
        : `- Color palette: ${paletteName}.`,
    );

  const lights = (controls.custom_lights || []).filter(Boolean);
  const scheme =
    controls.lighting && controls.lighting !== 'Auto'
      ? controls.lighting
      : lights.length
        ? 'Custom'
        : '';
  if (scheme) {
    const lightLines = lights.map((light, index) => {
      const role = index === 0 ? 'Key light' : `Light ${index + 1}`;
      return `${role} positioned ${lightPosition(light)} (x ${Number(light.x).toFixed(2)}, y ${Number(light.y).toFixed(2)}), color ${light.color}, brightness ${light.brightness}%, diffusion ${light.diffuse}%`;
    });
    lines.push(
      `- Lighting scheme: ${scheme}${lightLines.length ? `. ${lightLines.join('; ')}` : ''}.`,
    );
  }

  return lines.length ? `Creative direction:\n${lines.join('\n')}` : '';
}

/**
 * Engine sheet order is reference_0..reference_N, so this line must enumerate
 * active references in exactly that order.
 */
export function compileReferenceSheetLegend(refs: CinemaReferenceLegendEntry[]): string {
  if (!refs.length) return '';
  return `Reference sheet (numbered row by row, left to right): ${refs
    .map((ref, index) => `${index + 1}) ${ref.name} — ${ref.role}`)
    .join(', ')}`;
}
