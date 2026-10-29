import { Children, isValidElement, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from './Icon';

export function AnchoredPopover({
  anchor,
  onClose,
  children,
  width = 160,
  className = '',
  label,
  top,
  bottomOffset = 0,
  placement = 'right-end',
}: {
  anchor: HTMLElement | null;
  onClose: () => void;
  children: ReactNode;
  width?: number;
  className?: string;
  label: string;
  top?: number;
  bottomOffset?: number;
  placement?: 'right-end' | 'bottom-end';
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ left: 0, top: 0, visible: false });
  useLayoutEffect(() => {
    const place = () => {
      const r = anchor?.getBoundingClientRect();
      const box = ref.current?.getBoundingClientRect();
      if (!box) return;
      const mobile = innerWidth <= 700;
      setPosition({
        left: mobile
          ? Math.max(8, (innerWidth - box.width) / 2)
          : Math.max(
              8,
              Math.min(
                innerWidth - box.width - 8,
                placement === 'bottom-end'
                  ? (r?.right || innerWidth - 8) - box.width
                  : (r?.right || 16) + 8,
              ),
            ),
        top: Math.max(
          8,
          Math.min(
            innerHeight - box.height - 8,
            mobile
              ? innerHeight - box.height - 78
              : (top ??
                  (placement === 'bottom-end'
                    ? (r?.bottom || 16) + 8
                    : (r?.bottom || innerHeight / 2) - box.height + bottomOffset)),
          ),
        ),
        visible: true,
      });
    };
    place();
    const resizeObserver = new ResizeObserver(place);
    if (ref.current) resizeObserver.observe(ref.current);
    addEventListener('resize', place);
    addEventListener('scroll', place, true);
    return () => {
      resizeObserver.disconnect();
      removeEventListener('resize', place);
      removeEventListener('scroll', place, true);
    };
  }, [anchor, top, bottomOffset, width, placement]);
  useEffect(() => {
    const outside = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node) && !anchor?.contains(e.target as Node))
        onClose();
    };
    const keyboard = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        anchor?.focus();
      }
      if (
        (e.key === 'ArrowDown' || e.key === 'ArrowUp') &&
        ref.current?.contains(document.activeElement) &&
        !(document.activeElement instanceof HTMLInputElement)
      ) {
        e.preventDefault();
        const items = [
          ...ref.current.querySelectorAll<HTMLButtonElement>('[role=menuitemradio], .model-option'),
        ];
        const index = items.indexOf(document.activeElement as HTMLButtonElement);
        items[(index + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus();
      }
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', keyboard);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', keyboard);
    };
  }, [anchor, onClose]);
  useEffect(() => {
    if (!ref.current?.contains(document.activeElement)) {
      ref.current?.querySelector<HTMLElement>('[aria-checked="true"], input, button')?.focus();
    }
  }, []);
  return createPortal(
    <div
      ref={ref}
      role="dialog"
      aria-label={label}
      className={`anchored-popover ${className}`}
      style={{
        width,
        left: position.left,
        top: position.top,
        visibility: position.visible ? 'visible' : 'hidden',
      }}
    >
      {children}
    </div>,
    anchor?.closest('dialog') || document.body,
  );
}

export function FieldSelect({
  label,
  value,
  children,
  onChange,
  disabled = false,
  hint,
}: {
  label: string;
  value: string | number;
  children: ReactNode;
  onChange: (value: string) => void;
  disabled?: boolean;
  hint?: string;
}) {
  const button = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const options = Children.toArray(children).flatMap((node) => {
    if (!isValidElement<{ value?: string | number; children?: ReactNode }>(node)) return [];
    const text = Children.toArray(node.props.children).join('');
    return [{ value: String(node.props.value ?? text), text }];
  });
  const selected = options.find((o) => o.value === String(value));
  const duration = label === 'Duration';
  const numbers = options.map((o) => +o.value).filter(Number.isFinite);
  return (
    <>
      <button
        ref={button}
        type="button"
        className={`field-select ${open ? 'field-open' : ''}`}
        aria-label={label}
        title={hint}
        aria-haspopup="dialog"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen(!open)}
      >
        <span className="field-copy">
          <span>{label}</span>
          <strong>{selected?.text || String(value)}</strong>
        </span>
        <Icon name="chevron" size={16} />
      </button>
      {open && (
        <AnchoredPopover
          anchor={button.current}
          onClose={() => setOpen(false)}
          width={duration ? 262 : label === 'Selection tracking' ? 270 : 160}
          className={duration ? 'duration-popover' : 'option-popover'}
          label={label}
        >
          {duration ? (
            <div className="duration-content">
              <span>Total duration</span>
              <strong>{selected?.text || `${value}s`}</strong>
              <div className="duration-slider">
                {' '}
                <input
                  aria-label="Total duration"
                  type="range"
                  min={Math.min(...numbers)}
                  max={Math.max(...numbers)}
                  step={1}
                  value={value}
                  onChange={(e) => onChange(e.target.value)}
                />
                <div className="duration-dot-grid" aria-hidden="true">
                  {numbers.map((n) => (
                    <i key={n} />
                  ))}
                </div>
              </div>
              <div className="duration-ticks">
                {numbers.map((n) => (
                  <span key={n}>{n}</span>
                ))}
              </div>
              {hint && <p className="muted small">{hint}</p>}
            </div>
          ) : (
            <>
              <div className="menu-label">{label}</div>
              <div role="menu" aria-label={label}>
                {options.map((o) => (
                  <button
                    key={o.value}
                    role="menuitemradio"
                    aria-checked={o.value === String(value)}
                    className="menu-option"
                    onClick={() => {
                      onChange(o.value);
                      setOpen(false);
                      button.current?.focus();
                    }}
                  >
                    <span>{o.text}</span>
                    {o.value === String(value) && <Icon name="check" size={16} />}
                  </button>
                ))}
              </div>
            </>
          )}
        </AnchoredPopover>
      )}
    </>
  );
}

export function ModelPopover({
  anchor,
  options,
  selected,
  onSelect,
  onClose,
}: {
  anchor: HTMLElement | null;
  options: { id: string; name: string; description: string; badge?: string }[];
  selected: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState('');
  const filtered = options.filter((o) =>
    `${o.name} ${o.description}`.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <AnchoredPopover
      anchor={anchor}
      onClose={onClose}
      width={402}
      bottomOffset={64}
      label="Choose a model"
      className="model-popover"
    >
      <label className="model-search">
        <Icon name="search" size={20} />
        <input
          autoFocus
          placeholder="Search…"
          aria-label="Search models"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </label>
      <div className="model-group-label">
        <Icon name="spark" size={14} />
        Open models
      </div>
      <div className="model-options">
        {filtered.map((o) => (
          <button
            className={`model-option ${selected === o.id ? 'selected' : ''}`}
            key={o.id}
            title={o.description}
            onClick={() => {
              onSelect(o.id);
              onClose();
            }}
          >
            <span className="model-option-icon">
              <Icon name="film" size={22} />
            </span>
            <span className="model-option-copy">
              <strong>
                {o.name}
                {o.badge && <em>{o.badge}</em>}
              </strong>
              <small>{o.description}</small>
            </span>
            {selected === o.id && <Icon name="check" size={16} />}
          </button>
        ))}
        {!filtered.length && <p className="menu-empty">No models match your search.</p>}
      </div>
    </AnchoredPopover>
  );
}
