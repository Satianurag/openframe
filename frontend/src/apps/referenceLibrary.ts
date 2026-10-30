type Libraries = { apps: Record<string, Record<string, unknown>> };

function wordmarkImage(source: string): string | undefined {
  if (typeof DOMParser === 'undefined') return;
  const parsed = new DOMParser().parseFromString(source, 'image/svg+xml');
  if (parsed.querySelector('parsererror') || parsed.documentElement.localName !== 'svg') return;
  const clean = document.implementation.createDocument('http://www.w3.org/2000/svg', 'svg');
  const root = clean.documentElement;
  for (const name of ['width', 'height', 'viewBox', 'fill']) {
    const value = parsed.documentElement.getAttribute(name);
    if (value && !value.includes('url(')) root.setAttribute(name, value);
  }
  for (const item of parsed.querySelectorAll('path')) {
    const path = clean.createElementNS('http://www.w3.org/2000/svg', 'path');
    for (const name of ['d', 'fill', 'fill-rule', 'clip-rule']) {
      const value = item.getAttribute(name);
      if (value && !value.includes('url(')) path.setAttribute(name, value);
    }
    root.appendChild(path);
  }
  return `data:image/svg+xml,${encodeURIComponent(new XMLSerializer().serializeToString(clean))}`;
}

/** Prefer the optional local cache; fresh clones use the tracked public URL inventory. */
export async function loadReferenceLibraries(
  fallbackUrl: string,
  fetcher: typeof fetch = fetch,
  requiredApp?: string,
): Promise<Libraries> {
  async function read(url: string): Promise<Libraries> {
    const response = await fetcher(url);
    if (!response.ok) throw new Error('Reference inventory unavailable');
    const value = (await response.json()) as Partial<Libraries>;
    if (!value.apps || typeof value.apps !== 'object')
      throw new Error('Invalid reference inventory');
    return value as Libraries;
  }
  try {
    const local = await read('/reference-media/manifest.json');
    if (requiredApp && !local.apps[requiredApp])
      throw new Error('App absent from local reference cache');
    return local;
  } catch {
    const fallback = await read(fallbackUrl);
    const soul = fallback.apps['soul-image'];
    if (
      soul &&
      typeof soul.wordmark === 'string' &&
      soul.wordmark.startsWith('/reference-media/')
    ) {
      soul.wordmark =
        typeof soul.wordmark_svg === 'string' ? wordmarkImage(soul.wordmark_svg) : undefined;
    }
    return fallback;
  }
}
