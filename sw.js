// ===================== SERVICE WORKER =====================
const CACHE_NAME = 'affinity-v3';
const LOGO_URL = 'https://i.ibb.co/996nZCn7/file-000000000e4481f49ce58934aa6b6a51.png';

const OFFLINE_URLS = [
  '/',
  '/index',
  '/dashboard',
  '/travail',
  '/lancer',
  '/retirer',
  '/parrainage',
  '/missions',
  '/moi',
  '/ticket',
  '/classement',
  '/actualites',
  '/entreprise',
  '/faq',
  '/support',
  '/roue',
  '/notifications',
  '/inscription',
  '/manifest.json',
  LOGO_URL
];

// ===================== INSTALLATION =====================
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(OFFLINE_URLS).catch(err => {
        console.warn('[SW] Certaines URLs non cachées :', err);
      });
    })
  );
  self.skipWaiting();
});

// ===================== ACTIVATION =====================
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ===================== FETCH =====================
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;
  if (url.hostname.includes('supabase')) return;

  // Logo ImgBB : cache-first
  if (request.url === LOGO_URL) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(response => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
          return response;
        });
      })
    );
    return;
  }

  // Externe : network-first
  if (url.origin !== location.origin) {
    event.respondWith(
      fetch(request).then(response => {
        if (response && response.status === 200 && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
        }
        return response;
      }).catch(() => caches.match(request))
    );
    return;
  }

  // Local : network-first pour HTML, cache-first pour le reste
  const isHTML = request.headers.get('accept')?.includes('text/html');
  
  if (isHTML) {
    event.respondWith(
      fetch(request).then(response => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
        return response;
      }).catch(() => caches.match(request).then(cached => cached || caches.match('/index')))
    );
  } else {
    event.respondWith(
      caches.match(request).then(cached => {
        const fetchPromise = fetch(request).then(response => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
          }
          return response;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
  }
});

// ===================== PUSH =====================
self.addEventListener('push', (event) => {
  let data = { title: 'Affinity Network', body: 'Nouvelle notification !', icon: LOGO_URL, badge: LOGO_URL };
  if (event.data) {
    try { data = { ...data, ...event.data.json() }; } catch(e) { data.body = event.data.text(); }
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: data.icon || LOGO_URL,
      badge: data.badge || LOGO_URL,
      vibrate: [200, 100, 200],
      tag: 'affinity-notif',
      data: data.url || '/dashboard'
    })
  );
});

// ===================== CLIC NOTIF =====================
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data || '/dashboard';
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then(windowClients => {
      for (const client of windowClients) {
        if (client.url.includes(url) && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});