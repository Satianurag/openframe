import type { Job } from '../types';

export function ImagePromptDetails({ job }: { job: Job }) {
  const video = !!job.metadata?.video_prompt;
  const value = video ? job.metadata?.video_prompt : job.metadata?.image_prompt;
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  const original = typeof record.original === 'string' ? record.original : job.request.prompt;
  const expanded = typeof record.expanded === 'string' ? record.expanded : '';
  const modelPrompt = typeof record.model_prompt === 'string' ? record.model_prompt : '';
  return (
    <details className="image-prompt-record">
      <summary>
        {video
          ? 'Video prompt record'
          : record.mode === 'caption'
            ? 'Complete caption used'
            : 'Prompt expansion record'}
      </summary>
      <h3>Submitted instructions</h3>
      <pre>{original}</pre>
      {expanded && (
        <>
          <h3>{video ? 'Enhanced video prompt' : 'Expanded caption'}</h3>
          <pre>{expanded}</pre>
        </>
      )}
      {modelPrompt && modelPrompt !== expanded && modelPrompt !== original && (
        <>
          <h3>Final model instructions</h3>
          <pre>{modelPrompt}</pre>
        </>
      )}
      <p>
        {video
          ? 'The exported project retains the exact prompt text used for this render.'
          : 'The exported project retains this record and the exact layout and reference settings.'}
      </p>
    </details>
  );
}
