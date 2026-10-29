import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import {
  previewSources,
  previewVideos,
  previewBeforeSources,
  previewDescriptions,
} from './previews';
export const artMap: Record<string, { className: string; icon: string; label: string }> = {
  'text-to-video': { className: 'orbit', icon: 'video', label: 'An idea becomes a scene' },
  'image-to-video': { className: 'bloom', icon: 'image', label: 'Make the moment move' },
  'remove-object': { className: 'vanish', icon: 'mask', label: 'Keep only what belongs' },
  'replace-object': { className: 'replace', icon: 'brush', label: 'A new reality, same scene' },
  restyle: { className: 'chrome', icon: 'sliders', label: 'Change the whole atmosphere' },
  cinematic: { className: 'cinema', icon: 'film', label: 'Find your cinematic language' },
  'slow-motion': { className: 'motion', icon: 'clock', label: 'Let every second breathe' },
  dissolve: { className: 'dust', icon: 'spark', label: 'Matter into motion' },
  weather: { className: 'rain', icon: 'cloud', label: 'Set a different atmosphere' },
  'product-reveal': { className: 'product', icon: 'play', label: 'Put your product in focus' },
};
export function SceneArt({ id, children }: { id: string; children?: ReactNode }) {
  const art = artMap[id] || artMap['text-to-video'];
  const [missing, setMissing] = useState(false);
  useEffect(() => setMissing(false), [id]);
  return (
    <div
      className={`scene-art scene-${art.className}`}
      title={
        previewSources[id] && !missing
          ? previewDescriptions[id] ||
            'Original generated preview; see preview provenance for model and settings'
          : 'Authored workflow illustration, not a generated result'
      }
    >
      {!missing && previewVideos[id] ? (
        <video
          className="effect-poster"
          src={previewVideos[id]}
          poster={previewSources[id]}
          muted
          loop
          playsInline
          autoPlay={!matchMedia('(prefers-reduced-motion: reduce)').matches}
          onError={() => setMissing(true)}
        />
      ) : (
        !missing &&
        previewSources[id] && (
          <img
            className="effect-poster"
            src={previewSources[id]}
            alt={
              id === 'text-to-video'
                ? 'Original LTX Fast text-to-video example'
                : 'Original generated workflow preview'
            }
            onError={() => setMissing(true)}
          />
        )
      )}
      {previewBeforeSources[id] && !missing && (
        <>
          <img
            className="preview-before"
            src={previewBeforeSources[id]}
            alt="Original source before this actual edit"
          />
          <span className="preview-divider" />
          <span className="preview-comparison-label">Before / After</span>
        </>
      )}
      {(!previewSources[id] || missing) && (
        <div className="scene-geometry" aria-hidden="true">
          <div className="scene-orb" />
          <div className="scene-ring" />
          <div className="scene-floor" />
          <div className="scene-object" />
          <div className="scene-particles" />
        </div>
      )}
      {children}
    </div>
  );
}
