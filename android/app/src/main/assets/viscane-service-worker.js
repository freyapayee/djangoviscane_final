const CACHE_NAME = 'viscane-pages-v1';
const PAGE_PATHS = new Set(['/', '/homepage', '/farmer/recommendations', '/farmer/agronomic-logs', '/farmer/settings', '/farmer/feedback', '/scan/new', '/calculate']);
const inScope = (url) => url.origin === self.location.origin;
self.addEventListener('install', (event) => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
self.addEventListener('message', (event) => {
  const data = event.data;
  if (!data || data.type !== 'SAVE_PAGE') return;
  event.waitUntil((async () => {
    const url = new URL(data.url);
    if (!inScope(url) || !PAGE_PATHS.has(url.pathname) || typeof data.html !== 'string') return;
    const cache = await caches.open(CACHE_NAME);
    await cache.put(url.href, new Response(data.html, {headers:{'Content-Type':'text/html; charset=utf-8'}}));
    for (const href of (Array.isArray(data.styles) ? data.styles : [])) {
      const styleUrl = new URL(href);
      if (!inScope(styleUrl) || !styleUrl.pathname.startsWith('/static/')) continue;
      try { const response = await fetch(styleUrl.href); if (response.ok) await cache.put(styleUrl.href, response); } catch (_) {}
    }
  })());
});
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (!inScope(url)) return;
  if (url.pathname === '/logout') {
    event.respondWith(fetch(request).finally(() => caches.delete(CACHE_NAME)));
    return;
  }
  if (request.method !== 'GET' || url.pathname === '/service-worker.js') return;
  const isPage = request.mode === 'navigate' && PAGE_PATHS.has(url.pathname);
  const isStatic = url.pathname.startsWith('/static/');
  if (!isPage && !isStatic) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    try {
      const response = await fetch(request);
      if (response.ok && (isStatic || (isPage && response.headers.get('content-type')?.includes('text/html')))) await cache.put(request, response.clone());
      return response;
    } catch (error) {
      const saved = await cache.match(request);
      if (saved) return saved;
      if (isPage) { const root = await cache.match(new URL('/', self.location.origin).href); if (root) return root; }
      throw error;
    }
  })());
});

