// ===================== SERVICE WORKER =====================
const CACHE_NAME = 'affinity-v1';
const OFFLINE_URLS = [
  '/',
  '/index.html',
  '/dashboard.html',
  '/travail.html',
  '/lancer.html',
  '/retirer.html',
  '/parrainage.html',
  '/missions.html',
  '/moi.html',
  '/ticket.html',
  '/classement.html',
  '/actualites.html',
  '/entreprise.html',
  '/faq.html',
  '/support.html',
  '/roue.html',
  '/manifest.json'
];

// Installation : pré-cache
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(OFFLINE_URLS).catch(err => {
        console.warn('Certaines URLs non cachées :', err);
      });
    })
  );
  self.skipWaiting();
});

// Activation : nettoyage des vieux caches
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

// Fetch : cache-first pour les assets, network-first pour les pages
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Ne pas cacher les requêtes Supabase / API
  if (url.hostname.includes('supabase')) return;
  if (request.method !== 'GET') return;

  // Ignorer les requêtes externes (unsplash, flagcdn, etc.)
  if (url.origin !== location.origin) return;

  event.respondWith(
    caches.match(request).then(cached => {
      const fetchPromise = fetch(request).then(response => {
        // Mettre à jour le cache
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
        }
        return response;
      }).catch(() => cached);

      return cached || fetchPromise;
    })
  );
});

// Notifications push (pour plus tard)
self.addEventListener('push', (event) => {
  let data = { title: 'Affinity Network', body: 'Nouvelle notification !' };
  if (event.data) {
    try { data = event.data.json(); } catch(e) { data.body = event.data.text(); }
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: 'https://ui-avatars.com/api/?name=AN&size=192&background=075E54&color=25D366',
      badge: 'https://ui-avatars.com/api/?name=AN&size=72&background=075E54&color=25D366',
      vibrate: [200, 100, 200],
      tag: 'affinity-notif',
      data: data.url || '/dashboard'
    })
  );
});

// Clic sur la notification
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data || '/dashboard';
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then(windowClients => {
      for (const client of windowClients) {
        if (client.url.includes(url) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});