import type { Catalog } from '../types';

export function officialRecastAvailable(catalog: Catalog, provider: string, method: 'official' | 'official-union' = 'official'): boolean {
  if (provider !== 'local') return false;
  const methods = catalog.providers.find(item => item.id === provider)
    ?.model_capabilities?.['scail-2']?.composite_tracking_methods;
  if (methods) return methods.includes(method);
  return false;
}

export function preferredRecastSupport(catalog: Catalog, provider: string): 'native' | 'official' | 'official-union' {
  return officialRecastAvailable(catalog, provider, 'official-union') ? 'official-union'
    : officialRecastAvailable(catalog, provider) ? 'official' : 'native';
}

export function recastSupportIssue(catalog: Catalog, provider: string, method?: string): string {
  if (method !== 'official' && method !== 'official-union') return '';
  if (officialRecastAvailable(catalog, provider, method)) return '';
  const detail = catalog.providers.find(item => item.id === provider)
    ?.model_capabilities?.['scail-2']?.official_support_detail;
  if (method === 'official-union') return 'Source + generated performer support is unavailable on this connection. Update the OpenFrame nodes, configure the isolated SAM3.1 runtime and check the Local connection in Settings, or explicitly select an available support mode.';
  return detail || `Official source support requires a configured Linux CUDA ComfyUI host with compatible OpenFrame nodes and the isolated SAM3.1 runtime. Check the Local connection in Settings, or explicitly select an available support mode.`;
}

export function recastReferenceCleanupAvailable(catalog: Catalog, provider: string): boolean {
  if (provider !== 'local') return false;
  return catalog.providers.find(item => item.id === provider)
    ?.model_capabilities?.['scail-2']?.supports_recast_reference_cleanup === true;
}

export function recastReferenceCleanupIssue(catalog: Catalog, provider: string, enabled?: boolean): string {
  return enabled && !recastReferenceCleanupAvailable(catalog, provider)
    ? 'Clean reference edges is unavailable on this connection. Update the OpenFrame nodes and matting dependencies, then check the connection in Settings, or turn off this option explicitly.' : '';
}
