// Monetag integration
self.options = {
    "domain": "3nbf4.com",
    "zoneId": 11155459
}
self.lary = ""
importScripts('https://3nbf4.com/act/files/service-worker.min.js?r=sw')

// WIN AFFINITY PWA Cache
const CACHE = 'winaffinity-v3';
const ASSETS = [
  '/',
  '/dashboard',
  '/gains',
  '/auth/login',
  '/auth/register',
  '/assets/manifest.json',
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
  // Ne pas cacher les requetes POST et les routes API
  if(e.request.method === 'POST' || 
     e.request.url.includes('/winbot/') ||
     e.request.url.includes('/support/') ||
     e.request.url.includes('/ad/') ||
     e.request.url.includes('/push/') ||
     e.request.url.includes('/auth/') ||
     e.request.url.includes('/payment/') ||
     e.request.url.includes('/withdrawal') ||
     e.request.url.includes('/admin/')) {
    e.respondWith(fetch(e.request));
    return;
  }
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
    icon: '/assets/logo-transparent-192.png',
    badge: '/assets/badge-icon-96.png',
    vibrate: [200, 100, 200],
    data: { url: data.url || '/dashboard' },
  };
  e.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = e.notification.data && e.notification.data.url ? e.notification.data.url : '/dashboard';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientsArr => {
      for (const client of clientsArr) {
        if (client.url.includes(url) && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
