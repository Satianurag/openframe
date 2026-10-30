import { useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import { mediaUrl } from '../api';
import { Icon } from '../Icon';
import type { Asset, ImageBox, ImageLayoutRegion } from '../types';
import { WorkspaceDialog } from './engine-apps-shared';
import './image-region-editor.css';

type Operation = 'layout' | 'move' | 'keep' | 'remove' | 'new';
const centre: ImageBox = [250, 250, 750, 750];
const operationOf = (region: ImageLayoutRegion): Operation => {
  if (region.bbox) return 'layout';
  if (region.source_reference == null) return 'new';
  if (region.target_bbox === null) return 'remove';
  if (JSON.stringify(region.source_bbox) === JSON.stringify(region.target_bbox)) return 'keep';
  return 'move';
};

export function ImageRegionEditor({
  regions,
  references,
  width,
  height,
  onApply,
  onClose,
}: {
  regions: ImageLayoutRegion[];
  references: Asset[];
  width: number;
  height: number;
  onApply: (regions: ImageLayoutRegion[]) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<ImageLayoutRegion[]>(() => structuredClone(regions));
  const [selected, setSelected] = useState(regions[0]?.id || '');
  const [actions, setActions] = useState<Record<string, Operation>>(() =>
    Object.fromEntries(regions.map((item) => [item.id, operationOf(item)])),
  );
  const [surface, setSurface] = useState<'output' | 'source'>('output');
  const [error, setError] = useState('');
  const origin = useRef<{ x: number; y: number } | null>(null);
  const region = draft.find((item) => item.id === selected);
  const operation = region ? actions[region.id] || operationOf(region) : 'layout';
  const reference = references[region?.source_reference ?? 0];
  const ratio =
    surface === 'source' && reference
      ? `${reference.width || width}/${reference.height || height}`
      : `${width}/${height}`;
  function patch(value: Partial<ImageLayoutRegion>) {
    setDraft((items) => items.map((item) => (item.id === selected ? { ...item, ...value } : item)));
    setError('');
  }
  function add() {
    const value: ImageLayoutRegion = {
      id: `region_${crypto.randomUUID().replaceAll('-', '').slice(0, 24)}`,
      description: '',
      bbox: [...centre],
    };
    setDraft((items) => [...items, value]);
    setSelected(value.id);
    setSurface('output');
    setError('');
  }
  function changeOperation(next: Operation) {
    setActions((items) => ({ ...items, [selected]: next }));
    if (!region) return;
    const sourceBox = region.source_bbox || region.bbox || [...centre];
    const target = region.target_bbox || region.bbox || [...centre];
    const value: ImageLayoutRegion = { id: region.id, description: region.description };
    if (next === 'layout') value.bbox = target;
    else if (next === 'new') {
      value.source_reference = null;
      value.target_bbox = target;
    } else {
      value.source_reference = Math.min(region.source_reference ?? 0, references.length - 1);
      value.source_bbox = sourceBox;
      value.target_bbox = next === 'remove' ? null : next === 'keep' ? [...sourceBox] : target;
    }
    setDraft((items) => items.map((item) => (item.id === selected ? value : item)));
    setSurface(next === 'remove' ? 'source' : 'output');
    setError('');
  }
  function point(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.round(Math.max(0, Math.min(1000, ((event.clientX - rect.left) * 1000) / rect.width))),
      y: Math.round(Math.max(0, Math.min(1000, ((event.clientY - rect.top) * 1000) / rect.height))),
    };
  }
  function draw(event: PointerEvent<HTMLDivElement>) {
    if (!origin.current || !region) return;
    const end = point(event),
      start = origin.current;
    const box: ImageBox = [
      Math.min(start.y, end.y),
      Math.min(start.x, end.x),
      Math.max(start.y, end.y),
      Math.max(start.x, end.x),
    ];
    if (box[2] - box[0] < 2 || box[3] - box[1] < 2) return;
    if (surface === 'source')
      patch({
        source_bbox: box,
        ...(operation === 'keep' ? { target_bbox: [...box] as ImageBox } : {}),
      });
    else if (operation === 'layout') patch({ bbox: box });
    else
      patch({
        target_bbox: box,
        ...(operation === 'keep' ? { source_bbox: [...box] as ImageBox } : {}),
      });
  }
  function apply() {
    if (draft.some((item) => !item.description.trim())) {
      setError('Describe the subject or change in each region before applying.');
      return;
    }
    onApply(draft.map((item) => ({ ...item, description: item.description.trim() })));
    onClose();
  }
  return (
    <WorkspaceDialog title="Layout and regions" onClose={onClose} className="image-region-dialog">
      <div className="image-region-body">
        <aside className="image-region-list">
          <h3>
            Regions <small>{draft.length}/32</small>
          </h3>
          {draft.map((item, index) => (
            <button
              key={item.id}
              className={item.id === selected ? 'active' : ''}
              onClick={() => {
                setSelected(item.id);
                setSurface(operationOf(item) === 'remove' ? 'source' : 'output');
              }}
            >
              <span>{index + 1}</span>
              <strong>{item.description || `Region ${index + 1}`}</strong>
            </button>
          ))}
          <button className="ea-outline" onClick={add} disabled={draft.length >= 32}>
            <Icon name="plus" size={15} /> Add region
          </button>
          <p>
            Describe each subject, then draw its location. Boxes guide the model; use a preservation
            mask when original pixels must stay unchanged.
          </p>
        </aside>
        <section className="image-region-canvas">
          <div className="image-region-tabs">
            <button
              className={surface === 'output' ? 'active' : ''}
              disabled={operation === 'remove'}
              onClick={() => setSurface('output')}
            >
              Output layout
            </button>
            <button
              className={surface === 'source' ? 'active' : ''}
              disabled={!region || region.source_reference == null}
              onClick={() => setSurface('source')}
            >
              Source region
            </button>
            <span>{surface === 'source' ? reference?.name : `${width} × ${height}`}</span>
          </div>
          <div className="image-region-stage">
            <div
              className="image-region-plane"
              style={{
                aspectRatio: ratio,
                width: `min(100%, ${400 * (surface === 'source' && reference ? (reference.width || width) / (reference.height || height) : width / height)}px)`,
              }}
              onPointerDown={(event) => {
                if (!region) return;
                event.currentTarget.setPointerCapture(event.pointerId);
                origin.current = point(event);
              }}
              onPointerMove={draw}
              onPointerUp={(event) => {
                draw(event);
                origin.current = null;
              }}
              onPointerCancel={() => {
                origin.current = null;
              }}
            >
              {surface === 'source' && reference && (
                <img src={mediaUrl(reference)} alt="Source region reference" draggable={false} />
              )}
              <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Region layout">
                {draft.map((item, index) => {
                  const box =
                    surface === 'source'
                      ? item.source_reference === region?.source_reference
                        ? item.source_bbox
                        : undefined
                      : item.bbox || item.target_bbox;
                  if (!box) return null;
                  return (
                    <g key={item.id} className={item.id === selected ? 'selected' : ''}>
                      <rect
                        x={box[1]}
                        y={box[0]}
                        width={box[3] - box[1]}
                        height={box[2] - box[0]}
                      />
                      <text x={box[1] + 10} y={Math.min(980, box[0] + 33)}>
                        {index + 1}
                      </text>
                    </g>
                  );
                })}
              </svg>
              {!draft.length && <p>Add a region to begin arranging your image.</p>}
            </div>
          </div>
          <p className="image-region-guidance">
            Drag to replace the selected rectangle. The output view is a composition guide, not a
            generated preview.
          </p>
        </section>
        <aside className="image-region-properties">
          {region ? (
            <>
              <label>
                Description
                <textarea
                  value={region.description}
                  maxLength={1000}
                  placeholder="A red ceramic vase on a wooden table…"
                  onChange={(event) => patch({ description: event.target.value })}
                />
              </label>
              <label>
                Action
                <select
                  value={operation}
                  onChange={(event) => changeOperation(event.target.value as Operation)}
                >
                  <option value="layout">Place described subject</option>
                  <option value="new">Add or recolor region</option>
                  <option value="move" disabled={!references.length}>
                    Move from reference
                  </option>
                  <option value="keep" disabled={!references.length}>
                    Keep at same location
                  </option>
                  <option value="remove" disabled={!references.length}>
                    Remove from reference
                  </option>
                </select>
              </label>
              {region.source_reference != null && (
                <label>
                  Source reference
                  <select
                    value={region.source_reference}
                    onChange={(event) => patch({ source_reference: Number(event.target.value) })}
                  >
                    {references.map((asset, index) => (
                      <option value={index} key={asset.id}>
                        {index + 1}. {asset.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <p>
                {operation === 'remove'
                  ? 'Draw the source area to remove. No destination region is submitted.'
                  : operation === 'keep'
                    ? 'Source and destination coordinates match. This guides generation; it does not lock the original pixels.'
                    : 'Use the source and output tabs to set the corresponding regions.'}
              </p>
              <button
                className="ea-outline"
                onClick={() => {
                  const remaining = draft.filter((item) => item.id !== selected);
                  setDraft(remaining);
                  setSelected(remaining[0]?.id || '');
                  setSurface('output');
                }}
              >
                Remove region
              </button>
            </>
          ) : (
            <p>Select a region to edit its description and action.</p>
          )}
        </aside>
      </div>
      {error && (
        <p className="ea-error" role="alert">
          {error}
        </p>
      )}
      <footer>
        <button className="ea-outline" onClick={onClose}>
          Cancel
        </button>
        <button className="ea-lime" onClick={apply}>
          Apply regions
        </button>
      </footer>
    </WorkspaceDialog>
  );
}
