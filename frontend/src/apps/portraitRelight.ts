import type { ImageLighting } from './ImageRelightControls';

// Native Comfy FluxKontextImageScale buckets; the API enforces the same canvas.
const sizes = [[672,1568],[688,1504],[720,1456],[752,1392],[800,1328],[832,1248],[880,1184],[944,1104],[1024,1024],[1104,944],[1184,880],[1248,832],[1328,800],[1392,752],[1456,720],[1504,688],[1568,672]];
export function portraitRelightSize(width: number, height: number) {
  const [w,h] = [...sizes].sort((a,b) => Math.abs(width/height-a[0]/a[1])-Math.abs(width/height-b[0]/b[1]) || a[0]-b[0])[0];
  return {width:w,height:h};
}
export function portraitLightingPrompt(prompt: string, light?: ImageLighting | null) {
  if (!light) return prompt;
  const direction = Math.abs(light.azimuth) >= 135 ? 'behind the person' : Math.abs(light.azimuth) < 45 ? 'beside the camera' : `camera-${light.azimuth < 0 ? 'left' : 'right'}`;
  const elevation = light.elevation === 0 ? 'at face height' : `${light.elevation > 0 ? 'above' : 'below'} the face at ${Math.abs(light.elevation)} degrees`;
  const color = light.color.toUpperCase();
  const rgb = [1,3,5].map(i => parseInt(color.slice(i,i+2),16));
  const colorName = Math.max(...rgb)-Math.min(...rgb)<15 ? 'neutral white' : rgb[2]>rgb[0] && rgb[2]>rgb[1] ? 'cool blue' : rgb[0]>rgb[1] && rgb[0]>rgb[2] ? 'warm red' : rgb[1]>rgb[0] && rgb[1]>rgb[2] ? 'green' : 'colored';
  const quality = light.softness < 25 ? 'hard direct illumination with crisp, sharply defined cast shadows' : light.softness > 75 ? 'soft diffuse illumination with broad, blurred cast-shadow edges' : 'moderately soft illumination with gently defined cast shadows';
  return `Relight the portrait using a single ${colorName}${colorName === 'neutral white' ? '' : ` (${color})`} light positioned at ${direction}, ${elevation}. Keep medium overall exposure and the background dark. Use ${quality}. Preserve the same person, facial anatomy, expression, head position, clothing and framing; change only the illumination. Preserve the entire original scene content, background geometry, framing, and existing objects. Keep every light source outside the image. Do not add visible lighting equipment, softboxes, windows, white panels, wedges, or other objects.${prompt.trim() ? `\n\nAdditional instructions: ${prompt.trim()}` : ''}`;
}
