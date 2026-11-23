// Service worker of Speed_read_for_Andrey (the build for Android and other phones).
// 1. It keeps the files of the app in a cache, so the app opens without a network.
//    It never keeps the answers of other sites (OpenRouter, Europe PMC, the reader service).
// 2. It takes files, texts and links that other apps share with the installed app (Web Share Target):
//    it keeps the item in the cache "sra-share" and opens the app with ?shared=1. The app then opens the item.
const VERSION = 'bb5a3d45c070';
const CACHE = 'sra-app-' + VERSION;
const SHARE_CACHE = 'sra-share';
const FILES = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./icon-maskable-512.png"];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(FILES.map((f) => new Request(f, { cache: 'reload' })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (key.startsWith('sra-app-') && key !== CACHE) await caches.delete(key);
    await self.clients.claim();
  })());
});

async function takeShare(request) {
  const scope = self.registration.scope;
  try {
    const form = await request.formData();
    const files = form.getAll('file').filter((f) => f && typeof f === 'object' && typeof f.size === 'number' && f.size > 0);
    const cache = await caches.open(SHARE_CACHE);
    for (const key of await cache.keys()) await cache.delete(key);
    if (files.length) {
      const f = files[0];
      await cache.put(new Request(scope + 'shared-item'), new Response(f, { headers: {
        'content-type': f.type || 'application/octet-stream', 'x-share-kind': 'file', 'x-file-name': encodeURIComponent(f.name || 'shared file') } }));
    } else {
      const item = { title: String(form.get('title') || ''), text: String(form.get('text') || ''), url: String(form.get('url') || '') };
      if (!item.title && !item.text && !item.url) return Response.redirect(scope + '?shared=empty', 303);
      await cache.put(new Request(scope + 'shared-item'), new Response(JSON.stringify(item), { headers: { 'content-type': 'application/json', 'x-share-kind': 'text' } }));
    }
    return Response.redirect(scope + '?shared=1', 303);
  } catch (e) {
    return Response.redirect(scope + '?shared=empty', 303);
  }
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;                  // other sites: the browser handles them
  if (request.method === 'POST' && url.pathname.endsWith('/share-target')) { event.respondWith(takeShare(request)); return; }
  if (request.method !== 'GET') return;
  if (request.mode === 'navigate') {
    // only the app page itself comes from the cache; other pages of the site (for example the computer
    // version in desktop/) come from the network
    const root = new URL(self.registration.scope).pathname;
    if (url.pathname !== root && url.pathname !== root + 'index.html') return;
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      return (await cache.match('./index.html')) || (await cache.match('./')) || fetch(request);
    })());
    return;
  }
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    return (await cache.match(request, { ignoreSearch: true })) || fetch(request);
  })());
});
