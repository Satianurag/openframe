import type { CSSProperties } from 'react';
const paths: Record<string, string> = {
  arrow: 'm5 12 14 0m-5-5 5 5-5 5',
  chevron: 'm9 5 7 7-7 7',
  down: 'm6 9 6 6 6-6',
  close: 'm6 6 12 12M6 18 18 6',
  plus: 'M12 5v14M5 12h14',
  image: 'M4 4h16v16H4zM4 16l5-5 4 4 3-3 4 4M8 8h.01',
  video: 'M3 5h13v14H3zM16 9l5-3v12l-5-3',
  upload: 'M12 16V3m-4 4 4-4 4 4M4 16v5h16v-5',
  download: 'M12 3v13m-4-4 4 4 4-4M4 17v4h16v-4',
  folder: 'M3 5h6l2 3h10v12H3z',
  clock: 'M12 8v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
  settings: 'M9 3h6l1 4 4 1v8l-4 1-1 4H9l-1-4-4-1V8l4-1zM15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  search: 'M16 16l5 5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  play: 'm8 4 12 8-12 8z',
  pause: 'M8 5v14M16 5v14',
  fullscreen: 'M8 3H3v5M16 3h5v5M21 16v5h-5M3 16v5h5',
  spark: 'm12 2 2.8 7.2L22 12l-7.2 2.8L12 22l-2.8-7.2L2 12l7.2-2.8z',
  check: 'm4 12 5 5L20 6',
  heart: 'M12 21 3.5 12.5C-2 6 5 0 12 7c7-7 14-1 8.5 5.5z',
  trash: 'M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7',
  refresh: 'M20 7V2l-4 4M4 17v5l4-4M20 7a9 9 0 0 0-15-2M4 17a9 9 0 0 0 15 2',
  cloud: 'M7 19a5 5 0 1 1 0-10 7 7 0 0 1 13 2 4 4 0 0 1-1 8z',
  monitor: 'M3 3h18v14H3zM8 21h8m-4-4v4',
  code: 'm8 5-6 7 6 7m8-14 6 7-6 7m-3-16-2 18',
  book: 'M12 5c-3-2-6-2-10-1v16c4-1 7-1 10 1 3-2 6-2 10-1V4c-4-1-7-1-10 1v16',
  brush: 'm14 3 7 7-9 9-7-7zM5 12c-5 2-2 7-4 9 4 0 8-1 8-5',
  erase: 'm14 3 8 8-10 10H7l-6-6zM6 10l9 9',
  undo: 'M8 4 2 10l6 6M2 10h12a7 7 0 0 1 0 14',
  square: 'M4 4h16v16H4z',
  split: 'M3 4h18v16H3zM12 4v16',
  save: 'M4 3h13l4 4v14H3V3zM7 3v6h10V3M7 21v-8h10v8',
  info: 'M12 11v6m0-10v.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  menu: 'M3 6h18M3 12h18M3 18h18',
  stop: 'M5 5h14v14H5z',
  copy: 'M8 8h13v13H8zM16 8V3H3v13h5',
  external: 'M14 3h7v7m0-7L10 14M10 3H3v18h18v-7',
  mask: 'M3 5h18v10c-5 8-13 8-18 0zM7 10h2m6 0h2M9 16h6',
  film: 'M4 3h16v18H4zM4 8h16M4 16h16M8 3v18m8-18v18',
  sound: 'M3 9h4l5-5v16l-5-5H3zM16 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14',
  sliders: 'M5 3v18M12 3v18M19 3v18M2 8h6m1 8h6m1-10h6',
  bolt: 'm13 2-9 12h7l-1 8 10-13h-8z',
};
export function Icon({
  name,
  size = 18,
  style,
  className = '',
}: {
  name: string;
  size?: number;
  style?: CSSProperties;
  className?: string;
}) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
      className={className}
    >
      <path d={paths[name] || paths.spark} />
    </svg>
  );
}
