/* Veřejné soubory jedné verze. Nikdy nezapisovat síťovou odpověď mimo allowlist. */
const CACHE = "tanklog-public-__VERSION__";
const PUBLIC_FILES = __PUBLIC_FILES__;
const allowed = new Set(PUBLIC_FILES);
self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      for (const path of PUBLIC_FILES) {
        const response = await fetch(path, {
          credentials: "omit",
          cache: "reload",
        });
        if (!response.ok || response.redirected)
          throw new Error("Veřejný soubor není dostupný.");
        await cache.put(path, response);
      }
    })(),
  );
});
self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      for (const name of await caches.keys())
        if (name.startsWith("tanklog-public-") && name !== CACHE)
          await caches.delete(name);
      await self.clients.claim();
    })(),
  );
});
self.addEventListener("message", (event) => {
  if (event.data === "ACTIVATE_UPDATE") self.skipWaiting();
});
self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (
    url.origin !== self.location.origin ||
    request.method !== "GET" ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/media/") ||
    url.pathname.startsWith("/private_media/")
  )
    return;
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request, { cache: "no-store" }).catch(async () =>
        (await caches.open(CACHE)).match("/offline.html"),
      ),
    );
  } else if (!url.search && allowed.has(url.pathname)) {
    event.respondWith(
      (async () =>
        (await caches.open(CACHE))
          .match(url.pathname)
          .then(
            (cached) => cached || fetch(request, { credentials: "omit" }),
          ))(),
    );
  }
});
