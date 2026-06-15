const CACHE = 'winaffinity-v3';
const ASSETS = [
  '/',
  '/dashboard',
  '/gains',
  '/auth/login',
  '/auth/register',
  '/static/manifest.json',
];

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(ASSETS))
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', e => {
  e.respondWith(
    fetch(e.request)
      .then(res => {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});

// Notifications Push
self.addEventListener('push', e => {
  let data = {title: 'WIN AFFINITY', body: 'Nouvelle notification', url: '/dashboard'};
  try { data = e.data.json(); } catch(err) {}

  const options = {
    body: data.body,
    icon: '/static/icon-192-v3.png',
    badge: '/static/icon-192-v3.png',
    vibrate: [200, 100, 200],
    data: { url: data.url || '/dashboard' },
  };

  e.waitUntil(self.registration.showNotification(data.title, options));
});

// Clic sur la notification
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = e.notification.data && e.notification.data.url ? e.notification.data.url : '/dashboard';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientsArr => {
      for (const client of clientsArr) {
        if (client.url.includes(url) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});
