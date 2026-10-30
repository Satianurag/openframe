const appDefinitions = [
  { id: 'content-factory', name: 'Content Factory', path: '/content-factory' },
  { id: 'supercomputer', name: 'Supercomputer', path: '/supercomputer' },
  { id: 'cinema-studio', name: 'Cinema Studio', path: '/generate' },
  { id: 'ai-influencer', name: 'AI Influencer', path: '/ai-influencer-studio' },
  { id: 'marketing-ads', name: 'Marketing & Ads Studio', path: '/marketing-studio' },
  { id: 'canvas', name: 'Canvas', path: '/canvas' },
  { id: 'soul-image', name: 'Image Studio', path: '/soul' },
  { id: 'soul-id-cast', name: 'Characters', path: '/soul-id' },
  { id: 'popcorn', name: 'Popcorn', path: '/popcorn' },
  { id: 'speak', name: 'Speak', path: '/speak' },
  { id: 'katana', name: 'Katana', path: '/katana' },
  { id: 'genjutsu', name: 'Genjutsu', path: '/genjutsu' },
  { id: 'mini-apps', name: 'Mini-apps', path: '/apps' },
] as const;
export type ApplicationId = (typeof appDefinitions)[number]['id'];
export const applications = appDefinitions.filter(
  (app) => !['supercomputer', 'canvas', 'speak'].includes(app.id),
);
export type AppOperation = {
  id: string;
  label: string;
  available: boolean;
  reason: string;
  effect_ids: string[];
  model_ids: string[];
};
export type Application = { id: string; name: string; operations: AppOperation[] };
export type AppDocument<T> = {
  id: string;
  app_id: string;
  title: string;
  schema_version: number;
  revision: number;
  state: T;
  asset_ids: string[];
  created_at: string;
  updated_at: string;
};
