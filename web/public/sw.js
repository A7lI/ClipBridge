const version = 'clipbridge-mobile-0.7.1-v1';
const assets = ['./', './index.html', './phone.html', './app.css', './app.mjs', './transport.mjs', './files.mjs', './phone-app.mjs', './phone-transport.mjs', './phone-qr.mjs', './offline.mjs', './ui.mjs', './boot.js', './manifest.webmanifest', './icon-192.png', './icon-512.png', './vendor/jsQR.js', './vendor/qrcode.mjs'];
self.addEventListener('install', event => event.waitUntil(caches.open(version).then(cache => cache.addAll(assets))));
self.addEventListener('activate', event => event.waitUntil((async () => {
  for (const key of await caches.keys()) if (key.startsWith('clipbridge-mobile-') && key !== version) await caches.delete(key);
  await self.clients.claim();
})()));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  const scope = new URL(self.registration.scope);
  if (event.request.method !== 'GET' || url.origin !== scope.origin || !url.pathname.startsWith(scope.pathname)) return;
  const file = url.pathname.slice(scope.pathname.length);
  const cacheKey = file === 'phone' ? new URL('./phone.html', scope).href : event.request;
  if (file !== 'phone' && !assets.some(asset => asset.slice(2) === file)) return;
  event.respondWith((async () => {
    try { const response = await fetch(event.request); if (response.ok) return response; } catch { /* Use the installed version offline. */ }
    const cached = await caches.match(cacheKey, { ignoreSearch: true });
    // Asset hosting may redirect .html URLs to clean paths. Rebuild the cached
    // response so a navigation with redirect mode "manual" can use it offline.
    return cached ? new Response(cached.body, { status: cached.status, statusText: cached.statusText, headers: cached.headers }) : new Response('Open ClipBridge online once to prepare offline sharing.', { status: 503 });
  })());
});
