// ===================== SERVICE WORKER =====================
const CACHE_NAME = 'affinity-v2';
const LOGO_URL = 'https://i.ibb.co/996nZCn7/file-000000000e4481f49ce58934aa6b6a51.png';

// Pages de l'application à pré-cacher
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
  '/notifications.html',
  '/inscription.html',
  '/manifest.json',
  LOGO_URL
];

// ===================== INSTALLATION =====================
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('[SW] Pré-cache en cours...');
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
        keys.filter(k => k !== CACHE_NAME).map(k => {
          console.log('[SW] Suppression ancien cache :', k);
          return caches.delete(k);
        })
      )
    )
  );
  self.clients.claim();
});

// ===================== FETCH =====================
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 1. Ne pas intercepter les requêtes non-GET
  if (request.method !== 'GET') return;

  // 2. Ignorer Supabase et autres APIs (toujours en réseau)
  if (url.hostname.includes('supabase')) return;

  // 3. Le logo ImgBB : cache-first (toujours dispo)
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

  // 4. Ressources externes (unsplash, flagcdn, etc.) : network-first avec cache
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

  // 5. Ressources locales : cache-first avec mise à jour en arrière-plan
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
});

// ===================== PUSH NOTIFICATIONS =====================
self.addEventListener('push', (event) => {
  let data = { 
    title: 'Affinity Network', 
    body: 'Nouvelle notification !',
    icon: LOGO_URL,
    badge: LOGO_URL
  };
  
  if (event.data) {
    try { 
      data = { ...data, ...event.data.json() }; 
    } catch(e) { 
      data.body = event.data.text(); 
    }
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

// ===================== CLIC NOTIFICATION =====================
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