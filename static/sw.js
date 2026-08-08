const CACHE = "traveler-finance-v6";
const ASSETS = ["/", "/index.html", "/styles.css", "/app.js", "/manifest.json", "/icon.svg", "/favicon.ico"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)));
});

self.addEventListener("fetch", (event) => {
  if (event.request.url.includes("/api/")) return;
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
