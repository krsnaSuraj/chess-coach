/* Service worker for Chess Coach v3.0.0 — offline-first PWA.
 * Caches static assets; falls back to network for API.
 */
const CACHE_NAME = 'chess-coach-v3.0.0';
const PRECACHE = [
  '/',
  '/static/index.html',
  '/static/css/themes.css',
  '/static/css/chessboard.css',
  '/static/js/sound.js',
  '/static/js/board.js',
  '/static/js/app.js',
  '/static/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Network-first for API
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws')) {
    return;  // default network behavior
  }
  // Cache-first for static
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((resp) => {
        // Cache new same-origin GET requests
        if (resp.ok && event.request.method === 'GET' && url.origin === location.origin) {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return resp;
      }).catch(() => caches.match('/static/index.html'));
    })
  );
});
