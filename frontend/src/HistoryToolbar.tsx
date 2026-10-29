import { useRef, useState } from 'react';
import { AnchoredPopover } from './Popovers';
import { Icon } from './Icon';
import type { Model } from './types';

export type HistoryView = {
  model: string;
  dateFrom: string;
  dateTo: string;
  hideFailed: boolean;
  liked: boolean;
  downloaded: boolean;
  status?: string;
  layout: 'list' | 'grid' | 'masonry';
  size: number;
  fill: boolean;
};

const isoDay = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const marks = {
  filter: 'M4 6h16M7 12h10M10 18h4',
  calendar: 'M4 5h16v16H4zM4 10h16M8 3v4m8-4v4',
  hide: 'm3 3 18 18M10 5h2c5 0 9 7 9 7l-3 4M7 6C4 8 2 12 2 12s4 7 10 7l4-1M9 9a4 4 0 0 0 6 6',
  list: 'M3 3h18v18H3zM3 9h18',
  masonry: 'M3 3h18v18H3zM12 3v18M3 10h9m0 5h9',
  fill: 'M13.75 3.75h6.5v6.5m0-6.5-6.5 6.5M3.75 13.75v6.5h6.5m-6.5 0 6.5-6.5',
  stars:
    'M22.25 15C17.2153 15 15 17.2153 15 22.25C15 17.2153 12.7847 15 7.75 15C12.7847 15 15 12.7847 15 7.75C15 12.7847 17.2153 15 22.25 15ZM11.25 6.5C7.95139 6.5 6.5 7.95139 6.5 11.25C6.5 7.95139 5.04861 6.5 1.75 6.5C5.04861 6.5 6.5 5.04861 6.5 1.75C6.5 5.04861 7.95139 6.5 11.25 6.5Z',
};
function Mark({ name }: { name: keyof typeof marks }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={marks[name]} />
    </svg>
  );
}

export function HistoryToolbar({
  models,
  value,
  onChange,
}: {
  models: Model[];
  value: HistoryView;
  onChange: (patch: Partial<HistoryView>) => void;
}) {
  const filterRef = useRef<HTMLButtonElement>(null);
  const viewRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState<'filter' | 'view' | null>(null);
  const [submenu, setSubmenu] = useState<'models' | 'date' | 'status' | null>(null);
  const [month, setMonth] = useState(
    () => new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  );
  const [rangeStart, setRangeStart] = useState<string | null>(null);
  const close = () => {
    setOpen(null);
    setSubmenu(null);
    setRangeStart(null);
  };
  const today = isoDay(new Date());
  const active = Boolean(
    (value.model && value.model !== 'all') ||
    value.dateFrom ||
    value.dateTo ||
    value.hideFailed ||
    value.liked ||
    value.downloaded ||
    (value.status && value.status !== 'all'),
  );
  const choosePeriod = (days: number | null) => {
    const from = new Date();
    if (days) from.setDate(from.getDate() - days + 1);
    onChange({ dateFrom: days ? isoDay(from) : '', dateTo: days ? today : '' });
    setRangeStart(null);
  };
  const chooseDay = (day: string) => {
    if (!rangeStart) {
      setRangeStart(day);
      onChange({ dateFrom: day, dateTo: day });
    } else {
      onChange({
        dateFrom: day < rangeStart ? day : rangeStart,
        dateTo: day < rangeStart ? rangeStart : day,
      });
      setRangeStart(null);
    }
  };
  const calendarDays = Array.from(
    { length: 42 },
    (_, i) => new Date(month.getFullYear(), month.getMonth(), i - month.getDay() + 1),
  );
  return (
    <>
      <style>{styles}</style>
      <div className="history-toolbar">
        <button
          ref={filterRef}
          type="button"
          className={`history-tool ${open === 'filter' || active ? 'is-on' : ''}`}
          aria-haspopup="dialog"
          aria-expanded={open === 'filter'}
          onClick={() => {
            setSubmenu(null);
            setOpen(open === 'filter' ? null : 'filter');
          }}
        >
          <Mark name="filter" />
          Filter
        </button>
        <button
          ref={viewRef}
          type="button"
          className={`history-tool ${open === 'view' ? 'is-on' : ''}`}
          aria-haspopup="dialog"
          aria-expanded={open === 'view'}
          onClick={() => {
            setSubmenu(null);
            setOpen(open === 'view' ? null : 'view');
          }}
        >
          <Icon name="grid" size={14} />
          View
        </button>
      </div>
      {open && (
        <AnchoredPopover
          anchor={open === 'filter' ? filterRef.current : viewRef.current}
          label={open === 'filter' ? 'Filter history' : 'View history'}
          onClose={close}
          width={open === 'filter' ? 220 : 188}
          placement="bottom-end"
          className={`history-popover ${submenu ? 'has-submenu' : ''}`}
        >
          {open === 'filter' ? (
            <>
              <div className="history-main">
                <div className="history-label">Type</div>
                <button
                  type="button"
                  className="history-row"
                  aria-expanded={submenu === 'models'}
                  onClick={() => setSubmenu(submenu === 'models' ? null : 'models')}
                >
                  <Mark name="stars" />
                  <span>{models.find((m) => m.id === value.model)?.name || 'All models'}</span>
                  <Icon name="chevron" size={12} />
                </button>
                <button
                  type="button"
                  className="history-row"
                  aria-expanded={submenu === 'date'}
                  onClick={() => setSubmenu(submenu === 'date' ? null : 'date')}
                >
                  <Mark name="calendar" />
                  <span>Date range</span>
                  <Icon name="chevron" size={12} />
                </button>
                <button
                  type="button"
                  className="history-row"
                  role="switch"
                  aria-checked={value.hideFailed}
                  onClick={() => onChange({ hideFailed: !value.hideFailed })}
                >
                  <Mark name="hide" />
                  <span>Hide failed</span>
                  <i className={`history-switch ${value.hideFailed ? 'enabled' : ''}`} />
                </button>
                <div className="history-rule" />
                <div className="history-label">Activity</div>
                <button
                  type="button"
                  className="history-row"
                  aria-pressed={value.liked}
                  onClick={() => onChange({ liked: !value.liked })}
                >
                  <Icon name="heart" />
                  <span>Liked</span>
                  {value.liked && <Icon name="check" size={14} />}
                </button>
                <button
                  type="button"
                  className="history-row"
                  aria-pressed={value.downloaded}
                  onClick={() => onChange({ downloaded: !value.downloaded })}
                >
                  <Icon name="download" />
                  <span>Downloaded</span>
                  {value.downloaded && <Icon name="check" size={14} />}
                </button>
              </div>
              {submenu && (
                <div
                  className={`history-submenu history-submenu-${submenu}`}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') {
                      e.stopPropagation();
                      setSubmenu(null);
                    }
                  }}
                >
                  <button
                    type="button"
                    className="history-back history-row"
                    onClick={() => setSubmenu(null)}
                  >
                    <Icon name="chevron" style={{ transform: 'rotate(180deg)' }} size={12} />
                    Back
                  </button>
                  {submenu === 'models' && (
                    <>
                      <div className="history-label">Models</div>
                      {[{ id: 'all', name: 'All models' }, ...models].map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          className="history-row"
                          aria-pressed={value.model === m.id || (!value.model && m.id === 'all')}
                          onClick={() => {
                            onChange({ model: m.id });
                            setSubmenu(null);
                          }}
                        >
                          <span>{m.name}</span>
                          {(value.model === m.id || (!value.model && m.id === 'all')) && (
                            <Icon name="check" size={14} />
                          )}
                        </button>
                      ))}
                    </>
                  )}
                  {submenu === 'models' && value.status !== undefined && (
                    <>
                      <div className="history-rule" />
                      <div className="history-label">Job status</div>
                      {[
                        ['all', 'All'],
                        ['active', 'Active'],
                        ['succeeded', 'Completed'],
                        ['failed', 'Failed'],
                      ].map(([id, label]) => (
                        <button
                          key={id}
                          type="button"
                          className="history-row"
                          aria-pressed={value.status === id}
                          onClick={() => {
                            onChange({ status: id });
                            setSubmenu(null);
                          }}
                        >
                          <span>{label}</span>
                          {value.status === id && <Icon name="check" size={14} />}
                        </button>
                      ))}
                    </>
                  )}
                  {submenu === 'date' && (
                    <>
                      <div className="history-date-presets">
                        <div className="history-label">Date</div>
                        {[
                          [null, 'All period'],
                          [1, 'Today'],
                          [7, 'Last 7 days'],
                          [30, 'Last 30 days'],
                        ].map(([days, label]) => {
                          const start = new Date();
                          if (days) start.setDate(start.getDate() - Number(days) + 1);
                          const selected = days
                            ? value.dateFrom === isoDay(start) && value.dateTo === today
                            : !value.dateFrom && !value.dateTo;
                          return (
                            <button
                              key={String(label)}
                              type="button"
                              className="history-row"
                              aria-pressed={selected}
                              onClick={() => choosePeriod(days as number | null)}
                            >
                              <span>{label}</span>
                              {selected && <Icon name="check" size={14} />}
                            </button>
                          );
                        })}
                      </div>
                      <div className="history-calendar">
                        <div className="history-label">Custom range</div>
                        <div className="history-month">
                          <button
                            type="button"
                            aria-label="Previous month"
                            onClick={() =>
                              setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))
                            }
                          >
                            <Icon
                              name="chevron"
                              size={12}
                              style={{ transform: 'rotate(180deg)' }}
                            />
                          </button>
                          <span aria-live="polite">
                            {month.toLocaleDateString('en', { month: 'long', year: 'numeric' })}
                          </span>
                          <button
                            type="button"
                            aria-label="Next month"
                            onClick={() =>
                              setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))
                            }
                          >
                            <Icon name="chevron" size={12} />
                          </button>
                        </div>
                        <div className="history-calendar-grid">
                          {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
                            <span className="history-weekday" key={i}>
                              {d}
                            </span>
                          ))}
                          {calendarDays.map((d) => {
                            const day = isoDay(d);
                            const selected = Boolean(
                              value.dateFrom && day >= value.dateFrom && day <= value.dateTo,
                            );
                            return (
                              <button
                                key={day}
                                type="button"
                                aria-label={d.toLocaleDateString('en', { dateStyle: 'full' })}
                                aria-pressed={selected}
                                className={`${d.getMonth() !== month.getMonth() ? 'other-month' : ''} ${selected ? 'selected-day' : ''}`}
                                onClick={() => chooseDay(day)}
                              >
                                {d.getDate()}
                              </button>
                            );
                          })}
                        </div>
                        <span className="history-calendar-instruction" aria-live="polite">
                          {rangeStart
                            ? 'Choose the end date'
                            : value.dateFrom
                              ? `${value.dateFrom} – ${value.dateTo}`
                              : 'Choose start and end dates'}
                        </span>
                      </div>
                    </>
                  )}
                </div>
              )}
            </>
          ) : (
            <>
              <div className="history-label">Layout</div>
              <div role="menu" aria-label="History layout">
                {(['list', 'grid', 'masonry'] as const).map((layout) => (
                  <button
                    key={layout}
                    type="button"
                    className="history-row"
                    role="menuitemradio"
                    aria-checked={value.layout === layout}
                    onClick={() => onChange({ layout })}
                  >
                    {layout === 'grid' ? <Icon name="grid" /> : <Mark name={layout} />}
                    <span>{layout[0].toUpperCase() + layout.slice(1)}</span>
                    {value.layout === layout && <Icon name="check" size={14} />}
                  </button>
                ))}
              </div>
              <div className="history-rule" />
              <div className="history-label">Card size</div>
              <div className="history-size">
                <button
                  type="button"
                  aria-label="Fill card with media"
                  aria-pressed={value.fill}
                  onClick={() => onChange({ fill: !value.fill })}
                >
                  <Mark name="fill" />
                </button>
                <div
                  className="history-size-track"
                  style={{
                    background: `linear-gradient(to right,#4a4e50 ${(value.size - 1) * 25}%,#373a3c ${(value.size - 1) * 25}%)`,
                  }}
                >
                  <input
                    type="range"
                    aria-label="Card size"
                    min={1}
                    max={5}
                    step={1}
                    value={value.size}
                    onChange={(e) => onChange({ size: +e.target.value })}
                  />
                  <div className="history-size-ticks" aria-hidden="true">
                    {[20, 40, 60, 80].map((n) => (
                      <i key={n} style={{ left: `${n}%` }} />
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </AnchoredPopover>
      )}
    </>
  );
}

const styles = `
.history-toolbar{display:flex;align-items:center;gap:8px}
.history-toolbar .history-tool{display:flex;align-items:center;justify-content:center;gap:8px;height:36px;padding:0 12px;border:0;border-radius:11px;background:#141618;color:#939596;font-size:14px;font-weight:400;line-height:20px;cursor:pointer}
.history-toolbar .history-tool:hover,.history-toolbar .history-tool.is-on{background:#25282c;color:#f4f4f5}
.anchored-popover.history-popover{padding:8px;background:#121416;border:1px solid #202225;border-radius:12px;overflow:visible;backdrop-filter:none;color:#fafafa;font-size:14px;box-shadow:0 8px 24px #0002}
.history-popover .history-label{display:block;color:#919294;font-size:12px;font-weight:400;line-height:20px;padding:6px 8px 8px}
.history-popover .history-row{width:100%;height:36px;display:flex;align-items:center;gap:8px;border:0;background:transparent;color:inherit;padding:0 8px;border-radius:8px;text-align:left;font-size:14px;font-weight:400;line-height:20px;cursor:pointer;white-space:nowrap}
.history-popover .history-row span{flex:1;overflow:hidden;text-overflow:ellipsis}
.history-popover .history-row svg{flex-shrink:0}
.history-popover .history-row:hover{background:#232628}
.history-popover .history-row:focus-visible,.history-popover button:focus-visible{outline:2px solid #d1fe17;outline-offset:-2px}
.history-popover .history-rule{height:1px;background:#202225;margin:8px 0 4px}
.history-popover .history-switch{width:28px;height:16px;background:#626872;border-radius:10px;position:relative}
.history-popover .history-switch:after{content:'';position:absolute;top:2px;left:2px;width:12px;height:12px;background:#fff;border-radius:50%}
.history-popover .history-switch.enabled{background:#d1fe17}.history-popover .history-switch.enabled:after{left:14px;background:#151719}
.history-popover .history-size{display:flex;gap:4px;padding:4px}
.history-popover .history-size button{display:flex;align-items:center;justify-content:center;flex-shrink:0;width:32px;height:32px;padding:0;border:0;border-radius:8px;background:#292c2e;color:#989b9d;cursor:pointer}
.history-popover .history-size button[aria-pressed=true]{color:#d1fe17}
.history-size button svg{width:16px;height:16px}
.history-size-track{height:32px;position:relative;flex:1;min-width:0;border-radius:8px;overflow:hidden}
.history-popover .history-size input{appearance:none;-webkit-appearance:none;min-width:0;width:100%;height:32px;margin:0;border:0;border-radius:8px;background:transparent;cursor:pointer;position:relative;z-index:2;padding:0}
.history-size input::-webkit-slider-thumb{appearance:none;-webkit-appearance:none;width:1px;height:32px;background:transparent;border:0}
.history-size input::-moz-range-thumb{width:1px;height:32px;background:transparent;border:0}
.history-size-ticks{position:absolute;inset:0;pointer-events:none}
.history-size-ticks i{position:absolute;top:13px;width:1px;height:6px;background:#777b7d}
.history-submenu{position:absolute;right:calc(100% + 8px);top:40px;width:268px;padding:8px;border:1px solid #202225;border-radius:12px;background:#121416;box-shadow:0 8px 24px #0002;max-height:calc(100vh - 100px);overflow:auto}
.history-submenu-date{top:80px;padding:0;border:0;background:transparent;max-height:calc(100vh - 240px);overflow:auto}
.history-date-presets,.history-calendar{background:#121416;border:1px solid #202225;border-radius:12px;padding:8px}
.history-calendar{margin-top:4px;padding:12px 16px}
.history-calendar .history-label{padding:2px 0 18px}
.history-month{height:34px;border:1px solid #2c2f32;border-radius:20px;display:flex;align-items:center;justify-content:space-between;font-size:12px}
.history-month button{background:none;border:0;color:#8e9194;display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:50%;cursor:pointer}
.history-calendar-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:2px;margin-top:4px;text-align:center}
.history-calendar-grid .history-weekday{color:#919294;font-size:12px;line-height:30px}
.history-calendar-grid button{border:0;border-radius:8px;color:#fafafa;background:transparent;height:32px;padding:0;font-size:14px;font-weight:400;cursor:pointer}
.history-calendar-grid button.other-month{color:#62666a}.history-calendar-grid button[aria-current=date],.history-calendar-grid button:hover,.history-calendar-grid button.selected-day{background:#2c2f32;color:white}
.history-calendar-instruction{display:block;color:#939699;font-size:11px;line-height:16px;margin-top:6px}
.history-popover .history-back{display:none}
@media(max-width:700px){.history-popover.has-submenu{width:min(284px,calc(100vw - 16px))!important;max-height:calc(100dvh - 100px);overflow:auto}.history-popover.has-submenu .history-main{display:none}.history-submenu{position:static;width:100%;border:0;box-shadow:none;max-height:none;overflow:visible;padding:0}.history-popover .history-back{display:flex}.history-submenu-date{background:transparent;max-height:none}.history-date-presets,.history-calendar{border:0}.history-calendar{margin-top:0}}
@media(forced-colors:active){.history-tool,.history-popover,.history-submenu,.history-calendar,.history-date-presets,.history-switch{border:1px solid ButtonText!important}.history-popover button[aria-pressed=true],.history-popover button[aria-checked=true]{outline:1px solid Highlight}.history-popover .history-switch:after{background:ButtonText}.history-popover .history-switch.enabled{background:Highlight}}
`;
