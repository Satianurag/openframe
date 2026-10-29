/** Original outputs only. See public/previews/provenance.json for the exact render. */
export const previewSources: Record<string, string> = {
  'text-to-video': '/previews/ltx-fast-vase.jpg',
  'remove-object': '/previews/ltx-2.3-removal.jpg',
  'replace-object': '/previews/ltx-2.3-replacement.jpg',
  cinematic: '/previews/ltx-fast-cinematic.jpg',
  weather: '/previews/ltx-fast-weather.jpg',
  'product-reveal': '/previews/ltx-fast-lamp.jpg',
  restyle: '/previews/wan-restyle.jpg',
};
export const previewVideos: Record<string, string> = {
  'text-to-video': '/previews/ltx-fast-vase.mp4',
  'remove-object': '/previews/ltx-2.3-removal.mp4',
  'replace-object': '/previews/ltx-2.3-replacement.mp4',
  cinematic: '/previews/ltx-fast-cinematic.mp4',
  weather: '/previews/ltx-fast-weather.mp4',
  'product-reveal': '/previews/ltx-fast-lamp.mp4',
  restyle: '/previews/wan-restyle.mp4',
};

export const previewBeforeSources: Record<string, string> = {
  'remove-object': '/previews/ltx-2.3-removal-before.jpg',
  restyle: '/previews/ltx-2.3-removal-before.jpg',
};
export const previewDescriptions: Record<string, string> = {
  'text-to-video': 'Actual LTX Fast generation · seed42',
  'replace-object': 'Actual LTX2.3 replacement · full edited black-knight result',
  cinematic: 'Illustrative LTX Fast generation · not a video transformation',
  weather: 'Illustrative LTX Fast generation · not a weather edit',
  'product-reveal': 'Illustrative LTX Fast product shot · not reveal-motion proof',
  restyle: 'Actual Wan VACE restyle · source left / warm painterly result right',
  'remove-object': 'Actual LTX2.3 removal · source left / result right · static mask',
};

export const previewLabels: Record<string, string> = {
  'text-to-video': 'Actual · LTX Fast',
  'remove-object': 'Actual · LTX 2.3',
  'replace-object': 'Actual · LTX 2.3',
  restyle: 'Actual · Wan VACE',
  cinematic: 'Illustrative · LTX Fast',
  weather: 'Illustrative · LTX Fast',
  'product-reveal': 'Illustrative · LTX Fast',
};
