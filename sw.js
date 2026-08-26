const CACHE = 'bd-recipes-v10';
const CORE = [
  "./",
  "index.html",
  "styles.css",
  "app.js",
  "manifest.webmanifest",
  "recipes.json",
  "assets/icons/icon.svg",
  "assets/icons/icon-192.png",
  "assets/icons/icon-512.png",
  "assets/icons/placeholder.svg",
  "assets/bloody_dave_logo.png",
  "Recipes/BD-0001.md",
  "Recipes/BD-0002.md",
  "Recipes/BD-0003.md",
  "Recipes/BD-0004.md",
  "Recipes/BD-0005.md",
  "Recipes/BD-0006.md",
  "Recipes/BD-0007.md",
  "Recipes/BD-0008.md",
  "Recipes/BD-0009.md",
  "Recipes/BD-0010.md",
  "Recipes/BD-0011.md",
  "Recipes/BD-0012.md",
  "Recipes/BD-0013.md",
  "Recipes/BD-0014.md",
  "Recipes/BD-0015.md",
  "Recipes/BD-0016.md",
  "Recipes/BD-0017.md",
  "Recipes/BD-0018.md",
  "Recipes/BD-0019.md",
  "Recipes/BD-0020.md",
  "Recipes/BD-0021.md",
  "Recipes/BD-0022.md",
  "Recipes/BD-0023.md",
  "Recipes/BD-0024.md",
  "Recipes/BD-0025.md",
  "Recipes/BD-0026.md",
  "Recipes/BD-0027.md",
  "Recipes/BD-0028.md",
  "Recipes/BD-0029.md",
  "Recipes/BD-0030.md",
  "Recipes/BD-0031.md",
  "Recipes/BD-0032.md",
  "Recipes/BD-0033.md",
  "Recipes/BD-0034.md",
  "Recipes/BD-0035.md",
  "Recipes/BD-0036.md",
  "Recipes/BD-0037.md",
  "Recipes/BD-0038.md",
  "Recipes/BD-0039.md",
  "Recipes/BD-0040.md",
  "Recipes/BD-0041.md"
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(CORE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  const isCoreData = url.pathname.endsWith('/recipes.json') || url.pathname.endsWith('/data/recipes.json');
  const isArchiveData = url.pathname.endsWith('/Archive/index.json');

  if (isCoreData || isArchiveData) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response.ok) caches.open(CACHE).then(cache => cache.put(event.request, response.clone()));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
      if (response.ok && url.origin === self.location.origin) {
        caches.open(CACHE).then(cache => cache.put(event.request, response.clone()));
      }
      return response;
    }).catch(() => {
      if (event.request.mode === 'navigate') return caches.match('index.html');
      return caches.match('assets/icons/placeholder.svg');
    }))
  );
});
