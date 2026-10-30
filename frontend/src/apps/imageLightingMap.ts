import type { ImageLighting } from './ImageRelightControls';

// OpenFrame's explicit conditioning-map renderer. Gradient/color interpolation follows
// Apache-2.0 ComfyUI-IC-Light utils/image.py at 22811d903af8a90100dccef1c4b579526649a6ab.
// License: https://www.apache.org/licenses/LICENSE-2.0 (full text: docs/licenses/IC-Light-Apache-2.0.txt).
// Modified by OpenFrame: projected continuous direction, centered front/rear map and browser PNG output.
// dx8152's released two-image workflow permits custom luminance-map shape/color.
// These map controls are not a physical renderer or a prediction of the model output.
export const lightingMapVersion = 'openframe-qwen-lightmap-v1';
export const lightingMapKey = (light: ImageLighting) => JSON.stringify([lightingMapVersion, light.azimuth, light.elevation, light.softness, light.brightness, light.color.toLowerCase()]);

export function qwenLightDirection(light: ImageLighting) {
  if (light.elevation >= 60) return 'Above';
  if (light.elevation <= -60) return 'Below';
  const directions = ['Front', 'Right Front', 'Right', 'Right Rear', 'Rear', 'Left Rear', 'Left', 'Left Front'];
  return directions[((Math.round(light.azimuth / 45) % 8) + 8) % 8];
}
export function qwenLightingPrompt(prompt: string, light?: ImageLighting | null) {
  if (!light) return prompt;
  return `Relight Figure1 using the luminance map from Figure2 (light source from the ${qwenLightDirection(light)}). Preserve the subject's recognizable appearance, pose, scene and framing. ${prompt.trim()}`.trim();
}
export function imageRelightSize(width: number, height: number) {
  const scale = Math.sqrt(1024 * 1024 / (width * height));
  return { width: Math.floor(Math.round(width * scale) / 8) * 8, height: Math.floor(Math.round(height * scale) / 8) * 8 };
}

export function lightingMapPixels(light: ImageLighting, size = 1024) {
  const rgb = [1, 3, 5].map((start) => Number.parseInt(light.color.slice(start, start + 2), 16));
  if (rgb.some((value) => !Number.isFinite(value))) throw new Error('Choose a valid light color.');
  const az = light.azimuth * Math.PI / 180, el = light.elevation * Math.PI / 180;
  const dx = Math.sin(az) * Math.cos(el), dy = -Math.sin(el);
  const directional = Math.abs(dx) + Math.abs(dy);
  const exponent = 4 - 3.75 * light.softness / 100;
  const pixels = new Uint8ClampedArray(size * size * 4);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const nx = 2 * x / (size - 1) - 1, ny = 2 * y / (size - 1) - 1;
    const gradient = directional > 0.001
      ? Math.max(0, Math.min(1, 0.5 + (dx * nx + dy * ny) / (2 * directional)))
      : Math.max(0, 1 - Math.hypot(nx, ny) / Math.SQRT2);
    const luminance = (0.06 + 0.94 * gradient ** exponent) * light.brightness / 100;
    const offset = (y * size + x) * 4;
    for (let channel = 0; channel < 3; channel++) pixels[offset + channel] = rgb[channel] * luminance;
    pixels[offset + 3] = 255;
  }
  return pixels;
}
export async function lightingMapFile(light: ImageLighting) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1024;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('The lighting-map canvas is unavailable.');
  ctx.putImageData(new ImageData(lightingMapPixels(light), 1024, 1024), 0, 0);
  const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('Could not encode the lighting map.')), 'image/png'));
  return new File([blob], `${lightingMapVersion}-${qwenLightDirection(light).toLowerCase().replaceAll(' ', '-')}.png`, { type: 'image/png' });
}
