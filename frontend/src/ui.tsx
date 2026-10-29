import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { Icon } from './Icon';
export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    d?.showModal();
    return () => d?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      aria-label={title}
      className={`modal ${wide ? 'modal-wide' : ''}`}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          const r = e.currentTarget.getBoundingClientRect();
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            onClose();
        }
      }}
    >
      <header className="modal-header">
        <h2>{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Close dialog">
          <Icon name="close" />
        </button>
      </header>
      {children}
    </dialog>
  );
}
export { FieldSelect } from './Popovers';
export function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="toggle-row">
      <span>
        {label}
        {description && <small>{description}</small>}
      </span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="toggle" />
    </label>
  );
}
export function EmptyState({
  icon = 'film',
  title,
  description,
  action,
}: {
  icon?: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-symbol">
        <Icon name={icon} size={32} />
      </div>
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function ErrorBox({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div className="error-box" role="alert">
      <Icon name="info" />
      <span>{message}</span>
      {onDismiss && (
        <button className="icon-button" aria-label="Dismiss error" onClick={onDismiss}>
          <Icon name="close" size={16} />
        </button>
      )}
    </div>
  );
}

/** Human progress labels; the exact node class remains in the API record. */
export function renderStage(stage?: string) {
  if (!stage) return 'Preparing render';
  const value = stage.toLowerCase();
  if (/download.*(model|weight)|prepar.*model/.test(value)) return 'Preparing model files';
  if (/sampl|denois|diffus/.test(value)) return 'Rendering video';
  if (/upload|transfer|download|collect/.test(value)) return 'Transferring media';
  if (/mask|sam2|track/.test(value)) return 'Preparing the edit region';
  if (/text|token|clip.*encod/.test(value)) return 'Encoding your prompt';
  if (/audio/.test(value)) return 'Preparing audio';
  if (/decode/.test(value)) return 'Decoding video frames';
  if (/save|combine|write|mux/.test(value)) return 'Saving your video';
  if (/load|checkpoint|model/.test(value)) return 'Loading the model';
  if (/input|image|resize|source/.test(value)) return 'Preparing source media';
  if (/latent|noise|condition/.test(value)) return 'Preparing the video';
  if (/queued|submitted|waiting/.test(value)) return 'Waiting for the worker';
  if (/succeeded|complete/.test(value)) return 'Render complete';
  return stage.includes(' ') && !/[a-z][A-Z]|_/.test(stage) ? stage : 'Preparing render';
}
