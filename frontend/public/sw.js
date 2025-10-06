// Crash Pay Frontend Service Worker
// Graceful offline caching with proper error handling

// Increment this version to invalidate old caches after each build
const CACHE_NAME = 'crash-pay-v6';
const urlsToCache = [
    '/',
    '/banking/login',
    '/admin/dashboard'
];

self.addEventListener('install', (event) => {
    console.log('🔧 Service Worker: Installing...');

    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('📦 Service Worker: Cache opened');
                // Don't fail if caching fails - graceful degradation
                return cache.addAll(urlsToCache).catch((error) => {
                    console.warn('⚠️ Service Worker: Cache add failed:', error);
                });
            })
            .then(() => {
                console.log('✅ Service Worker: Installed successfully');
                self.skipWaiting();
            })
            .catch((error) => {
                console.warn('⚠️ Service Worker: Install failed:', error);
            })
    );
});

self.addEventListener('activate', (event) => {
    console.log('🚀 Service Worker: Activating...');

    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('🗑️ Service Worker: Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('✅ Service Worker: Activated successfully');
            return self.clients.claim();
        })
    );
});

self.addEventListener('fetch', (event) => {
    // Skip observability requests that will fail due to CORS
    const url = new URL(event.request.url);
    const isObservabilityRequest =
        url.hostname === 'localhost' &&
        (url.port === '9200' || url.port === '5601' || url.port === '8200');

    if (isObservabilityRequest) {
        // Let observability requests fail naturally without SW intervention
        return;
    }

    // For HTML requests always go to network first to avoid serving stale index.html
    if (event.request.destination === 'document') {
        return;
    }

    // For static assets: network first, cache fallback
    event.respondWith(
        fetch(event.request).catch(() => {
            return caches.match(event.request).then((response) => {
                return response || new Response('Service Unavailable', { status: 503 });
            });
        })
    );
}); 